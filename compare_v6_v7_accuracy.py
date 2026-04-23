#!/usr/bin/env python3
"""
Compare prediction accuracy between architecture v6.0 (pre Mar 7, 2026)
and v7.0 (post Mar 7, 2026) using completed fixtures in
football_game_fixtures_prod.

Version boundary comes from commit 1807d3f (Mar 6, 2026) which bumped
CURRENT_ARCHITECTURE_VERSION 6.0 -> 7.0. The changes it tests:
  - Opponent-aware defensive factor (1807d3f)
  - Additive confidence calibration (1807d3f)
  - Season fix for standings lookups (9f677ad)
  - Blended defensive factor 60/40 (5c261fa)
  - League-anchored lambda for underprediction (39f65c7)

Metrics computed per version cohort:
  - mean predicted vs actual total goals (underprediction bias)
  - expected-goals MAE / RMSE
  - exact-score hit rate (most_likely_score == actual)
  - 1X2 pick accuracy
  - Brier scores: 1X2, over 2.5, BTTS
  - home-win probability calibration curve

Usage:
    python compare_v6_v7_accuracy.py [--table NAME] [--region REGION]
"""
from __future__ import annotations

import argparse
import math
import statistics
from collections import defaultdict
from decimal import Decimal
from typing import Any, Iterator

import boto3

TABLE = "football_game_fixtures_prod"
REGION = "eu-west-2"


def scan_fixtures(table_name: str, region: str) -> Iterator[dict]:
    """Yield items from game_fixtures with actual scores + arch version."""
    table = boto3.resource("dynamodb", region_name=region).Table(table_name)
    kwargs: dict[str, Any] = dict(
        FilterExpression=(
            "attribute_exists(goals) "
            "AND attribute_exists(prediction_metadata.architecture_version)"
        ),
        ProjectionExpression=(
            "fixture_id, #d, #ts, prediction_metadata, predictions, goals"
        ),
        ExpressionAttributeNames={"#d": "date", "#ts": "timestamp"},
    )
    while True:
        resp = table.scan(**kwargs)
        for item in resp.get("Items", []):
            yield item
        if "LastEvaluatedKey" not in resp:
            return
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def to_num(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def extract(item: dict) -> dict | None:
    """Flatten a raw item into the fields needed for scoring."""
    try:
        version = str(item["prediction_metadata"]["architecture_version"])
        goals = item["goals"]
        actual_h = int(goals["home"])
        actual_a = int(goals["away"])
    except (KeyError, TypeError, ValueError):
        return None

    preds = item.get("predictions") or {}
    eg = preds.get("expected_goals") or {}
    mo = preds.get("match_outcome") or {}
    mls = preds.get("most_likely_score") or {}
    goal_probs = preds.get("goals") or {}
    over = goal_probs.get("over") or {}
    btts = goal_probs.get("btts") or {}

    return {
        "version": version,
        "fixture_id": int(item["fixture_id"]),
        "date": item.get("date"),
        "actual_home": actual_h,
        "actual_away": actual_a,
        "actual_total": actual_h + actual_a,
        "pred_total": to_num(eg.get("total")),
        "pred_home": to_num(eg.get("home")),
        "pred_away": to_num(eg.get("away")),
        "p_home_win": to_num(mo.get("home_win")),
        "p_draw": to_num(mo.get("draw")),
        "p_away_win": to_num(mo.get("away_win")),
        "mls_score": mls.get("score"),
        "p_over_2_5": to_num(over.get("2.5") or over.get(Decimal("2.5"))),
        "p_over_1_5": to_num(over.get("1.5") or over.get(Decimal("1.5"))),
        "p_btts_yes": to_num(btts.get("yes")),
    }


def new_bucket() -> dict:
    return {
        "n": 0,
        "total_pred_sum": 0.0,
        "total_actual_sum": 0,
        "home_pred_sum": 0.0,
        "home_actual_sum": 0,
        "away_pred_sum": 0.0,
        "away_actual_sum": 0,
        "abs_err_total": [],
        "sq_err_total": [],
        "mls_hits": 0,
        "mls_n": 0,
        "winner_hits": 0,
        "winner_n": 0,
        "brier_1x2": [],
        "brier_over_2_5": [],
        "brier_over_1_5": [],
        "brier_btts": [],
        # calibration: bucket lower-bound (0,10,...,90) -> [n, positive_outcomes]
        "calib_home_win": defaultdict(lambda: [0, 0]),
        "calib_over_2_5": defaultdict(lambda: [0, 0]),
    }


def score_records(records: list[dict]) -> dict[str, dict]:
    buckets: dict[str, dict] = defaultdict(new_bucket)

    for r in records:
        b = buckets[r["version"]]
        b["n"] += 1
        at = r["actual_total"]
        b["total_actual_sum"] += at
        b["home_actual_sum"] += r["actual_home"]
        b["away_actual_sum"] += r["actual_away"]

        pt = r["pred_total"]
        if pt is not None:
            b["total_pred_sum"] += pt
            b["abs_err_total"].append(abs(pt - at))
            b["sq_err_total"].append((pt - at) ** 2)
        if r["pred_home"] is not None:
            b["home_pred_sum"] += r["pred_home"]
        if r["pred_away"] is not None:
            b["away_pred_sum"] += r["pred_away"]

        # Exact-score hit via most_likely_score
        if r["mls_score"]:
            try:
                ph, pa = r["mls_score"].split("-")
                b["mls_n"] += 1
                if int(ph) == r["actual_home"] and int(pa) == r["actual_away"]:
                    b["mls_hits"] += 1
            except ValueError:
                pass

        # 1X2 Brier + top-pick accuracy
        if (
            r["p_home_win"] is not None
            and r["p_draw"] is not None
            and r["p_away_win"] is not None
        ):
            ph = r["p_home_win"] / 100.0
            pd = r["p_draw"] / 100.0
            pa = r["p_away_win"] / 100.0
            if r["actual_home"] > r["actual_away"]:
                oh, od, oa = 1, 0, 0
                truth = "H"
            elif r["actual_home"] < r["actual_away"]:
                oh, od, oa = 0, 0, 1
                truth = "A"
            else:
                oh, od, oa = 0, 1, 0
                truth = "D"

            b["brier_1x2"].append(
                (ph - oh) ** 2 + (pd - od) ** 2 + (pa - oa) ** 2
            )
            b["winner_n"] += 1
            pick = max({"H": ph, "D": pd, "A": pa}.items(), key=lambda kv: kv[1])[0]
            if pick == truth:
                b["winner_hits"] += 1

            # Home-win calibration bins (0-10, 10-20, ... 90-100)
            bkt = min(int(ph * 10) * 10, 90)
            b["calib_home_win"][bkt][0] += 1
            b["calib_home_win"][bkt][1] += oh

        # Over 2.5
        if r["p_over_2_5"] is not None:
            p = r["p_over_2_5"] / 100.0
            o = 1 if at > 2.5 else 0
            b["brier_over_2_5"].append((p - o) ** 2)
            bkt = min(int(p * 10) * 10, 90)
            b["calib_over_2_5"][bkt][0] += 1
            b["calib_over_2_5"][bkt][1] += o

        # Over 1.5
        if r["p_over_1_5"] is not None:
            p = r["p_over_1_5"] / 100.0
            o = 1 if at > 1.5 else 0
            b["brier_over_1_5"].append((p - o) ** 2)

        # BTTS
        if r["p_btts_yes"] is not None:
            p = r["p_btts_yes"] / 100.0
            o = 1 if r["actual_home"] > 0 and r["actual_away"] > 0 else 0
            b["brier_btts"].append((p - o) ** 2)

    return buckets


def summarize(b: dict) -> dict:
    n = b["n"] or 1
    mean = statistics.mean
    return {
        "n": b["n"],
        "mean_pred_total_goals": b["total_pred_sum"] / n,
        "mean_actual_total_goals": b["total_actual_sum"] / n,
        "underprediction_bias": b["total_pred_sum"] / n - b["total_actual_sum"] / n,
        "mean_pred_home_goals": b["home_pred_sum"] / n,
        "mean_actual_home_goals": b["home_actual_sum"] / n,
        "mean_pred_away_goals": b["away_pred_sum"] / n,
        "mean_actual_away_goals": b["away_actual_sum"] / n,
        "total_goals_MAE": mean(b["abs_err_total"]) if b["abs_err_total"] else None,
        "total_goals_RMSE": (
            math.sqrt(mean(b["sq_err_total"])) if b["sq_err_total"] else None
        ),
        "exact_score_hit_rate": (
            b["mls_hits"] / b["mls_n"] if b["mls_n"] else None
        ),
        "winner_1x2_accuracy": (
            b["winner_hits"] / b["winner_n"] if b["winner_n"] else None
        ),
        "Brier_1x2": mean(b["brier_1x2"]) if b["brier_1x2"] else None,
        "Brier_over_2_5": mean(b["brier_over_2_5"]) if b["brier_over_2_5"] else None,
        "Brier_over_1_5": mean(b["brier_over_1_5"]) if b["brier_over_1_5"] else None,
        "Brier_btts": mean(b["brier_btts"]) if b["brier_btts"] else None,
    }


def fmt(x: Any, width: int = 14) -> str:
    if x is None:
        return f"{'n/a':>{width}}"
    if isinstance(x, int):
        return f"{x:>{width},}"
    if isinstance(x, float):
        return f"{x:>{width}.4f}"
    return f"{x:>{width}}"


def print_scorecard(v6: dict, v7: dict) -> None:
    print()
    print(f"{'Metric':<28} {'v6.0 (old)':>14} {'v7.0 (new)':>14} {'Δ (new-old)':>14}")
    print("-" * 74)
    for key in v6:
        a, b = v6.get(key), v7.get(key)
        if key == "n" or not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            delta = None
        else:
            delta = b - a
        print(f"{key:<28} {fmt(a)} {fmt(b)} {fmt(delta)}")


def print_calibration(title: str, bins_v6: dict, bins_v7: dict) -> None:
    print()
    print(f"{title}")
    print(
        f"  {'bin (pred%)':<12} "
        f"{'v6 n':>8} {'v6 hit%':>10} "
        f"{'v7 n':>8} {'v7 hit%':>10}"
    )
    all_bkts = sorted(set(bins_v6.keys()) | set(bins_v7.keys()))
    for bkt in all_bkts:
        a = bins_v6.get(bkt, [0, 0])
        b = bins_v7.get(bkt, [0, 0])
        hr_a = (a[1] / a[0] * 100) if a[0] else None
        hr_b = (b[1] / b[0] * 100) if b[0] else None
        print(
            f"  {bkt:>2}-{bkt + 10:<8} "
            f"{a[0]:>8} {(f'{hr_a:.1f}' if hr_a is not None else 'n/a'):>10} "
            f"{b[0]:>8} {(f'{hr_b:.1f}' if hr_b is not None else 'n/a'):>10}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--table", default=TABLE)
    ap.add_argument("--region", default=REGION)
    args = ap.parse_args()

    print(f"Scanning {args.table} in {args.region}...")
    records: list[dict] = []
    for i, item in enumerate(scan_fixtures(args.table, args.region), 1):
        r = extract(item)
        if r is not None:
            records.append(r)
        if i % 2000 == 0:
            print(f"  ...scanned {i} items")
    print(f"Collected {len(records)} completed fixtures with predictions")

    buckets = score_records(records)
    print(
        f"Cohort sizes: v6.0={buckets.get('6.0', {'n': 0})['n']}  "
        f"v7.0={buckets.get('7.0', {'n': 0})['n']}  "
        f"other={sum(v['n'] for k, v in buckets.items() if k not in ('6.0', '7.0'))}"
    )

    v6 = summarize(buckets.get("6.0") or new_bucket())
    v7 = summarize(buckets.get("7.0") or new_bucket())
    print_scorecard(v6, v7)

    print_calibration(
        "Home-win probability calibration",
        buckets.get("6.0", new_bucket())["calib_home_win"],
        buckets.get("7.0", new_bucket())["calib_home_win"],
    )
    print_calibration(
        "Over 2.5 goals probability calibration",
        buckets.get("6.0", new_bucket())["calib_over_2_5"],
        buckets.get("7.0", new_bucket())["calib_over_2_5"],
    )


if __name__ == "__main__":
    main()
