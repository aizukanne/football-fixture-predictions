"""Test to find correct Championship season format"""

import os
from datetime import datetime

# Set API key
os.environ['RAPIDAPI_KEY'] = '4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4'

from src.data.api_client import _make_api_request
from src.utils.constants import API_FOOTBALL_BASE_URL

print("=" * 70)
print("Testing different season formats for Championship (league 40)")
print("=" * 70)

league_id = 40

# Test different season formats
season_formats = [
    "2024",
    "2023",
    "2024-2025",
    "2023-2024"
]

for season in season_formats:
    print(f"\nTesting season: {season}")
    print("-" * 50)
    
    # Try getting league info
    url = f"{API_FOOTBALL_BASE_URL}/leagues"
    params = {
        "id": str(league_id),
        "season": season
    }
    
    try:
        data = _make_api_request(url, params, max_retries=2)
        
        if data and "response" in data and len(data["response"]) > 0:
            league_info = data["response"][0]
            seasons_available = league_info.get("seasons", [])
            
            print(f"✓ League found for season {season}")
            print(f"  Current season: {league_info.get('league', {}).get('name')}")
            
            # Check available seasons
            if seasons_available:
                print(f"  Available seasons:")
                for s in seasons_available[-3:]:  # Show last 3 seasons
                    print(f"    - {s.get('year')}: start={s.get('start')}, end={s.get('end')}, current={s.get('current')}")
        else:
            print(f"✗ No data for season {season}")
            
    except Exception as e:
        print(f"✗ Error: {e}")

print()
print("=" * 70)
print("Now testing fixtures with correct season format")
print("=" * 70)

# Test with the 2024-2025 season
season = "2024"  # Championship typically uses single year for the STARTING year
start_date = "2024-08-01"
end_date = "2024-10-24"

print(f"\nQuerying fixtures:")
print(f"  League: {league_id}")
print(f"  Season: {season}")
print(f"  Date range: {start_date} to {end_date}")

url = f"{API_FOOTBALL_BASE_URL}/fixtures"
params = {
    "league": str(league_id),
    "season": season,
    "from": start_date,
    "to": end_date
}

print(f"\nAPI call: {url}")
print(f"Params: {params}")

try:
    data = _make_api_request(url, params, max_retries=2)
    
    if data and "response" in data:
        fixtures = data["response"]
        print(f"\n✓ Found {len(fixtures)} fixtures")
        
        if len(fixtures) > 0:
            # Show first fixture
            f = fixtures[0]
            print(f"\nFirst fixture:")
            print(f"  ID: {f['fixture']['id']}")
            print(f"  Date: {f['fixture']['date']}")
            print(f"  {f['teams']['home']['name']} vs {f['teams']['away']['name']}")
            print(f"  Status: {f['fixture']['status']['short']}")
            print(f"  Score: {f['goals']['home']}-{f['goals']['away']}")
    else:
        print(f"\n✗ No fixtures data returned")
        
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()