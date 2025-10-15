#!/usr/bin/env python3
"""
Test script to directly query manager/coach data from API-Football.
This will show if we can actually get real manager data.
"""

import sys
import os
from pprint import pprint

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_get_manager_profile():
    """Test getting manager profile from API."""
    print("\n" + "="*80)
    print("TEST: Get Manager Profile from API-Football")
    print("="*80)

    try:
        from src.features.manager_analyzer import get_manager_profile

        # Test with multiple teams
        test_cases = [
            (33, 39, 2024, "Manchester United"),
            (50, 39, 2024, "Manchester City"),
            (40, 39, 2024, "Liverpool"),
            (42, 39, 2024, "Arsenal"),
        ]

        for team_id, league_id, season, team_name in test_cases:
            print(f"\n{'='*80}")
            print(f"Team: {team_name} (ID: {team_id})")
            print(f"League: {league_id}, Season: {season}")
            print("="*80)

            manager_profile = get_manager_profile(team_id, league_id, season)

            if manager_profile:
                print(f"\n✅ Manager Profile Retrieved:")

                # Basic Info
                print(f"\n📋 Basic Information:")
                print(f"   Manager ID: {manager_profile.get('manager_id')}")
                print(f"   Name: {manager_profile.get('manager_name')}")
                print(f"   Age: {manager_profile.get('manager_age')}")
                print(f"   Nationality: {manager_profile.get('manager_nationality')}")

                # Experience
                print(f"\n💼 Experience:")
                print(f"   Years: {manager_profile.get('experience_years')}")
                print(f"   Teams Managed: {manager_profile.get('teams_managed')}")
                print(f"   Top Level Experience: {manager_profile.get('top_level_experience')}")

                # Tactical Profile
                print(f"\n⚽ Tactical Profile:")
                print(f"   Tactical Flexibility: {manager_profile.get('tactical_flexibility')}")
                print(f"   Formation Consistency: {manager_profile.get('formation_consistency')}")

                preferred_formations = manager_profile.get('preferred_formations', {})
                if preferred_formations.get('most_used'):
                    print(f"\n📊 Preferred Formations:")
                    print(f"   Most Used: {preferred_formations.get('most_used')}")
                    print(f"   Count: {preferred_formations.get('formations_count')}")

                # Check if it's real data or defaults
                if manager_profile.get('manager_name') != 'Unknown' and manager_profile.get('manager_id') != 0:
                    print(f"\n✅ REAL MANAGER DATA RETRIEVED!")
                else:
                    print(f"\n⚠️  Using default/fallback data (API data not available)")

                # Show full profile
                print(f"\n📄 Full Profile:")
                pprint(manager_profile)
            else:
                print(f"\n❌ No manager profile returned")

            print("\n" + "-"*80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def test_api_client_coach_endpoint():
    """Test the API client coach endpoints directly."""
    print("\n" + "="*80)
    print("TEST: API Client Coach Endpoints")
    print("="*80)

    try:
        from src.data.api_client import get_coach_by_team

        team_id = 33  # Manchester United
        league_id = 39
        season = 2024

        print(f"\nCalling get_coach_by_team({team_id}, {league_id}, {season})...")

        coach_data = get_coach_by_team(team_id, league_id, season)

        if coach_data:
            print(f"\n✅ Coach Data Retrieved from API:")
            pprint(coach_data)

            if isinstance(coach_data, list) and len(coach_data) > 0:
                coach = coach_data[0]
                print(f"\n📋 Coach Info:")
                print(f"   ID: {coach.get('id')}")
                print(f"   Name: {coach.get('name')}")
                print(f"   Age: {coach.get('age')}")
                print(f"   Nationality: {coach.get('nationality')}")

                if coach.get('name') and coach.get('name') != 'Unknown':
                    print(f"\n✅ REAL API DATA WORKING!")
                else:
                    print(f"\n⚠️  API returned but no real data")
            else:
                print(f"\n⚠️  Unexpected data format")
        else:
            print(f"\n❌ No coach data returned from API")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("MANAGER DATA API TEST SUITE")
    print("Testing if we can get real manager data from API-Football")
    print("="*80)

    # Test 1: Direct API client test
    test_api_client_coach_endpoint()

    # Test 2: Full manager profile
    test_get_manager_profile()

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nℹ️  If you see 'Unknown' or default data:")
    print("   - API key may be invalid or rate-limited")
    print("   - Check environment variables for API credentials")
    print("   - System will use neutral defaults (0% adjustment)")
    print("\nℹ️  If you see real names (e.g., 'Pep Guardiola'):")
    print("   - API integration is working!")
    print("   - Manager multipliers will use real data")


if __name__ == "__main__":
    main()
