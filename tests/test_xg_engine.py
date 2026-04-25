"""Unit tests for src/prediction/xg_engine.

Pure-math tests on synthetic per-match xG arrays. No DynamoDB, no API.
"""

from __future__ import annotations

import math
import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.prediction.xg_engine import (
    calculate_coordinated_predictions_xg,
    create_xg_prediction_summary_dict,
    dixon_coles_joint_probs,
    _dc_tau,
    _poisson_pmf,
    _marginals,
    _smooth,
)
from src.prediction.prediction_engine import create_prediction_summary_dict


# --------------------------------------------------------------------------
# Building blocks
# --------------------------------------------------------------------------


class TestPoissonPmf(unittest.TestCase):

    def test_zero_lambda(self):
        self.assertEqual(_poisson_pmf(0, 0.0), 1.0)
        self.assertEqual(_poisson_pmf(1, 0.0), 0.0)

    def test_pmf_sum_to_one(self):
        total = sum(_poisson_pmf(k, 1.5) for k in range(20))
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_mean_matches_lambda(self):
        lam = 2.3
        mean = sum(k * _poisson_pmf(k, lam) for k in range(30))
        self.assertAlmostEqual(mean, lam, places=3)


class TestSmooth(unittest.TestCase):

    def test_no_observations_returns_prior(self):
        self.assertEqual(_smooth([], 1.4, prior_weight=5), 1.4)

    def test_equal_weight_blend_proportional(self):
        # decay=1.0 disables form decay; tests the basic Bayesian blend.
        # 5 observations averaging 2.0 with prior 1.0 weight 5:
        #   (1.0*5 + 2.0*5) / (5+5) = 1.5
        result = _smooth([2.0]*5, prior_mean=1.0, prior_weight=5, decay=1.0)
        self.assertAlmostEqual(result, 1.5, places=4)

    def test_equal_weight_many_observations_approach_mean(self):
        obs = [2.0] * 100
        result = _smooth(obs, prior_mean=1.0, prior_weight=5, decay=1.0)
        # Weight on prior is 5/(5+100) ≈ 0.048; observed dominates
        self.assertGreater(result, 1.9)
        self.assertLess(result, 2.0)

    def test_zero_prior_weight_returns_observed_mean_no_decay(self):
        result = _smooth(
            [1.0, 2.0, 3.0], prior_mean=99.0, prior_weight=0, decay=1.0,
        )
        self.assertAlmostEqual(result, 2.0, places=4)

    def test_form_decay_upweights_recent(self):
        # Observations are most-recent-first. Hot recent form (2.5) with
        # cold older form (0.5) should yield a smoothed value above the
        # plain mean of 1.5.
        result_decay = _smooth(
            [2.5, 2.5, 2.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            prior_mean=1.5, prior_weight=0, decay=0.9,
        )
        result_equal = _smooth(
            [2.5, 2.5, 2.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            prior_mean=1.5, prior_weight=0, decay=1.0,
        )
        self.assertAlmostEqual(result_equal, 1.25, places=4)
        self.assertGreater(result_decay, result_equal)
        self.assertGreater(result_decay, 1.4)

    def test_form_decay_effective_n_caps(self):
        # With decay=0.9, ∑decay^i for n=∞ = 1/(1-0.9) = 10.
        # 100 identical observations should still leave the prior with
        # weight ~5/(5+10) ≈ 33% (vs ~5% under equal weighting).
        result = _smooth(
            [2.0] * 100, prior_mean=1.0, prior_weight=5, decay=0.9,
        )
        # Expected: (1.0*5 + 2.0*10) / (5+10) ≈ 1.667
        self.assertAlmostEqual(result, 1.667, places=2)

    def test_form_decay_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            _smooth([1.0], prior_mean=1.0, decay=0.0)
        with self.assertRaises(ValueError):
            _smooth([1.0], prior_mean=1.0, decay=1.5)


class TestDcTau(unittest.TestCase):

    def test_identity_outside_corner(self):
        self.assertEqual(_dc_tau(2, 3, 1.5, 1.2, -0.18), 1.0)
        self.assertEqual(_dc_tau(0, 2, 1.5, 1.2, -0.18), 1.0)

    def test_zero_zero_boost_for_negative_rho(self):
        tau = _dc_tau(0, 0, 1.5, 1.2, -0.18)
        self.assertGreater(tau, 1.0)

    def test_rho_zero_identity(self):
        for h in range(3):
            for a in range(3):
                self.assertEqual(_dc_tau(h, a, 1.5, 1.2, 0.0), 1.0)


class TestDixonColesJoint(unittest.TestCase):

    def test_sum_to_one(self):
        joint = dixon_coles_joint_probs(1.4, 1.1, rho=-0.18)
        total = sum(joint[h][a] for h in joint for a in joint[h])
        self.assertAlmostEqual(total, 1.0, places=9)

    def test_marginals_valid(self):
        joint = dixon_coles_joint_probs(1.4, 1.1, rho=-0.18)
        h, a = _marginals(joint)
        self.assertAlmostEqual(sum(h.values()), 1.0, places=6)
        self.assertAlmostEqual(sum(a.values()), 1.0, places=6)
        for v in (*h.values(), *a.values()):
            self.assertGreaterEqual(v, 0)


# --------------------------------------------------------------------------
# End-to-end engine
# --------------------------------------------------------------------------


class TestCalculateCoordinated(unittest.TestCase):

    def _league(self):
        return {
            "league_avg_xg_home": Decimal("1.55"),
            "league_avg_xg_away": Decimal("1.25"),
            "rho_dc": Decimal("-0.18"),
        }

    def _strong_priors(self):
        return {"mu_xg_for": Decimal("1.8"), "mu_xg_against": Decimal("1.0"),
                "data_quality": "full"}

    def _weak_priors(self):
        return {"mu_xg_for": Decimal("1.0"), "mu_xg_against": Decimal("1.8"),
                "data_quality": "full"}

    def test_returns_9_tuple(self):
        result = calculate_coordinated_predictions_xg(
            home_xg_for_array=[1.7]*10,
            home_xg_against_array=[0.9]*10,
            away_xg_for_array=[1.0]*10,
            away_xg_against_array=[1.7]*10,
            home_priors=self._strong_priors(),
            away_priors=self._weak_priors(),
            league_params=self._league(),
        )
        self.assertEqual(len(result), 9)
        h_sp, h_pg, h_lh, h_probs, a_sp, a_pg, a_lh, a_probs, info = result
        # Probabilities valid
        self.assertAlmostEqual(sum(h_probs.values()), 1.0, places=6)
        self.assertAlmostEqual(sum(a_probs.values()), 1.0, places=6)
        for v in (h_sp, a_sp, h_lh, a_lh):
            self.assertGreaterEqual(v, 0); self.assertLessEqual(v, 1)
        # Strong vs weak: home should have higher score probability
        self.assertGreater(h_sp, a_sp)
        # coordination_info present
        self.assertEqual(info["engine_version"], "v2-xg-2.2")
        self.assertIn("lambda_H", info)
        # predicted_goals = round(λ), not argmax of marginal PMF
        self.assertEqual(h_pg, max(0, round(info["lambda_H"])))
        self.assertEqual(a_pg, max(0, round(info["lambda_A"])))

    def test_predicted_goals_is_round_of_lambda(self):
        """round(λ) preserves the difference between weak and strong attacks
        that the marginal mode would collapse to '1' for any λ in [1, 2)."""
        league = self._league()
        priors = {"mu_xg_for": Decimal("1.4"), "mu_xg_against": Decimal("1.4"),
                  "data_quality": "full"}

        # Strong home team (xG_for ≈ 2.4 in observations) → λ_H likely ≥ 1.5
        result = calculate_coordinated_predictions_xg(
            home_xg_for_array=[2.4]*15, home_xg_against_array=[0.6]*15,
            away_xg_for_array=[0.7]*15, away_xg_against_array=[2.3]*15,
            home_priors=priors, away_priors=priors, league_params=league,
        )
        info = result[8]
        h_pg = result[1]
        a_pg = result[5]
        self.assertGreater(info["lambda_H"], 1.5)
        # round(λ_H) for λ_H > 1.5 → at least 2
        self.assertGreaterEqual(h_pg, 2)
        # round(λ_A) for typical low away λ → 0 or 1
        self.assertLessEqual(a_pg, 1)

    def test_per_match_observations_drive_prediction(self):
        """The same priors but different observation arrays should yield
        meaningfully different lambdas. This is the property V1 has and
        v2-xg-1.0 lacked."""
        league = self._league()
        # Same neutral priors for both fixtures
        priors = {"mu_xg_for": Decimal("1.4"), "mu_xg_against": Decimal("1.4"),
                  "data_quality": "full"}

        # Fixture A: home dominant in observations
        result_a = calculate_coordinated_predictions_xg(
            home_xg_for_array=[2.5]*15,    # team_H generates a lot
            home_xg_against_array=[0.5]*15, # concedes little
            away_xg_for_array=[0.7]*15,
            away_xg_against_array=[2.3]*15,
            home_priors=priors, away_priors=priors,
            league_params=league,
        )
        # Fixture B: away dominant in observations
        result_b = calculate_coordinated_predictions_xg(
            home_xg_for_array=[0.7]*15,
            home_xg_against_array=[2.3]*15,
            away_xg_for_array=[2.5]*15,
            away_xg_against_array=[0.5]*15,
            home_priors=priors, away_priors=priors,
            league_params=league,
        )
        # Lambdas should differ in opposite directions
        info_a = result_a[8]
        info_b = result_b[8]
        self.assertGreater(info_a["lambda_H"], info_b["lambda_H"])
        self.assertLess(info_a["lambda_A"], info_b["lambda_A"])

    def test_empty_arrays_fall_back_to_priors(self):
        """If a team has no observations, the smoothed mean equals the prior."""
        league = self._league()
        result = calculate_coordinated_predictions_xg(
            home_xg_for_array=[],
            home_xg_against_array=[],
            away_xg_for_array=[],
            away_xg_against_array=[],
            home_priors=self._strong_priors(),
            away_priors=self._weak_priors(),
            league_params=league,
        )
        info = result[8]
        # Smoothed values equal the priors when there are 0 observations
        self.assertAlmostEqual(info["smoothed_h_xg_for"], 1.8, places=4)
        self.assertAlmostEqual(info["smoothed_h_xg_against"], 1.0, places=4)
        self.assertAlmostEqual(info["smoothed_a_xg_for"], 1.0, places=4)
        self.assertAlmostEqual(info["smoothed_a_xg_against"], 1.8, places=4)

    def test_venue_mode_picks_venue_priors(self):
        league = self._league()
        priors = {
            "mu_xg_for": Decimal("1.4"),
            "mu_xg_against": Decimal("1.4"),
            "mu_xg_for_home": Decimal("2.0"),    # would be picked in venue_mode
            "mu_xg_for_away": Decimal("0.9"),
            "mu_xg_against_home": Decimal("0.8"),
            "mu_xg_against_away": Decimal("1.7"),
            "data_quality": "full",
        }
        # No observations — smoothed values fall back to whichever prior
        # the engine selected.
        result_pooled = calculate_coordinated_predictions_xg(
            home_xg_for_array=[], home_xg_against_array=[],
            away_xg_for_array=[], away_xg_against_array=[],
            home_priors=priors, away_priors=priors,
            league_params=league, venue_mode=False,
        )
        result_venue = calculate_coordinated_predictions_xg(
            home_xg_for_array=[], home_xg_against_array=[],
            away_xg_for_array=[], away_xg_against_array=[],
            home_priors=priors, away_priors=priors,
            league_params=league, venue_mode=True,
        )
        self.assertAlmostEqual(result_pooled[8]["smoothed_h_xg_for"], 1.4, places=4)
        self.assertAlmostEqual(result_venue[8]["smoothed_h_xg_for"],  2.0, places=4)
        self.assertAlmostEqual(result_pooled[8]["smoothed_a_xg_for"], 1.4, places=4)
        self.assertAlmostEqual(result_venue[8]["smoothed_a_xg_for"],  0.9, places=4)

    def test_missing_league_params_raises(self):
        with self.assertRaises(ValueError):
            calculate_coordinated_predictions_xg(
                home_xg_for_array=[], home_xg_against_array=[],
                away_xg_for_array=[], away_xg_against_array=[],
                home_priors=self._strong_priors(),
                away_priors=self._weak_priors(),
                league_params=None,
            )

    def test_zero_league_avg_raises(self):
        bad_league = {
            "league_avg_xg_home": Decimal("0"),
            "league_avg_xg_away": Decimal("1.25"),
            "rho_dc": Decimal("-0.18"),
        }
        with self.assertRaises(ValueError):
            calculate_coordinated_predictions_xg(
                home_xg_for_array=[1.5]*5, home_xg_against_array=[1.0]*5,
                away_xg_for_array=[1.0]*5, away_xg_against_array=[1.5]*5,
                home_priors=self._strong_priors(),
                away_priors=self._weak_priors(),
                league_params=bad_league,
            )


class TestXgSummaryDict(unittest.TestCase):
    """V2's wrapper around V1's summary dict. Same schema, but
    most_likely_score reflects round(λ) so summary view and per-team
    xg_predicted_goals attribute always agree."""

    def test_most_likely_score_uses_predicted_goals(self):
        # Marginal modes for these probs: home=1, away=1 → joint mode 1-1
        # But suppose round(λ) gave 1-2: the summary should reflect that.
        home_probs = {0: 0.20, 1: 0.34, 2: 0.27, 3: 0.13, 4: 0.05, 5: 0.01}
        away_probs = {0: 0.15, 1: 0.30, 2: 0.30, 3: 0.16, 4: 0.07, 5: 0.02}
        s = create_xg_prediction_summary_dict(
            home_probs, away_probs,
            home_predicted_goals=1, away_predicted_goals=2,
        )
        self.assertEqual(s["most_likely_score"]["score"], "1-2")
        # Probability under independence: 0.34 × 0.30 = 0.102 → 10.2%
        self.assertAlmostEqual(s["most_likely_score"]["probability"], 10.2, places=1)

    def test_most_likely_score_appears_at_top_of_top_scores(self):
        home_probs = {0: 0.25, 1: 0.33, 2: 0.24, 3: 0.12, 4: 0.04}
        away_probs = {0: 0.30, 1: 0.32, 2: 0.22, 3: 0.11, 4: 0.04}
        s = create_xg_prediction_summary_dict(
            home_probs, away_probs,
            home_predicted_goals=2, away_predicted_goals=1,
        )
        self.assertEqual(s["top_scores"][0]["score"], "2-1")
        self.assertLessEqual(len(s["top_scores"]), 5)
        # No duplicate for the surfaced score
        scores = [t["score"] for t in s["top_scores"]]
        self.assertEqual(len(scores), len(set(scores)))

    def test_v1_schema_keys_preserved(self):
        home_probs = {0: 0.2, 1: 0.3, 2: 0.25, 3: 0.15, 4: 0.07, 5: 0.03}
        away_probs = {0: 0.3, 1: 0.3, 2: 0.2, 3: 0.12, 4: 0.05, 5: 0.03}
        s = create_xg_prediction_summary_dict(
            home_probs, away_probs,
            home_predicted_goals=1, away_predicted_goals=1,
        )
        # All V1 schema keys still present
        for key in ("most_likely_score", "expected_goals", "match_outcome",
                    "goals", "top_scores", "odds"):
            self.assertIn(key, s)


class TestV1SchemaCompatibility(unittest.TestCase):
    """V2 reuses V1's create_prediction_summary_dict so output schemas
    are identical between engines."""

    def test_v2_output_uses_v1_schema(self):
        home_probs = {0: 0.2, 1: 0.3, 2: 0.25, 3: 0.15, 4: 0.07, 5: 0.03}
        away_probs = {0: 0.3, 1: 0.3, 2: 0.2, 3: 0.12, 4: 0.05, 5: 0.03}
        s = create_prediction_summary_dict(home_probs, away_probs)
        for key in ("most_likely_score", "expected_goals", "match_outcome",
                    "goals", "top_scores", "odds"):
            self.assertIn(key, s, f"V1 schema missing key: {key}")
        for key in ("home_win", "draw", "away_win"):
            self.assertIn(key, s["match_outcome"])
        for key in ("over", "under", "btts"):
            self.assertIn(key, s["goals"])
        # Match outcome is in PERCENT not probability
        total_pct = (s["match_outcome"]["home_win"]
                     + s["match_outcome"]["draw"]
                     + s["match_outcome"]["away_win"])
        self.assertAlmostEqual(total_pct, 100.0, places=0)


if __name__ == "__main__":
    unittest.main()
