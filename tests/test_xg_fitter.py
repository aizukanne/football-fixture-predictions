"""Unit tests for src/parameters/xg_fitter.

Tests the pure fitting logic against hand-constructed row lists. Does
NOT talk to DynamoDB — the public DB reader/writer helpers in xg_fitter
are smoke-tested separately via integration scripts.
"""

from __future__ import annotations

import os
import sys
import unittest
from decimal import Decimal

# Make sure the package is importable; match the project convention.
os.environ.setdefault("TABLE_PREFIX", "football_")
os.environ.setdefault("TABLE_SUFFIX", "_prod")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.parameters.xg_fitter import (
    fit_league_xg_params,
    fit_team_xg_params,
    _shrink,
    SOT_PROXY_FRACTION_FLAG,
)


def _mk_row(fixture_id: int, team_id: int, is_home: bool, xg: float,
            season: int = 2025, xg_source: str = "native",
            match_date: str = "2025-08-17T15:00:00+00:00") -> dict:
    return {
        "fixture_id": fixture_id,
        "team_id": team_id,
        "league_id": 39,
        "season": season,
        "match_date": match_date,
        "is_home": is_home,
        "xg_source": xg_source,
        "expected_goals": Decimal(str(xg)),
    }


class TestShrink(unittest.TestCase):

    def test_zero_n_returns_league_mean(self):
        self.assertEqual(_shrink(None, 1.4, 0), 1.4)
        self.assertEqual(_shrink(2.0, 1.4, 0), 1.4)

    def test_large_n_returns_team_mean(self):
        # n >> k, weight on team sample approaches 1
        # 1000/(1000+10) * 2.0 + 10/1010 * 1.4 ≈ 1.9941
        result = _shrink(2.0, 1.4, 1000)
        self.assertAlmostEqual(result, 2.0, places=1)

    def test_small_n_blends_toward_prior(self):
        # n=3 with k=10 gives weight 3/13 on team, 10/13 on league
        result = _shrink(2.0, 1.4, 3, k=10)
        expected = (3 / 13) * 2.0 + (10 / 13) * 1.4
        self.assertAlmostEqual(result, expected, places=4)
        # Must be closer to 1.4 than to 2.0
        self.assertLess(abs(result - 1.4), abs(result - 2.0))


class TestFitLeagueXgParams(unittest.TestCase):

    def _build_league(self, n_fixtures: int = 10, home_xg_seq=None, away_xg_seq=None) -> list:
        """Build a synthetic league with n_fixtures matches between two teams."""
        rows = []
        for i in range(n_fixtures):
            home_xg = home_xg_seq[i] if home_xg_seq else 1.5
            away_xg = away_xg_seq[i] if away_xg_seq else 1.2
            fid = 1000 + i
            rows.append(_mk_row(fid, team_id=100, is_home=True, xg=home_xg))
            rows.append(_mk_row(fid, team_id=200, is_home=False, xg=away_xg))
        return rows

    def test_mean_reflects_input(self):
        rows = self._build_league(10, home_xg_seq=[1.5]*10, away_xg_seq=[1.0]*10)
        p = fit_league_xg_params(39, 2025, rows)
        self.assertAlmostEqual(float(p["league_avg_xg_home"]), 1.5, places=3)
        self.assertAlmostEqual(float(p["league_avg_xg_away"]), 1.0, places=3)
        self.assertAlmostEqual(float(p["league_avg_xg_for"]), 1.25, places=3)
        self.assertAlmostEqual(float(p["home_adv"]), 1.5, places=3)
        self.assertEqual(int(p["n_matches"]), 10)

    def test_no_data_returns_zeros_and_unity_home_adv(self):
        p = fit_league_xg_params(39, 2025, [])
        self.assertEqual(float(p["league_avg_xg_for"]), 0.0)
        self.assertEqual(float(p["home_adv"]), 1.0)
        self.assertEqual(int(p["n_matches"]), 0)

    def test_rho_default_when_no_prior(self):
        # No existing league record → rho_dc falls back to the literature default.
        # (The function calls DynamoDB for the prior; in tests without a
        # table it catches the exception and returns None → default applies.)
        rows = self._build_league(5)
        p = fit_league_xg_params(999999, 2025, rows)  # unused league_id
        self.assertEqual(float(p["rho_dc"]), -0.18)


class TestFitTeamXgParams(unittest.TestCase):

    def _build_mixed_league(self):
        """A 3-team league where team 100 plays 4 matches, team 200 plays 6,
        team 300 plays 2. Each row is (team_id, opponent_id, is_home, xg).
        Teams 100 and 200 are balanced; team 300 is the cold-start test case.
        """
        script = [
            # fid, home_tid, away_tid, home_xg, away_xg
            (1001, 100, 200, 2.0, 0.8),
            (1002, 200, 100, 1.5, 1.0),
            (1003, 100, 200, 1.8, 1.2),
            (1004, 200, 100, 1.3, 0.9),
            (1005, 100, 300, 2.2, 0.5),
            (1006, 300, 100, 1.0, 1.5),
            (1007, 200, 300, 1.7, 0.6),
            (1008, 300, 200, 0.8, 2.0),
            (1009, 200, 100, 1.6, 1.1),
            (1010, 100, 200, 1.9, 1.0),
            (1011, 200, 100, 1.2, 1.3),
            (1012, 100, 200, 2.1, 0.7),
        ]
        rows = []
        for fid, h, a, hx, ax in script:
            rows.append(_mk_row(fid, h, True, hx))
            rows.append(_mk_row(fid, a, False, ax))
        return rows

    def test_team_100_means(self):
        rows = self._build_mixed_league()
        lp = fit_league_xg_params(39, 2025, rows)
        tp = fit_team_xg_params(100, 39, 2025, rows, lp)

        # Team 100 plays: 1001(H, 2.0/0.8), 1002(A, 1.0/1.5), 1003(H, 1.8/1.2),
        # 1004(A, 0.9/1.3), 1005(H, 2.2/0.5), 1006(A, 1.5/1.0),
        # 1009(A, 1.1/1.6), 1010(H, 1.9/1.0), 1011(A, 1.3/1.2), 1012(H, 2.1/0.7).
        # That's 10 matches — 5 home, 5 away.
        self.assertEqual(int(tp["n_matches"]), 10)
        self.assertEqual(int(tp["n_matches_home"]), 5)
        self.assertEqual(int(tp["n_matches_away"]), 5)

        # data_quality should be 'full' (10 matches, no sot_proxy)
        self.assertEqual(tp["data_quality"], "full")

    def test_cold_start_team(self):
        rows = self._build_mixed_league()
        lp = fit_league_xg_params(39, 2025, rows)
        # Fit a team with no rows at all
        tp = fit_team_xg_params(999, 39, 2025, rows, lp)
        self.assertEqual(int(tp["n_matches"]), 0)
        self.assertEqual(tp["data_quality"], "cold_start")
        # All means fall back to league averages
        self.assertAlmostEqual(float(tp["mu_xg_for"]), float(lp["league_avg_xg_for"]), places=4)
        self.assertAlmostEqual(float(tp["mu_xg_for_home"]), float(lp["league_avg_xg_home"]), places=4)
        self.assertAlmostEqual(float(tp["mu_xg_for_away"]), float(lp["league_avg_xg_away"]), places=4)

    def test_sparse_team_flag(self):
        rows = self._build_mixed_league()
        lp = fit_league_xg_params(39, 2025, rows)
        tp = fit_team_xg_params(300, 39, 2025, rows, lp)
        # Team 300 plays 4 matches — below XG_MIN_MATCHES_FULL (10)
        self.assertLess(int(tp["n_matches"]), 10)
        self.assertEqual(tp["data_quality"], "sparse")

    def test_sot_proxy_flag(self):
        # Build a league where one team's rows are mostly sot_proxy
        rows = []
        for i in range(12):
            fid = 2000 + i
            src = "sot_proxy" if i < 10 else "native"
            rows.append(_mk_row(fid, 700, True, 1.0, xg_source=src))
            rows.append(_mk_row(fid, 800, False, 1.0, xg_source="native"))
        lp = fit_league_xg_params(39, 2025, rows)
        tp_700 = fit_team_xg_params(700, 39, 2025, rows, lp)
        self.assertEqual(tp_700["data_quality"], "sot_proxy")
        # Team 800 had 0 sot_proxy rows → 'full'
        tp_800 = fit_team_xg_params(800, 39, 2025, rows, lp)
        self.assertEqual(tp_800["data_quality"], "full")

    def test_shrinkage_pulls_small_sample_toward_league(self):
        # Team 300 played 4 matches with relatively extreme values
        # (0.5, 1.5, 0.6, 2.0 avg ~= 1.15 for; 2.2, 1.0, 1.7, 0.8 avg ~= 1.425 against)
        # With n=4 and k=10, shrinkage weight on team = 4/14 = 0.286
        rows = self._build_mixed_league()
        lp = fit_league_xg_params(39, 2025, rows)
        tp = fit_team_xg_params(300, 39, 2025, rows, lp)

        # mu_xg_for should be between team's raw and league avg, closer to league.
        # Team 300's raw for: 0.5 (A vs 100 in 1005), 1.0 (H vs 100 in 1006),
        #   0.6 (A vs 200 in 1007), 0.8 (H vs 200 in 1008). Mean = 0.725.
        # League avg = mean of all xG. With shrinkage, mu should sit between.
        raw_team_mean = (0.5 + 1.0 + 0.6 + 0.8) / 4
        league_mean = float(lp["league_avg_xg_for"])
        result = float(tp["mu_xg_for"])
        low, high = sorted((raw_team_mean, league_mean))
        self.assertGreaterEqual(result, low - 1e-6)
        self.assertLessEqual(result, high + 1e-6)
        # And closer to the league prior than to the raw team sample
        self.assertLess(abs(result - league_mean), abs(result - raw_team_mean))


if __name__ == "__main__":
    unittest.main()
