"""V2 xG-based prediction engine.

Clean-room reimplementation. Shares no math with V1's prediction_engine.
Produces the same 9-tuple output shape as V1's calculate_coordinated_predictions
so the orchestrator can call both engines and write to the same record.

Validated formula (from walk-forward tests in docs/v2/06-engine-core.md):
    lambda_H = mu_atk_H * mu_def_A / league_avg_xG  * home_adv (unless skipped)
    lambda_A = mu_atk_A * mu_def_H / league_avg_xG  * (1/home_adv if applied)

then Dixon-Coles-corrected Poisson joint distribution, marginalized to
home_probs / away_probs.

What V2 explicitly does NOT do:
    - Negative Binomial (Poisson alone is correct for goals given xG).
    - V1's empirical 1.35 calibration constant (that was fit against the
      goals-derived lambda pipeline).
    - Opponent stratification, manager/tactical/archetype multipliers,
      H2H adjusters, confidence overlays that rewrite lambdas.

Inputs & outputs: see calculate_coordinated_predictions_xg.
"""

from __future__ import annotations

import math
import time
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..statistics.distributions import squash_lambda
from ..utils.constants import (
    MAX_GOALS_ANALYSIS,
    XG_FORM_DECAY,
    XG_FORM_MULT_MIN,
    XG_FORM_MULT_MAX,
    XG_DEFAULT_RHO_DC,
)


# --------------------------------------------------------------------------
# Form multiplier
# --------------------------------------------------------------------------


def compute_form_multiplier(
    recent_xg_stream: Iterable[float],
    baseline_xg: float,
    decay: float = XG_FORM_DECAY,
    max_matches: int = 10,
) -> float:
    """Weight recent xG-for against a long-run baseline.

    Returns a multiplier near 1.0 (hot form > 1, cold form < 1), clamped
    to [XG_FORM_MULT_MIN, XG_FORM_MULT_MAX]. If the stream is empty or the
    baseline is zero, returns 1.0.

    `recent_xg_stream` must be ordered most-recent-first.
    """
    baseline = float(baseline_xg or 0.0)
    if baseline <= 0:
        return 1.0

    xs: List[float] = []
    for v in recent_xg_stream:
        if v is None:
            continue
        try:
            xs.append(float(v))
        except (TypeError, ValueError):
            continue
        if len(xs) >= max_matches:
            break
    if not xs:
        return 1.0

    weights = [decay ** i for i in range(len(xs))]
    weighted_avg = sum(x * w for x, w in zip(xs, weights)) / sum(weights)
    raw = weighted_avg / baseline
    return max(XG_FORM_MULT_MIN, min(XG_FORM_MULT_MAX, raw))


# --------------------------------------------------------------------------
# Dixon-Coles low-score correction
# --------------------------------------------------------------------------


def _poisson_pmf(k: int, lam: float) -> float:
    """Local Poisson PMF; keeps this engine dependency-free on the V1
    distributions module for everything except squash_lambda."""
    if lam < 0:
        return 0.0
    if lam == 0:
        return 1.0 if k == 0 else 0.0
    try:
        return (lam ** k) * math.exp(-lam) / math.factorial(k)
    except (OverflowError, ValueError):
        return 0.0


def _dc_tau(h: int, a: int, lh: float, la: float, rho: float) -> float:
    """Dixon-Coles low-score correction factor.

    Applied only to the four cells (0,0), (0,1), (1,0), (1,1); identity
    elsewhere. rho < 0 makes low scores slightly more likely than
    independent Poisson predicts; typical empirical values ~-0.18.
    """
    if h == 0 and a == 0:
        return 1.0 - lh * la * rho
    if h == 0 and a == 1:
        return 1.0 + lh * rho
    if h == 1 and a == 0:
        return 1.0 + la * rho
    if h == 1 and a == 1:
        return 1.0 - rho
    return 1.0


def dixon_coles_joint_probs(
    lambda_h: float,
    lambda_a: float,
    rho: float = XG_DEFAULT_RHO_DC,
    max_goals: int = MAX_GOALS_ANALYSIS,
) -> Dict[int, Dict[int, float]]:
    """Joint P(home=h, away=a) table under DC-corrected Poissons.

    The grid is truncated at max_goals, then renormalized so the visible
    cells sum to 1 exactly. tau can in principle push a cell negative for
    aggressive rho; we clamp at 0.
    """
    joint: Dict[int, Dict[int, float]] = {}
    for h in range(max_goals + 1):
        joint[h] = {}
        ph = _poisson_pmf(h, lambda_h)
        for a in range(max_goals + 1):
            pa = _poisson_pmf(a, lambda_a)
            tau = _dc_tau(h, a, lambda_h, lambda_a, rho)
            joint[h][a] = max(0.0, ph * pa * tau)

    total = sum(joint[h][a] for h in joint for a in joint[h])
    if total > 0:
        for h in joint:
            for a in joint[h]:
                joint[h][a] /= total
    return joint


def _marginals(
    joint: Dict[int, Dict[int, float]]
) -> Tuple[Dict[int, float], Dict[int, float]]:
    home_probs = {h: sum(joint[h].values()) for h in joint}
    keys = next(iter(joint.values())).keys()
    away_probs = {a: sum(joint[h][a] for h in joint) for a in keys}
    return home_probs, away_probs


# --------------------------------------------------------------------------
# Parameter coercion helpers
# --------------------------------------------------------------------------


def _as_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _pick(params: Dict[str, Any], keys: Iterable[str], default: float = 0.0) -> float:
    """First present key wins. Used to select between pooled / venue-specific
    mu fields in a caller-friendly way.
    """
    for k in keys:
        if k in params and params[k] is not None:
            v = _as_float(params[k])
            if v > 0:
                return v
    return default


# --------------------------------------------------------------------------
# Main entrypoint
# --------------------------------------------------------------------------


def calculate_coordinated_predictions_xg(
    home_team_xg_stats: Optional[Iterable[float]],
    away_team_xg_stats: Optional[Iterable[float]],
    home_params: Dict[str, Any],
    away_params: Dict[str, Any],
    league_params: Dict[str, Any],
    league_id: Optional[int] = None,
    season: Optional[int] = None,
    home_team_id: Optional[int] = None,
    away_team_id: Optional[int] = None,
    prediction_date: Any = None,
    skip_home_adv: bool = False,
    venue_mode: bool = False,
) -> Tuple[
    float, int, float, Dict[int, float],
    float, int, float, Dict[int, float],
    Dict[str, Any],
]:
    """Produce a V2 coordinated prediction.

    Args:
        home_team_xg_stats: recent xG_for stream (most-recent-first). Used
            for form decay. None → treat as empty (flat form multiplier).
        away_team_xg_stats: same for away team.
        home_params: per-team (or per-league fallback) xG params. Expected
            keys: mu_xg_for / mu_xg_against plus optional venue splits
            (mu_xg_for_home, mu_xg_against_home, mu_xg_for_away,
            mu_xg_against_away) and data_quality.
        away_params: same shape.
        league_params: per-league xG params. Required keys:
            league_avg_xg_for, home_adv, rho_dc. Optional venue splits.
        league_id, season, home_team_id, away_team_id, prediction_date:
            identifiers for logging and bookkeeping. Not used in math.
        skip_home_adv: if True, do NOT multiply by home_adv. Used for the
            V2c/V2d venue variants where the params already reflect
            venue-specific rates.
        venue_mode: if True, prefer the venue-specific mu fields
            (mu_xg_for_home, mu_xg_against_away, etc.) over the pooled ones.

    Returns:
        (home_score_prob, home_predicted_goals, home_likelihood, home_probs,
         away_score_prob, away_predicted_goals, away_likelihood, away_probs,
         coordination_info)
    """
    if not home_params or not away_params or not league_params:
        raise ValueError("home_params, away_params, and league_params are required")

    league_avg = _as_float(league_params.get("league_avg_xg_for"))
    if league_avg <= 0:
        raise ValueError(
            f"league_params.league_avg_xg_for must be > 0, got {league_avg}"
        )
    home_adv = _as_float(league_params.get("home_adv"), 1.0) or 1.0
    rho_dc = _as_float(league_params.get("rho_dc"), XG_DEFAULT_RHO_DC)

    # Pick the right mu fields depending on venue_mode.
    if venue_mode:
        mu_atk_H = _pick(home_params, ("mu_xg_for_home", "mu_xg_for"), league_avg)
        mu_def_H = _pick(home_params, ("mu_xg_against_home", "mu_xg_against"), league_avg)
        mu_atk_A = _pick(away_params, ("mu_xg_for_away", "mu_xg_for"), league_avg)
        mu_def_A = _pick(away_params, ("mu_xg_against_away", "mu_xg_against"), league_avg)
    else:
        mu_atk_H = _pick(home_params, ("mu_xg_for",), league_avg)
        mu_def_H = _pick(home_params, ("mu_xg_against",), league_avg)
        mu_atk_A = _pick(away_params, ("mu_xg_for",), league_avg)
        mu_def_A = _pick(away_params, ("mu_xg_against",), league_avg)

    # Core lambda: F3 pooled-ratio formula validated in phase-3 analysis.
    lambda_h = mu_atk_H * mu_def_A / league_avg
    lambda_a = mu_atk_A * mu_def_H / league_avg

    # Form decay on recent xG history.
    form_mult_H = compute_form_multiplier(home_team_xg_stats or (), mu_atk_H)
    form_mult_A = compute_form_multiplier(away_team_xg_stats or (), mu_atk_A)
    lambda_h *= form_mult_H
    lambda_a *= form_mult_A

    # Home advantage is chance-creation, not finishing. Apply as a sqrt
    # split so the ratio of home/away lambdas is preserved under the
    # square-root-of-home_adv convention used in modern xG models
    # (matches validated home_adv ≈ 1.23 -> home team creates ~11% more,
    # away team concedes ~11% less, product ≈ 1.23).
    if not skip_home_adv and home_adv > 0:
        sqrt_adv = math.sqrt(home_adv)
        lambda_h *= sqrt_adv
        lambda_a /= sqrt_adv

    # Squash extreme values (reuses V1 helper; purely defensive).
    lambda_h = float(squash_lambda(lambda_h))
    lambda_a = float(squash_lambda(lambda_a))

    # Joint probability matrix with Dixon-Coles low-score correction.
    joint = dixon_coles_joint_probs(lambda_h, lambda_a, rho=rho_dc)
    home_probs, away_probs = _marginals(joint)

    home_score_prob = 1.0 - home_probs.get(0, 0.0)
    away_score_prob = 1.0 - away_probs.get(0, 0.0)
    home_predicted_goals = max(home_probs, key=home_probs.get)
    away_predicted_goals = max(away_probs, key=away_probs.get)
    home_likelihood = home_probs[home_predicted_goals]
    away_likelihood = away_probs[away_predicted_goals]

    coordination_info: Dict[str, Any] = {
        "engine_version": "v2-xg-1.0",
        "lambda_H": round(lambda_h, 4),
        "lambda_A": round(lambda_a, 4),
        "mu_atk_H": round(mu_atk_H, 4),
        "mu_def_H": round(mu_def_H, 4),
        "mu_atk_A": round(mu_atk_A, 4),
        "mu_def_A": round(mu_def_A, 4),
        "league_avg_xg_for": round(league_avg, 4),
        "home_adv": round(home_adv, 4),
        "home_adv_applied": not skip_home_adv,
        "venue_mode": venue_mode,
        "form_multiplier_H": round(form_mult_H, 4),
        "form_multiplier_A": round(form_mult_A, 4),
        "rho_dc": round(rho_dc, 4),
        "data_quality_home": home_params.get("data_quality", "unknown"),
        "data_quality_away": away_params.get("data_quality", "unknown"),
        "league_id": league_id,
        "season": season,
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "prediction_timestamp": int(time.time()),
    }

    return (
        home_score_prob, home_predicted_goals, home_likelihood, home_probs,
        away_score_prob, away_predicted_goals, away_likelihood, away_probs,
        coordination_info,
    )


# --------------------------------------------------------------------------
# Summary dict (for fixture-level xg_predictions attribute)
# --------------------------------------------------------------------------


def create_xg_prediction_summary_dict(
    home_probs: Dict[int, float], away_probs: Dict[int, float]
) -> Dict[str, Any]:
    """Build the fixture-level xg_predictions summary used by downstream
    consumers (visualization, analytics, AI). Shape mirrors V1's
    create_prediction_summary_dict so consumers can reuse parsing.

    Includes market-level aggregates (BTTS, O/U, etc.) derived from the
    goal-probability distributions. Uses independence between the two
    marginals for these aggregates — the Dixon-Coles correction is already
    baked into the marginals via the upstream joint table.
    """
    def _dec_dict(probs: Dict[int, float]) -> Dict[str, Decimal]:
        return {str(k): Decimal(str(round(float(v), 6))) for k, v in probs.items()}

    def _side_side(probs: Dict[int, float]) -> Dict[str, Any]:
        prob_to_score = 1.0 - probs.get(0, 0.0)
        most_likely = max(probs, key=probs.get)
        likelihood = probs[most_likely]
        over15 = sum(v for k, v in probs.items() if k >= 2)
        over25 = sum(v for k, v in probs.items() if k >= 3)
        over35 = sum(v for k, v in probs.items() if k >= 4)
        return {
            "probability_to_score": Decimal(str(round(prob_to_score, 6))),
            "predicted_goals": int(most_likely),
            "likelihood": Decimal(str(round(likelihood, 6))),
            "goal_probabilities": _dec_dict(probs),
            "over_1_5": Decimal(str(round(over15, 6))),
            "over_2_5": Decimal(str(round(over25, 6))),
            "over_3_5": Decimal(str(round(over35, 6))),
            "under_2_5": Decimal(str(round(1.0 - over25, 6))),
        }

    # Market aggregates that combine both teams
    p_h_scores = 1.0 - home_probs.get(0, 0.0)
    p_a_scores = 1.0 - away_probs.get(0, 0.0)
    btts_yes = p_h_scores * p_a_scores

    # Total-goals distribution: convolve marginals (approximation — exact
    # total-goals probs should come from the joint table, but the marginals
    # already reflect DC correction so the convolution is close enough for
    # market aggregation).
    max_goals = max(home_probs) + max(away_probs)
    total_probs: Dict[int, float] = {t: 0.0 for t in range(max_goals + 1)}
    for h, ph in home_probs.items():
        for a, pa in away_probs.items():
            total_probs[h + a] += ph * pa

    total_over_15 = sum(v for k, v in total_probs.items() if k >= 2)
    total_over_25 = sum(v for k, v in total_probs.items() if k >= 3)
    total_over_35 = sum(v for k, v in total_probs.items() if k >= 4)

    return {
        "home": _side_side(home_probs),
        "away": _side_side(away_probs),
        "btts_yes": Decimal(str(round(btts_yes, 6))),
        "btts_no": Decimal(str(round(1.0 - btts_yes, 6))),
        "total_goals_over_1_5": Decimal(str(round(total_over_15, 6))),
        "total_goals_over_2_5": Decimal(str(round(total_over_25, 6))),
        "total_goals_over_3_5": Decimal(str(round(total_over_35, 6))),
        "total_goals_under_2_5": Decimal(str(round(1.0 - total_over_25, 6))),
    }
