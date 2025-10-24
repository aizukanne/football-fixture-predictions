"""Test script to diagnose league 40 (Championship) API calls"""

import sys
from datetime import datetime

# Test get_fixtures_goals
print("=" * 70)
print("Testing get_fixtures_goals for League 40 (Championship)")
print("=" * 70)

try:
    from src.data.api_client import get_fixtures_goals
    
    season = 2024
    start_ts = int(datetime(season, 8, 1).timestamp())
    end_ts = int(datetime.now().timestamp())
    
    print(f"League ID: 40")
    print(f"Season: {season}")
    print(f"Start timestamp: {start_ts}")
    print(f"End timestamp: {end_ts}")
    print()
    
    fixtures = get_fixtures_goals(40, start_ts, end_ts)
    
    print(f"Result type: {type(fixtures)}")
    print(f"Result value: {fixtures}")
    
    if fixtures:
        print(f"Number of fixtures: {len(fixtures) if isinstance(fixtures, list) else 'N/A'}")
        if isinstance(fixtures, list) and len(fixtures) > 0:
            print(f"First fixture sample: {fixtures[0]}")
    else:
        print("⚠️ No fixtures returned")
        
except Exception as e:
    print(f"❌ Error calling get_fixtures_goals: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
print("Testing get_league_teams for League 40 (Championship)")
print("=" * 70)

try:
    from src.data.api_client import get_league_teams
    
    season = 2024
    
    print(f"League ID: 40")
    print(f"Season: {season}")
    print()
    
    teams_data = get_league_teams(40, season)
    
    print(f"Result type: {type(teams_data)}")
    print(f"Result keys: {teams_data.keys() if isinstance(teams_data, dict) else 'N/A'}")
    
    if teams_data:
        if isinstance(teams_data, dict):
            print(f"Has 'response' key: {'response' in teams_data}")
            if 'response' in teams_data:
                response = teams_data['response']
                print(f"Response type: {type(response)}")
                print(f"Number of teams: {len(response) if isinstance(response, list) else 'N/A'}")
                if isinstance(response, list) and len(response) > 0:
                    print(f"First team sample: {response[0]}")
            else:
                print(f"teams_data content: {teams_data}")
    else:
        print("⚠️ No teams data returned")
        
except Exception as e:
    print(f"❌ Error calling get_league_teams: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
print("Done")
print("=" * 70)