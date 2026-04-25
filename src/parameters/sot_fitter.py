"""SoT parameter fitter for the V3 prediction engine.

Reads two source tables:
    football_match_statistics_prod -> per-team-per-fixture shots_on_goal
    football_game_fixtures_prod    -> per-fixture actual goals scored

Joins them by fixture_id, computes:
    * per-league parameters (sot_to_goal_conv_rate, avg_goals_conceded by venue,
      avg_sot by venue) — a small number of league-wide averages.
    * per-team parameters (sot_for / goals_conceded — venue-split, plus pooled),
      Bayesian-shrunk toward the league mean with k=SOT_SHRINKAGE_K.
and writes them to:
    football_league_sot_parameters_prod
    football_team_sot_parameters_prod

Both tables are *overwritten* each weekly run — the fit is the single
source of truth, no merge or incremental update.

Entry points:
    fit_team_sot_params(team_id, league_id, season, league_rows, fixture_goals, league_params)
    fit_league_sot_params(league_id, season, league_rows, fixture_goals)
    run_fit_for_league(league_id, season)
    run_fit_for_all_leagues(season_map)

See docs/v3/README.md for the full design.
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

import boto3
from boto3.dynamodb.conditions import Key

from ..utils.constants import (
    MATCH_STATISTICS_TABLE,
    GAME_FIXTURES_TABLE,
    TEAM_SOT_PARAMETERS_TABLE,
    LEAGUE_SOT_PARAMETERS_TABLE,
    SOT_SHRINKAGE_K,
    SOT_MIN_MATCHES_FULL,
    SOT_TO_GOAL_FALLBACK,
)


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------


def _ddb():
    return boto3.resource("dynamodb")


def load_league_match_stats(league_id: int, season: int) -> List[dict]:
    """Scan all per-team match_statistics rows for (league_id, season).

    Uses the `league_date_idx` GSI (PK=league_id, SK=match_date), then
    filters to the requested season in Python — season is low cardinality
    so pushing it into the key buys nothing.
    """
    table = _ddb().Table(MATCH_STATISTICS_TABLE)
    items: List[dict] = []
    kwargs = {
        "IndexName": "league_date_idx",
        "KeyConditionExpression": Key("league_id").eq(int(league_id)),
    }
    while True:
        resp = table.query(**kwargs)
        for it in resp.get("Items", []):
            try:
                if int(it.get("season", -1)) == int(season):
                    items.append(it)
            except (TypeError, ValueError):
                continue
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek
    return items


def load_fixture_goals(fixture_ids: Iterable[int]) -> Dict[int, Tuple[int, int]]:
    """Batch-fetch (home_goals, away_goals) for a set of fixture_ids from
    football_game_fixtures_prod.

    DynamoDB BatchGetItem caps at 100 keys per request, so we chunk.
    Fixtures with no `goals` field (not yet finished, or pre-checkScores)
    are silently skipped — the fitter treats them as unobserved.
    """
    table_name = GAME_FIXTURES_TABLE
    client = _ddb()
    out: Dict[int, Tuple[int, int]] = {}
    ids = sorted({int(f) for f in fixture_ids if f is not None})

    BATCH = 100
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        keys = [{"fixture_id": fid} for fid in chunk]
        # Project only what we need.
        req = {
            table_name: {
                "Keys": keys,
                "ProjectionExpression": "fixture_id, goals",
            }
        }
        # Loop on UnprocessedKeys until empty (BatchGetItem can return
        # partial results under throttling).
        while req:
            resp = client.batch_get_item(RequestItems=req)
            for it in resp.get("Responses", {}).get(table_name, []):
                try:
                    fid = int(it["fixture_id"])
                except (KeyError, TypeError, ValueError):
                    continue
                g = it.get("goals") or {}
                hg = g.get("home")
                ag = g.get("away")
                if hg is None or ag is None:
                    continue
                try:
                    out[fid] = (int(hg), int(ag))
                except (TypeError, ValueError):
                    continue
            unprocessed = resp.get("UnprocessedKeys") or {}
            req = unprocessed if unprocessed else None
    return out


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _mean(values: Iterable[float]) -> Optional[float]:
    vs = [v for v in values if v is not None]
    if not vs:
        return None
    return sum(vs) / len(vs)


def _shrink(
    team_mean: Optional[float], league_mean: float, n: int,
    k: int = SOT_SHRINKAGE_K,
) -> float:
    """Bayesian shrinkage:
        shrunk = (n × team_mean + k × league_mean) / (n + k)
    Equivalent to weight w = n/(n+k) on team data, (1-w) on league prior.
    With k=5 a team needs ~5 real matches to outweigh the prior.
    Falls back to league mean when team has no data.
    """
    if team_mean is None or n <= 0:
        return float(league_mean)
    return (n * float(team_mean) + k * float(league_mean)) / (n + k)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dec(v: Optional[float]) -> Optional[Decimal]:
    if v is None:
        return None
    return Decimal(str(round(float(v), 6)))


# --------------------------------------------------------------------------
# League fitter
# --------------------------------------------------------------------------


def fit_league_sot_params(
    league_id: int,
    season: int,
    league_rows: List[dict],
    fixture_goals: Dict[int, Tuple[int, int]],
) -> Dict[str, Any]:
    """Compute per-league averages.

    Args:
        league_rows: match_statistics items for the league/season.
        fixture_goals: {fixture_id: (home_goals, away_goals)} from
            game_fixtures, restricted to FINISHED matches (callers fetch
            with no status filter, but goals only present once a match
            has actually been played).

    Returns the dict that gets persisted to football_league_sot_parameters_prod.
    """
    sot_home: List[float] = []   # SoT generated by home teams
    sot_away: List[float] = []   # SoT generated by away teams

    # Counters for the conv rate. Pooled (Σgoals / ΣSoT) is the right
    # estimator — it weights matches by their information content, where
    # mean-of-team-rates would over-weight low-volume teams.
    total_goals = 0.0
    total_sot = 0.0

    # Goals conceded by venue. For a finished fixture, the home team's
    # goals_conceded == away_goals, and vice-versa.
    gc_home: List[int] = []      # goals conceded BY home teams (= away_goals)
    gc_away: List[int] = []      # goals conceded BY away teams (= home_goals)
    fixtures_seen: set[int] = set()

    for r in league_rows:
        fid = _to_int(r.get("fixture_id"))
        if fid is None:
            continue
        sot = _to_int(r.get("shots_on_goal"))
        if sot is None or sot < 0:
            continue
        is_home = bool(r.get("is_home"))
        goals = fixture_goals.get(fid)
        if goals is None:
            # No actual-result join (match not finished yet, or goals
            # never written): skip this row entirely.
            continue
        hg, ag = goals
        team_goals = hg if is_home else ag

        if is_home:
            sot_home.append(float(sot))
            gc_home.append(ag)  # home's goals_conceded == away_goals
        else:
            sot_away.append(float(sot))
            gc_away.append(hg)

        total_goals += team_goals
        total_sot += sot
        fixtures_seen.add(fid)

    league_avg_sot_home = _mean(sot_home)
    league_avg_sot_away = _mean(sot_away)
    league_avg_sot_for = _mean(sot_home + sot_away)

    league_avg_gc_home = _mean(gc_home)        # what home teams concede
    league_avg_gc_away = _mean(gc_away)        # what away teams concede
    league_avg_gc = _mean(gc_home + gc_away)

    # Pooled SoT->goal conversion. Falls back to global pooled mean
    # (0.317) only when the league has zero data — should be rare.
    if total_sot > 0:
        sot_to_goal_conv_rate = total_goals / total_sot
    else:
        sot_to_goal_conv_rate = SOT_TO_GOAL_FALLBACK

    # Convenience: home advantage as a simple SoT ratio. Not used by the
    # core formula (venue is handled by venue-split team arrays), but
    # surfaced for monitoring.
    home_adv = (
        (league_avg_sot_home / league_avg_sot_away)
        if league_avg_sot_home and league_avg_sot_away
        else 1.0
    )

    return {
        "league_id": int(league_id),
        "season": int(season),
        "sot_to_goal_conv_rate": _dec(sot_to_goal_conv_rate),
        "league_avg_sot_for": _dec(league_avg_sot_for or 0.0),
        "league_avg_sot_home": _dec(league_avg_sot_home or 0.0),
        "league_avg_sot_away": _dec(league_avg_sot_away or 0.0),
        "league_avg_goals_conceded": _dec(league_avg_gc or 0.0),
        "league_avg_goals_conceded_home": _dec(league_avg_gc_home or 0.0),
        "league_avg_goals_conceded_away": _dec(league_avg_gc_away or 0.0),
        "home_adv": _dec(home_adv),
        "n_fixtures": len(fixtures_seen),
        "n_team_rows": len([r for r in league_rows
                            if _to_int(r.get("fixture_id")) in fixture_goals]),
        "last_updated": _iso_now(),
    }


# --------------------------------------------------------------------------
# Team fitter
# --------------------------------------------------------------------------


def fit_team_sot_params(
    team_id: int,
    league_id: int,
    season: int,
    league_rows: List[dict],
    fixture_goals: Dict[int, Tuple[int, int]],
    league_params: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute per-team SoT params, venue-split, with k=5 shrinkage.

    `league_rows` is the full list of league rows (both teams in every
    fixture). We filter internally so the caller doesn't bucket.
    """
    league_avg_sot_home = _to_float(league_params.get("league_avg_sot_home")) or 0.0
    league_avg_sot_away = _to_float(league_params.get("league_avg_sot_away")) or 0.0
    league_avg_sot_for = _to_float(league_params.get("league_avg_sot_for")) or 0.0
    league_avg_gc_home = _to_float(league_params.get("league_avg_goals_conceded_home")) or 0.0
    league_avg_gc_away = _to_float(league_params.get("league_avg_goals_conceded_away")) or 0.0
    league_avg_gc = _to_float(league_params.get("league_avg_goals_conceded")) or 0.0

    sot_for_home: List[float] = []
    sot_for_away: List[float] = []
    gc_home: List[int] = []   # goals conceded when team played at home
    gc_away: List[int] = []   # goals conceded when team played away

    for r in league_rows:
        if _to_int(r.get("team_id")) != int(team_id):
            continue
        fid = _to_int(r.get("fixture_id"))
        if fid is None:
            continue
        sot = _to_int(r.get("shots_on_goal"))
        goals = fixture_goals.get(fid)
        if goals is None or sot is None or sot < 0:
            continue

        hg, ag = goals
        is_home = bool(r.get("is_home"))
        if is_home:
            sot_for_home.append(float(sot))
            gc_home.append(ag)              # opponent's goals == this team's GC
        else:
            sot_for_away.append(float(sot))
            gc_away.append(hg)

    n_home = len(sot_for_home)
    n_away = len(sot_for_away)
    n = n_home + n_away

    raw_sot_for_home = _mean(sot_for_home)
    raw_sot_for_away = _mean(sot_for_away)
    raw_sot_for_all = _mean(sot_for_home + sot_for_away)
    raw_gc_home = _mean(gc_home)
    raw_gc_away = _mean(gc_away)
    raw_gc_all = _mean(gc_home + gc_away)

    sot_for_home_s = _shrink(raw_sot_for_home, league_avg_sot_home, n_home)
    sot_for_away_s = _shrink(raw_sot_for_away, league_avg_sot_away, n_away)
    sot_for_all_s = _shrink(raw_sot_for_all, league_avg_sot_for, n)
    gc_home_s = _shrink(raw_gc_home, league_avg_gc_home, n_home)
    gc_away_s = _shrink(raw_gc_away, league_avg_gc_away, n_away)
    gc_all_s = _shrink(raw_gc_all, league_avg_gc, n)

    if n == 0:
        data_quality = "cold_start"
    elif n < SOT_MIN_MATCHES_FULL:
        data_quality = "sparse"
    else:
        data_quality = "full"

    return {
        "team_id": int(team_id),
        "league_id": int(league_id),
        "season": int(season),
        "sot_for_home": _dec(sot_for_home_s),
        "sot_for_away": _dec(sot_for_away_s),
        "sot_for_all": _dec(sot_for_all_s),
        "goals_conceded_home": _dec(gc_home_s),
        "goals_conceded_away": _dec(gc_away_s),
        "goals_conceded_all": _dec(gc_all_s),
        "n_matches": int(n),
        "n_matches_home": int(n_home),
        "n_matches_away": int(n_away),
        "data_quality": data_quality,
        "last_updated": _iso_now(),
    }


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------


def _put_league_params(params: Dict[str, Any]) -> None:
    _ddb().Table(LEAGUE_SOT_PARAMETERS_TABLE).put_item(Item=params)


def _put_team_params(params: Dict[str, Any]) -> None:
    _ddb().Table(TEAM_SOT_PARAMETERS_TABLE).put_item(Item=params)


# --------------------------------------------------------------------------
# End-to-end driver
# --------------------------------------------------------------------------


def run_fit_for_league(league_id: int, season: int) -> Dict[str, Any]:
    """Read, fit, and write all SoT params for a single (league_id, season).

    Returns a summary dict suitable for logging.
    """
    start = time.time()
    rows = load_league_match_stats(league_id, season)
    if not rows:
        return {
            "league_id": league_id, "season": season,
            "status": "no_data", "rows": 0, "teams_fit": 0,
            "elapsed_seconds": round(time.time() - start, 2),
        }

    fixture_ids = {_to_int(r.get("fixture_id")) for r in rows}
    fixture_ids.discard(None)
    fixture_goals = load_fixture_goals(fixture_ids)
    if not fixture_goals:
        return {
            "league_id": league_id, "season": season,
            "status": "no_finished_fixtures",
            "rows": len(rows), "teams_fit": 0,
            "elapsed_seconds": round(time.time() - start, 2),
        }

    league_params = fit_league_sot_params(league_id, season, rows, fixture_goals)
    _put_league_params(league_params)

    team_ids: set[int] = set()
    for r in rows:
        tid = _to_int(r.get("team_id"))
        if tid is not None:
            team_ids.add(tid)

    teams_fit = 0
    quality_counter: Dict[str, int] = defaultdict(int)
    for tid in sorted(team_ids):
        params = fit_team_sot_params(
            tid, league_id, season, rows, fixture_goals, league_params,
        )
        _put_team_params(params)
        teams_fit += 1
        quality_counter[params["data_quality"]] += 1

    elapsed = time.time() - start
    return {
        "league_id": league_id, "season": season, "status": "ok",
        "rows": len(rows),
        "fixtures_with_goals": len(fixture_goals),
        "teams_fit": teams_fit,
        "data_quality_counts": dict(quality_counter),
        "sot_to_goal_conv_rate": float(league_params["sot_to_goal_conv_rate"]),
        "league_avg_goals_conceded": float(
            league_params["league_avg_goals_conceded"]
        ),
        "elapsed_seconds": round(elapsed, 2),
    }


def run_fit_for_all_leagues(season_map: Dict[int, int]) -> List[Dict[str, Any]]:
    """Run run_fit_for_league for every (league_id, season) in season_map.

    Per-league failures are caught and returned in the summary; one bad
    league doesn't stop the rest.
    """
    summaries: List[Dict[str, Any]] = []
    for league_id, season in season_map.items():
        try:
            summaries.append(run_fit_for_league(league_id, season))
        except Exception as e:
            import traceback
            traceback.print_exc()
            summaries.append({
                "league_id": league_id, "season": season,
                "status": "error", "error": str(e),
            })
    return summaries
