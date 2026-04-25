"""Unit tests for src/parameters/sot_fitter.

Tests the pure fitting logic against hand-constructed row lists. Does
NOT talk to DynamoDB — the load_/persist helpers are exercised via the
local-verification script run during V3 bring-up.
"""

from __future__ import annotations

import os
import sys
import unittest
from decimal import Decimal

# Project convention: stamp the env so constants.py picks up the
# football_/_prod fully-qualified table names during import.
os.environ.setdefault("TABLE_PREFIX", "football_")
os.environ.setdefault("TABLE_SUFFIX", "_prod")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.parameters.sot_fitter import (  # noqa: E402
    fit_league_sot_params,
    fit_team_sot_params,
    _shrink,
)


def _mk_row(fixture_id: int, team_id: int, is_home: bool,
            shots_on_goal: int, season: int = 2025,
            league_id: int = 39,
            match_date: str = "2025-08-17T15:00:00+00:00") -> dict:
    return {
        "fixture_id": fixture_id,
        "team_id": team_id,
        "league_id": league_id,
        "season": season,
        "match_date": match_date,
        "is_home": is_home,
        "shots_on_goal": int(shots_on_goal),
    }


class TestShrink(unittest.TestCase):

    def test_zero_n_returns_league_mean(self):
        self.assertEqual(_shrink(None, 4.5, 0), 4.5)
        self.assertEqual(_shrink(6.0, 4.5, 0), 4.5)

    def test_small_n_blends_toward_prior(self):
        # n=3 with k=5 ⇒ weight 3/8 on team, 5/8 on league
        result = _shrink(6.0, 4.5, 3, k=5)
        expected = (3 * 6.0 + 5 * 4.5) / 8
        self.assertAlmostEqual(result, expected, places=6)
        # Must be closer to 4.5 (league) than to 6.0 (team).
        self.assertLess(abs(result - 4.5), abs(result - 6.0))

    def test_large_n_returns_team_mean(self):
        # n=1000 with k=5 ⇒ weight ≈ 0.995 on team.
        result = _shrink(6.0, 4.5, 1000, k=5)
        self.assertAlmostEqual(result, 6.0, places=1)


class TestLeagueFit(unittest.TestCase):
    """Two fixtures, both finished. Conv rate, venue averages, GC averages
    should all be derivable by hand."""

    def setUp(self):
        # Fixture 1: home_team=10 vs away_team=20, 2-1 result.
        # Home took 5 SoT, away took 3 SoT.
        # Fixture 2: home_team=20 vs away_team=10, 1-1 result.
        # Home took 4 SoT, away took 4 SoT.
        self.rows = [
            _mk_row(1001, 10, True, 5),
            _mk_row(1001, 20, False, 3),
            _mk_row(1002, 20, True, 4),
            _mk_row(1002, 10, False, 4),
        ]
        self.fixture_goals = {
            1001: (2, 1),
            1002: (1, 1),
        }

    def test_pooled_conv_rate(self):
        params = fit_league_sot_params(39, 2025, self.rows, self.fixture_goals)
        # Total goals = 2+1 + 1+1 = 5; total SoT = 5+3+4+4 = 16; conv = 5/16 = 0.3125
        self.assertAlmostEqual(float(params["sot_to_goal_conv_rate"]),
                               5.0 / 16.0, places=6)

    def test_venue_split_sot_averages(self):
        params = fit_league_sot_params(39, 2025, self.rows, self.fixture_goals)
        # Home SoT: 5 (fixture 1) and 4 (fixture 2) → mean 4.5
        # Away SoT: 3 (fixture 1) and 4 (fixture 2) → mean 3.5
        self.assertAlmostEqual(float(params["league_avg_sot_home"]), 4.5)
        self.assertAlmostEqual(float(params["league_avg_sot_away"]), 3.5)

    def test_venue_split_gc_averages(self):
        params = fit_league_sot_params(39, 2025, self.rows, self.fixture_goals)
        # GC for home teams = away_goals: 1 (fixture 1), 1 (fixture 2) → 1.0
        # GC for away teams = home_goals: 2, 1 → 1.5
        self.assertAlmostEqual(float(params["league_avg_goals_conceded_home"]), 1.0)
        self.assertAlmostEqual(float(params["league_avg_goals_conceded_away"]), 1.5)

    def test_n_fixtures(self):
        params = fit_league_sot_params(39, 2025, self.rows, self.fixture_goals)
        self.assertEqual(int(params["n_fixtures"]), 2)


class TestTeamFit(unittest.TestCase):
    """Single team across multiple matches with varied venues."""

    def setUp(self):
        # Team 10 played 4 matches: 2 at home, 2 away.
        # Home matches:  fid=1, scored 5 SoT, conceded 1 goal
        #                fid=2, scored 7 SoT, conceded 2 goals
        # Away matches:  fid=3, scored 4 SoT, conceded 0 goals
        #                fid=4, scored 6 SoT, conceded 3 goals
        self.rows = [
            # Team 10 home in fixtures 1 and 2
            _mk_row(1, 10, True, 5),
            _mk_row(1, 99, False, 6),  # opponent
            _mk_row(2, 10, True, 7),
            _mk_row(2, 98, False, 8),
            # Team 10 away in fixtures 3 and 4
            _mk_row(3, 10, False, 4),
            _mk_row(3, 97, True, 5),
            _mk_row(4, 10, False, 6),
            _mk_row(4, 96, True, 7),
        ]
        # Goals: (home_goals, away_goals) per fixture
        self.fixture_goals = {
            1: (3, 1),  # team 10 home, scored 3, conceded 1
            2: (4, 2),  # team 10 home, scored 4, conceded 2
            3: (0, 5),  # team 10 away, scored 5, conceded 0
            4: (3, 2),  # team 10 away, scored 2, conceded 3
        }
        # Build a synthetic league_params for shrinkage testing.
        # League averages — picked roughly so we can detect when shrinkage
        # is/is not active. Set close to team mean ⇒ shrunk == team mean,
        # set far ⇒ visible pull.
        self.league_params = {
            "league_avg_sot_home": Decimal("6.0"),
            "league_avg_sot_away": Decimal("5.0"),
            "league_avg_sot_for": Decimal("5.5"),
            "league_avg_goals_conceded_home": Decimal("1.5"),
            "league_avg_goals_conceded_away": Decimal("1.5"),
            "league_avg_goals_conceded": Decimal("1.5"),
        }

    def test_venue_split_counts(self):
        params = fit_team_sot_params(
            10, 39, 2025, self.rows, self.fixture_goals, self.league_params,
        )
        self.assertEqual(int(params["n_matches_home"]), 2)
        self.assertEqual(int(params["n_matches_away"]), 2)
        self.assertEqual(int(params["n_matches"]), 4)

    def test_sparse_data_quality_under_threshold(self):
        # 4 matches < SOT_MIN_MATCHES_FULL (10) ⇒ sparse.
        params = fit_team_sot_params(
            10, 39, 2025, self.rows, self.fixture_goals, self.league_params,
        )
        self.assertEqual(params["data_quality"], "sparse")

    def test_cold_start_data_quality(self):
        # Empty rows for team 10 → cold_start.
        params = fit_team_sot_params(
            999, 39, 2025, self.rows, self.fixture_goals, self.league_params,
        )
        self.assertEqual(params["data_quality"], "cold_start")
        # Cold-start params fall back to league means.
        self.assertAlmostEqual(
            float(params["sot_for_home"]),
            float(self.league_params["league_avg_sot_home"])
        )

    def test_shrinkage_pulls_team_toward_league(self):
        # Team home SoT: (5+7)/2 = 6.0; league home avg = 6.0.
        # n=2 with k=5: shrunk = (2*6 + 5*6) / 7 = 6.0 (equal so no movement).
        params = fit_team_sot_params(
            10, 39, 2025, self.rows, self.fixture_goals, self.league_params,
        )
        self.assertAlmostEqual(float(params["sot_for_home"]), 6.0, places=6)

        # Team away SoT raw mean = (4+6)/2 = 5.0; league away avg = 5.0.
        self.assertAlmostEqual(float(params["sot_for_away"]), 5.0, places=6)

    def test_team_gc_calculation(self):
        # Team 10 GC at home: away_goals when team played home: 1 (fid=1), 2 (fid=2) → 1.5
        # League prior 1.5 with n=2 → still 1.5.
        params = fit_team_sot_params(
            10, 39, 2025, self.rows, self.fixture_goals, self.league_params,
        )
        self.assertAlmostEqual(float(params["goals_conceded_home"]), 1.5, places=6)

        # Team 10 GC away: home_goals when team played away: 0 (fid=3), 3 (fid=4) → 1.5
        self.assertAlmostEqual(float(params["goals_conceded_away"]), 1.5, places=6)


if __name__ == "__main__":
    unittest.main()
