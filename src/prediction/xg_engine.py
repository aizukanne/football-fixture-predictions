"""V2 xG-based prediction engine.

Mirrors V1's two-channel structure (priors + per-match observations),
substituting per-match xG arrays for V1's per-match goal arrays.

Inputs per team:
  - xg_for_array:     list of xG generated, one entry per past match
  - xg_against_array: list of xG conceded, one entry per past match

Plus shared inputs:
  - home_priors / away_priors:  smoothing priors for the four arrays
       (mu_xg_for, mu_xg_against — these come either from
       league_xg_params (Primary) or team_xg_params (Alternate))
  - league_params:  league_avg_xg_home, league_avg_xg_away, rho_dc

Pipeline:
  1. Bayesian-smooth each team's per-match arrays toward the priors.
     prior_weight controls how strongly the smoothing pulls toward
     the prior; observed_sum + n_observations pulls toward the data.
  2. Compose the multiplicative strength index for each side:
        raw_lambda_H = home_xg_for_smoothed × away_xg_against_smoothed
        raw_lambda_A = away_xg_for_smoothed × home_xg_against_smoothed
  3. Anchor each side to the league's home/away xG average. Home
     advantage is implicit in this anchoring (mu_xg_home > mu_xg_away
     globally), so we do NOT apply a separate home_adv multiplier
     unless the per-match arrays are venue-filtered (in which case
     the venue effect is already present in the data and we still
     anchor with mu_xg_home/away).
  4. Sample joint goal distribution under Dixon-Coles correction.
  5. Marginalize for per-team probabilities.

What V2 explicitly does NOT do (validated drops from analysis):
  - Negative Binomial: pure Poisson is sufficient given xG ≈ rate.
  - V1's empirical 1.35 calibration constant.
  - Opponent stratification, H2H, tactical/archetype multipliers.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..statistics.distributions import squash_lambda
from ..utils.constants import (
    MAX_GOALS_ANALYSIS,
    XG_DEFAULT_RHO_DC,
)


# Default Bayesian-smoothing prior weight (effective # of pseudo-matches).
# 5 keeps team data dominant once a team has played ≥10 matches, while
# stabilizing early-season fits. Mirrors the order-of-magnitude V1 uses
# for goal smoothing via prior_weight_from_k.
DEFAULT_PRIOR_WEIGHT = 5.0


# --------------------------------------------------------------------------
# Bayesian smoothing
# --------------------------------------------------------------------------


def _smooth(
    observations: Sequence[float],
    prior_mean: float,
    prior_weight: float = DEFAULT_PRIOR_WEIGHT,
) -> float:
    """Bayesian-smooth a list of observations toward a prior mean.

    Returns (prior_mean × prior_weight + sum(obs)) / (prior_weight + n_obs).
    With no observations, returns the prior mean.
    With many observations, approaches the observed mean.
    """
    obs = [float(v) for v in observations if v is not None]
    n = len(obs)
    if prior_weight <= 0 and n == 0:
        return float(prior_mean)
    return (float(prior_mean) * prior_weight + sum(obs)) / (prior_weight + n)


# --------------------------------------------------------------------------
# Dixon-Coles low-score correction
# --------------------------------------------------------------------------


def _poisson_pmf(k: int, lam: float) -> float:
    if lam < 0:
        return 0.0
    if lam == 0:
        return 1.0 if k == 0 else 0.0
    try:
        return (lam ** k) * math.exp(-lam) / math.factorial(k)
    except (OverflowError, ValueError):
        return 0.0


def _dc_tau(h: int, a: int, lh: float, la: float, rho: float) -> float:
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
    """Joint P(home=h, away=a) under DC-corrected Poissons. Renormalized
    after truncation at max_goals to ensure cells sum to 1."""
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
# Helpers
# --------------------------------------------------------------------------


def _as_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _resolve_prior(
    priors: Dict[str, Any], keys: Iterable[str], default: float,
) -> float:
    """First numeric value found among the given keys. Used to pick between
    pooled (mu_xg_for) and venue-specific (mu_xg_for_home / _away) priors."""
    for k in keys:
        if k in priors and priors[k] is not None:
            v = _as_float(priors[k])
            if v > 0:
                return v
    return default


# --------------------------------------------------------------------------
# Main entrypoint
# --------------------------------------------------------------------------


def calculate_coordinated_predictions_xg(
    home_xg_for_array: Sequence[float],
    home_xg_against_array: Sequence[float],
    away_xg_for_array: Sequence[float],
    away_xg_against_array: Sequence[float],
    home_priors: Dict[str, Any],
    away_priors: Dict[str, Any],
    league_params: Dict[str, Any],
    league_id: Optional[int] = None,
    season: Optional[int] = None,
    home_team_id: Optional[int] = None,
    away_team_id: Optional[int] = None,
    prediction_date: Any = None,
    venue_mode: bool = False,
    prior_weight: float = DEFAULT_PRIOR_WEIGHT,
) -> Tuple[
    float, int, float, Dict[int, float],
    float, int, float, Dict[int, float],
    Dict[str, Any],
]:
    """Produce a V2 coordinated prediction.

    Args:
        home_xg_for_array, home_xg_against_array,
        away_xg_for_array, away_xg_against_array:
            Per-match xG observation arrays. For pooled variants,
            include all matches the team played. For venue variants,
            include only home matches for the home team and only away
            matches for the away team — caller filters.
        home_priors, away_priors:
            Smoothing priors. For Primary variants pass the league xG
            params (or league_params_as_team_shape output); for
            Alternate variants pass the team's own fitted xg params.
            Required keys: mu_xg_for, mu_xg_against. Venue-specific
            keys (mu_xg_for_home, mu_xg_against_away, etc.) are used
            when venue_mode is True.
        league_params:
            Required keys: league_avg_xg_home, league_avg_xg_away, rho_dc.
        venue_mode:
            If True, prefer venue-specific prior fields and skip
            implicit home_adv (since per-match arrays are already
            venue-filtered).
        prior_weight:
            Effective pseudo-match count for the prior. Larger -> more
            shrinkage toward prior; smaller -> more weight on observations.

    Returns 9-tuple matching V1's calculate_coordinated_predictions:
        (home_score_prob, home_predicted_goals, home_likelihood, home_probs,
         away_score_prob, away_predicted_goals, away_likelihood, away_probs,
         coordination_info)
    """
    if not league_params:
        raise ValueError("league_params is required")

    league_avg_home = _as_float(league_params.get("league_avg_xg_home"))
    league_avg_away = _as_float(league_params.get("league_avg_xg_away"))
    if league_avg_home <= 0 or league_avg_away <= 0:
        raise ValueError(
            "league_params.league_avg_xg_home and league_avg_xg_away must be > 0"
        )
    rho_dc = _as_float(league_params.get("rho_dc"), XG_DEFAULT_RHO_DC)

    # Pick prior fields. In venue_mode, prefer venue-split priors so that
    # the league/team prior aligns with the venue context the team is in.
    if venue_mode:
        prior_h_for = _resolve_prior(
            home_priors, ("mu_xg_for_home", "mu_xg_for"), league_avg_home
        )
        prior_h_against = _resolve_prior(
            home_priors, ("mu_xg_against_home", "mu_xg_against"), league_avg_away
        )
        prior_a_for = _resolve_prior(
            away_priors, ("mu_xg_for_away", "mu_xg_for"), league_avg_away
        )
        prior_a_against = _resolve_prior(
            away_priors, ("mu_xg_against_away", "mu_xg_against"), league_avg_home
        )
    else:
        prior_h_for = _resolve_prior(home_priors, ("mu_xg_for",), league_avg_home)
        prior_h_against = _resolve_prior(
            home_priors, ("mu_xg_against",), league_avg_away
        )
        prior_a_for = _resolve_prior(away_priors, ("mu_xg_for",), league_avg_away)
        prior_a_against = _resolve_prior(
            away_priors, ("mu_xg_against",), league_avg_home
        )

    # Bayesian-smooth per-match observations against the priors.
    h_xg_for = _smooth(home_xg_for_array, prior_h_for, prior_weight)
    h_xg_against = _smooth(home_xg_against_array, prior_h_against, prior_weight)
    a_xg_for = _smooth(away_xg_for_array, prior_a_for, prior_weight)
    a_xg_against = _smooth(away_xg_against_array, prior_a_against, prior_weight)

    # Multiplicative strength index.
    raw_lambda_H = h_xg_for * a_xg_against
    raw_lambda_A = a_xg_for * h_xg_against

    # League anchor. The expected raw_lambda for an "average" matchup is
    # league_avg_home × league_avg_away (the home side's typical xG_for
    # times the away side's typical xG_against, since at home a team
    # typically generates league_avg_home and the away team typically
    # concedes league_avg_home — these are the same number in expectation).
    avg_raw_lambda = league_avg_home * league_avg_away
    if avg_raw_lambda <= 0:
        raise ValueError("avg_raw_lambda <= 0; check league_params")

    # Anchor each side to the league mean for its venue. Home advantage
    # is encoded by anchoring home to mu_xg_home and away to mu_xg_away
    # (which is lower) — no separate sqrt(home_adv) multiplier needed.
    lambda_H = league_avg_home * (raw_lambda_H / avg_raw_lambda)
    lambda_A = league_avg_away * (raw_lambda_A / avg_raw_lambda)

    # Bound extremes.
    lambda_H = float(squash_lambda(lambda_H))
    lambda_A = float(squash_lambda(lambda_A))

    # Joint distribution under Dixon-Coles, then marginalize.
    joint = dixon_coles_joint_probs(lambda_H, lambda_A, rho=rho_dc)
    home_probs, away_probs = _marginals(joint)

    home_score_prob = 1.0 - home_probs.get(0, 0.0)
    away_score_prob = 1.0 - away_probs.get(0, 0.0)
    home_predicted_goals = max(home_probs, key=home_probs.get)
    away_predicted_goals = max(away_probs, key=away_probs.get)
    home_likelihood = home_probs[home_predicted_goals]
    away_likelihood = away_probs[away_predicted_goals]

    coordination_info: Dict[str, Any] = {
        "engine_version": "v2-xg-2.0",
        "lambda_H": round(lambda_H, 4),
        "lambda_A": round(lambda_A, 4),
        "n_obs_home_for": len(home_xg_for_array or ()),
        "n_obs_home_against": len(home_xg_against_array or ()),
        "n_obs_away_for": len(away_xg_for_array or ()),
        "n_obs_away_against": len(away_xg_against_array or ()),
        "prior_weight": prior_weight,
        "smoothed_h_xg_for": round(h_xg_for, 4),
        "smoothed_h_xg_against": round(h_xg_against, 4),
        "smoothed_a_xg_for": round(a_xg_for, 4),
        "smoothed_a_xg_against": round(a_xg_against, 4),
        "league_avg_xg_home": round(league_avg_home, 4),
        "league_avg_xg_away": round(league_avg_away, 4),
        "rho_dc": round(rho_dc, 4),
        "venue_mode": venue_mode,
        "data_quality_home": home_priors.get("data_quality", "unknown"),
        "data_quality_away": away_priors.get("data_quality", "unknown"),
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
# Summary dict
# --------------------------------------------------------------------------
#
# V2 reuses V1's create_prediction_summary_dict (in
# src/prediction/prediction_engine.py) for the fixture-level
# xg_predictions / xg_alternate_predictions / xg_venue_predictions /
# xg_venue_alternate_predictions attributes. V1's function takes goal-prob
# dicts and returns the canonical {most_likely_score, expected_goals,
# match_outcome, goals, top_scores, odds} structure. Reusing it
# guarantees identical schema between V1 and V2 outputs.
