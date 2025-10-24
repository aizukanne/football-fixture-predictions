"""Test season parameter requirement for multiple leagues"""

import os

# Set API key
os.environ['RAPIDAPI_KEY'] = '4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4'

from src.data.api_client import _make_api_request
from src.utils.constants import API_FOOTBALL_BASE_URL

print("=" * 70)
print("Testing season parameter requirement for multiple leagues")
print("=" * 70)

# Test leagues
test_leagues = [
    {"id": 39, "name": "Premier League", "season": "2025"},
    {"id": 40, "name": "Championship", "season": "2025"},
    {"id": 103, "name": "Eliteserien", "season": "2025"}
]

start_date = "2025-08-01"
end_date = "2025-10-24"

url = f"{API_FOOTBALL_BASE_URL}/fixtures"

for league in test_leagues:
    league_id = league["id"]
    league_name = league["name"]
    season = league["season"]
    
    print(f"\n{'='*70}")
    print(f"League: {league_name} (ID: {league_id})")
    print(f"{'='*70}")
    
    # Test WITHOUT season
    print(f"\n1. WITHOUT season parameter")
    print("-" * 50)
    params_no_season = {
        "league": str(league_id),
        "from": start_date,
        "to": end_date
    }
    print(f"Params: {params_no_season}")
    
    try:
        data = _make_api_request(url, params_no_season, max_retries=2)
        
        if data and "response" in data:
            fixtures = data["response"]
            print(f"✓ API call successful")
            print(f"  Fixtures returned: {len(fixtures)}")
            
            if len(fixtures) == 0:
                print(f"  ⚠️ ZERO fixtures without season")
        else:
            print(f"✗ No data returned")
            
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test WITH season
    print(f"\n2. WITH season parameter")
    print("-" * 50)
    params_with_season = {
        "league": str(league_id),
        "season": season,
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
                print(f"  ✓ Got {len(fixtures)} fixtures with season")
                # Show sample
                f = fixtures[0]
                print(f"  Sample: {f['teams']['home']['name']} vs {f['teams']['away']['name']}")
        else:
            print(f"✗ No data returned")
            
    except Exception as e:
        print(f"✗ Error: {e}")

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print("Compare fixtures returned WITH vs WITHOUT season parameter for each league")