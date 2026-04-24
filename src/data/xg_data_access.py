"""Read-side helpers for the V2 xG engine.

Isolated from src/data/database_client.py so the V1 and V2 code paths
cannot accidentally share references. Talks only to the three V2 tables:
    football_match_statistics_prod
    football_team_xg_parameters_prod
    football_league_xg_parameters_prod
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from ..utils.constants import (
    MATCH_STATISTICS_TABLE,
    TEAM_XG_PARAMETERS_TABLE,
    LEAGUE_XG_PARAMETERS_TABLE,
)


_ddb = None


def _table(name: str):
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource("dynamodb")
    return _ddb.Table(name)


def get_team_xg_params(team_id: int, league_id: int) -> Optional[Dict[str, Any]]:
    """Fetch fitted xG params for a team in a league.

    Returns None if no parameter record exists (cold-start: caller should
    fall back to league-average params).
    """
    resp = _table(TEAM_XG_PARAMETERS_TABLE).get_item(
        Key={"team_id": int(team_id), "league_id": int(league_id)}
    )
    return resp.get("Item")


def get_league_xg_params(league_id: int) -> Optional[Dict[str, Any]]:
    """Fetch fitted xG params for a league. None if missing."""
    resp = _table(LEAGUE_XG_PARAMETERS_TABLE).get_item(
        Key={"league_id": int(league_id)}
    )
    return resp.get("Item")


def fetch_team_xg_stream(
    team_id: int,
    league_id: int,
    season: int,
    venue: Optional[str] = None,   # 'home' | 'away' | None
    limit: int = 20,
) -> List[float]:
    """Recent xG_for values for a team, most-recent-first.

    Used by the engine for form-decay weighting. Queries the
    league_date_idx GSI in reverse chronological order and filters to
    rows for this team (and, optionally, this team's venue).

    Args:
        team_id, league_id, season: identifiers.
        venue: 'home' → only matches where the team was home; 'away' →
            only away; None → all.
        limit: upper bound on the returned list length. The engine only
            uses the first ~10 entries for form weighting, so this cap
            keeps the query cheap.

    Returns:
        List of xG values (floats), ordered most-recent-first. May be
        shorter than `limit`. Empty list on any error or if nothing found.
    """
    table = _table(MATCH_STATISTICS_TABLE)
    stream: List[float] = []

    # Over-fetch by 4x because each fixture has 2 team rows (the other
    # team's row is filtered out), and we also filter by season + venue.
    page_limit = max(limit * 4, 40)

    kwargs = {
        "IndexName": "league_date_idx",
        "KeyConditionExpression": Key("league_id").eq(int(league_id)),
        "ScanIndexForward": False,  # newest first
        "Limit": page_limit,
    }
    try:
        while len(stream) < limit:
            resp = table.query(**kwargs)
            items = resp.get("Items", [])
            if not items:
                break
            for it in items:
                try:
                    if int(it.get("team_id", -1)) != int(team_id):
                        continue
                    if int(it.get("season", -1)) != int(season):
                        continue
                    if venue == "home" and not bool(it.get("is_home")):
                        continue
                    if venue == "away" and bool(it.get("is_home")):
                        continue
                    xg = it.get("expected_goals")
                    if xg is None:
                        continue
                    stream.append(float(xg))
                    if len(stream) >= limit:
                        break
                except (TypeError, ValueError, KeyError):
                    continue
            lek = resp.get("LastEvaluatedKey")
            if not lek:
                break
            kwargs["ExclusiveStartKey"] = lek
    except Exception as e:
        # Non-fatal: an empty stream just flattens the form multiplier to 1.0.
        print(f"fetch_team_xg_stream failed for team={team_id} "
              f"league={league_id} season={season}: {e}")
        return []

    return stream


def league_params_as_team_shape(league_params: Dict[str, Any]) -> Dict[str, Any]:
    """Produce a team-shaped params dict from league averages.

    Used by the engine when a team has no fitted params (cold-start) or
    when the caller wants V2a-style predictions driven purely by league
    averages.

    mu_xg_for (attack) at home == league_avg_xg_home (what home teams
    typically generate). mu_xg_against at home == league_avg_xg_away
    (what visiting teams typically generate — i.e., what home teams
    typically CONCEDE). Venue-split logic is symmetric.
    """
    if not league_params:
        return {}
    avg_home = league_params.get("league_avg_xg_home")
    avg_away = league_params.get("league_avg_xg_away")
    avg_for = league_params.get("league_avg_xg_for")
    return {
        "mu_xg_for": avg_for,
        "mu_xg_against": avg_for,
        "mu_xg_for_home": avg_home,
        "mu_xg_against_home": avg_away,
        "mu_xg_for_away": avg_away,
        "mu_xg_against_away": avg_home,
        "data_quality": "league_avg",
    }


def aggregate_data_quality(*param_dicts: Dict[str, Any]) -> str:
    """Worst-case roll-up of `data_quality` flags across the param dicts
    that fed one prediction. See docs/v2/09 for the precedence order.
    """
    qualities = [(p or {}).get("data_quality", "unknown") for p in param_dicts]
    if "unavailable" in qualities:
        return "unavailable"
    if "cold_start" in qualities:
        return "cold_start"
    if "sparse" in qualities:
        return "sparse"
    if "sot_proxy" in qualities:
        return "sot_proxy"
    if "league_avg" in qualities:
        return "league_avg"
    if "unknown" in qualities:
        return "unknown"
    return "full"
