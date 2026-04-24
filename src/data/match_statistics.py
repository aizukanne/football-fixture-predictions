"""Shared logic for parsing and persisting /v3/fixtures/statistics data.

Used by:
    - src/handlers/match_data_handler.py   (post-match live ingestion)
    - scripts/backfill_sqlite_to_dynamo.py (one-time SQLite migration)

Keep the stat-mapping table here so the two callers cannot drift.
"""

from __future__ import annotations

import json
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import boto3

from ..utils.constants import MATCH_STATISTICS_TABLE, SOT_TO_XG_FACTOR


# Canonical API type string -> DynamoDB attribute key.
STAT_KEY_MAP = {
    "Shots on Goal":      "shots_on_goal",
    "Shots off Goal":     "shots_off_goal",
    "Total Shots":        "total_shots",
    "Blocked Shots":      "blocked_shots",
    "Shots insidebox":    "shots_insidebox",
    "Shots outsidebox":   "shots_outsidebox",
    "Fouls":              "fouls",
    "Corner Kicks":       "corner_kicks",
    "Offsides":           "offsides",
    "Ball Possession":    "ball_possession_pct",
    "Yellow Cards":       "yellow_cards",
    "Red Cards":          "red_cards",
    "Goalkeeper Saves":   "goalkeeper_saves",
    "Total passes":       "total_passes",
    "Passes accurate":    "passes_accurate",
    "Passes %":           "passes_pct",
    "expected_goals":     "expected_goals",
    "goals_prevented":    "goals_prevented",
}

# Categorize fields for type coercion.
INT_FIELDS = {
    "shots_on_goal", "shots_off_goal", "total_shots", "blocked_shots",
    "shots_insidebox", "shots_outsidebox", "fouls", "corner_kicks", "offsides",
    "yellow_cards", "red_cards", "goalkeeper_saves",
    "total_passes", "passes_accurate",
}
PCT_FIELDS = {"ball_possession_pct", "passes_pct"}
FLOAT_FIELDS = {"expected_goals", "goals_prevented"}


def _coerce(api_value: Any, target_key: str) -> Optional[float | int]:
    """Normalize a single stat value. Returns None if unparseable."""
    if api_value is None:
        return None
    if target_key in INT_FIELDS:
        try:
            return int(api_value)
        except (TypeError, ValueError):
            return None
    if target_key in PCT_FIELDS:
        if isinstance(api_value, str):
            s = api_value.strip().rstrip("%")
            try:
                return float(s)
            except ValueError:
                return None
        try:
            return float(api_value)
        except (TypeError, ValueError):
            return None
    if target_key in FLOAT_FIELDS:
        try:
            return float(api_value)
        except (TypeError, ValueError):
            return None
    return None


def _to_decimal(v: Optional[float | int]) -> Optional[Decimal]:
    if v is None:
        return None
    return Decimal(str(v))


class FixtureMeta:
    """Minimal context required to build a match_statistics item.

    Any source that knows this about the fixture can produce items.
    """

    __slots__ = ("league_id", "season", "match_date", "home_team_id", "away_team_id")

    def __init__(self, league_id: int, season: int, match_date: str,
                 home_team_id: int, away_team_id: int):
        self.league_id = int(league_id)
        self.season = int(season)
        self.match_date = str(match_date)
        self.home_team_id = int(home_team_id)
        self.away_team_id = int(away_team_id)


def build_team_item(
    fixture_id: int,
    fixture_meta: FixtureMeta,
    team_entry: dict,
) -> Optional[dict]:
    """Translate one API team-statistics block into a DynamoDB item.

    Returns None if the team's stats are empty or lack any usable xG signal
    (no expected_goals in the payload AND no shots_on_goal to proxy from).
    """
    team = team_entry.get("team") or {}
    team_id = team.get("id")
    if not team_id:
        return None

    stats_list = team_entry.get("statistics") or []
    if not stats_list:
        return None

    is_home = (int(team_id) == fixture_meta.home_team_id)

    parsed: dict[str, Any] = {}
    for s in stats_list:
        api_type = s.get("type")
        key = STAT_KEY_MAP.get(api_type)
        if not key:
            continue
        parsed[key] = _coerce(s.get("value"), key)

    expected_goals = parsed.get("expected_goals")
    sot = parsed.get("shots_on_goal")
    if expected_goals is None and sot is not None and sot > 0:
        expected_goals = float(sot) * SOT_TO_XG_FACTOR
        xg_source = "sot_proxy"
    elif expected_goals is not None:
        xg_source = "native"
    else:
        return None  # No usable xG signal.

    item: dict[str, Any] = {
        "fixture_id": int(fixture_id),
        "team_id": int(team_id),
        "league_id": fixture_meta.league_id,
        "season": fixture_meta.season,
        "match_date": fixture_meta.match_date,
        "is_home": is_home,
        "xg_source": xg_source,
        "stat_raw_json": json.dumps(team_entry),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "expected_goals": _to_decimal(expected_goals),
    }

    for k in INT_FIELDS:
        v = parsed.get(k)
        item[k] = 0 if v is None else int(v)

    for k in PCT_FIELDS | {"goals_prevented"}:
        v = parsed.get(k)
        if v is not None:
            item[k] = _to_decimal(v)

    return item


def build_items_from_response(
    fixture_id: int,
    fixture_meta: FixtureMeta,
    api_response: dict,
) -> list[dict]:
    """Produce the (usually 2) items for one fixture from the raw API dict.

    An empty list means the API has no coverage for this fixture; callers
    should treat that as a legitimate skip, not an error.
    """
    teams = (api_response or {}).get("response") or []
    items: list[dict] = []
    for te in teams:
        it = build_team_item(fixture_id, fixture_meta, te)
        if it is not None:
            items.append(it)
    return items


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------

_ddb_resource = None


def _get_table():
    global _ddb_resource
    if _ddb_resource is None:
        _ddb_resource = boto3.resource("dynamodb")
    return _ddb_resource.Table(MATCH_STATISTICS_TABLE)


def write_items(items: Iterable[dict]) -> int:
    """Batch-write match_statistics items to DynamoDB.

    Returns the number of items written. Safe to call with an empty iterable.
    """
    items = list(items)
    if not items:
        return 0
    table = _get_table()
    with table.batch_writer() as batch:
        for it in items:
            batch.put_item(Item=it)
    return len(items)


def write_fixture_statistics(
    fixture_id: int,
    fixture_meta: FixtureMeta,
    api_response: dict,
) -> dict:
    """High-level entrypoint for post-match ingestion.

    Build items from the API response and persist them in one call.

    Returns:
        {
            'fixture_id': int,
            'items_written': int,
            'xg_sources': {'native': int, 'sot_proxy': int},
            'skipped': bool,     # True iff API returned no team entries
        }
    """
    items = build_items_from_response(fixture_id, fixture_meta, api_response)
    skipped = (not api_response.get("response")) or not items
    sources = {"native": 0, "sot_proxy": 0}
    for it in items:
        sources[it["xg_source"]] = sources.get(it["xg_source"], 0) + 1
    written = write_items(items)
    return {
        "fixture_id": int(fixture_id),
        "items_written": written,
        "xg_sources": sources,
        "skipped": bool(skipped),
    }
