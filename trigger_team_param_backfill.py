#!/usr/bin/env python3
"""
Trigger team_parameter_handler Lambda for every league that has v8.0 backfilled
fixtures. The handler will:

  1. Detect the v7.0 → v8.0 architecture mismatch on existing team_parameters
     records and reset brier_ema to 0.25 (src/handlers/team_parameter_handler.py:283-287).
  2. Recompute team multipliers using ONLY v8.0 fixtures via the version
     filter in src/parameters/multiplier_calculator.py:154-186.
  3. Write fresh home_multiplier, away_multiplier, total_multiplier,
     brier_ema, and updated architecture_version to football_team_parameters_prod.

Discovers leagues by scanning football_game_fixtures_prod for distinct
(league_id, country, league) tuples from v8.0 records, then sends one SQS
message per league to the parameter-update queue.

Usage:
    python trigger_team_param_backfill.py              # dry-run: print plan
    python trigger_team_param_backfill.py --apply      # send SQS messages
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

import boto3

FIXTURES_TABLE = "football_game_fixtures_prod"
QUEUE_URL = (
    "https://sqs.eu-west-2.amazonaws.com/985019772236/"
    "football_football-team-parameter-updates_prod"
)
REGION = "eu-west-2"


def discover_leagues(region: str, table: str) -> list[dict]:
    t = boto3.resource("dynamodb", region_name=region).Table(table)
    seen: dict[int, dict] = {}
    kwargs: dict = dict(
        FilterExpression="prediction_metadata.architecture_version = :v",
        ExpressionAttributeValues={":v": "8.0"},
        ProjectionExpression="league_id, country, league, #s",
        ExpressionAttributeNames={"#s": "season"},
    )
    while True:
        resp = t.scan(**kwargs)
        for item in resp.get("Items", []):
            try:
                lid = int(item["league_id"])
            except (KeyError, TypeError, ValueError):
                continue
            seen.setdefault(lid, {
                "league_id": lid,
                "league_name": str(item.get("league", f"League {lid}")),
                "country": str(item.get("country", "Unknown")),
                "fixture_count": 0,
            })
            seen[lid]["fixture_count"] += 1
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return sorted(seen.values(), key=lambda d: -d["fixture_count"])


def send_message(sqs, queue_url: str, league: dict) -> str:
    body = {
        "league_id": league["league_id"],
        "league_name": league["league_name"],
        "country": league["country"],
        "trigger_type": "v8_backfill",
        "force_recompute": True,
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
    }
    resp = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))
    return resp["MessageId"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region", default=REGION)
    ap.add_argument("--fixtures-table", default=FIXTURES_TABLE)
    ap.add_argument("--queue-url", default=QUEUE_URL)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.5,
                    help="Seconds between sends to stagger Lambda invocations")
    args = ap.parse_args()

    print(f"Discovering leagues with v8.0 fixtures in {args.fixtures_table}...")
    leagues = discover_leagues(args.region, args.fixtures_table)
    print(f"  {len(leagues)} leagues found, "
          f"{sum(l['fixture_count'] for l in leagues)} fixtures total\n")

    print(f"{'league_id':<10} {'fixtures':>9}  country / league")
    print("-" * 75)
    for l in leagues:
        print(f"{l['league_id']:<10} {l['fixture_count']:>9}  "
              f"{l['country']} / {l['league_name']}")
    print()

    if not args.apply:
        print(f"Dry run. To send {len(leagues)} SQS messages to:")
        print(f"  {args.queue_url}")
        print(f"Rerun with --apply")
        return

    sqs = boto3.client("sqs", region_name=args.region)
    sent = 0
    errs = 0
    for l in leagues:
        try:
            mid = send_message(sqs, args.queue_url, l)
            sent += 1
            print(f"  [{sent}/{len(leagues)}] league_id={l['league_id']:<6} "
                  f"({l['country']} {l['league_name']})  msg_id={mid[:16]}...")
            if args.sleep > 0:
                time.sleep(args.sleep)
        except Exception as e:
            errs += 1
            print(f"  ERROR league_id={l['league_id']}: {e}")

    print(f"\nDone. sent={sent}, errors={errs}")


if __name__ == "__main__":
    main()
