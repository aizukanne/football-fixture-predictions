"""Read-side helpers for the V3 SoT-based prediction engine.

Talks only to the V3 parameter tables:
    football_team_sot_parameters_prod
    football_league_sot_parameters_prod

The fitter writes; the engine reads. Source-of-truth match data lives
in football_match_statistics_prod (SoT, etc.) and football_game_fixtures_prod
(actual goals); helpers for reading those live in sot_fitter.py since
the engine itself only consumes pre-fitted aggregates.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import boto3

from ..utils.constants import (
    TEAM_SOT_PARAMETERS_TABLE,
    LEAGUE_SOT_PARAMETERS_TABLE,
)


_ddb = None


def _table(name: str):
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource("dynamodb")
    return _ddb.Table(name)


def get_team_sot_params(team_id: int, league_id: int) -> Optional[Dict[str, Any]]:
    """Fetch fitted SoT params for a team in a league.

    Returns None if no parameter record exists yet (cold-start: caller
    should fall back to the league record's averages).
    """
    resp = _table(TEAM_SOT_PARAMETERS_TABLE).get_item(
        Key={"team_id": int(team_id), "league_id": int(league_id)}
    )
    return resp.get("Item")


def get_league_sot_params(league_id: int) -> Optional[Dict[str, Any]]:
    """Fetch fitted SoT params for a league. None if not yet fit."""
    resp = _table(LEAGUE_SOT_PARAMETERS_TABLE).get_item(
        Key={"league_id": int(league_id)}
    )
    return resp.get("Item")


def league_params_as_team_fallback(
    league_params: Dict[str, Any]
) -> Dict[str, Any]:
    """Produce a team-shaped param dict from league averages.

    Used by the engine when a team has no fitted record yet (brand-new
    team mid-season, or the weekly fitter hasn't picked them up). Maps:
        league_avg_sot_home  -> team's expected sot_for_home
        league_avg_sot_away  -> team's expected sot_for_away
        league_avg_goals_conceded_home -> team's expected goals_conceded_home
        league_avg_goals_conceded_away -> team's expected goals_conceded_away

    The naming preserves the venue-aware structure the engine expects.
    """
    if not league_params:
        return {}
    return {
        "sot_for_home": league_params.get("league_avg_sot_home"),
        "sot_for_away": league_params.get("league_avg_sot_away"),
        "sot_for_all": league_params.get("league_avg_sot_for"),
        "goals_conceded_home": league_params.get("league_avg_goals_conceded_home"),
        "goals_conceded_away": league_params.get("league_avg_goals_conceded_away"),
        "goals_conceded_all": league_params.get("league_avg_goals_conceded"),
        "data_quality": "league_avg",
        "n_matches": 0,
        "n_matches_home": 0,
        "n_matches_away": 0,
    }
