"""Unit tests for src/prediction/sot_engine.

Covers the V3 lambda formula, NB marginal distribution, and predicted-
goals rounding rule.
"""

from __future__ import annotations

import os
import sys
import unittest
from decimal import Decimal

os.environ.setdefault("TABLE_PREFIX", "football_")
os.environ.setdefault("TABLE_SUFFIX", "_prod")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.prediction.sot_engine import (  # noqa: E402
    calculate_lambdas,
    calculate_predictions_sot,
    create_sot_prediction_summary_dict,
    _nb_marginal,
)


# Hand-picked baseline. Numbers chosen so by-hand computation is easy.
def _baseline_team(sot_h=5.0, sot_a=4.0, gc_h=1.2, gc_a=1.4):
    return {
        "sot_for_home": Decimal(str(sot_h)),
        "sot_for_away": Decimal(str(sot_a)),
        "sot_for_all": Decimal(str((sot_h + sot_a) / 2)),
        "goals_conceded_home": Decimal(str(gc_h)),
        "goals_conceded_away": Decimal(str(gc_a)),
        "goals_conceded_all": Decimal(str((gc_h + gc_a) / 2)),
        "data_quality": "full",
        "n_matches_home": 10,
        "n_matches_away": 10,
        "n_matches": 20,
    }


def _baseline_league(conv=0.32, gc_home=1.0, gc_away=1.5,
                     sot_home=5.0, sot_away=4.0):
    return {
        "sot_to_goal_conv_rate": Decimal(str(conv)),
        "league_avg_goals_conceded_home": Decimal(str(gc_home)),
        "league_avg_goals_conceded_away": Decimal(str(gc_away)),
        "league_avg_goals_conceded": Decimal(str((gc_home + gc_away) / 2)),
        "league_avg_sot_home": Decimal(str(sot_home)),
        "league_avg_sot_away": Decimal(str(sot_away)),
        "league_avg_sot_for": Decimal(str((sot_home + sot_away) / 2)),
    }


class TestLambdaFormula(unittest.TestCase):

    def test_neutral_match_yields_league_baseline(self):
        # Both teams equal to league averages ⇒ defensive ratios = 1.0
        # ⇒ λ_H = league_avg_sot_home × conv;  λ_A = league_avg_sot_away × conv
        home = _baseline_team(sot_h=5.0, sot_a=4.0, gc_h=1.0, gc_a=1.5)
        away = _baseline_team(sot_h=5.0, sot_a=4.0, gc_h=1.0, gc_a=1.5)
        league = _baseline_league(conv=0.32, gc_home=1.0, gc_away=1.5,
                                  sot_home=5.0, sot_away=4.0)

        lh, la, debug = calculate_lambdas(home, away, league)
        self.assertAlmostEqual(lh, 5.0 * 0.32, places=6)  # 1.6
        self.assertAlmostEqual(la, 4.0 * 0.32, places=6)  # 1.28
        self.assertAlmostEqual(debug["def_ratio_for_h"], 1.0, places=6)
        self.assertAlmostEqual(debug["def_ratio_for_a"], 1.0, places=6)

    def test_leaky_opponent_inflates_lambda(self):
        home = _baseline_team(sot_h=5.0)
        # Away team concedes 3.0 away vs league avg 1.5 ⇒ ratio = 2.0
        away = _baseline_team(gc_a=3.0)
        league = _baseline_league(conv=0.32, gc_away=1.5)

        lh, _, debug = calculate_lambdas(home, away, league)
        # λ_H = 5.0 × 0.32 × 2.0 = 3.2
        self.assertAlmostEqual(lh, 3.2, places=6)
        self.assertAlmostEqual(debug["def_ratio_for_h"], 2.0, places=6)

    def test_stingy_opponent_deflates_lambda(self):
        home = _baseline_team(sot_h=5.0)
        # Away team concedes 0.5 away vs league avg 1.5 ⇒ ratio = 1/3
        away = _baseline_team(gc_a=0.5)
        league = _baseline_league(conv=0.32, gc_away=1.5)

        lh, _, debug = calculate_lambdas(home, away, league)
        # λ_H = 5.0 × 0.32 × (0.5/1.5) ≈ 0.5333
        self.assertAlmostEqual(lh, 5.0 * 0.32 * (0.5 / 1.5), places=6)

    def test_zero_league_gc_falls_back_to_no_adjustment(self):
        # Edge: brand-new league with zero data ⇒ ratio default = 1.0.
        home = _baseline_team()
        away = _baseline_team()
        league = _baseline_league()
        league["league_avg_goals_conceded_away"] = Decimal("0")
        league["league_avg_goals_conceded_home"] = Decimal("0")

        lh, la, debug = calculate_lambdas(home, away, league)
        # No defensive adjustment ⇒ ratio = 1.0
        self.assertAlmostEqual(debug["def_ratio_for_h"], 1.0, places=6)
        self.assertAlmostEqual(debug["def_ratio_for_a"], 1.0, places=6)

    def test_zero_conv_rate_falls_back(self):
        # Edge: brand-new league ⇒ conv falls back to global mean (0.317).
        home = _baseline_team()
        away = _baseline_team()
        league = _baseline_league(conv=0)  # falls back

        _, _, debug = calculate_lambdas(home, away, league)
        self.assertAlmostEqual(debug["conv_rate"], 0.317, places=4)


class TestNBMarginal(unittest.TestCase):

    def test_probabilities_sum_to_one(self):
        probs = _nb_marginal(1.5)
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=6)

    def test_lambda_zero_concentrates_on_zero(self):
        probs = _nb_marginal(0.0)
        self.assertAlmostEqual(probs[0], 1.0, places=6)
        for k in range(1, 11):
            self.assertAlmostEqual(probs[k], 0.0, places=6)

    def test_higher_lambda_shifts_mass_right(self):
        low = _nb_marginal(0.5)
        high = _nb_marginal(2.5)
        # Mean of distribution should track λ.
        mean_low = sum(k * p for k, p in low.items())
        mean_high = sum(k * p for k, p in high.items())
        self.assertGreater(mean_high, mean_low)


class TestPredictedGoalsRounding(unittest.TestCase):

    def test_round_lambda_not_marginal_mode(self):
        # λ_H = 1.7 ⇒ round = 2; marginal NB mode of 1.7 with α=0.3 = 1.
        # The engine must emit 2, not 1.
        home = _baseline_team(sot_h=5.3125)  # 5.3125 × 0.32 = 1.7
        away = _baseline_team()
        league = _baseline_league(conv=0.32, gc_away=1.5)
        # neutral defensive ratio
        away["goals_conceded_away"] = Decimal("1.5")

        result = calculate_predictions_sot(home, away, league)
        home_predicted_goals = result[1]
        # round(1.7) = 2
        self.assertEqual(home_predicted_goals, 2)

    def test_low_lambda_rounds_to_one(self):
        # λ_H = 1.1 ⇒ round = 1.
        home = _baseline_team(sot_h=3.4375)  # 3.4375 × 0.32 = 1.1
        away = _baseline_team()
        away["goals_conceded_away"] = Decimal("1.5")
        league = _baseline_league(conv=0.32, gc_away=1.5)

        result = calculate_predictions_sot(home, away, league)
        self.assertEqual(result[1], 1)

    def test_zero_lambda_rounds_to_zero(self):
        # Force every SoT field to zero so the pooled-fallback also gives 0.
        # The engine's _resolve_team_sot falls back to sot_for_all when the
        # venue-specific field is zero — a real team that's never shot on
        # target would still have a non-zero sot_for_all from shrinkage,
        # so this is an artificial all-zeros configuration.
        home = _baseline_team(sot_h=0.0, sot_a=0.0)
        home["sot_for_all"] = Decimal("0")
        away = _baseline_team()
        away["goals_conceded_away"] = Decimal("1.5")
        league = _baseline_league(conv=0.32, gc_away=1.5)

        result = calculate_predictions_sot(home, away, league)
        self.assertEqual(result[1], 0)


class TestSummaryDictOverride(unittest.TestCase):

    def test_most_likely_score_uses_round_lambda(self):
        # Build marginals with both modes at 1, but feed predicted=(0,2).
        # Summary's most_likely_score must be "0-2", not the joint argmax.
        probs = {0: 0.3, 1: 0.4, 2: 0.2, 3: 0.1}
        for k in range(4, 11):
            probs[k] = 0.0
        # Re-normalize defensively.
        total = sum(probs.values())
        probs = {k: v / total for k, v in probs.items()}

        summary = create_sot_prediction_summary_dict(probs, probs, 0, 2)
        self.assertEqual(summary["most_likely_score"]["score"], "0-2")

    def test_top_scores_starts_with_overridden_score(self):
        probs = {k: 0.0 for k in range(11)}
        probs[1] = 0.5
        probs[2] = 0.3
        probs[0] = 0.2
        summary = create_sot_prediction_summary_dict(probs, probs, 1, 2)
        # First entry should match the overridden score.
        self.assertEqual(summary["top_scores"][0]["score"], "1-2")
        self.assertLessEqual(len(summary["top_scores"]), 5)


class TestEngineReturnShape(unittest.TestCase):

    def test_returns_nine_tuple(self):
        home = _baseline_team()
        away = _baseline_team()
        league = _baseline_league()

        result = calculate_predictions_sot(home, away, league,
                                           league_id=39, season=2025,
                                           home_team_id=10, away_team_id=20)
        self.assertEqual(len(result), 9)
        (h_score, h_pg, h_lh, h_probs,
         a_score, a_pg, a_lh, a_probs,
         info) = result
        self.assertGreaterEqual(h_score, 0.0)
        self.assertLessEqual(h_score, 1.0)
        self.assertEqual(info["engine_version"], "v3-sot-1.0")
        self.assertEqual(info["league_id"], 39)


if __name__ == "__main__":
    unittest.main()
