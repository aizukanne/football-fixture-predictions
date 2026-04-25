"""Re-enqueue fixtures for prediction processing.

Reads fixtures from football_game_fixtures_prod, groups by league, and
sends one SQS message per league to football_football-fixture-predictions_prod
(matching the convention used by fixture_ingestion_handler).

Common uses:
    # All fixtures from now through end-of-Sunday in every league
    python scripts/reenqueue_fixtures.py --weekend

    # Specific date range (UTC), all leagues
    python scripts/reenqueue_fixtures.py --from 2026-04-25 --to 2026-04-27

    # Single league
    python scripts/reenqueue_fixtures.py --weekend --league 39

    # Specific fixture IDs (one or many)
    python scripts/reenqueue_fixtures.py --fixture-ids 1379299 1379300

    # Dry-run prints what would be enqueued and exits
    python scripts/reenqueue_fixtures.py --weekend --dry-run

The lambda picks up messages within seconds. Each fixture takes ~10-30s
to process; a Premier League weekend (~10 fixtures) usually completes
within a few minutes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from boto3.dynamodb.conditions import Key

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

os.environ.setdefault("TABLE_PREFIX", "football_")
os.environ.setdefault("TABLE_SUFFIX", "_prod")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")

from src.utils.constants import GAME_FIXTURES_TABLE  # noqa: E402
from leagues import allLeagues  # noqa: E402


def _resolve_queue_url() -> str:
    """The default in constants.py has a literal '{account_id}' placeholder
    that's filled in via the FIXTURES_QUEUE_URL env var in production.
    Resolve it here for local invocations."""
    explicit = os.environ.get("FIXTURES_QUEUE_URL")
    if explicit and "{account_id}" not in explicit:
        return explicit
    account = boto3.client("sts").get_caller_identity()["Account"]
    region = os.environ.get("AWS_DEFAULT_REGION", "eu-west-2")
    env = os.environ.get("ENVIRONMENT", "prod")
    return (
        f"https://sqs.{region}.amazonaws.com/{account}"
        f"/football_football-fixture-predictions_{env}"
    )


def weekend_range(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return (start, end) datetimes spanning Fri 00:00 UTC -> Mon 00:00 UTC
    of the current/upcoming weekend.

    If today is Mon-Thu: the COMING Fri-Sun.
    If today is Fri-Sun: the current weekend, from now() forward to Mon 00:00.
    """
    now = now or datetime.now(timezone.utc)
    weekday = now.weekday()  # Mon=0, Sun=6
    if weekday <= 3:                  # Mon, Tue, Wed, Thu
        days_to_friday = 4 - weekday
        start = (now + timedelta(days=days_to_friday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:                             # Fri, Sat, Sun
        start = now
    # End is Monday 00:00 UTC
    days_to_monday = (7 - start.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7
    end = (start + timedelta(days=days_to_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return start, end


def all_country_league_pairs() -> list[tuple[str, str, int]]:
    """Each kept league as (country, name, id) — what the GSI is keyed on."""
    out: list[tuple[str, str, int]] = []
    for country, lgs in allLeagues.items():
        for lg in lgs:
            out.append((country, lg["name"], int(lg["id"])))
    return out


def fetch_fixtures_for_league(
    table, country: str, league_name: str,
    start_ts: int, end_ts: int,
) -> list[dict]:
    """Pull fixtures in [start_ts, end_ts] for one league via the
    country-league-index GSI (the same path checkScores uses)."""
    items: list[dict] = []
    kwargs = {
        "IndexName": "country-league-index",
        "KeyConditionExpression":
            Key("country").eq(country) & Key("league").eq(league_name),
        "FilterExpression":
            Key("timestamp").between(start_ts, end_ts),
    }
    while True:
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek
    return items


def fetch_fixtures_by_ids(table, ids: list[int]) -> list[dict]:
    """Direct get_item lookups for explicit fixture_ids."""
    out: list[dict] = []
    for fid in ids:
        resp = table.get_item(Key={"fixture_id": int(fid)})
        if resp.get("Item"):
            out.append(resp["Item"])
        else:
            print(f"  [warn] fixture {fid} not found in {GAME_FIXTURES_TABLE}")
    return out


def to_payload_fixture(item: dict) -> dict:
    """Project a game_fixtures item into the prediction-handler payload shape."""
    home = item.get("home", {}) or {}
    away = item.get("away", {}) or {}
    return {
        "fixture_id": int(item["fixture_id"]),
        "home_id": int(home.get("team_id")),
        "away_id": int(away.get("team_id")),
        "league_id": int(item["league_id"]),
        "season": int(item["season"]),
        "date": item.get("date"),
        "timestamp": int(item.get("timestamp", 0)),
    }


def group_by_league(fixtures: list[dict]) -> dict[int, list[dict]]:
    bucket: dict[int, list[dict]] = defaultdict(list)
    for fx in fixtures:
        bucket[int(fx["league_id"])].append(fx)
    return bucket


def league_info_for(league_id: int, fixtures: list[dict]) -> dict:
    """Best-effort league info from the first fixture's record."""
    if fixtures and "league" in fixtures[0]:
        return {"id": league_id, "name": fixtures[0].get("league")}
    for country, lgs in allLeagues.items():
        for lg in lgs:
            if int(lg["id"]) == int(league_id):
                return {"id": league_id, "name": lg["name"], "country": country}
    return {"id": league_id}


def main() -> int:
    ap = argparse.ArgumentParser()
    range_grp = ap.add_mutually_exclusive_group()
    range_grp.add_argument(
        "--weekend", action="store_true",
        help="Default: enqueue everything from Fri 00:00 UTC through Sun 23:59 UTC.",
    )
    range_grp.add_argument(
        "--from", dest="from_date",
        help="Start date (UTC), YYYY-MM-DD. Pairs with --to.",
    )
    range_grp.add_argument(
        "--fixture-ids", nargs="+", type=int,
        help="Specific fixture_ids to re-enqueue. Skips date logic.",
    )
    ap.add_argument(
        "--to", dest="to_date",
        help="End date (UTC), YYYY-MM-DD inclusive. Pairs with --from.",
    )
    ap.add_argument(
        "--league", type=int, default=None,
        help="Only enqueue this league_id.",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not (args.weekend or args.from_date or args.fixture_ids):
        args.weekend = True

    table = boto3.resource("dynamodb").Table(GAME_FIXTURES_TABLE)
    fixtures: list[dict] = []

    if args.fixture_ids:
        print(f"Fetching {len(args.fixture_ids)} explicit fixture(s)…")
        fixtures = fetch_fixtures_by_ids(table, args.fixture_ids)

    else:
        if args.weekend:
            start, end = weekend_range()
        else:
            if not args.to_date:
                print("ERROR: --to is required with --from", file=sys.stderr)
                return 2
            start = datetime.fromisoformat(args.from_date).replace(tzinfo=timezone.utc)
            end = (datetime.fromisoformat(args.to_date) + timedelta(days=1)) \
                .replace(tzinfo=timezone.utc)

        print(f"Date range: {start.isoformat()}  ->  {end.isoformat()}")
        start_ts, end_ts = int(start.timestamp()), int(end.timestamp())

        target_pairs = all_country_league_pairs()
        if args.league is not None:
            target_pairs = [t for t in target_pairs if t[2] == args.league]
            if not target_pairs:
                print(f"ERROR: --league {args.league} not in leagues.py", file=sys.stderr)
                return 2

        print(f"Scanning {len(target_pairs)} league(s) for fixtures…")
        for country, league_name, league_id in target_pairs:
            league_fxs = fetch_fixtures_for_league(
                table, country, league_name, start_ts, end_ts
            )
            if league_fxs:
                fixtures.extend(league_fxs)
                print(f"  [{league_id:>4}] {country}/{league_name}: {len(league_fxs)} fixture(s)")

    if not fixtures:
        print("\nNo fixtures matched. Nothing to enqueue.")
        return 0

    # Project to payload shape and group by league
    try:
        payloads = [to_payload_fixture(fx) for fx in fixtures]
    except (KeyError, TypeError, ValueError) as e:
        print(f"ERROR: malformed fixture record: {e}", file=sys.stderr)
        return 1
    grouped = group_by_league(payloads)

    print(f"\nReady to enqueue {len(payloads)} fixtures across "
          f"{len(grouped)} league message(s).")

    if args.dry_run:
        print("\n[dry-run] Per-league summary:")
        for lid in sorted(grouped):
            fxs = grouped[lid]
            sample = ", ".join(str(f["fixture_id"]) for f in fxs[:5])
            more = f", … +{len(fxs) - 5}" if len(fxs) > 5 else ""
            print(f"  [{lid:>4}] {len(fxs)} fixtures: {sample}{more}")
        return 0

    queue_url = _resolve_queue_url()
    print(f"\nQueue: {queue_url}")
    sqs = boto3.client("sqs")

    sent = 0
    for lid in sorted(grouped):
        fxs = grouped[lid]
        message_body = {
            "payload": fxs,
            "league_info": league_info_for(lid, fixtures),
            "timestamp": int(datetime.now(timezone.utc).timestamp()),
            "source": "scripts/reenqueue_fixtures.py",
            "fixture_count": len(fxs),
        }
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body, default=str),
            MessageAttributes={
                "league_id": {"StringValue": str(lid), "DataType": "String"},
            },
        )
        sent += 1
        print(f"  [{lid:>4}] sent message with {len(fxs)} fixtures")

    print(f"\nDone. {sent} SQS message(s) sent. The prediction lambda will "
          f"process {len(payloads)} fixture(s) over the next few minutes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
