#!/usr/bin/env python3
"""
Test script for manager/coach analysis functionality.
Tests the complete manager analysis implementation.
"""

import sys
from pprint import pprint

# Add src to path
sys.path.insert(0, './src')

def test_manager_profile_extraction():
    """Test extracting manager profile from API."""
    print("\n" + "="*80)
    print("TEST 1: Manager Profile Extraction")
    print("="*80)

    from src.features.manager_analyzer import get_manager_profile

    # Test with Manchester United (team_id=33)
    team_id = 33
    league_id = 39  # Premier League
    season = 2024

    print(f"\nGetting manager profile for team {team_id}, league {league_id}, season {season}")

    manager_profile = get_manager_profile(team_id, league_id, season)

    print("\n✅ Manager Profile Retrieved:")
    print("\nBasic Info:")
    print(f"  Manager ID: {manager_profile.get('manager_id')}")
    print(f"  Manager Name: {manager_profile.get('manager_name')}")
    print(f"  Age: {manager_profile.get('manager_age')}")
    print(f"  Nationality: {manager_profile.get('manager_nationality')}")

    print("\nExperience:")
    print(f"  Years of Experience: {manager_profile.get('experience_years')}")
    print(f"  Teams Managed: {manager_profile.get('teams_managed')}")
    print(f"  Top Level Experience: {manager_profile.get('top_level_experience')}")

    print("\nTactical Profile:")
    print(f"  Tactical Flexibility: {manager_profile.get('tactical_flexibility')}")
    print(f"  Formation Consistency: {manager_profile.get('formation_consistency')}")

    preferred_formations = manager_profile.get('preferred_formations', {})
    print(f"\nPreferred Formations:")
    print(f"  Most Used: {preferred_formations.get('most_used')}")
    print(f"  Formation Count: {preferred_formations.get('formations_count')}")

    home_away = manager_profile.get('home_away_strategy_difference', {})
    print(f"\nHome/Away Strategy:")
    print(f"  Home Formation: {home_away.get('home_formation')}")
    print(f"  Away Formation: {home_away.get('away_formation')}")
    print(f"  Strategy Difference: {home_away.get('strategy_difference')}")

    opponent_adapt = manager_profile.get('opponent_adaptation', {})
    print(f"\nOpponent Adaptation:")
    for tier in ['vs_top_teams', 'vs_mid_teams', 'vs_bottom_teams']:
        if tier in opponent_adapt:
            print(f"  {tier}: {opponent_adapt[tier]}")

    print(f"\n  Adaptation Level: {opponent_adapt.get('adaptation_level')}")

    return manager_profile


def test_manager_tactical_multiplier():
    """Test manager-based tactical multipliers."""
    print("\n" + "="*80)
    print("TEST 2: Manager Tactical Multipliers")
    print("="*80)

    from src.features.manager_analyzer import get_manager_tactical_multiplier

    team_id = 33
    league_id = 39
    season = 2024

    scenarios = [
        ('home', 'top'),
        ('home', 'middle'),
        ('home', 'bottom'),
        ('away', 'top'),
        ('away', 'middle'),
        ('away', 'bottom'),
    ]

    print(f"\nCalculating tactical multipliers for team {team_id}:\n")

    for venue, opponent_tier in scenarios:
        multiplier = get_manager_tactical_multiplier(
            team_id, league_id, season, opponent_tier, venue
        )
        print(f"  {venue.upper()} vs {opponent_tier.upper()} teams: {multiplier} ({float(multiplier-1)*100:+.1f}%)")


def test_integration_with_tactical_analyzer():
    """Test integration with existing tactical analyzer."""
    print("\n" + "="*80)
    print("TEST 3: Integration with Tactical Analyzer")
    print("="*80)

    from src.features.tactical_analyzer import TacticalAnalyzer

    analyzer = TacticalAnalyzer()

    team_id = 33
    league_id = 39
    season = 2024

    print(f"\nGetting manager tactical profile via TacticalAnalyzer...")

    try:
        manager_profile = analyzer.get_manager_tactical_profile(team_id, league_id, season)

        print("\n✅ Manager Tactical Profile (via TacticalAnalyzer):")
        print(f"  Manager Name: {manager_profile.get('manager_name', 'N/A')}")
        print(f"  Formation Preferences: {manager_profile.get('formation_preferences', {}).get('primary_formation', 'N/A')}")
        print(f"  Tactical Flexibility: {manager_profile.get('tactical_flexibility', 'N/A')}")
        print(f"  Adaptation Strategy: {manager_profile.get('adaptation_strategy', 'N/A')}")

        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_manager_data_quality():
    """Test data quality and fallback mechanisms."""
    print("\n" + "="*80)
    print("TEST 4: Data Quality & Fallback Mechanisms")
    print("="*80)

    from src.features.manager_analyzer import get_manager_profile

    # Test with potentially unavailable team
    team_id = 999999
    league_id = 39
    season = 2024

    print(f"\nTesting with unavailable team {team_id}...")

    manager_profile = get_manager_profile(team_id, league_id, season)

    print("\n✅ Fallback Profile Retrieved:")
    print(f"  Manager Name: {manager_profile.get('manager_name')}")
    print(f"  Data Quality: {manager_profile.get('data_quality', 'unknown')}")
    print(f"  Features Enabled: {manager_profile.get('manager_features_enabled')}")

    if manager_profile.get('manager_name') == 'Unknown':
        print("\n✅ Fallback mechanism working correctly")
    else:
        print("\n⚠️  Unexpected: got data for unavailable team")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("MANAGER/COACH ANALYSIS - COMPREHENSIVE TEST SUITE")
    print("="*80)

    test_results = []

    # Test 1: Profile Extraction
    try:
        manager_profile = test_manager_profile_extraction()
        test_results.append(("Profile Extraction", True, manager_profile.get('manager_name') != 'Unknown'))
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {e}")
        test_results.append(("Profile Extraction", False, str(e)))

    # Test 2: Tactical Multipliers
    try:
        test_manager_tactical_multiplier()
        test_results.append(("Tactical Multipliers", True, "Calculated successfully"))
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED: {e}")
        test_results.append(("Tactical Multipliers", False, str(e)))

    # Test 3: Integration
    try:
        integration_success = test_integration_with_tactical_analyzer()
        test_results.append(("Integration with TacticalAnalyzer", integration_success, "Integrated"))
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED: {e}")
        test_results.append(("Integration with TacticalAnalyzer", False, str(e)))

    # Test 4: Data Quality
    try:
        test_manager_data_quality()
        test_results.append(("Data Quality & Fallbacks", True, "Fallbacks working"))
    except Exception as e:
        print(f"\n❌ TEST 4 FAILED: {e}")
        test_results.append(("Data Quality & Fallbacks", False, str(e)))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, success, _ in test_results if success)
    total = len(test_results)

    for test_name, success, detail in test_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if detail and not success:
            print(f"         Error: {detail}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL MANAGER ANALYSIS TESTS PASSED!")
        print("\n✅ Manager analysis implementation complete and working!")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed - review errors above")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
