"""Test that the season parameter fix works correctly"""

import os
from datetime import datetime

# Set API key
os.environ['RAPIDAPI_KEY'] = '4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4'

from src.data.api_client import get_fixtures_goals

print("=" * 70)
print("Testing get_fixtures_goals() with season parameter fix")
print("=" * 70)

# Test with multiple leagues
test_cases = [
    {"league_id": 39, "name": "Premier League", "season": 2024},
    {"league_id": 40, "name": "Championship", "season": 2024},
    {"league_id": 103, "name": "Eliteserien", "season": 2024}
]

for test in test_cases:
    league_id = test["league_id"]
    league_name = test["name"]
    season = test["season"]
    
    print(f"\nTesting {league_name} (ID: {league_id})")
    print("-" * 50)
    
    try:
        season_year = int(season)
        start_ts = int(datetime(season_year, 8, 1).timestamp())
        end_ts = int(datetime.now().timestamp())
        
        # Call with season parameter (new signature)
        fixtures = get_fixtures_goals(league_id, start_ts, end_ts, season)
        
        print(f"✓ Function call successful")
        print(f"  Season: {season}")
        print(f"  Fixtures returned: {len(fixtures)}")
        
        if len(fixtures) > 0:
            print(f"  ✓ SUCCESS: Got fixtures with season parameter")
            # Show sample
            f = fixtures[0]
            print(f"  Sample: {f['teams']['home']['name']} vs {f['teams']['away']['name']}")
        else:
            print(f"  ⚠️ WARNING: Zero fixtures returned")
            
    except TypeError as e:
        print(f"  ✗ TypeError: {e}")
        print(f"  This means the function signature wasn't updated correctly")
    except Exception as e:
        print(f"  ✗ Error: {e}")

print()
print("=" * 70)
print("CONCLUSION")
print("=" * 70)
print("If all tests show ✓ SUCCESS, the fix is working correctly.")
print("The function now requires and uses the season parameter.")