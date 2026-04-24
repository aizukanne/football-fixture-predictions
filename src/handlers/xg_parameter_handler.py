"""Weekly xG parameter fitter lambda.

Triggered by EventBridge rule `football-xg-parameter-weekly-prod`
(Wednesdays at 04:00 UTC, after V1 team-parameter fit at 03:00).

Iterates over every league in leagues.py, resolves its current season
via /leagues?current=true, then invokes the xG fitter to read from
football_match_statistics_prod and write to football_team_xg_parameters_prod
and football_league_xg_parameters_prod.

Per-league failures are isolated so one bad league doesn't block the rest.

Supports manual invocation for a single league:
    {"league_id": 39, "season": 2025}
If `season` is omitted, it's resolved via the API.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone

from ..data.api_client import get_league_start_date
from ..parameters.xg_fitter import run_fit_for_league
from leagues import allLeagues


def _resolve_season(league_id: int) -> int | None:
    """Return the 4-digit year of the current season for `league_id`, or
    None if the API couldn't resolve it.
    """
    try:
        start_date = get_league_start_date(league_id)
        if not start_date:
            return None
        return int(str(start_date)[:4])
    except Exception as e:
        print(f"Failed to resolve season for league {league_id}: {e}")
        return None


def _all_leagues() -> list[dict]:
    flat = []
    for country, lgs in allLeagues.items():
        for lg in lgs:
            flat.append({
                "league_id": int(lg["id"]),
                "name": lg.get("name", f"League {lg['id']}"),
                "country": country,
            })
    return flat


def lambda_handler(event, context):
    """Main entry point. Event shape:

    - EventBridge scheduled: empty dict {} → fits every league in leagues.py.
    - Manual single-league: {"league_id": N, "season": YYYY (optional)}.
    - SQS-dispatched: {"Records": [...]} with one message per league.
    """
    started_at = datetime.now(timezone.utc)
    print(f"xG parameter fitter starting at {started_at.isoformat()}")

    # SQS-style invocation (per-league dispatch)
    if isinstance(event, dict) and event.get("Records"):
        summaries = []
        for rec in event["Records"]:
            try:
                body = json.loads(rec["body"])
                lid = int(body["league_id"])
                season = body.get("season") or _resolve_season(lid)
                if season is None:
                    summaries.append({
                        "league_id": lid, "status": "error",
                        "error": "cannot resolve current season",
                    })
                    continue
                summaries.append(run_fit_for_league(lid, int(season)))
            except Exception as e:
                traceback.print_exc()
                summaries.append({
                    "status": "error", "error": str(e),
                    "message_id": rec.get("messageId", "unknown"),
                })
        return _wrap(started_at, summaries)

    # Single-league direct invocation
    if isinstance(event, dict) and event.get("league_id"):
        lid = int(event["league_id"])
        season = event.get("season") or _resolve_season(lid)
        if season is None:
            return _wrap(started_at, [{
                "league_id": lid, "status": "error",
                "error": "cannot resolve current season",
            }])
        return _wrap(started_at, [run_fit_for_league(lid, int(season))])

    # Default: fit all leagues in leagues.py
    leagues = _all_leagues()
    print(f"Fitting xG params for {len(leagues)} leagues")
    summaries = []
    for lg in leagues:
        lid = lg["league_id"]
        try:
            season = _resolve_season(lid)
            if season is None:
                summaries.append({
                    "league_id": lid, "name": lg["name"],
                    "status": "error",
                    "error": "cannot resolve current season",
                })
                continue
            print(f"Fitting league {lid} ({lg['country']}/{lg['name']}) "
                  f"season {season}")
            summary = run_fit_for_league(lid, season)
            summary["name"] = lg["name"]
            summaries.append(summary)
        except Exception as e:
            traceback.print_exc()
            summaries.append({
                "league_id": lid, "name": lg["name"],
                "status": "error", "error": str(e),
            })

    return _wrap(started_at, summaries)


def _wrap(started_at: datetime, summaries: list[dict]) -> dict:
    completed_at = datetime.now(timezone.utc)
    ok = sum(1 for s in summaries if s.get("status") == "ok")
    no_data = sum(1 for s in summaries if s.get("status") == "no_data")
    err = sum(1 for s in summaries if s.get("status") == "error")
    payload = {
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "elapsed_seconds": round(
            (completed_at - started_at).total_seconds(), 2
        ),
        "leagues_ok": ok,
        "leagues_no_data": no_data,
        "leagues_error": err,
        "summaries": summaries,
    }
    print(json.dumps({k: v for k, v in payload.items() if k != "summaries"}))
    return payload
