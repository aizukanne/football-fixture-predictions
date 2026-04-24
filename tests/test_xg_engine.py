"""Unit tests for src/prediction/xg_engine.

Pure-math tests on synthetic parameter inputs. No DynamoDB, no API.
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
    compute_form_multiplier,
    dixon_coles_joint_probs,
    _dc_tau,
    _poisson_pmf,
    _marginals,
)
from src.prediction.prediction_engine import create_prediction_summary_dict


class TestPoissonPmf(unittest.TestCase):

    def test_zero_lambda_returns_one_at_zero(self):
        self.assertEqual(_poisson_pmf(0, 0.0), 1.0)
        self.assertEqual(_poisson_pmf(1, 0.0), 0.0)

    def test_sum_to_1_truncation(self):
        # Lambda=1.5, summing PMF over 0..10 should be ≈ 1
        total = sum(_poisson_pmf(k, 1.5) for k in range(20))
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_mean_matches_lambda(self):
        # E[X] = lambda for Poisson
        lam = 2.3
        mean = sum(k * _poisson_pmf(k, lam) for k in range(30))
        self.assertAlmostEqual(mean, lam, places=3)


class TestDcTau(unittest.TestCase):

    def test_identity_away_from_corners(self):
        # Any (h, a) with h>1 or a>1 is identity
        self.assertEqual(_dc_tau(2, 3, 1.5, 1.2, -0.18), 1.0)
        self.assertEqual(_dc_tau(0, 2, 1.5, 1.2, -0.18), 1.0)

    def test_zero_zero(self):
        # tau(0,0) = 1 - lh*la*rho. For rho<0, this is > 1 (low scores boosted).
        tau = _dc_tau(0, 0, 1.5, 1.2, -0.18)
        expected = 1 - 1.5 * 1.2 * -0.18
        self.assertAlmostEqual(tau, expected, places=6)
        self.assertGreater(tau, 1.0)

    def test_rho_zero_gives_identity_everywhere(self):
        for h in range(3):
            for a in range(3):
                self.assertEqual(_dc_tau(h, a, 1.5, 1.2, 0.0), 1.0)


class TestDixonColesJoint(unittest.TestCase):

    def test_sum_to_1(self):
        joint = dixon_coles_joint_probs(1.4, 1.1, rho=-0.18, max_goals=10)
        total = sum(joint[h][a] for h in joint for a in joint[h])
        self.assertAlmostEqual(total, 1.0, places=9)

    def test_rho_zero_matches_independent_poisson(self):
        joint = dixon_coles_joint_probs(1.5, 1.0, rho=0.0, max_goals=10)
        # Independent: P(h,a) = Poisson(h,1.5) * Poisson(a,1.0) (normalized to 1)
        for h in range(4):
            for a in range(4):
                expected_raw = _poisson_pmf(h, 1.5) * _poisson_pmf(a, 1.0)
                # Renormalization: total should be close to 1 already for max_goals=10
                self.assertAlmostEqual(joint[h][a], expected_raw, places=3)

    def test_marginals_are_valid_distributions(self):
        joint = dixon_coles_joint_probs(1.4, 1.1, rho=-0.18, max_goals=10)
        home, away = _marginals(joint)
        self.assertAlmostEqual(sum(home.values()), 1.0, places=6)
        self.assertAlmostEqual(sum(away.values()), 1.0, places=6)
        for v in home.values():
            self.assertGreaterEqual(v, 0)
        for v in away.values():
            self.assertGreaterEqual(v, 0)

    def test_negative_rho_boosts_low_scores(self):
        joint_indep = dixon_coles_joint_probs(1.4, 1.1, rho=0.0, max_goals=10)
        joint_dc = dixon_coles_joint_probs(1.4, 1.1, rho=-0.18, max_goals=10)
        # 0-0 should be more likely under DC with negative rho
        self.assertGreater(joint_dc[0][0], joint_indep[0][0])


class TestFormMultiplier(unittest.TestCase):

    def test_empty_stream_returns_one(self):
        self.assertEqual(compute_form_multiplier([], 1.5), 1.0)
        self.assertEqual(compute_form_multiplier(None or (), 1.5), 1.0)

    def test_zero_baseline_returns_one(self):
        self.assertEqual(compute_form_multiplier([2.0, 1.5], 0.0), 1.0)

    def test_flat_stream_returns_one(self):
        mult = compute_form_multiplier([1.5, 1.5, 1.5], 1.5)
        self.assertAlmostEqual(mult, 1.0, places=4)

    def test_hot_stream_clamped_to_max(self):
        # Recent xG way above baseline
        mult = compute_form_multiplier([5.0, 4.0, 5.0], 1.0)
        self.assertEqual(mult, 1.3)  # clamped

    def test_cold_stream_clamped_to_min(self):
        mult = compute_form_multiplier([0.1, 0.2, 0.0], 2.0)
        self.assertEqual(mult, 0.7)  # clamped

    def test_moderate_hot_not_clamped(self):
        # Stream slightly above baseline
        mult = compute_form_multiplier([1.7, 1.6, 1.5], 1.5)
        self.assertGreater(mult, 1.0)
        self.assertLess(mult, 1.3)


class TestCalculateCoordinated(unittest.TestCase):

    def _std_params(self):
        league = {
            "league_avg_xg_for": Decimal("1.4"),
            "league_avg_xg_home": Decimal("1.55"),
            "league_avg_xg_away": Decimal("1.25"),
            "home_adv": Decimal("1.24"),
            "rho_dc": Decimal("-0.18"),
            "n_matches": 200,
        }
        home = {
            "mu_xg_for": Decimal("1.8"),       # strong attack
            "mu_xg_against": Decimal("1.0"),   # good defense
            "mu_xg_for_home": Decimal("1.9"),
            "mu_xg_against_home": Decimal("0.95"),
            "mu_xg_for_away": Decimal("1.7"),
            "mu_xg_against_away": Decimal("1.05"),
            "data_quality": "full",
        }
        away = {
            "mu_xg_for": Decimal("1.2"),
            "mu_xg_against": Decimal("1.5"),
            "mu_xg_for_home": Decimal("1.3"),
            "mu_xg_against_home": Decimal("1.45"),
            "mu_xg_for_away": Decimal("1.1"),
            "mu_xg_against_away": Decimal("1.55"),
            "data_quality": "full",
        }
        return home, away, league

    def test_standard_call_produces_expected_shape(self):
        home, away, league = self._std_params()
        result = calculate_coordinated_predictions_xg(
            home_team_xg_stats=[], away_team_xg_stats=[],
            home_params=home, away_params=away, league_params=league,
        )
        self.assertEqual(len(result), 9)
        (h_sp, h_pg, h_lh, h_probs,
         a_sp, a_pg, a_lh, a_probs, info) = result

        # Probabilities in [0, 1]
        for v in (h_sp, a_sp, h_lh, a_lh):
            self.assertGreaterEqual(v, 0)
            self.assertLessEqual(v, 1)
        self.assertAlmostEqual(sum(h_probs.values()), 1.0, places=6)
        self.assertAlmostEqual(sum(a_probs.values()), 1.0, places=6)
        # Predicted goals in valid range
        self.assertGreaterEqual(h_pg, 0)
        self.assertLessEqual(h_pg, 10)
        # Home should score more than away given the strong-home profile
        self.assertGreater(h_sp, a_sp)
        # coordination_info sanity
        self.assertEqual(info["engine_version"], "v2-xg-1.0")
        self.assertTrue(info["home_adv_applied"])
        self.assertIn("lambda_H", info)

    def test_lambda_formula(self):
        home, away, league = self._std_params()
        # Expected lambda_H: mu_atk_H * mu_def_A / league_avg * sqrt(home_adv)
        # = 1.8 * 1.5 / 1.4 * sqrt(1.24) ≈ 2.148
        result = calculate_coordinated_predictions_xg(
            home_team_xg_stats=[], away_team_xg_stats=[],
            home_params=home, away_params=away, league_params=league,
        )
        info = result[-1]
        expected = 1.8 * 1.5 / 1.4 * math.sqrt(1.24)
        self.assertAlmostEqual(info["lambda_H"], expected, places=3)

    def test_skip_home_adv(self):
        home, away, league = self._std_params()
        result_with = calculate_coordinated_predictions_xg(
            home_team_xg_stats=[], away_team_xg_stats=[],
            home_params=home, away_params=away, league_params=league,
            skip_home_adv=False,
        )
        result_skip = calculate_coordinated_predictions_xg(
            home_team_xg_stats=[], away_team_xg_stats=[],
            home_params=home, away_params=away, league_params=league,
            skip_home_adv=True,
        )
        # Without home_adv, lambda_H is smaller, lambda_A is larger
        self.assertLess(result_skip[-1]["lambda_H"], result_with[-1]["lambda_H"])
        self.assertGreater(result_skip[-1]["lambda_A"], result_with[-1]["lambda_A"])
        self.assertFalse(result_skip[-1]["home_adv_applied"])

    def test_venue_mode_uses_venue_mus(self):
        home, away, league = self._std_params()
        result_pooled = calculate_coordinated_predictions_xg(
            home_team_xg_stats=[], away_team_xg_stats=[],
            home_params=home, away_params=away, league_params=league,
            skip_home_adv=True, venue_mode=False,
        )
        result_venue = calculate_coordinated_predictions_xg(
            home_team_xg_stats=[], away_team_xg_stats=[],
            home_params=home, away_params=away, league_params=league,
            skip_home_adv=True, venue_mode=True,
        )
        # Venue-mode should pick mu_xg_for_home (1.9) rather than mu_xg_for (1.8)
        self.assertAlmostEqual(result_venue[-1]["mu_atk_H"], 1.9, places=3)
        self.assertAlmostEqual(result_pooled[-1]["mu_atk_H"], 1.8, places=3)

    def test_missing_league_avg_raises(self):
        home, away, league = self._std_params()
        league["league_avg_xg_for"] = Decimal("0")
        with self.assertRaises(ValueError):
            calculate_coordinated_predictions_xg(
                home_team_xg_stats=[], away_team_xg_stats=[],
                home_params=home, away_params=away, league_params=league,
            )


class TestV1SummaryShape(unittest.TestCase):
    """V2 reuses V1's create_prediction_summary_dict so output shapes
    are identical between engines. Verify the shape contract here."""

    def test_v2_uses_v1_summary_shape(self):
        home_probs = {0: 0.2, 1: 0.3, 2: 0.25, 3: 0.15, 4: 0.07, 5: 0.03}
        away_probs = {0: 0.3, 1: 0.3, 2: 0.2, 3: 0.12, 4: 0.05, 5: 0.03}
        s = create_prediction_summary_dict(home_probs, away_probs)

        # V1 schema (these MUST be present so V2 output is shape-compatible)
        for key in ("most_likely_score", "expected_goals", "match_outcome",
                    "goals", "top_scores", "odds"):
            self.assertIn(key, s, f"V1 schema missing key: {key}")

        # match_outcome inner shape
        for key in ("home_win", "draw", "away_win"):
            self.assertIn(key, s["match_outcome"])
        # goals inner shape
        for key in ("over", "under", "btts"):
            self.assertIn(key, s["goals"])

        # Match outcome values are in PERCENT (not probability) — V1 multiplies by 100.
        # Sum should be ~100, not ~1.
        total_pct = (s["match_outcome"]["home_win"]
                     + s["match_outcome"]["draw"]
                     + s["match_outcome"]["away_win"])
        self.assertAlmostEqual(total_pct, 100.0, places=0)


if __name__ == "__main__":
    unittest.main()
