#!/usr/bin/env python3
"""Test the full manager profile retrieval with real API data."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("\n" + "="*80)
print("TESTING FULL MANAGER PROFILE RETRIEVAL")
print("="*80)

try:
    from src.features.manager_analyzer import get_manager_profile

    team_id = 50  # Manchester City
    league_id = 39
    season = 2024

    print(f"\nCalling get_manager_profile({team_id}, {league_id}, {season})")
    print("Team: Manchester City")

    profile = get_manager_profile(team_id, league_id, season)

    print("\n" + "="*80)
    print("MANAGER PROFILE RESULTS")
    print("="*80)

    print(f"\n📋 Basic Information:")
    print(f"   Manager Name: {profile.get('manager_name')}")
    print(f"   Manager ID: {profile.get('manager_id')}")
    print(f"   Age: {profile.get('manager_age')}")
    print(f"   Nationality: {profile.get('manager_nationality')}")

    print(f"\n💼 Experience:")
    print(f"   Years of Experience: {profile.get('experience_years')}")
    print(f"   Teams Managed: {profile.get('teams_managed')}")
    print(f"   Top Level Experience: {profile.get('top_level_experience')}")

    print(f"\n⚽ Tactical Profile:")
    print(f"   Tactical Flexibility: {profile.get('tactical_flexibility')}")
    print(f"   Formation Consistency: {profile.get('formation_consistency')}")

    preferred = profile.get('preferred_formations', {})
    if preferred:
        print(f"\n📊 Preferred Formations:")
        print(f"   Most Used: {preferred.get('most_used')}")
        print(f"   Formations Count: {preferred.get('formations_count')}")

    home_away = profile.get('home_away_strategy_difference', {})
    if home_away:
        print(f"\n🏠 Home/Away Strategy:")
        print(f"   Home Formation: {home_away.get('home_formation')}")
        print(f"   Away Formation: {home_away.get('away_formation')}")
        print(f"   Strategy Difference: {home_away.get('strategy_difference')}")

    print("\n" + "="*80)
    print("VERDICT")
    print("="*80)

    if profile.get('manager_name') and profile.get('manager_name') != 'Unknown':
        print(f"\n🎉 SUCCESS! Real manager profile retrieved!")
        print(f"\n✅ Manager: {profile.get('manager_name')}")
        print(f"✅ Experience: {profile.get('experience_years')} years")
        print(f"✅ Teams: {profile.get('teams_managed')}")
        print(f"\n✅ THE MANAGER ANALYSIS INTEGRATION IS WORKING WITH REAL DATA!")
    else:
        print(f"\n❌ Got default/fallback profile")
        print(f"   Manager name: {profile.get('manager_name')}")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
