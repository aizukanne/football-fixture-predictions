"""Backfill goals_scored / goals_conceded onto existing match_statistics rows.

Why this exists
---------------
The /v3/fixtures/statistics endpoint does NOT return goals scored. Goals
are only available from /v3/fixtures, which we already call elsewhere in
match_data_handler. The original V2-era ingest didn't plumb the goals
through, so every existing row in football_match_statistics_prod is
missing goals_scored / goals_conceded. Going forward, the ingest path
populates them; this script fills in the historical rows.

How it works
------------
1. Scan match_statistics_prod page-by-page.
2. Group up to 100 fixture_ids and BatchGetItem the corresponding rows
   from game_fixtures_prod, projecting only the `goals` field.
3. For each match_statistics row in the batch, derive
       goals_scored   = home_goals if is_home else away_goals
       goals_conceded = away_goals if is_home else home_goals
   and emit an UpdateItem with a `attribute_not_exists` guard so the
   script is idempotent — re-running is safe and only touches rows that
   still lack the fields.

Safety
------
- Dry-run by default: prints what *would* be updated, writes nothing.
- Pass --apply to actually persist updates.
- --limit N processes only the first N rows for a smoke test.
- Updates use SET ... only IF NOT EXISTS, so we never overwrite goals
  that have already been written by the new ingest path.

Usage
-----
    # Smoke-test against 50 rows, no writes
    python scripts/backfill_match_stats_goals.py --limit 50

    # Full backfill, actually write
    python scripts/backfill_match_stats_goals.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import boto3
from boto3.dynamodb.conditions import Key

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

os.environ.setdefault("TABLE_PREFIX", "football_")
os.environ.setdefault("TABLE_SUFFIX", "_prod")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")

from src.utils.constants import MATCH_STATISTICS_TABLE, GAME_FIXTURES_TABLE  # noqa: E402


_ddb = None


def ddb():
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource("dynamodb")
    return _ddb


def scan_match_stats(
    limit: Optional[int] = None,
) -> Iterable[dict]:
    """Yield items from match_statistics_prod, lazily, page by page.

    We only need: fixture_id, team_id, is_home, goals_scored (to skip
    already-backfilled rows). ProjectionExpression keeps the bytes minimal.
    """
    table = ddb().Table(MATCH_STATISTICS_TABLE)
    kwargs = {
        "ProjectionExpression": "fixture_id, team_id, is_home, goals_scored",
    }
    yielded = 0
    while True:
        resp = table.scan(**kwargs)
        for it in resp.get("Items", []):
            yield it
            yielded += 1
            if limit is not None and yielded >= limit:
                return
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            return
        kwargs["ExclusiveStartKey"] = lek


def batch_get_goals(fixture_ids: List[int]) -> Dict[int, Tuple[int, int]]:
    """BatchGetItem game_fixtures → {fixture_id: (home_goals, away_goals)}.

    Up to 100 keys per request; loop on UnprocessedKeys to handle throttles.
    """
    out: Dict[int, Tuple[int, int]] = {}
    table_name = GAME_FIXTURES_TABLE
    client = ddb()
    BATCH = 100
    fixture_ids = sorted(set(int(f) for f in fixture_ids if f is not None))

    for i in range(0, len(fixture_ids), BATCH):
        chunk = fixture_ids[i:i + BATCH]
        req = {
            table_name: {
                "Keys": [{"fixture_id": fid} for fid in chunk],
                "ProjectionExpression": "fixture_id, goals",
            }
        }
        while req:
            resp = client.batch_get_item(RequestItems=req)
            for it in resp.get("Responses", {}).get(table_name, []):
                try:
                    fid = int(it["fixture_id"])
                except (KeyError, TypeError, ValueError):
                    continue
                g = it.get("goals") or {}
                hg, ag = g.get("home"), g.get("away")
                if hg is None or ag is None:
                    continue
                try:
                    out[fid] = (int(hg), int(ag))
                except (TypeError, ValueError):
                    continue
            unprocessed = resp.get("UnprocessedKeys") or {}
            req = unprocessed if unprocessed else None
    return out


def update_one(fixture_id: int, team_id: int,
               goals_scored: int, goals_conceded: int) -> str:
    """Idempotent UpdateItem on match_statistics_prod.

    Uses ConditionExpression `attribute_not_exists(goals_scored)` so a
    re-run never overwrites a row that already has the field — important
    once the new ingest path is live and writes both attrs at write time.

    Returns 'updated' on success, 'skipped' if the row already had the
    field (ConditionalCheckFailedException), or 'error' otherwise.
    """
    table = ddb().Table(MATCH_STATISTICS_TABLE)
    try:
        table.update_item(
            Key={"fixture_id": int(fixture_id), "team_id": int(team_id)},
            UpdateExpression=(
                "SET goals_scored = :gs, goals_conceded = :gc"
            ),
            ConditionExpression="attribute_not_exists(goals_scored)",
            ExpressionAttributeValues={
                ":gs": int(goals_scored),
                ":gc": int(goals_conceded),
            },
        )
        return "updated"
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return "skipped"
    except Exception as e:
        print(f"  ERROR updating ({fixture_id}, {team_id}): {e}")
        return "error"


def main(apply: bool, limit: Optional[int], chunk_size: int) -> None:
    started = time.time()
    print(f"Backfill mode: {'APPLY (writing)' if apply else 'DRY-RUN (no writes)'}")
    if limit:
        print(f"Row limit: {limit}")

    # Streaming scan with chunked fixture-id grouping. We collect up to
    # `chunk_size` rows, fetch their goals in one pass, then emit updates.
    counts = defaultdict(int)
    pending: List[dict] = []

    def flush(rows: List[dict]) -> None:
        if not rows:
            return
        fixture_ids = [int(r["fixture_id"]) for r in rows]
        goals_map = batch_get_goals(fixture_ids)

        for r in rows:
            fid = int(r["fixture_id"])
            tid = int(r["team_id"])
            is_home = bool(r.get("is_home"))

            if "goals_scored" in r:
                counts["already_present"] += 1
                continue

            goals = goals_map.get(fid)
            if goals is None:
                counts["fixture_missing_goals"] += 1
                continue

            hg, ag = goals
            gs = hg if is_home else ag
            gc = ag if is_home else hg

            if not apply:
                counts["would_update"] += 1
                if counts["would_update"] <= 10:
                    print(f"  WOULD update ({fid},{tid}) is_home={is_home} → "
                          f"goals_scored={gs} goals_conceded={gc}")
            else:
                result = update_one(fid, tid, gs, gc)
                counts[result] += 1

    seen = 0
    for row in scan_match_stats(limit=limit):
        pending.append(row)
        seen += 1
        if len(pending) >= chunk_size:
            flush(pending)
            pending = []
            elapsed = time.time() - started
            print(f"  progress: {seen} rows scanned, {dict(counts)} "
                  f"({elapsed:.1f}s)")
    flush(pending)

    elapsed = time.time() - started
    print()
    print(f"Done in {elapsed:.1f}s.")
    print(f"Rows scanned: {seen}")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    if not apply and counts.get("would_update"):
        print()
        print("This was a dry-run. Re-run with --apply to actually write.")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apply", action="store_true",
                   help="Actually write updates. Default is dry-run.")
    p.add_argument("--limit", type=int, default=None,
                   help="Process only the first N rows (for smoke tests).")
    p.add_argument("--chunk-size", type=int, default=100,
                   help="Batch size for fixture-goal lookups (default 100, "
                        "the DynamoDB BatchGetItem maximum).")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(apply=args.apply, limit=args.limit, chunk_size=args.chunk_size)
