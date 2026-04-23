#!/usr/bin/env python3
"""
Stage 2 boost sweep.

Stage 1 (the anchor fix) reduced home bias from -0.46 to -0.14, but the total
residual bias is still -0.63 goals/match. This script sweeps a post-anchor λ
boost over a grid of values and reports bias / MAE / Brier for each, so we
can pick an empirically optimal value before shipping Stage 2.

Three sweep modes:
  - uniform  : single scalar applied to both home and away λ
  - per-side : independent boosts for home and away (from a grid)
  - best-per-league : fit a per-league uniform scalar that minimises |bias|

The boost is applied AFTER the Option A anchor correction. All other pipeline
steps (smoothing, multipliers, distribution) are left unchanged.

Usage:
    python sweep_anchor_boost.py                       # uniform + per-side
    python sweep_anchor_boost.py --mode per-league     # per-league fit
"""
from __future__ import annotations

import argparse
import math
import statistics
from collections import defaultdict

import boto3

from src.statistics.distributions import calculate_goal_probabilities
from src.utils.constants import DEFAULT_ALPHA

from prototype_anchor_fix import (
    FIXTURES_TABLE,
    LEAGUE_PARAMS_TABLE,
    REGION,
    correction_factors,
    joint_probs,
    load_league_params,
    load_v7_fixtures,
    new_bucket,
    score_into,
    summarize,
)


def sweep_uniform(fixtures, params, grid) -> list[dict]:
    rows = []
    for boost in grid:
        b = new_bucket()
        for fx in fixtures:
            p = params.get((fx["league_id"], fx["season"]))
            if p is None:
                continue
            corr_h, corr_a = correction_factors(p)
            lam_h = fx["pred_home"] * corr_h * boost
            lam_a = fx["pred_away"] * corr_a * boost
            score_into(b, lam_h, lam_a, fx["actual_home"], fx["actual_away"])
        s = summarize(b)
        s["boost_home"] = boost
        s["boost_away"] = boost
        rows.append(s)
    return rows


def sweep_per_side(fixtures, params, grid_h, grid_a) -> list[dict]:
    rows = []
    for bh in grid_h:
        for ba in grid_a:
            b = new_bucket()
            for fx in fixtures:
                p = params.get((fx["league_id"], fx["season"]))
                if p is None:
                    continue
                corr_h, corr_a = correction_factors(p)
                lam_h = fx["pred_home"] * corr_h * bh
                lam_a = fx["pred_away"] * corr_a * ba
                score_into(b, lam_h, lam_a, fx["actual_home"], fx["actual_away"])
            s = summarize(b)
            s["boost_home"] = bh
            s["boost_away"] = ba
            rows.append(s)
    return rows


def fit_per_league(fixtures, params) -> dict:
    """For each league, find the uniform boost that minimises |total_bias|.

    Returns league_id -> (best_boost, n, total_bias_at_best).
    """
    grid = [round(1.00 + 0.02 * i, 2) for i in range(36)]  # 1.00..1.70
    by_league = defaultdict(list)
    for fx in fixtures:
        by_league[fx["league_id"]].append(fx)
    out = {}
    for lid, fxs in by_league.items():
        best = (None, float("inf"), None)
        for boost in grid:
            b = new_bucket()
            for fx in fxs:
                p = params.get((fx["league_id"], fx["season"]))
                if p is None:
                    continue
                corr_h, corr_a = correction_factors(p)
                lam_h = fx["pred_home"] * corr_h * boost
                lam_a = fx["pred_away"] * corr_a * boost
                score_into(b, lam_h, lam_a, fx["actual_home"], fx["actual_away"])
            if b["n"] == 0:
                continue
            s = summarize(b)
            if abs(s["total_bias"]) < best[1]:
                best = (boost, abs(s["total_bias"]), s["total_bias"])
        out[lid] = {"n": len(fxs), "best_boost": best[0],
                    "abs_bias": best[1], "signed_bias": best[2]}
    return out


def print_uniform_table(rows: list[dict]) -> None:
    print()
    print("UNIFORM BOOST SWEEP (same multiplier applied to home and away λ)")
    print("-" * 104)
    print(
        f"  {'boost':>6} {'n':>6} {'tot bias':>10} "
        f"{'home bias':>11} {'away bias':>11} "
        f"{'MAE':>8} {'RMSE':>8} {'win acc':>8} "
        f"{'Br 1X2':>8} {'Br O2.5':>8} {'Br BTTS':>8}"
    )
    for s in rows:
        print(
            f"  {s['boost_home']:>6.2f} {s['n']:>6,} "
            f"{s['total_bias']:>10.4f} "
            f"{s['home_bias']:>11.4f} {s['away_bias']:>11.4f} "
            f"{s['MAE_total']:>8.4f} {s['RMSE_total']:>8.4f} "
            f"{s['winner_accuracy']:>8.4f} "
            f"{s['Brier_1x2']:>8.4f} {s['Brier_over_2_5']:>8.4f} "
            f"{s['Brier_btts']:>8.4f}"
        )


def print_per_side_table(rows: list[dict]) -> None:
    print()
    print("PER-SIDE BOOST SWEEP (independent home and away multipliers)")
    print("-" * 110)
    print(
        f"  {'b_h':>5} {'b_a':>5} {'tot bias':>10} "
        f"{'home bias':>11} {'away bias':>11} "
        f"{'MAE':>8} {'RMSE':>8} {'win acc':>8} "
        f"{'Br 1X2':>8} {'Br O2.5':>8}"
    )
    rows_sorted = sorted(rows, key=lambda s: abs(s["total_bias"]))[:20]
    for s in rows_sorted:
        print(
            f"  {s['boost_home']:>5.2f} {s['boost_away']:>5.2f} "
            f"{s['total_bias']:>10.4f} "
            f"{s['home_bias']:>11.4f} {s['away_bias']:>11.4f} "
            f"{s['MAE_total']:>8.4f} {s['RMSE_total']:>8.4f} "
            f"{s['winner_accuracy']:>8.4f} "
            f"{s['Brier_1x2']:>8.4f} {s['Brier_over_2_5']:>8.4f}"
        )
    print("  (top 20 by |total bias|)")


def print_per_league_fit(fit: dict) -> None:
    print()
    print("PER-LEAGUE OPTIMAL UNIFORM BOOST (minimises |total bias|)")
    print("-" * 60)
    print(f"  {'league':<8} {'n':>5} {'best boost':>12} {'bias':>10}")
    rows = sorted(fit.items(), key=lambda kv: -kv[1]["n"])
    for lid, d in rows[:30]:
        if d["best_boost"] is None:
            continue
        print(
            f"  {lid:<8} {d['n']:>5,} "
            f"{d['best_boost']:>12.2f} {d['signed_bias']:>10.4f}"
        )
    boosts = [d["best_boost"] for d in fit.values() if d["best_boost"] is not None]
    if boosts:
        print()
        print(f"  median best boost across {len(boosts)} leagues: {statistics.median(boosts):.3f}")
        print(f"  mean best boost:                      {statistics.mean(boosts):.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region", default=REGION)
    ap.add_argument("--fixtures-table", default=FIXTURES_TABLE)
    ap.add_argument("--params-table", default=LEAGUE_PARAMS_TABLE)
    ap.add_argument(
        "--mode", choices=("uniform", "per-side", "per-league", "all"), default="all",
    )
    args = ap.parse_args()

    print(f"Loading league parameters...")
    params = load_league_params(args.region, args.params_table)
    print(f"  {len(params)} (league, season) records")

    print(f"Loading v7 completed fixtures...")
    fixtures = load_v7_fixtures(args.region, args.fixtures_table)
    print(f"  {len(fixtures)} fixtures")

    if args.mode in ("uniform", "all"):
        grid = [round(1.00 + 0.05 * i, 2) for i in range(11)]  # 1.00..1.50
        rows = sweep_uniform(fixtures, params, grid)
        print_uniform_table(rows)

    if args.mode in ("per-side", "all"):
        grid_h = [round(1.00 + 0.05 * i, 2) for i in range(5)]   # 1.00..1.20
        grid_a = [round(1.00 + 0.10 * i, 2) for i in range(8)]   # 1.00..1.70
        rows = sweep_per_side(fixtures, params, grid_h, grid_a)
        print_per_side_table(rows)

    if args.mode in ("per-league", "all"):
        fit = fit_per_league(fixtures, params)
        print_per_league_fit(fit)


if __name__ == "__main__":
    main()
