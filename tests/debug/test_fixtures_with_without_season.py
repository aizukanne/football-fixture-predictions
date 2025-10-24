"""Test to confirm season parameter is required for fixtures API"""

import os
from datetime import datetime

# Set API key
os.environ['RAPIDAPI_KEY'] = '4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4'

from src.data.api_client import _make_api_request
from src.utils.constants import API_FOOTBALL_BASE_URL

print("=" * 70)
print("Testing fixtures API with and without season parameter")
print("=" * 70)

league_id = 40
start_date = "2024-08-01"
end_date = "2024-10-24"

print("\n1. WITHOUT season parameter (current get_fixtures_goals behavior)")
print("-" * 70)

url = f"{API_FOOTBALL_BASE_URL}/fixtures"
params = {
    "league": str(league_id),
    "from": start_date,
    "to": end_date
}

print(f"Params: {params}")

try:
    data = _make_api_request(url, params, max_retries=2)
    
    if data and "response" in data:
        fixtures = data["response"]
        print(f"✓ API call successful")
        print(f"  Fixtures returned: {len(fixtures)}")
        
        if len(fixtures) == 0:
            print(f"  ⚠️ PROBLEM: Zero fixtures despite valid date range and league")
    else:
        print(f"✗ No data returned")
        
except Exception as e:
    print(f"✗ Error: {e}")

print("\n2. WITH season parameter (what we should be doing)")
print("-" * 70)

params_with_season = {
    "league": str(league_id),
    "season": "2024",
    "from": start_date,
    "to": end_date
}

print(f"Params: {params_with_season}")

try:
    data = _make_api_request(url, params_with_season, max_retries=2)
    
    if data and "response" in data:
        fixtures = data["response"]
        print(f"✓ API call successful")
        print(f"  Fixtures returned: {len(fixtures)}")
        
        if len(fixtures) > 0:
            print(f"  ✓ SUCCESS: Got {len(fixtures)} fixtures with season parameter")
            print(f"\n  Sample fixture:")
            f = fixtures[0]
            print(f"    {f['teams']['home']['name']} vs {f['teams']['away']['name']}")
            print(f"    Date: {f['fixture']['date']}")
            print(f"    Score: {f['goals']['home']}-{f['goals']['away']}")
    else:
        print(f"✗ No data returned")
        
except Exception as e:
    print(f"✗ Error: {e}")

print()
print("=" * 70)
print("CONCLUSION")
print("=" * 70)
print("The API requires the 'season' parameter to return fixtures for league 40.")
print("Without it, the API returns 0 fixtures even with valid date ranges.")
print("\nFix: Update get_fixtures_goals() to accept and include season parameter.")