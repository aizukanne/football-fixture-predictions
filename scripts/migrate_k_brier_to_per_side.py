#!/usr/bin/env python3
"""Rename legacy k_goals / k_score / brier / brier_ema fields to the new
per-side equivalents on football_team_parameters_prod and
football_league_parameters_prod.

Why this exists
---------------
The home-only Brier loop has been tuning a single `k_goals` / `k_score`
per team (and per league), then applying the same constants to both home
and away smoothing. Per-side fields (`k_goals_home` / `k_goals_away` etc.)
mean each side's k is tuned by its own Brier feedback. New writes only
populate the per-side fields; this script seeds the per-side fields on
existing records by copying from the legacy fields, then optionally
deletes the legacy fields.

Field mapping
-------------
    k_goals             -> k_goals_home, k_goals_away              (both seeded with same value)
    k_score             -> k_score_home, k_score_away
    goal_prior_weight   -> goal_prior_weight_home/away
    score_prior_weight  -> score_prior_weight_home/away
    brier               -> brier_home, brier_away
    brier_ema           -> brier_ema_home, brier_ema_away
    k_feedback_step     -> k_feedback_step_home/away
    k_feedback_reason   -> k_feedback_reason_home/away

Idempotent: only copies when the per-side field is missing. Safe to re-run.

Usage
-----
    # Smoke check (no writes), tables visible:
    python scripts/migrate_k_brier_to_per_side.py

    # Apply: seed per-side fields where missing
    python scripts/migrate_k_brier_to_per_side.py --apply

    # Apply AND delete legacy fields. Run only after one weekly cycle
    # has confirmed the new fields are populated correctly.
    python scripts/migrate_k_brier_to_per_side.py --apply --drop-legacy
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

import boto3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

os.environ.setdefault("TABLE_PREFIX", "football_")
os.environ.setdefault("TABLE_SUFFIX", "_prod")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")

from src.utils.constants import TEAM_PARAMETERS_TABLE, LEAGUE_PARAMETERS_TABLE  # noqa: E402


# Each tuple = (legacy_name, side_default_for_missing)
# When a record has the legacy field but neither *_home nor *_away, both
# sides are seeded with the legacy value. Existing per-side fields are
# never overwritten.
FIELD_MAP = [
    "k_goals",
    "k_score",
    "goal_prior_weight",
    "score_prior_weight",
    "brier",
    "brier_ema",
    "k_feedback_step",
    "k_feedback_reason",
]

_ddb = None


def ddb():
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource("dynamodb")
    return _ddb


def scan_all(table_name):
    table = ddb().Table(table_name)
    kwargs = {}
    while True:
        resp = table.scan(**kwargs)
        for it in resp.get("Items", []):
            yield it
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            return
        kwargs["ExclusiveStartKey"] = lek


def derive_updates(item, drop_legacy):
    """Return (set_attrs, remove_attrs).

    set_attrs   – dict of new attributes to write (only those missing).
    remove_attrs – list of legacy attribute names to delete (drop_legacy only).
    """
    set_attrs = {}
    remove_attrs = []

    for legacy in FIELD_MAP:
        legacy_val = item.get(legacy)
        if legacy_val is None:
            continue
        home_key = f"{legacy}_home"
        away_key = f"{legacy}_away"
        if home_key not in item:
            set_attrs[home_key] = legacy_val
        if away_key not in item:
            set_attrs[away_key] = legacy_val
        if drop_legacy:
            remove_attrs.append(legacy)

    return set_attrs, remove_attrs


def update_one(table_name, key, set_attrs, remove_attrs):
    """Single UpdateItem with SET and REMOVE clauses combined.

    Returns 'updated', 'noop', or 'error'.
    """
    if not set_attrs and not remove_attrs:
        return "noop"
    table = ddb().Table(table_name)

    # Build expression. Use placeholders for attribute names because some
    # legacy names might collide with reserved words (none of ours do, but
    # safer this way).
    expr_parts = []
    expr_attr_names = {}
    expr_attr_values = {}
    if set_attrs:
        set_clauses = []
        for i, (k, v) in enumerate(set_attrs.items()):
            ph_name = f"#sn{i}"
            ph_val = f":sv{i}"
            expr_attr_names[ph_name] = k
            expr_attr_values[ph_val] = v
            set_clauses.append(f"{ph_name} = {ph_val}")
        expr_parts.append("SET " + ", ".join(set_clauses))
    if remove_attrs:
        remove_clauses = []
        for i, k in enumerate(remove_attrs):
            ph_name = f"#rn{i}"
            expr_attr_names[ph_name] = k
            remove_clauses.append(ph_name)
        expr_parts.append("REMOVE " + ", ".join(remove_clauses))

    update_kwargs = {
        "Key": key,
        "UpdateExpression": " ".join(expr_parts),
        "ExpressionAttributeNames": expr_attr_names,
    }
    if expr_attr_values:
        update_kwargs["ExpressionAttributeValues"] = expr_attr_values

    try:
        table.update_item(**update_kwargs)
        return "updated"
    except Exception as e:
        print(f"  ERROR updating {key}: {e}")
        return "error"


def migrate_table(table_name, key_attrs, apply, drop_legacy, limit=None):
    print(f"\n=== {table_name} ===")
    counts = defaultdict(int)
    seen = 0

    for item in scan_all(table_name):
        seen += 1
        if limit and seen > limit:
            break

        key = {a: item[a] for a in key_attrs if a in item}
        set_attrs, remove_attrs = derive_updates(item, drop_legacy)

        if not set_attrs and not remove_attrs:
            counts["already_per_side"] += 1
            continue

        if not apply:
            counts["would_update"] += 1
            if counts["would_update"] <= 5:
                print(f"  WOULD update {key}: "
                      f"set={list(set_attrs.keys())} "
                      f"remove={remove_attrs}")
            continue

        result = update_one(table_name, key, set_attrs, remove_attrs)
        counts[result] += 1

    print(f"  rows scanned: {seen}")
    for k, v in counts.items():
        print(f"  {k}: {v}")


def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--apply", action="store_true",
                   help="Persist updates. Default is dry-run.")
    p.add_argument("--drop-legacy", action="store_true",
                   help="Remove legacy field names after seeding per-side "
                        "fields. Use only after one weekly cycle confirms "
                        "the new fields are populated.")
    p.add_argument("--limit", type=int, default=None,
                   help="Process only the first N rows (for smoke tests).")
    return p.parse_args()


def main():
    args = parse_args()
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}"
          + (" + DROP-LEGACY" if args.drop_legacy else ""))

    # team_parameters key: (team_id, league_id)
    migrate_table(
        TEAM_PARAMETERS_TABLE,
        key_attrs=("team_id", "league_id"),
        apply=args.apply,
        drop_legacy=args.drop_legacy,
        limit=args.limit,
    )

    # league_parameters key: (league_id, season) — verify on actual schema
    migrate_table(
        LEAGUE_PARAMETERS_TABLE,
        key_attrs=("league_id", "season"),
        apply=args.apply,
        drop_legacy=args.drop_legacy,
        limit=args.limit,
    )

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
