#!/usr/bin/env python3
"""
Backfill v7.0 → v8.0 predictions for all 4 variants in
football_game_fixtures_prod.

For every record with prediction_metadata.architecture_version == "7.0":
  1. Preserve the original 4 prediction variants in *_v7_original fields.
  2. Recompute each variant's stored λ (home and away) with the v8 transform:
       - predictions, alternate_predictions (cross-venue, home_adv was applied):
           λ' = λ_v7 × anchor_correction × (home_adv_inverse on home, home_adv on away) × 1.35
       - venue_predictions, venue_alternate_predictions (venue-specific, home_adv was skipped):
           λ' = λ_v7 × anchor_correction × 1.35
  3. Re-derive all prediction sub-fields (most_likely_score, expected_goals,
     match_outcome, goals.over/under/btts, odds, top_scores) from the
     corrected λ using a Negative Binomial distribution (α = DEFAULT_ALPHA).
  4. Update prediction_metadata:
       architecture_version  = "8.0"
       backfilled_at         = <unix ts>
       backfill_source       = "v7_math_transform"
       backfill_leaves_other_fields = True  # e.g. multipliers baked into stored λ

Approximation: uses the *current* league_parameters snapshot as the correction
basis (not a historical snapshot). Within a single season this drifts by only
a few percent, which is dominated by the much larger structural fix.

Approximation 2: uses league params for all 4 variants, including the two
alternate variants that were originally computed with team params. The
correction factor is a ratio; for well-observed teams, team μH/μA are close
to league values after Bayesian smoothing, so the error here is small.

Usage:
    python backfill_v7_to_v8.py                 # dry-run: print stats + 3 sample diffs
    python backfill_v7_to_v8.py --limit 20      # dry-run limited to 20 records
    python backfill_v7_to_v8.py --apply         # actually write to DynamoDB
    python backfill_v7_to_v8.py --apply --sleep 0.02   # throttle writes
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError
from scipy import stats

from src.utils.constants import DEFAULT_ALPHA, MAX_GOALS_ANALYSIS

FIXTURES_TABLE = "football_game_fixtures_prod"
LEAGUE_PARAMS_TABLE = "football_league_parameters_prod"
REGION = "eu-west-2"

BOOST = 1.35
CROSS_VENUE_VARIANTS = ("predictions", "alternate_predictions")
VENUE_VARIANTS = ("venue_predictions", "venue_alternate_predictions")
ALL_VARIANTS = CROSS_VENUE_VARIANTS + VENUE_VARIANTS

BACKFILL_SOURCE = "v7_math_transform"
TARGET_VERSION = "8.0"

OVER_UNDER_THRESHOLDS = (0.5, 1.5, 2.5, 3.5, 4.5)


# ---------------------------------------------------------------------------
# Distribution helpers — boost-free so the backfill applies the 1.35 explicitly
# rather than relying on the now-baked-in value in distributions.py
# ---------------------------------------------------------------------------
def nb_pmf(k: int, mu: float, alpha: float = DEFAULT_ALPHA) -> float:
    if mu <= 0:
        return 1.0 if k == 0 else 0.0
    if alpha <= 0.01:
        try:
            return (mu ** k) * math.exp(-mu) / math.factorial(k)
        except OverflowError:
            return 0.0
    r = 1.0 / alpha
    p = 1.0 / (1.0 + alpha * mu)
    return float(stats.nbinom.pmf(k, r, p))


def goal_probs(lmbda: float) -> dict[int, float]:
    raw = {k: nb_pmf(k, lmbda) for k in range(MAX_GOALS_ANALYSIS + 1)}
    total = sum(raw.values())
    if total <= 0:
        raw[0] = 1.0
        return raw
    return {k: v / total for k, v in raw.items()}


def avg_def_of(p: float) -> float:
    cs = 1 - p
    return 0.6 * p + 0.4 * (1 - cs * (1 - p))


def correction_factors(params: dict) -> tuple[float, float]:
    mu_h = params["mu_home"]
    mu_a = params["mu_away"]
    p_h = params["p_score_home"]
    p_a = params["p_score_away"]
    mu_bar = 0.5 * (mu_h + mu_a)
    p_bar = 0.5 * (p_h + p_a)
    avg_raw_old_h = mu_h * mu_h * p_h * avg_def_of(p_h)
    avg_raw_old_a = mu_a * mu_a * p_a * avg_def_of(p_a)
    avg_raw_new = mu_bar * mu_bar * p_bar * avg_def_of(p_bar)
    if avg_raw_new <= 0:
        return 1.0, 1.0
    return avg_raw_old_h / avg_raw_new, avg_raw_old_a / avg_raw_new


def corrected_lambdas(
    variant: str, lam_h: float, lam_a: float, params: dict
) -> tuple[float, float]:
    corr_h, corr_a = correction_factors(params)
    home_adv = float(params.get("home_adv", 1.0)) or 1.0
    if variant in CROSS_VENUE_VARIANTS:
        new_h = lam_h * corr_h * (1.0 / home_adv) * BOOST
        new_a = lam_a * corr_a * home_adv * BOOST
    else:
        new_h = lam_h * corr_h * BOOST
        new_a = lam_a * corr_a * BOOST
    # Apply the same squash-ceiling as production (distributions.squash_lambda)
    new_h = squash(new_h)
    new_a = squash(new_a)
    return new_h, new_a


def squash(lmbda: float, ceiling: float = 7.0) -> float:
    if lmbda <= ceiling:
        return lmbda
    return ceiling * (1 + math.tanh((lmbda - ceiling) / ceiling))


# ---------------------------------------------------------------------------
# Build the stored prediction summary dict from corrected λ
# ---------------------------------------------------------------------------
def build_summary(lam_h: float, lam_a: float) -> dict:
    hp = goal_probs(lam_h)
    ap = goal_probs(lam_a)

    # Joint matrix
    mat = [[hp[h] * ap[a] for a in range(11)] for h in range(11)]
    # Most likely
    best = (0, 0, mat[0][0])
    for h in range(11):
        for a in range(11):
            if mat[h][a] > best[2]:
                best = (h, a, mat[h][a])

    phw = sum(mat[h][a] for h in range(11) for a in range(11) if h > a)
    pd = sum(mat[h][a] for h in range(11) for a in range(11) if h == a)
    paw = sum(mat[h][a] for h in range(11) for a in range(11) if h < a)

    overs = {
        t: sum(mat[h][a] for h in range(11) for a in range(11) if h + a > t)
        for t in OVER_UNDER_THRESHOLDS
    }
    pbtts = sum(mat[h][a] for h in range(1, 11) for a in range(1, 11))

    e_h = sum(k * p for k, p in hp.items())
    e_a = sum(k * p for k, p in ap.items())

    # Top 5 scores
    flat = [(h, a, mat[h][a]) for h in range(11) for a in range(11)]
    flat.sort(key=lambda t: -t[2])
    top_scores = [
        {"score": f"{h}-{a}", "probability": round(p * 100, 1)}
        for h, a, p in flat[:5]
    ]

    return {
        "most_likely_score": {
            "score": f"{best[0]}-{best[1]}",
            "probability": round(best[2] * 100, 1),
        },
        "expected_goals": {
            "home": round(e_h, 2),
            "away": round(e_a, 2),
            "total": round(e_h + e_a, 2),
        },
        "match_outcome": {
            "home_win": round(phw * 100, 1),
            "draw": round(pd * 100, 1),
            "away_win": round(paw * 100, 1),
        },
        "goals": {
            "over": {
                str(t): round(overs[t] * 100, 1) for t in OVER_UNDER_THRESHOLDS
            },
            "under": {
                str(t): round((1 - overs[t]) * 100, 1) for t in OVER_UNDER_THRESHOLDS
            },
            "btts": {
                "yes": round(pbtts * 100, 1),
                "no": round((1 - pbtts) * 100, 1),
            },
        },
        "odds": {
            "match_outcome": {
                "home_win": round(1 / max(phw, 0.01), 2),
                "draw": round(1 / max(pd, 0.01), 2),
                "away_win": round(1 / max(paw, 0.01), 2),
            },
            "over_under": {
                "over_2.5": round(1 / max(overs[2.5], 0.01), 2),
                "under_2.5": round(1 / max(1 - overs[2.5], 0.01), 2),
            },
            "btts": {
                "yes": round(1 / max(pbtts, 0.01), 2),
                "no": round(1 / max(1 - pbtts, 0.01), 2),
            },
        },
        "top_scores": top_scores,
    }


# ---------------------------------------------------------------------------
# DynamoDB I/O
# ---------------------------------------------------------------------------
def load_league_params(region: str, table: str) -> dict:
    out: dict = {}
    t = boto3.resource("dynamodb", region_name=region).Table(table)
    kwargs: dict[str, Any] = {}
    while True:
        resp = t.scan(**kwargs)
        for item in resp.get("Items", []):
            try:
                key = (int(item["league_id"]), int(item["season"]))
                out[key] = {
                    "mu_home": float(item["mu_home"]),
                    "mu_away": float(item["mu_away"]),
                    "p_score_home": float(item["p_score_home"]),
                    "p_score_away": float(item["p_score_away"]),
                    "home_adv": float(item.get("home_adv", 1.0)),
                }
            except (KeyError, TypeError, ValueError):
                continue
        if "LastEvaluatedKey" not in resp:
            return out
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def scan_v7_records(region: str, table: str, limit: int | None = None):
    t = boto3.resource("dynamodb", region_name=region).Table(table)
    kwargs: dict[str, Any] = dict(
        FilterExpression="prediction_metadata.architecture_version = :v",
        ExpressionAttributeValues={":v": "7.0"},
    )
    yielded = 0
    while True:
        resp = t.scan(**kwargs)
        for item in resp.get("Items", []):
            yield item
            yielded += 1
            if limit is not None and yielded >= limit:
                return
        if "LastEvaluatedKey" not in resp:
            return
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def to_decimal(obj: Any) -> Any:
    """Recursively convert floats to Decimals for DynamoDB."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return Decimal("0")
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_decimal(v) for v in obj]
    return obj


def update_fixture(table, fixture_id: int, originals: dict, new_vars: dict,
                   now_ts: int) -> None:
    """Single UpdateItem carrying all backup + new variants + metadata."""
    set_parts: list[str] = []
    names: dict[str, str] = {}
    values: dict[str, Any] = {}

    # Preserve originals (only if we actually have them in the source record)
    for i, v in enumerate(ALL_VARIANTS):
        if v not in originals:
            continue
        orig_field = f"{v}_v7_original"
        names[f"#o{i}"] = orig_field
        names[f"#v{i}"] = v
        values[f":o{i}"] = originals[v]
        values[f":v{i}"] = to_decimal(new_vars[v])
        set_parts.append(f"#o{i} = :o{i}")
        set_parts.append(f"#v{i} = :v{i}")

    # Metadata
    names["#pm"] = "prediction_metadata"
    names["#av"] = "architecture_version"
    names["#ba"] = "backfilled_at"
    names["#bs"] = "backfill_source"
    values[":av"] = TARGET_VERSION
    values[":ba"] = now_ts
    values[":bs"] = BACKFILL_SOURCE
    set_parts += [
        "#pm.#av = :av",
        "#pm.#ba = :ba",
        "#pm.#bs = :bs",
    ]

    # Idempotency guard: only update if still at v7 and not already backfilled.
    values[":old_v"] = "7.0"

    table.update_item(
        Key={"fixture_id": fixture_id},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ConditionExpression=(
            "#pm.#av = :old_v AND attribute_not_exists(#pm.#ba)"
        ),
    )


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------
def process_record(item: dict, league_params: dict) -> dict | None:
    """Compute new variants for a record. Return dict with keys
    {'originals', 'new_vars', 'skipped_variants', 'lambda_summary'} or None to skip.
    """
    try:
        league_id = int(item["league_id"])
        season = int(item["season"])
    except (KeyError, TypeError, ValueError):
        return None

    p = league_params.get((league_id, season))
    if p is None:
        return None

    meta = item.get("prediction_metadata", {}) or {}
    if meta.get("architecture_version") == TARGET_VERSION:
        return {"skip_reason": "already_v8"}
    if "backfilled_at" in meta:
        return {"skip_reason": "already_backfilled"}

    originals: dict = {}
    new_vars: dict = {}
    lambda_summary: dict = {}
    skipped: list[str] = []

    for variant in ALL_VARIANTS:
        stored = item.get(variant)
        if stored is None:
            skipped.append(variant)
            continue
        eg = stored.get("expected_goals") or {}
        try:
            lam_h_old = float(eg["home"])
            lam_a_old = float(eg["away"])
        except (KeyError, TypeError, ValueError):
            skipped.append(variant)
            continue

        lam_h_new, lam_a_new = corrected_lambdas(variant, lam_h_old, lam_a_old, p)
        new_summary = build_summary(lam_h_new, lam_a_new)

        originals[variant] = stored
        new_vars[variant] = new_summary
        lambda_summary[variant] = {
            "old_home": round(lam_h_old, 3),
            "old_away": round(lam_a_old, 3),
            "new_home": round(lam_h_new, 3),
            "new_away": round(lam_a_new, 3),
        }

    if not new_vars:
        return None

    return {
        "originals": originals,
        "new_vars": new_vars,
        "lambda_summary": lambda_summary,
        "skipped_variants": skipped,
    }


def print_sample(fixture_id: int, result: dict) -> None:
    print(f"\n  fixture_id={fixture_id}")
    for variant, d in result["lambda_summary"].items():
        print(
            f"    {variant:<32} "
            f"home {d['old_home']:.3f} → {d['new_home']:.3f}  "
            f"away {d['old_away']:.3f} → {d['new_away']:.3f}"
        )
    if result.get("skipped_variants"):
        print(f"    (no data for: {result['skipped_variants']})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region", default=REGION)
    ap.add_argument("--fixtures-table", default=FIXTURES_TABLE)
    ap.add_argument("--params-table", default=LEAGUE_PARAMS_TABLE)
    ap.add_argument("--apply", action="store_true",
                    help="Actually write to DynamoDB (default is dry-run)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sample", type=int, default=3)
    ap.add_argument("--sleep", type=float, default=0.0,
                    help="Sleep between writes to throttle (seconds)")
    args = ap.parse_args()

    print(f"[1/3] Loading league parameters from {args.params_table}...")
    league_params = load_league_params(args.region, args.params_table)
    print(f"      {len(league_params)} (league, season) records")

    print(f"[2/3] Scanning {args.fixtures_table} for v7.0 records...")
    t = boto3.resource("dynamodb", region_name=args.region).Table(args.fixtures_table)
    now_ts = int(datetime.now(timezone.utc).timestamp())

    counts = {
        "scanned": 0, "skipped_no_params": 0, "skipped_already_backfilled": 0,
        "skipped_no_variants": 0, "applied": 0, "errors": 0,
    }
    variant_hits = {v: 0 for v in ALL_VARIANTS}
    bias_before_home: list[float] = []
    bias_after_home: list[float] = []
    bias_before_away: list[float] = []
    bias_after_away: list[float] = []
    samples_printed = 0

    for item in scan_v7_records(args.region, args.fixtures_table, args.limit):
        counts["scanned"] += 1
        result = process_record(item, league_params)
        if result is None:
            counts["skipped_no_params"] += 1
            continue
        if "skip_reason" in result:
            counts["skipped_already_backfilled"] += 1
            continue
        if not result["new_vars"]:
            counts["skipped_no_variants"] += 1
            continue

        for v in result["new_vars"]:
            variant_hits[v] += 1
        # Accumulate bias for the primary 'predictions' variant
        if "predictions" in result["lambda_summary"]:
            d = result["lambda_summary"]["predictions"]
            bias_before_home.append(d["old_home"])
            bias_after_home.append(d["new_home"])
            bias_before_away.append(d["old_away"])
            bias_after_away.append(d["new_away"])

        if samples_printed < args.sample:
            print_sample(int(item["fixture_id"]), result)
            samples_printed += 1

        if args.apply:
            try:
                fixture_id = int(item["fixture_id"])
                update_fixture(t, fixture_id, result["originals"],
                               result["new_vars"], now_ts)
                counts["applied"] += 1
                if args.sleep > 0:
                    time.sleep(args.sleep)
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code == "ConditionalCheckFailedException":
                    counts["skipped_already_backfilled"] += 1
                else:
                    counts["errors"] += 1
                    print(f"  ERROR on fixture_id={item.get('fixture_id')}: {e}")

    print(f"\n[3/3] Summary:")
    print(f"      mode: {'APPLY (writes committed)' if args.apply else 'DRY RUN'}")
    for k, v in counts.items():
        print(f"      {k:>28}: {v:,}")
    print(f"      variant coverage (correctable records per variant):")
    for v, n in variant_hits.items():
        print(f"        {v:<32} {n:,}")

    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    if bias_before_home:
        print(f"\n      `predictions` variant λ means (across {len(bias_before_home)} records):")
        print(f"        home: {mean(bias_before_home):.3f} → {mean(bias_after_home):.3f}  "
              f"(Δ={mean(bias_after_home) - mean(bias_before_home):+.3f})")
        print(f"        away: {mean(bias_before_away):.3f} → {mean(bias_after_away):.3f}  "
              f"(Δ={mean(bias_after_away) - mean(bias_before_away):+.3f})")

    if not args.apply:
        print("\n      Dry run complete. To commit: rerun with --apply")


if __name__ == "__main__":
    main()
