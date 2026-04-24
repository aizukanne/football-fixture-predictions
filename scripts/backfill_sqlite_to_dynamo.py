"""One-time backfill of fixture_statistics from local SQLite to DynamoDB.

Reads data/fixture_stats/stats.db -> writes to football_match_statistics_prod
(or prefix/suffix-adjusted variant per env).

Idempotent: re-runs overwrite existing items. Resumable: skips fixtures
already fully written via a progress file.

Usage:
    python scripts/backfill_sqlite_to_dynamo.py [--dry-run] [--limit N]
        [--progress-file FILE] [--region REGION]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import boto3
from botocore.exceptions import ClientError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Ensure V2 table constants resolve to production names even when run locally
os.environ.setdefault("TABLE_PREFIX", "football_")
os.environ.setdefault("TABLE_SUFFIX", "_prod")

from src.utils.constants import MATCH_STATISTICS_TABLE, SOT_TO_XG_FACTOR  # noqa: E402

DB_PATH = PROJECT_ROOT / "data" / "fixture_stats" / "stats.db"
DEFAULT_PROGRESS_FILE = PROJECT_ROOT / "data" / "fixture_stats" / "backfill_progress.json"

FINISHED_STATUSES = ("FT", "AET", "PEN", "FT_PEN")

# Canonical mapping from API stat-type strings to DynamoDB attribute keys.
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

# Fields parsed as plain ints; null becomes 0.
INT_FIELDS = {
    "shots_on_goal", "shots_off_goal", "total_shots", "blocked_shots",
    "shots_insidebox", "shots_outsidebox", "fouls", "corner_kicks", "offsides",
    "yellow_cards", "red_cards", "goalkeeper_saves",
    "total_passes", "passes_accurate",
}
# Fields that arrive as "52%" strings; parse to float.
PCT_FIELDS = {"ball_possession_pct", "passes_pct"}
# Fields that arrive as string numerics or raw numerics; parse to float.
FLOAT_FIELDS = {"expected_goals", "goals_prevented"}


def parse_stat_value(api_value: Any, target_key: str) -> float | int | None:
    """Normalize a single stat value from the API into the target type.

    Returns None if the value is missing/unparseable. Callers decide what
    None means (usually: omit attribute for expected_goals/goals_prevented,
    zero for counters).
    """
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


def to_decimal(v: float | int | None) -> Decimal | None:
    """DynamoDB-safe numeric. Returns None so callers can drop the attribute."""
    if v is None:
        return None
    # Decimal(float) is prohibited because of binary-precision surprises;
    # go via str() to preserve intent.
    return Decimal(str(v))


def build_team_item(
    fixture_id: int,
    fixture_meta: dict,
    team_entry: dict,
) -> dict | None:
    """Translate one API team-statistics block into a DynamoDB item.

    Returns None if the team's stats are empty (no usable data).
    """
    team = team_entry.get("team") or {}
    team_id = team.get("id")
    if not team_id:
        return None

    stats_list = team_entry.get("statistics") or []
    if not stats_list:
        return None

    is_home = (team_id == fixture_meta["home_team_id"])

    # Parse every stat into its target slot.
    parsed: dict[str, Any] = {}
    for s in stats_list:
        api_type = s.get("type")
        key = STAT_KEY_MAP.get(api_type)
        if not key:
            continue
        parsed[key] = parse_stat_value(s.get("value"), key)

    # Impute expected_goals if missing and we have shots_on_goal.
    expected_goals = parsed.get("expected_goals")
    sot = parsed.get("shots_on_goal")
    if expected_goals is None and sot is not None and sot > 0:
        expected_goals = float(sot) * SOT_TO_XG_FACTOR
        xg_source = "sot_proxy"
    elif expected_goals is not None:
        xg_source = "native"
    else:
        # No usable xG signal for this team in this match. Skip.
        return None

    item: dict[str, Any] = {
        "fixture_id": fixture_id,
        "team_id": int(team_id),
        "league_id": int(fixture_meta["league_id"]),
        "season": int(fixture_meta["season"]),
        "match_date": fixture_meta["match_date"],
        "is_home": is_home,
        "xg_source": xg_source,
        "stat_raw_json": json.dumps(team_entry),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    # Counter fields: None -> 0 (the API returns null for yellow/red cards
    # when there were none; normalizing to 0 is unambiguous here).
    for k in INT_FIELDS:
        v = parsed.get(k)
        item[k] = 0 if v is None else int(v)

    # Percent fields and free-float fields: None -> attribute omitted so
    # downstream can distinguish missing-from-API from present-and-zero.
    for k in PCT_FIELDS | {"goals_prevented"}:
        v = parsed.get(k)
        if v is not None:
            item[k] = to_decimal(v)

    # Expected goals: always written (either native or imputed).
    item["expected_goals"] = to_decimal(expected_goals)

    return item


def iter_fixtures_with_stats(
    sqlite_path: Path, skip_ids: set[int]
) -> Iterator[tuple[int, dict, dict]]:
    """Yield (fixture_id, fixture_meta, parsed_payload) for each fixture
    that has a raw stats payload in SQLite and isn't in skip_ids.

    Payloads with zero team entries are yielded so the caller can log/skip.
    """
    con = sqlite3.connect(str(sqlite_path))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """SELECT r.fixture_id, r.payload_json,
                      f.league_id, f.season, f.date, f.home_team_id, f.away_team_id,
                      f.status_short
                 FROM fixture_statistics_raw r
                 JOIN fixtures f ON f.fixture_id = r.fixture_id"""
        )
        for r in rows:
            fid = r["fixture_id"]
            if fid in skip_ids:
                continue
            if r["status_short"] not in FINISHED_STATUSES:
                continue
            try:
                payload = json.loads(r["payload_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            meta = {
                "league_id": r["league_id"],
                "season": r["season"],
                "match_date": r["date"],
                "home_team_id": r["home_team_id"],
                "away_team_id": r["away_team_id"],
            }
            yield fid, meta, payload
    finally:
        con.close()


def load_progress(path: Path) -> set[int]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
        return set(int(x) for x in data.get("completed_fixture_ids", []))
    except (json.JSONDecodeError, ValueError, OSError):
        return set()


def save_progress(path: Path, completed: set[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({
        "completed_fixture_ids": sorted(completed),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }))
    tmp.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Print first 5 items that would be written, then stop.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Stop after writing N fixtures (for smoke tests).")
    ap.add_argument("--progress-file", default=str(DEFAULT_PROGRESS_FILE))
    ap.add_argument("--region", default=os.getenv("AWS_REGION", "eu-west-2"))
    ap.add_argument("--reset-progress", action="store_true",
                    help="Ignore existing progress and re-write everything.")
    args = ap.parse_args()

    progress_path = Path(args.progress_file)
    skip_ids: set[int] = set() if args.reset_progress else load_progress(progress_path)
    if skip_ids:
        print(f"Skipping {len(skip_ids)} fixture_ids from prior run.")

    if not DB_PATH.exists():
        print(f"ERROR: SQLite DB not found at {DB_PATH}", file=sys.stderr)
        return 1

    ddb = boto3.resource("dynamodb", region_name=args.region)
    table = ddb.Table(MATCH_STATISTICS_TABLE)

    # Early existence check — fail fast if the table isn't ready.
    try:
        status = ddb.meta.client.describe_table(TableName=MATCH_STATISTICS_TABLE)["Table"]["TableStatus"]
        if status != "ACTIVE":
            print(f"ERROR: {MATCH_STATISTICS_TABLE} status is {status}, not ACTIVE.", file=sys.stderr)
            return 1
    except ClientError as e:
        print(f"ERROR: cannot describe {MATCH_STATISTICS_TABLE}: {e}", file=sys.stderr)
        return 1

    stats = {
        "fixtures_seen": 0,
        "fixtures_empty_payload": 0,
        "fixtures_written": 0,
        "items_written": 0,
        "items_skipped_no_xg": 0,
    }
    start = time.time()

    if args.dry_run:
        print("DRY RUN — no DynamoDB writes will occur.")
        items_preview: list[dict] = []
        for fid, meta, payload in iter_fixtures_with_stats(DB_PATH, skip_ids):
            stats["fixtures_seen"] += 1
            teams = payload.get("response") or []
            if not teams:
                stats["fixtures_empty_payload"] += 1
                continue
            for te in teams:
                item = build_team_item(fid, meta, te)
                if item is None:
                    stats["items_skipped_no_xg"] += 1
                    continue
                items_preview.append(item)
                if len(items_preview) >= 5:
                    break
            if len(items_preview) >= 5:
                break
        print("\nFirst 5 items that would be written:")
        for it in items_preview:
            # Don't dump the huge stat_raw_json in the preview
            printable = {k: ("<json>" if k == "stat_raw_json" else v) for k, v in it.items()}
            print(json.dumps(printable, default=str, indent=2))
            print("---")
        print(f"\nSummary (partial): {stats}")
        return 0

    # Real run.
    try:
        with table.batch_writer() as batch:
            for fid, meta, payload in iter_fixtures_with_stats(DB_PATH, skip_ids):
                stats["fixtures_seen"] += 1
                teams = payload.get("response") or []
                if not teams:
                    stats["fixtures_empty_payload"] += 1
                    skip_ids.add(fid)
                    continue

                fixture_had_any_item = False
                for te in teams:
                    item = build_team_item(fid, meta, te)
                    if item is None:
                        stats["items_skipped_no_xg"] += 1
                        continue
                    batch.put_item(Item=item)
                    stats["items_written"] += 1
                    fixture_had_any_item = True

                if fixture_had_any_item:
                    stats["fixtures_written"] += 1

                skip_ids.add(fid)

                # Checkpoint progress every 500 fixtures.
                if stats["fixtures_seen"] % 500 == 0:
                    save_progress(progress_path, skip_ids)
                    elapsed = time.time() - start
                    rate = stats["items_written"] / elapsed if elapsed > 0 else 0
                    print(f"[{stats['fixtures_seen']:>5d} fixtures] "
                          f"{stats['items_written']:>6d} items written "
                          f"({rate:.1f}/s), "
                          f"{stats['fixtures_empty_payload']} empty payloads, "
                          f"{stats['items_skipped_no_xg']} items lacked usable xG")

                if args.limit is not None and stats["fixtures_written"] >= args.limit:
                    print(f"--limit {args.limit} reached, stopping.")
                    break

    finally:
        save_progress(progress_path, skip_ids)

    elapsed = time.time() - start
    print("\n=== BACKFILL COMPLETE ===")
    for k, v in stats.items():
        print(f"  {k:30s}  {v:,}")
    print(f"  elapsed_seconds             {elapsed:,.1f}")
    print(f"  progress file               {progress_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
