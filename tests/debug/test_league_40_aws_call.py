"""Test script to replicate exact AWS Lambda call for league 40"""

import os
from datetime import datetime

# Set API key from constants.py
os.environ['RAPIDAPI_KEY'] = '4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4'

from src.data.api_client import get_fixtures_goals, get_league_teams

print("=" * 70)
print("Test 1: get_fixtures_goals() - Exactly as AWS Lambda calls it")
print("=" * 70)

# Mimic tactical_analyzer.py lines 825-828
league_id = 40
season = "2024"
season_year = int(season)
start_ts = int(datetime(season_year, 8, 1).timestamp())
end_ts = int(datetime.now().timestamp())

print(f"League ID: {league_id}")
print(f"Season: {season} (year: {season_year})")
print(f"Start timestamp: {start_ts} ({datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d')})")
print(f"End timestamp: {end_ts} ({datetime.fromtimestamp(end_ts).strftime('%Y-%m-%d')})")
print()

try:
    all_fixtures = get_fixtures_goals(league_id, start_ts, end_ts)
    
    print(f"✓ Call successful")
    print(f"Result type: {type(all_fixtures)}")
    print(f"Number of fixtures: {len(all_fixtures) if isinstance(all_fixtures, list) else 'N/A'}")
    
    if all_fixtures:
        print(f"\nFirst fixture sample:")
        print(f"  Fixture ID: {all_fixtures[0].get('fixture_id')}")
        print(f"  Home team: {all_fixtures[0].get('teams', {}).get('home', {}).get('name')}")
        print(f"  Away team: {all_fixtures[0].get('teams', {}).get('away', {}).get('name')}")
        print(f"  Score: {all_fixtures[0].get('home_goals')}-{all_fixtures[0].get('away_goals')}")
    else:
        print("\n⚠️ WARNING: No fixtures returned (empty list)")
        print("This explains the 'No fixtures data for league 40' warning in AWS")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
print("Test 2: get_league_teams() - Exactly as tactical_analyzer calls it")
print("=" * 70)

print(f"League ID: {league_id}")
print(f"Season: {season}")
print()

try:
    teams_data = get_league_teams(league_id, season)
    
    print(f"✓ Call successful")
    print(f"Result type: {type(teams_data)}")
    
    if isinstance(teams_data, dict):
        print(f"Has 'response' key: {'response' in teams_data}")
        if 'response' in teams_data:
            response = teams_data['response']
            print(f"Response type: {type(response)}")
            if isinstance(response, list):
                print(f"Number of teams: {len(response)}")
                if len(response) > 0:
                    print(f"\nFirst team sample:")
                    print(f"  Team ID: {response[0].get('team', {}).get('id')}")
                    print(f"  Team name: {response[0].get('team', {}).get('name')}")
                else:
                    print("\n⚠️ WARNING: Empty teams list")
            else:
                print(f"Response value: {response}")
        else:
            print(f"Response keys: {list(teams_data.keys())}")
    elif isinstance(teams_data, list):
        print(f"Number of items: {len(teams_data)}")
        if len(teams_data) == 0:
            print("\n⚠️ WARNING: Empty list returned (not a dict with 'response' key)")
            print("This explains the 'No league teams data for league 40' warning in AWS")
    else:
        print(f"Unexpected type: {teams_data}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
print("Analysis Complete")
print("=" * 70)