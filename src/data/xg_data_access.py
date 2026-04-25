"""Read-side helpers for the V2 xG engine.

Isolated from src/data/database_client.py so the V1 and V2 code paths
cannot accidentally share references. Talks only to the three V2 tables:
    football_match_statistics_prod
    football_team_xg_parameters_prod
    football_league_xg_parameters_prod
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

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


def fetch_team_xg_arrays(
    team_id: int,
    league_id: int,
    season: int,
    venue: Optional[str] = None,   # 'home' | 'away' | None
    limit: int = 50,
) -> Dict[str, List[float]]:
    """Fetch a team's per-match xG_for and xG_against arrays.

    These are the V2 engine's primary observation channel — analogous to
    V1's per-match goals_scored / goals_conceded arrays. Returns lists in
    chronological order (oldest first) so downstream weighting (e.g. form
    decay) can be applied if needed. The engine treats them as IID
    samples for Bayesian smoothing.

    To get xG_against for a fixture, we join on fixture_id: this team's
    row gives xG_for, the OTHER team's row in the same fixture gives
    xG_against. We do this with a single league/season query and an
    in-memory grouping by fixture_id.

    Args:
        team_id, league_id, season: identifiers.
        venue: 'home' → only matches the team played at home;
               'away' → only matches away; None → all.
        limit: upper bound on the number of recent matches to return.

    Returns:
        {
          'xg_for':     [float, ...],   # this team's xG generated
          'xg_against': [float, ...],   # this team's xG conceded
        }
        The two lists are aligned (same fixtures, same order). Empty
        on any failure or if no data exists yet.
    """
    table = _table(MATCH_STATISTICS_TABLE)

    # Pull all rows for this league/season and group by fixture_id.
    fixtures_by_id: Dict[int, Dict[int, dict]] = {}  # fixture_id -> {team_id: row}
    kwargs = {
        "IndexName": "league_date_idx",
        "KeyConditionExpression": Key("league_id").eq(int(league_id)),
        "ScanIndexForward": False,  # newest first
    }
    try:
        while True:
            resp = table.query(**kwargs)
            for it in resp.get("Items", []):
                try:
                    if int(it.get("season", -1)) != int(season):
                        continue
                    fid = int(it["fixture_id"])
                    tid = int(it["team_id"])
                    fixtures_by_id.setdefault(fid, {})[tid] = it
                except (KeyError, TypeError, ValueError):
                    continue
            lek = resp.get("LastEvaluatedKey")
            if not lek:
                break
            kwargs["ExclusiveStartKey"] = lek
    except Exception as e:
        print(f"fetch_team_xg_arrays failed for team={team_id} "
              f"league={league_id} season={season}: {e}")
        return {"xg_for": [], "xg_against": []}

    # Build the arrays: most-recent first based on match_date.
    rows_with_team: List[Tuple[str, dict, dict]] = []
    for fid, by_tid in fixtures_by_id.items():
        own = by_tid.get(team_id)
        if not own:
            continue
        # Find the opponent's row.
        opp_row = next(
            (r for tid, r in by_tid.items() if tid != team_id), None
        )
        if opp_row is None:
            continue
        # Venue filter on this team's role.
        if venue == "home" and not bool(own.get("is_home")):
            continue
        if venue == "away" and bool(own.get("is_home")):
            continue
        rows_with_team.append((own.get("match_date") or "", own, opp_row))

    rows_with_team.sort(key=lambda x: x[0], reverse=True)
    rows_with_team = rows_with_team[:limit]

    xg_for: List[float] = []
    xg_against: List[float] = []
    for _, own, opp in rows_with_team:
        own_xg = own.get("expected_goals")
        opp_xg = opp.get("expected_goals")
        if own_xg is None or opp_xg is None:
            continue
        try:
            xg_for.append(float(own_xg))
            xg_against.append(float(opp_xg))
        except (TypeError, ValueError):
            continue

    return {"xg_for": xg_for, "xg_against": xg_against}


def fetch_team_xg_stream(
    team_id: int,
    league_id: int,
    season: int,
    venue: Optional[str] = None,
    limit: int = 20,
) -> List[float]:
    """Backwards-compatible wrapper returning just the xg_for stream.
    Some callers (e.g. legacy form-decay logic) only need this side."""
    return fetch_team_xg_arrays(
        team_id, league_id, season, venue=venue, limit=limit
    )["xg_for"]


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
