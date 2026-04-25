"""V3 SoT-based prediction engine.

The whole system in one formula:

    λ_H = SoT_H_home × conv × (gc_A_away / lg_avg_gc_away)
    λ_A = SoT_A_away × conv × (gc_H_home / lg_avg_gc_home)

where:
    SoT_H_home   = home team's average shots-on-target when playing at home
                   (Bayesian-shrunk toward the league-mean home SoT)
    SoT_A_away   = away team's average shots-on-target when playing away
    conv         = league's pooled SoT->goal conversion rate
                   (Σ goals scored in the league / Σ shots-on-target)
    gc_A_away    = away team's average goals conceded when playing away
                   (i.e. the strength of A's defence in away venues)
    lg_avg_gc_away = league average goals conceded by visiting teams
    gc_H_home    = home team's average goals conceded when playing at home
    lg_avg_gc_home = league average goals conceded by home teams

The defensive ratio (`gc_X / lg_avg_gc`) is opponent-relative defence: 1.0
means league-average, >1 means leakier than average, <1 means stingier.

Per-team marginal goal distributions are Negative Binomial(α=0.3) under
independence — no joint distribution, no Dixon-Coles correction. This
mirrors the legacy 2025-03-21 engine that the user wants V3 to behave
like, minus the hand-tuned league multipliers and the post-hoc ×1.02 /
×1.35 calibration constants. predicted_goals = round(λ), not the marginal
mode (which collapses every fixture in [1,2] to "1").

What V3 explicitly does NOT do:
  - Dixon-Coles low-score correction (legacy didn't either).
  - Joint distribution (treats home & away as independent for derived
    markets like 1X2 and BTTS — same convention V1 ultimately uses too).
  - Per-league multipliers, country-specific boosts, or any hand-tuned
    constants. The only constants are NB α (0.3) and the cold-start
    shrinkage k (5), both global and well-justified.
  - Form decay / time weighting. Aggregate season-to-date averages.
"""

from __future__ import annotations

import math
import time
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from ..statistics.distributions import nb_pmf, squash_lambda
from ..utils.constants import (
    MAX_GOALS_ANALYSIS,
    SOT_NB_ALPHA,
    SOT_TO_GOAL_FALLBACK,
)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def _as_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_ratio(num: float, denom: float, default: float = 1.0) -> float:
    """num/denom with a guard against division-by-zero. Used for the
    opponent defensive ratio — when league averages are zero (brand-new
    league), default to 1.0 (i.e. no defensive adjustment)."""
    if denom is None or denom <= 0:
        return default
    return num / denom


# --------------------------------------------------------------------------
# Lambda calculation
# --------------------------------------------------------------------------


def _resolve_team_sot(team_params: Dict[str, Any], is_home: bool) -> float:
    """Return the team's venue-appropriate SoT_for, falling back to the
    pooled value if the venue-split field is missing."""
    key = "sot_for_home" if is_home else "sot_for_away"
    v = _as_float(team_params.get(key))
    if v > 0:
        return v
    return _as_float(team_params.get("sot_for_all"))


def _resolve_team_gc(team_params: Dict[str, Any], is_home: bool) -> float:
    """Return the team's venue-appropriate goals_conceded, falling back to
    the pooled value if the venue-split field is missing."""
    key = "goals_conceded_home" if is_home else "goals_conceded_away"
    v = _as_float(team_params.get(key))
    if v > 0:
        return v
    return _as_float(team_params.get("goals_conceded_all"))


def calculate_lambdas(
    home_team_params: Dict[str, Any],
    away_team_params: Dict[str, Any],
    league_params: Dict[str, Any],
) -> Tuple[float, float, Dict[str, float]]:
    """Compute (λ_H, λ_A, debug_info) under the V3 formula.

    home_team_params / away_team_params: outputs of fit_team_sot_params
    (or league_params_as_team_fallback for cold-start). Required keys:
        sot_for_home, sot_for_away (venue-split)
        goals_conceded_home, goals_conceded_away (venue-split)
        sot_for_all, goals_conceded_all (pooled, used as fallback)

    league_params: output of fit_league_sot_params. Required keys:
        sot_to_goal_conv_rate
        league_avg_goals_conceded_home, league_avg_goals_conceded_away

    Returns the two lambdas plus a small debug dict of the intermediate
    multipliers — useful for explaining a prediction back to the user.
    """
    conv = _as_float(
        league_params.get("sot_to_goal_conv_rate"),
        default=SOT_TO_GOAL_FALLBACK,
    )
    if conv <= 0:
        conv = SOT_TO_GOAL_FALLBACK

    lg_gc_home = _as_float(league_params.get("league_avg_goals_conceded_home"))
    lg_gc_away = _as_float(league_params.get("league_avg_goals_conceded_away"))

    # Home team is playing at home, so its SoT_for is "home" and its
    # opponent (away team) is playing away, so we use opponent's away GC.
    sot_h = _resolve_team_sot(home_team_params, is_home=True)
    sot_a = _resolve_team_sot(away_team_params, is_home=False)
    gc_h_home = _resolve_team_gc(home_team_params, is_home=True)
    gc_a_away = _resolve_team_gc(away_team_params, is_home=False)

    # Defensive ratio: opponent's GC at their venue / league's average GC
    # at that venue. >1 ⇒ opponent's defence is leakier than league avg ⇒
    # we score more.
    def_ratio_for_h = _safe_ratio(gc_a_away, lg_gc_away)
    def_ratio_for_a = _safe_ratio(gc_h_home, lg_gc_home)

    lambda_h = sot_h * conv * def_ratio_for_h
    lambda_a = sot_a * conv * def_ratio_for_a

    lambda_h = float(squash_lambda(lambda_h))
    lambda_a = float(squash_lambda(lambda_a))

    debug = {
        "sot_h_home": round(sot_h, 4),
        "sot_a_away": round(sot_a, 4),
        "conv_rate": round(conv, 5),
        "gc_h_home": round(gc_h_home, 4),
        "gc_a_away": round(gc_a_away, 4),
        "lg_gc_home": round(lg_gc_home, 4),
        "lg_gc_away": round(lg_gc_away, 4),
        "def_ratio_for_h": round(def_ratio_for_h, 4),
        "def_ratio_for_a": round(def_ratio_for_a, 4),
        "lambda_h": round(lambda_h, 4),
        "lambda_a": round(lambda_a, 4),
    }
    return lambda_h, lambda_a, debug


# --------------------------------------------------------------------------
# Goal-probability distribution
# --------------------------------------------------------------------------


def _nb_marginal(lam: float, alpha: float = SOT_NB_ALPHA,
                 max_goals: int = MAX_GOALS_ANALYSIS) -> Dict[int, float]:
    """Negative Binomial PMF over [0, max_goals], normalized to sum to 1.

    No ×1.35 / ×1.02 calibration — V3 uses raw λ. The legacy ×1.02 was a
    fudge factor; V1's ×1.35 was added later to compensate for over-
    deflated lambdas in the V1 multiplier stack. V3's λ comes out at the
    right scale by construction (SoT × conv ≈ goals), so we trust it.
    """
    probs = {k: float(nb_pmf(k, lam, alpha)) for k in range(max_goals + 1)}
    total = sum(probs.values())
    if total > 0:
        for k in probs:
            probs[k] /= total
    return probs


# --------------------------------------------------------------------------
# Main entrypoint
# --------------------------------------------------------------------------


def calculate_predictions_sot(
    home_team_params: Dict[str, Any],
    away_team_params: Dict[str, Any],
    league_params: Dict[str, Any],
    league_id: Optional[int] = None,
    season: Optional[int] = None,
    home_team_id: Optional[int] = None,
    away_team_id: Optional[int] = None,
    prediction_date: Any = None,
) -> Tuple[
    float, int, float, Dict[int, float],
    float, int, float, Dict[int, float],
    Dict[str, Any],
]:
    """Produce a V3 prediction.

    Returns the same 9-tuple shape as V1's calculate_coordinated_predictions
    so the integration in prediction_handler can mirror V1 exactly:
        (home_score_prob, home_predicted_goals, home_likelihood, home_probs,
         away_score_prob, away_predicted_goals, away_likelihood, away_probs,
         info)
    """
    if not league_params:
        raise ValueError("league_params is required for V3 SoT engine")

    lambda_h, lambda_a, debug = calculate_lambdas(
        home_team_params, away_team_params, league_params,
    )

    home_probs = _nb_marginal(lambda_h)
    away_probs = _nb_marginal(lambda_a)

    home_score_prob = 1.0 - home_probs.get(0, 0.0)
    away_score_prob = 1.0 - away_probs.get(0, 0.0)

    # round(λ), not argmax — same reasoning as V2: marginal mode of any
    # 1 ≤ λ < 2 is 1, which collapses every typical fixture to "1".
    home_predicted_goals = max(0, min(MAX_GOALS_ANALYSIS, int(round(lambda_h))))
    away_predicted_goals = max(0, min(MAX_GOALS_ANALYSIS, int(round(lambda_a))))
    home_likelihood = home_probs.get(home_predicted_goals, 0.0)
    away_likelihood = away_probs.get(away_predicted_goals, 0.0)

    info: Dict[str, Any] = {
        "engine_version": "v3-sot-1.0",
        "lambda_h": debug["lambda_h"],
        "lambda_a": debug["lambda_a"],
        "conv_rate": debug["conv_rate"],
        "sot_h_home": debug["sot_h_home"],
        "sot_a_away": debug["sot_a_away"],
        "gc_h_home": debug["gc_h_home"],
        "gc_a_away": debug["gc_a_away"],
        "def_ratio_for_h": debug["def_ratio_for_h"],
        "def_ratio_for_a": debug["def_ratio_for_a"],
        "alpha": SOT_NB_ALPHA,
        "data_quality_home": home_team_params.get("data_quality", "unknown"),
        "data_quality_away": away_team_params.get("data_quality", "unknown"),
        "n_matches_home": int(home_team_params.get("n_matches_home") or 0),
        "n_matches_away": int(away_team_params.get("n_matches_away") or 0),
        "league_id": league_id,
        "season": season,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "prediction_timestamp": int(time.time()),
    }

    return (
        home_score_prob, home_predicted_goals, home_likelihood, home_probs,
        away_score_prob, away_predicted_goals, away_likelihood, away_probs,
        info,
    )


# --------------------------------------------------------------------------
# Summary dict (V3 wrapper around V1's create_prediction_summary_dict)
# --------------------------------------------------------------------------


def create_sot_prediction_summary_dict(
    home_probs: Dict[int, float],
    away_probs: Dict[int, float],
    home_predicted_goals: int,
    away_predicted_goals: int,
) -> Dict[str, Any]:
    """V3's fixture-level summary dict.

    Same schema as V1's create_prediction_summary_dict (so downstream
    consumers parse both engines identically), with most_likely_score
    overridden to match V3's predicted_goals = round(λ) convention.

    Why the override:
        V1's create_prediction_summary_dict computes most_likely_score
        as argmax over a re-derived joint Poisson table. For typical V3
        lambdas in [1.0, 1.7] both marginal modes are 1, which collapses
        the joint mode to "1-1" even when the underlying lambdas (e.g.
        1.22 / 1.86) imply "1-2". round(λ) preserves that distinction,
        so the summary dict aligns with the per-team marginal-mode fields.
    """
    # Lazy import — avoid circular dependency at module load time.
    from .prediction_engine import create_prediction_summary_dict

    summary = create_prediction_summary_dict(home_probs, away_probs)

    h = int(home_predicted_goals)
    a = int(away_predicted_goals)
    score_str = f"{h}-{a}"

    p_h = float(home_probs.get(h, 0.0))
    p_a = float(away_probs.get(a, 0.0))
    p_round = round(p_h * p_a * 100, 1)

    summary["most_likely_score"] = {
        "score": score_str,
        "probability": p_round,
    }

    # Surface the same scoreline at the top of top_scores. If already in
    # the list, move it up; otherwise prepend. Cap at 5 so downstream UIs
    # that depend on that count don't break.
    top = list(summary.get("top_scores") or [])
    top = [s for s in top if isinstance(s, dict) and s.get("score") != score_str]
    top.insert(0, {"score": score_str, "probability": p_round})
    summary["top_scores"] = top[:5]

    return summary
