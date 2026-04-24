"""xG parameter fitter for the V2 prediction engine.

Reads per-team-per-fixture rows from football_match_statistics_prod,
computes:
    * per-league parameters (7 fields, see constants below)
    * per-team  parameters (11 fields, see constants below)
and writes them to football_league_xg_parameters_prod and
football_team_xg_parameters_prod respectively.

Both param tables are *overwritten* each weekly run — the weekly fit
is the single source of truth and there's no merge or incremental update.

Entry points
    fit_team_xg_params(team_id, league_id, season, rows, league_params)
    fit_league_xg_params(league_id, season, rows)
    run_fit_for_league(league_id, season)
    run_fit_for_all_leagues(season_map)

See docs/v2/04-xg-parameter-fitter.md for the full design.
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from ..utils.constants import (
    MATCH_STATISTICS_TABLE,
    TEAM_XG_PARAMETERS_TABLE,
    LEAGUE_XG_PARAMETERS_TABLE,
    XG_SHRINKAGE_K,
    XG_MIN_MATCHES_FULL,
    XG_DEFAULT_RHO_DC,
)


# Thresholds for flagging a team's data_quality. See docs/v2/09 for rationale.
SOT_PROXY_FRACTION_FLAG = 0.20


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------


def _ddb():
    return boto3.resource("dynamodb")


def load_league_rows(league_id: int, season: int) -> List[dict]:
    """Scan all per-team match_statistics rows for a given (league_id, season).

    Uses the `league_date_idx` GSI (PK=league_id, SK=match_date) for
    efficient per-league retrieval, then filters to the requested season
    in Python — season is low cardinality so pushing it into the key
    doesn't buy much.
    """
    table = _ddb().Table(MATCH_STATISTICS_TABLE)
    items: List[dict] = []
    kwargs = {
        "IndexName": "league_date_idx",
        "KeyConditionExpression": Key("league_id").eq(league_id),
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


def _mean(values: Iterable[float]) -> Optional[float]:
    vs = [v for v in values if v is not None]
    if not vs:
        return None
    return sum(vs) / len(vs)


def _shrink(team_mean: Optional[float], league_mean: float, n: int, k: int = XG_SHRINKAGE_K) -> float:
    """Weighted blend of team sample toward league prior.

    If the team has no data, fall back to the league mean entirely.
    """
    if team_mean is None or n <= 0:
        return float(league_mean)
    w = n / (n + k)
    return w * float(team_mean) + (1.0 - w) * float(league_mean)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dec(v: Optional[float]) -> Optional[Decimal]:
    if v is None:
        return None
    return Decimal(str(round(float(v), 6)))


# --------------------------------------------------------------------------
# Fitters
# --------------------------------------------------------------------------


def fit_league_xg_params(
    league_id: int, season: int, rows: List[dict]
) -> Dict[str, Any]:
    """Compute the 7 per-league parameters from match_statistics rows.

    rows are DynamoDB items from the match_statistics table; expected keys:
        expected_goals (Decimal), is_home (bool), fixture_id (int).
    """
    xg_all: List[float] = []
    xg_home: List[float] = []   # xG scored BY home team
    xg_away: List[float] = []   # xG scored BY away team
    fixtures: set[int] = set()

    for r in rows:
        fid = r.get("fixture_id")
        if fid is not None:
            try:
                fixtures.add(int(fid))
            except (TypeError, ValueError):
                pass
        xg = _to_float(r.get("expected_goals"))
        if xg is None:
            continue
        is_home = bool(r.get("is_home"))
        xg_all.append(xg)
        (xg_home if is_home else xg_away).append(xg)

    league_avg_xg_for = _mean(xg_all) or 0.0
    league_avg_xg_home = _mean(xg_home) or league_avg_xg_for
    league_avg_xg_away = _mean(xg_away) or league_avg_xg_for
    home_adv = (
        league_avg_xg_home / league_avg_xg_away
        if league_avg_xg_away > 0
        else 1.0
    )

    # Preserve rho_dc from the existing record if already re-fit (the
    # Dixon-Coles re-fitting script writes back to this same table). On a
    # brand-new league, fall back to the literature default.
    existing_rho = _fetch_existing_league_rho(league_id, season)

    return {
        "league_id": int(league_id),
        "season": int(season),
        "league_avg_xg_for": _dec(league_avg_xg_for),
        "league_avg_xg_home": _dec(league_avg_xg_home),
        "league_avg_xg_away": _dec(league_avg_xg_away),
        "home_adv": _dec(home_adv),
        "rho_dc": _dec(existing_rho if existing_rho is not None else XG_DEFAULT_RHO_DC),
        "n_matches": len(fixtures),
        "last_updated": _iso_now(),
    }


def _fetch_existing_league_rho(league_id: int, season: int) -> Optional[float]:
    """Return the previously-fitted rho_dc if present, else None."""
    try:
        table = _ddb().Table(LEAGUE_XG_PARAMETERS_TABLE)
        resp = table.get_item(Key={"league_id": int(league_id)})
        item = resp.get("Item") or {}
        if int(item.get("season", -1)) != int(season):
            return None
        return _to_float(item.get("rho_dc"))
    except Exception:
        return None


def fit_team_xg_params(
    team_id: int,
    league_id: int,
    season: int,
    rows: List[dict],
    league_params: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute the 11 per-team parameters from match_statistics rows.

    `rows` must be the full list of league rows (both teams in every
    fixture). We filter internally so the caller doesn't need to bucket.
    """
    league_avg_xg_for = _to_float(league_params["league_avg_xg_for"]) or 0.0
    league_avg_xg_home = _to_float(league_params["league_avg_xg_home"]) or league_avg_xg_for
    league_avg_xg_away = _to_float(league_params["league_avg_xg_away"]) or league_avg_xg_for

    team_rows = [r for r in rows if int(r.get("team_id", -1)) == int(team_id)]

    # Build (team's fixture_ids) -> opponent_xg so we can compute xG_against
    # even without a join. match_statistics has one row per team per fixture.
    fixtures_this_team: dict[int, dict] = {}
    for r in team_rows:
        try:
            fixtures_this_team[int(r["fixture_id"])] = r
        except (KeyError, TypeError, ValueError):
            continue

    # Map fixture_id -> {team_id: xg} for the whole league (for opponents).
    by_fid_team: dict[int, dict[int, float]] = defaultdict(dict)
    for r in rows:
        try:
            fid = int(r["fixture_id"])
            tid = int(r["team_id"])
        except (KeyError, TypeError, ValueError):
            continue
        xg = _to_float(r.get("expected_goals"))
        if xg is None:
            continue
        by_fid_team[fid][tid] = xg

    # Partition by venue.
    xg_for_home: List[float] = []
    xg_against_home: List[float] = []  # what the home team's opponents generated
    xg_for_away: List[float] = []
    xg_against_away: List[float] = []
    xg_for_all: List[float] = []
    xg_against_all: List[float] = []

    sot_proxy_count = 0

    for r in team_rows:
        fid = int(r.get("fixture_id", -1))
        xg_for = _to_float(r.get("expected_goals"))
        if xg_for is None:
            continue
        # Opponent xG: the other entry in the same fixture.
        opponents = {t: v for t, v in by_fid_team.get(fid, {}).items() if t != int(team_id)}
        if not opponents:
            continue
        xg_against = next(iter(opponents.values()))

        if r.get("xg_source") == "sot_proxy":
            sot_proxy_count += 1

        xg_for_all.append(xg_for)
        xg_against_all.append(xg_against)
        if bool(r.get("is_home")):
            xg_for_home.append(xg_for)
            xg_against_home.append(xg_against)
        else:
            xg_for_away.append(xg_for)
            xg_against_away.append(xg_against)

    n = len(xg_for_all)
    n_home = len(xg_for_home)
    n_away = len(xg_for_away)

    # Raw means (may be None when a venue-split set is empty).
    raw_for_home = _mean(xg_for_home)
    raw_for_away = _mean(xg_for_away)
    raw_for_all = _mean(xg_for_all)
    raw_against_home = _mean(xg_against_home)
    raw_against_away = _mean(xg_against_away)
    raw_against_all = _mean(xg_against_all)

    # Shrunk means (always defined; fall back to league when no data).
    mu_xg_for = _shrink(raw_for_all, league_avg_xg_for, n)
    mu_xg_against = _shrink(raw_against_all, league_avg_xg_for, n)
    # For venue means, the prior is the *league's venue-matched* average.
    # At home: team's xG_for is drawn from the "home teams" distribution
    # whose mean is league_avg_xg_home. Team's xG_against at home is what
    # visitors typically generate, which equals league_avg_xg_away.
    mu_xg_for_home = _shrink(raw_for_home, league_avg_xg_home, n_home)
    mu_xg_against_home = _shrink(raw_against_home, league_avg_xg_away, n_home)
    mu_xg_for_away = _shrink(raw_for_away, league_avg_xg_away, n_away)
    mu_xg_against_away = _shrink(raw_against_away, league_avg_xg_home, n_away)

    # Quality flag. Order matters: check cold-start first.
    if n == 0:
        data_quality = "cold_start"
    elif n < XG_MIN_MATCHES_FULL:
        data_quality = "sparse"
    elif sot_proxy_count / n > SOT_PROXY_FRACTION_FLAG:
        data_quality = "sot_proxy"
    else:
        data_quality = "full"

    return {
        "team_id": int(team_id),
        "league_id": int(league_id),
        "season": int(season),
        "mu_xg_for": _dec(mu_xg_for),
        "mu_xg_against": _dec(mu_xg_against),
        "mu_xg_for_home": _dec(mu_xg_for_home),
        "mu_xg_against_home": _dec(mu_xg_against_home),
        "mu_xg_for_away": _dec(mu_xg_for_away),
        "mu_xg_against_away": _dec(mu_xg_against_away),
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
    _ddb().Table(LEAGUE_XG_PARAMETERS_TABLE).put_item(Item=params)


def _put_team_params(params: Dict[str, Any]) -> None:
    _ddb().Table(TEAM_XG_PARAMETERS_TABLE).put_item(Item=params)


# --------------------------------------------------------------------------
# End-to-end drivers
# --------------------------------------------------------------------------


def run_fit_for_league(league_id: int, season: int) -> Dict[str, Any]:
    """Read, fit, and write all params for a single (league_id, season).

    Returns a summary dict suitable for logging.
    """
    start = time.time()
    rows = load_league_rows(league_id, season)
    if not rows:
        msg = f"No match_statistics rows for league {league_id} season {season}"
        print(msg)
        return {
            "league_id": league_id,
            "season": season,
            "status": "no_data",
            "rows": 0,
            "teams_fit": 0,
            "elapsed_seconds": time.time() - start,
        }

    league_params = fit_league_xg_params(league_id, season, rows)
    _put_league_params(league_params)

    # Unique team_ids seen in this league's rows.
    team_ids: set[int] = set()
    for r in rows:
        try:
            team_ids.add(int(r["team_id"]))
        except (KeyError, TypeError, ValueError):
            continue

    teams_fit = 0
    quality_counter: Dict[str, int] = defaultdict(int)
    for tid in sorted(team_ids):
        team_params = fit_team_xg_params(tid, league_id, season, rows, league_params)
        _put_team_params(team_params)
        teams_fit += 1
        quality_counter[team_params["data_quality"]] += 1

    elapsed = time.time() - start
    return {
        "league_id": league_id,
        "season": season,
        "status": "ok",
        "rows": len(rows),
        "teams_fit": teams_fit,
        "data_quality_counts": dict(quality_counter),
        "league_avg_xg_for": float(league_params["league_avg_xg_for"]),
        "home_adv": float(league_params["home_adv"]),
        "rho_dc": float(league_params["rho_dc"]),
        "elapsed_seconds": round(elapsed, 2),
    }


def run_fit_for_all_leagues(season_map: Dict[int, int]) -> List[Dict[str, Any]]:
    """Run run_fit_for_league for every (league_id, season) in season_map.

    Per-league failures are caught and returned in the summary list; they
    don't stop the rest of the batch.
    """
    summaries: List[Dict[str, Any]] = []
    for league_id, season in season_map.items():
        try:
            summaries.append(run_fit_for_league(league_id, season))
        except Exception as e:
            import traceback
            traceback.print_exc()
            summaries.append({
                "league_id": league_id,
                "season": season,
                "status": "error",
                "error": str(e),
            })
    return summaries
