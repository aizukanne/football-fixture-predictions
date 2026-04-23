#!/usr/bin/env python3
"""
Prototype Option A: fix the league-anchor denominator in prediction_engine.py
by using cross-venue factor centers (μ̄, p̄) instead of the home-biased
(μH, p_score_home) / away-biased (μA, p_score_away) priors.

The current v7 anchor at src/prediction/prediction_engine.py:280-285 computes:
    avg_raw_lambda = goal_prior² * score_prior * avg_def(score_prior)
but the raw lambda factors (team_goals_scored, opp_goals_conceded, games_scored,
defensive_factor) center at cross-venue averages, not on the home-biased priors.
This compresses home λ by ~20% and inflates away λ by ~13% in a typical league.

Because every downstream step is multiplicative, swapping the anchor denominator
is equivalent to multiplying each stored final λ by:
    correction_home = μH² * p_h * avg_def(p_h) / (μ̄² * p̄ * avg_def(p̄))
    correction_away = μA² * p_a * avg_def(p_a) / (μ̄² * p̄ * avg_def(p̄))

This script:
  1. loads every completed v7 fixture with league_id + season + expected_goals + actuals,
  2. loads the per-(league, season) parameters from football_league_parameters_prod,
  3. applies the correction factor to each fixture's stored λ,
  4. rederives Negative-Binomial goal distributions and match probabilities,
  5. scores before / after against the actuals.

This tests ONLY the anchor fix. Confidence multiplier, venue adjustments,
stadium advantage, and the blended defensive factor are left unchanged.
"""
from __future__ import annotations

import argparse
import math
import statistics
from collections import defaultdict
from typing import Any, Iterator

import boto3

from src.statistics.distributions import calculate_goal_probabilities
from src.utils.constants import DEFAULT_ALPHA

FIXTURES_TABLE = "football_game_fixtures_prod"
LEAGUE_PARAMS_TABLE = "football_league_parameters_prod"
REGION = "eu-west-2"


def avg_def_of(p: float) -> float:
    """Expected defensive factor given a scoring probability p.
    Matches the blended formula in prediction_engine.py:263-266, averaged over
    an opponent whose clean-sheet rate is (1-p) and scoring rate is p."""
    cs = 1 - p
    original_factor = 1 - cs            # = p
    opp_aware_factor = 1 - cs * (1 - p)
    return 0.6 * original_factor + 0.4 * opp_aware_factor


def scan_all(region: str, table: str, **kwargs) -> Iterator[dict]:
    t = boto3.resource("dynamodb", region_name=region).Table(table)
    while True:
        resp = t.scan(**kwargs)
        for item in resp.get("Items", []):
            yield item
        if "LastEvaluatedKey" not in resp:
            return
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def load_league_params(region: str, table: str) -> dict:
    params: dict = {}
    for item in scan_all(
        region, table,
        ProjectionExpression=(
            "league_id, #s, mu_home, mu_away, p_score_home, p_score_away, home_adv"
        ),
        ExpressionAttributeNames={"#s": "season"},
    ):
        try:
            lid = int(item["league_id"])
            season = int(item["season"])
            params[(lid, season)] = {
                "mu_home": float(item["mu_home"]),
                "mu_away": float(item["mu_away"]),
                "p_score_home": float(item["p_score_home"]),
                "p_score_away": float(item["p_score_away"]),
                "home_adv": float(item.get("home_adv", 1.0)),
            }
        except (KeyError, TypeError, ValueError):
            continue
    return params


def load_v7_fixtures(region: str, table: str) -> list[dict]:
    fixtures: list[dict] = []
    for item in scan_all(
        region, table,
        FilterExpression=(
            "attribute_exists(goals) "
            "AND prediction_metadata.architecture_version = :v"
        ),
        ExpressionAttributeValues={":v": "7.0"},
        ProjectionExpression=(
            "fixture_id, league_id, #s, predictions, goals"
        ),
        ExpressionAttributeNames={"#s": "season"},
    ):
        try:
            eg = item["predictions"]["expected_goals"]
            mo = item["predictions"]["match_outcome"]
            over = item["predictions"].get("goals", {}).get("over", {})
            btts = item["predictions"].get("goals", {}).get("btts", {})
            fixtures.append({
                "fixture_id": int(item["fixture_id"]),
                "league_id": int(item["league_id"]),
                "season": int(item["season"]),
                "pred_home": float(eg["home"]),
                "pred_away": float(eg["away"]),
                "actual_home": int(item["goals"]["home"]),
                "actual_away": int(item["goals"]["away"]),
                "stored_p_home_win": float(mo["home_win"]) / 100,
                "stored_p_draw": float(mo["draw"]) / 100,
                "stored_p_away_win": float(mo["away_win"]) / 100,
                "stored_p_over_2_5": float(over.get("2.5", 0)) / 100 if over.get("2.5") else None,
                "stored_p_btts_yes": float(btts.get("yes", 0)) / 100 if btts.get("yes") else None,
            })
        except (KeyError, TypeError, ValueError):
            continue
    return fixtures


def correction_factors(p: dict) -> tuple[float, float]:
    mu_h, mu_a = p["mu_home"], p["mu_away"]
    p_h, p_a = p["p_score_home"], p["p_score_away"]
    mu_bar = 0.5 * (mu_h + mu_a)
    p_bar = 0.5 * (p_h + p_a)
    avg_raw_old_h = mu_h * mu_h * p_h * avg_def_of(p_h)
    avg_raw_old_a = mu_a * mu_a * p_a * avg_def_of(p_a)
    avg_raw_new = mu_bar * mu_bar * p_bar * avg_def_of(p_bar)
    if avg_raw_new <= 0:
        return 1.0, 1.0
    return avg_raw_old_h / avg_raw_new, avg_raw_old_a / avg_raw_new


def joint_probs(lam_h: float, lam_a: float, alpha: float = DEFAULT_ALPHA) -> dict:
    _, _, hp = calculate_goal_probabilities(lam_h, alpha)
    _, _, ap = calculate_goal_probabilities(lam_a, alpha)
    p_hw = p_d = p_aw = p_over_2_5 = p_btts = 0.0
    e_h = sum(k * v for k, v in hp.items())
    e_a = sum(k * v for k, v in ap.items())
    for h, ph in hp.items():
        for a, pa in ap.items():
            pj = ph * pa
            if h > a:
                p_hw += pj
            elif h == a:
                p_d += pj
            else:
                p_aw += pj
            if h + a > 2.5:
                p_over_2_5 += pj
            if h > 0 and a > 0:
                p_btts += pj
    return {
        "e_home": e_h, "e_away": e_a, "e_total": e_h + e_a,
        "p_home_win": p_hw, "p_draw": p_d, "p_away_win": p_aw,
        "p_over_2_5": p_over_2_5, "p_btts_yes": p_btts,
    }


def new_bucket() -> dict:
    return {
        "n": 0,
        "pred_total_sum": 0.0, "actual_total_sum": 0,
        "pred_home_sum": 0.0, "actual_home_sum": 0,
        "pred_away_sum": 0.0, "actual_away_sum": 0,
        "abs_err_total": [], "sq_err_total": [],
        "winner_hits": 0, "winner_n": 0,
        "brier_1x2": [], "brier_over_2_5": [], "brier_btts": [],
    }


def score_into(b: dict, lam_h: float, lam_a: float, actual_h: int, actual_a: int,
               probs: dict | None = None, alpha: float = DEFAULT_ALPHA) -> None:
    if probs is None:
        probs = joint_probs(lam_h, lam_a, alpha)
    at = actual_h + actual_a
    b["n"] += 1
    b["pred_total_sum"] += probs["e_total"]
    b["pred_home_sum"] += probs["e_home"]
    b["pred_away_sum"] += probs["e_away"]
    b["actual_total_sum"] += at
    b["actual_home_sum"] += actual_h
    b["actual_away_sum"] += actual_a
    b["abs_err_total"].append(abs(probs["e_total"] - at))
    b["sq_err_total"].append((probs["e_total"] - at) ** 2)

    if actual_h > actual_a:
        oh, od, oa = 1, 0, 0
        truth = "H"
    elif actual_h < actual_a:
        oh, od, oa = 0, 0, 1
        truth = "A"
    else:
        oh, od, oa = 0, 1, 0
        truth = "D"

    b["brier_1x2"].append(
        (probs["p_home_win"] - oh) ** 2
        + (probs["p_draw"] - od) ** 2
        + (probs["p_away_win"] - oa) ** 2
    )
    pick = max(
        {"H": probs["p_home_win"], "D": probs["p_draw"], "A": probs["p_away_win"]}.items(),
        key=lambda kv: kv[1],
    )[0]
    b["winner_n"] += 1
    if pick == truth:
        b["winner_hits"] += 1

    o_over = 1 if at > 2.5 else 0
    b["brier_over_2_5"].append((probs["p_over_2_5"] - o_over) ** 2)
    o_btts = 1 if actual_h > 0 and actual_a > 0 else 0
    b["brier_btts"].append((probs["p_btts_yes"] - o_btts) ** 2)


def summarize(b: dict) -> dict:
    n = b["n"] or 1
    return {
        "n": b["n"],
        "mean_pred_total": b["pred_total_sum"] / n,
        "mean_actual_total": b["actual_total_sum"] / n,
        "total_bias": b["pred_total_sum"] / n - b["actual_total_sum"] / n,
        "mean_pred_home": b["pred_home_sum"] / n,
        "mean_actual_home": b["actual_home_sum"] / n,
        "home_bias": b["pred_home_sum"] / n - b["actual_home_sum"] / n,
        "mean_pred_away": b["pred_away_sum"] / n,
        "mean_actual_away": b["actual_away_sum"] / n,
        "away_bias": b["pred_away_sum"] / n - b["actual_away_sum"] / n,
        "MAE_total": statistics.mean(b["abs_err_total"]),
        "RMSE_total": math.sqrt(statistics.mean(b["sq_err_total"])),
        "winner_accuracy": b["winner_hits"] / b["winner_n"] if b["winner_n"] else None,
        "Brier_1x2": statistics.mean(b["brier_1x2"]),
        "Brier_over_2_5": statistics.mean(b["brier_over_2_5"]),
        "Brier_btts": statistics.mean(b["brier_btts"]),
    }


def fmt(x: Any, w: int = 14) -> str:
    if x is None:
        return f"{'n/a':>{w}}"
    if isinstance(x, int):
        return f"{x:>{w},}"
    return f"{x:>{w}.4f}"


def print_scorecard(stored: dict, local_v7: dict, patched: dict) -> None:
    print()
    headers = ["stored v7", "local v7 repro", "patched (A)"]
    print(f"{'Metric':<22} {headers[0]:>14} {headers[1]:>14} {headers[2]:>14} {'Δ patched-local':>18}")
    print("-" * 92)
    for k in stored:
        a, b, c = stored.get(k), local_v7.get(k), patched.get(k)
        if k == "n" or not all(isinstance(x, (int, float)) for x in (a, b, c)):
            delta = None
        else:
            delta = c - b
        print(f"{k:<22} {fmt(a)} {fmt(b)} {fmt(c)} {fmt(delta, 18)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region", default=REGION)
    ap.add_argument("--fixtures-table", default=FIXTURES_TABLE)
    ap.add_argument("--params-table", default=LEAGUE_PARAMS_TABLE)
    ap.add_argument(
        "--per-league", action="store_true",
        help="Print per-league bias breakdown (patched − current)",
    )
    args = ap.parse_args()

    print(f"Loading league parameters from {args.params_table}...")
    params = load_league_params(args.region, args.params_table)
    print(f"  {len(params)} (league, season) records")

    print(f"Loading v7 completed fixtures from {args.fixtures_table}...")
    fixtures = load_v7_fixtures(args.region, args.fixtures_table)
    print(f"  {len(fixtures)} fixtures")

    stored_bucket = new_bucket()
    local_bucket = new_bucket()
    patched_bucket = new_bucket()

    per_league_local: dict = defaultdict(new_bucket)
    per_league_patched: dict = defaultdict(new_bucket)

    skipped_no_params = 0
    for fx in fixtures:
        key = (fx["league_id"], fx["season"])
        p = params.get(key)
        if p is None:
            skipped_no_params += 1
            continue

        # 1. "stored v7": score stored probabilities directly
        stored_probs = {
            "e_home": fx["pred_home"],
            "e_away": fx["pred_away"],
            "e_total": fx["pred_home"] + fx["pred_away"],
            "p_home_win": fx["stored_p_home_win"],
            "p_draw": fx["stored_p_draw"],
            "p_away_win": fx["stored_p_away_win"],
            "p_over_2_5": fx["stored_p_over_2_5"] if fx["stored_p_over_2_5"] is not None else 0.5,
            "p_btts_yes": fx["stored_p_btts_yes"] if fx["stored_p_btts_yes"] is not None else 0.5,
        }
        score_into(stored_bucket, fx["pred_home"], fx["pred_away"],
                   fx["actual_home"], fx["actual_away"], probs=stored_probs)

        # 2. "local v7 repro": use stored λ, run NB locally (sanity check)
        score_into(local_bucket, fx["pred_home"], fx["pred_away"],
                   fx["actual_home"], fx["actual_away"])
        score_into(per_league_local[fx["league_id"]],
                   fx["pred_home"], fx["pred_away"],
                   fx["actual_home"], fx["actual_away"])

        # 3. "patched (Option A)": apply anchor correction, re-derive
        corr_h, corr_a = correction_factors(p)
        lam_h = fx["pred_home"] * corr_h
        lam_a = fx["pred_away"] * corr_a
        score_into(patched_bucket, lam_h, lam_a,
                   fx["actual_home"], fx["actual_away"])
        score_into(per_league_patched[fx["league_id"]],
                   lam_h, lam_a, fx["actual_home"], fx["actual_away"])

    if skipped_no_params:
        print(f"  skipped {skipped_no_params} fixtures without league parameters")

    print_scorecard(
        summarize(stored_bucket),
        summarize(local_bucket),
        summarize(patched_bucket),
    )

    if args.per_league:
        print()
        print("Per-league home/total bias (patched vs local):")
        print(
            f"  {'league_id':<10} {'n':>6} "
            f"{'home bias loc':>14} {'home bias new':>14} "
            f"{'tot bias loc':>14} {'tot bias new':>14}"
        )
        league_rows = []
        for lid in per_league_local:
            l = summarize(per_league_local[lid])
            q = summarize(per_league_patched[lid])
            league_rows.append((
                lid, l["n"], l["home_bias"], q["home_bias"],
                l["total_bias"], q["total_bias"],
            ))
        league_rows.sort(key=lambda r: -r[1])
        for r in league_rows[:30]:
            print(
                f"  {r[0]:<10} {r[1]:>6,} "
                f"{r[2]:>14.4f} {r[3]:>14.4f} {r[4]:>14.4f} {r[5]:>14.4f}"
            )
        if len(league_rows) > 30:
            print(f"  ...({len(league_rows) - 30} more leagues not shown)")


if __name__ == "__main__":
    main()
