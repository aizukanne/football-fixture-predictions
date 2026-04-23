#!/usr/bin/env python3
"""
Investigate the away-side ×1.70 boost finding.

Hypothesis: after Stage 1 (anchor uses mu_bar/p_bar denominators), the
league-anchor NUMERATOR still uses mu_home for home and mu_away for away,
which already encodes the home/away goal asymmetry. Then the pipeline
further multiplies home λ by league_home_adv = mu_home/mu_away and divides
away λ by the same — DOUBLE-COUNTING home advantage.

  With anchor alone:     avg home λ = mu_home,  avg away λ = mu_away
  With home_adv added:   avg home λ = mu_home²/mu_away,  avg away λ = mu_away²/mu_home
  Implied asymmetry:     (mu_home/mu_away)³ ≈ 1.95× for mu_home/mu_away = 1.25

This script tests four configurations on stored v7 λ values:
  A. baseline:        Stage 1 anchor correction only (current state)
  B. undo home_adv:   A + divide home by home_adv, multiply away by home_adv
  C. boost 1.30:      A + uniform ×1.30 (what we just shipped)
  D. undo + boost:    B + uniform boost (sweep 1.0–1.4)

If the double-counting hypothesis is correct, config B should nearly zero
the home/away split (but may leave residual total bias from compression
elsewhere), and D should outperform C on home/away symmetry.
"""
from __future__ import annotations

import boto3

from prototype_anchor_fix import (
    FIXTURES_TABLE, LEAGUE_PARAMS_TABLE, REGION,
    correction_factors, joint_probs, load_league_params, load_v7_fixtures,
    new_bucket, score_into, summarize,
)

# `calculate_goal_probabilities` (via joint_probs) now applies a ×1.30 boost
# internally after Stage 2 shipped. For this investigation we want a neutral
# baseline, so pre-divide every λ by the in-code boost factor so the internal
# ×1.30 cancels out.
IN_CODE_BOOST = 1.30


def run(fixtures, params, *, undo_home_adv: bool, boost: float) -> dict:
    b = new_bucket()
    for fx in fixtures:
        p = params.get((fx["league_id"], fx["season"]))
        if p is None:
            continue
        corr_h, corr_a = correction_factors(p)
        home_adv = p["home_adv"] if p["home_adv"] > 0 else 1.0
        adj_h = corr_h * boost * ((1.0 / home_adv) if undo_home_adv else 1.0)
        adj_a = corr_a * boost * (home_adv if undo_home_adv else 1.0)
        score_into(
            b,
            fx["pred_home"] * adj_h / IN_CODE_BOOST,
            fx["pred_away"] * adj_a / IN_CODE_BOOST,
            fx["actual_home"], fx["actual_away"],
        )
    return summarize(b)


def print_row(label: str, s: dict) -> None:
    print(
        f"  {label:<38} "
        f"{s['mean_pred_home']:>7.3f}  {s['home_bias']:>+7.3f}  "
        f"{s['mean_pred_away']:>7.3f}  {s['away_bias']:>+7.3f}  "
        f"{s['total_bias']:>+7.3f}  "
        f"{s['MAE_total']:>6.3f}  {s['RMSE_total']:>6.3f}  "
        f"{s['winner_accuracy']:>6.3f}  "
        f"{s['Brier_1x2']:>6.3f}  {s['Brier_over_2_5']:>7.3f}"
    )


def main() -> None:
    params = load_league_params(REGION, LEAGUE_PARAMS_TABLE)
    fixtures = load_v7_fixtures(REGION, FIXTURES_TABLE)
    print(f"Loaded {len(params)} league params, {len(fixtures)} fixtures")
    print()
    print(
        f"  {'config':<38} "
        f"{'pred_h':>7}  {'bias_h':>7}  {'pred_a':>7}  {'bias_a':>7}  "
        f"{'tot_b':>7}  {'MAE':>6}  {'RMSE':>6}  "
        f"{'winAcc':>6}  {'Br1X2':>6}  {'BrO2.5':>7}"
    )
    print("  " + "-" * 128)

    print_row("A. Stage 1 only (baseline)",
              run(fixtures, params, undo_home_adv=False, boost=1.00))

    print_row("B. A + undo home_adv",
              run(fixtures, params, undo_home_adv=True, boost=1.00))

    print_row("C. A + 1.30 uniform boost (shipped)",
              run(fixtures, params, undo_home_adv=False, boost=1.30))

    for bst in (1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30, 1.35, 1.40):
        print_row(f"D. A + undo home_adv + ×{bst:.2f}",
                  run(fixtures, params, undo_home_adv=True, boost=bst))

    # Actual observed means (from prototype_anchor_fix output):
    print()
    print("  Actual observed means:   pred_h=<--    home=1.521    pred_a=<--   away=1.220    total=2.741")


if __name__ == "__main__":
    main()
