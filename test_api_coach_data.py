#!/usr/bin/env python3
"""
Test script to explore API-Football coach/manager data availability.
This will test various endpoints to see what coach data is available.
"""

import os
import requests
import json
from pprint import pprint

# API Configuration
API_KEY = os.getenv('RAPIDAPI_KEY', '4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4')
BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"

headers = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
}

def test_coachs_endpoint():
    """Test the /coachs endpoint if it exists."""
    print("\n" + "="*80)
    print("TEST 1: Testing /coachs endpoint")
    print("="*80)

    # Try with team parameter
    url = f"{BASE_URL}/coachs"
    params = {"team": "33"}  # Manchester United

    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("\n✅ Coaches endpoint EXISTS!")
            print(f"\nResponse structure:")
            print(f"Keys: {list(data.keys())}")

            if 'response' in data and data['response']:
                print(f"\nNumber of coaches returned: {len(data['response'])}")
                print(f"\nFirst coach data:")
                pprint(data['response'][0], depth=3)
                return data['response'][0]
        else:
            print(f"❌ Coaches endpoint returned: {response.status_code}")
            print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"❌ Error testing coaches endpoint: {e}")

    return None


def test_lineups_for_coach():
    """Test what coach data is in lineups endpoint."""
    print("\n" + "="*80)
    print("TEST 2: Testing /fixtures/lineups for coach data")
    print("="*80)

    # Get a recent fixture first
    fixtures_url = f"{BASE_URL}/fixtures"
    fixtures_params = {
        "team": "33",
        "season": "2024",
        "last": "1"
    }

    try:
        fixtures_response = requests.get(fixtures_url, headers=headers, params=fixtures_params)
        if fixtures_response.status_code == 200:
            fixtures_data = fixtures_response.json()
            if fixtures_data.get('response'):
                fixture_id = fixtures_data['response'][0]['fixture']['id']
                print(f"Using fixture ID: {fixture_id}")

                # Now get lineups
                lineups_url = f"{BASE_URL}/fixtures/lineups"
                lineups_params = {"fixture": fixture_id}

                lineups_response = requests.get(lineups_url, headers=headers, params=lineups_params)
                if lineups_response.status_code == 200:
                    lineups_data = lineups_response.json()
                    print(f"\n✅ Lineups endpoint response:")
                    print(f"Response keys: {list(lineups_data.keys())}")

                    if lineups_data.get('response'):
                        home_team_data = lineups_data['response'][0]
                        print(f"\nHome team lineup structure:")
                        print(f"Keys: {list(home_team_data.keys())}")

                        if 'coach' in home_team_data:
                            print(f"\n✅ COACH DATA FOUND IN LINEUPS!")
                            print(f"Coach data structure:")
                            pprint(home_team_data['coach'], depth=2)
                            return home_team_data['coach']
                        else:
                            print(f"\n❌ No 'coach' key in lineup data")
                            print(f"Available keys: {list(home_team_data.keys())}")
                else:
                    print(f"❌ Lineups returned: {lineups_response.status_code}")
        else:
            print(f"❌ Fixtures returned: {fixtures_response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

    return None


def test_team_info_for_coach():
    """Test if team info includes coach."""
    print("\n" + "="*80)
    print("TEST 3: Testing /teams endpoint for coach data")
    print("="*80)

    url = f"{BASE_URL}/teams"
    params = {
        "id": "33",
        "league": "39",
        "season": "2024"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Teams endpoint response")

            if data.get('response'):
                team_data = data['response'][0]
                print(f"\nTeam data keys: {list(team_data.keys())}")

                if 'coach' in team_data:
                    print(f"\n✅ COACH DATA FOUND IN TEAMS!")
                    pprint(team_data['coach'], depth=2)
                    return team_data['coach']
                else:
                    print(f"\n❌ No coach data in teams endpoint")
        else:
            print(f"❌ Teams returned: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

    return None


def test_coach_statistics():
    """Test if there's a coach statistics endpoint."""
    print("\n" + "="*80)
    print("TEST 4: Testing potential coach statistics endpoints")
    print("="*80)

    # Try various possible endpoints
    endpoints_to_try = [
        "/coachs/statistics",
        "/coach/statistics",
        "/coaches/statistics",
        "/coachs/history",
        "/coachs/trophies"
    ]

    for endpoint in endpoints_to_try:
        url = f"{BASE_URL}{endpoint}"
        params = {"coach": "1"}  # Test with a coach ID

        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                print(f"\n✅ Found working endpoint: {endpoint}")
                data = response.json()
                if data.get('response'):
                    print(f"Response preview:")
                    pprint(data['response'][:1] if isinstance(data['response'], list) else data['response'], depth=2)
            elif response.status_code != 404:
                print(f"⚠️ {endpoint}: {response.status_code}")
        except Exception as e:
            print(f"❌ {endpoint}: {e}")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("API-FOOTBALL COACH/MANAGER DATA EXPLORATION")
    print("="*80)

    # Test 1: Dedicated coaches endpoint
    coach_from_coachs = test_coachs_endpoint()

    # Test 2: Lineups endpoint
    coach_from_lineups = test_lineups_for_coach()

    # Test 3: Teams endpoint
    coach_from_teams = test_team_info_for_coach()

    # Test 4: Statistics/History endpoints
    test_coach_statistics()

    # Summary
    print("\n" + "="*80)
    print("SUMMARY OF AVAILABLE COACH DATA")
    print("="*80)

    sources = []
    if coach_from_coachs:
        sources.append("✅ /coachs endpoint")
    if coach_from_lineups:
        sources.append("✅ /fixtures/lineups endpoint")
    if coach_from_teams:
        sources.append("✅ /teams endpoint")

    if sources:
        print("\nCoach data available from:")
        for source in sources:
            print(f"  {source}")
    else:
        print("\n❌ No coach data found in tested endpoints")

    print("\n" + "="*80)
    print("RECOMMENDATIONS FOR IMPLEMENTATION")
    print("="*80)

    if coach_from_coachs:
        print("\n✅ Use /coachs endpoint for detailed coach information")
        print("   Parameters: team, id, search")
        print("   Use Case: Get coach profile, career history, trophies")

    if coach_from_lineups:
        print("\n✅ Use /fixtures/lineups for match-specific coach info")
        print("   Use Case: Track which coach managed which match")

    if not sources:
        print("\n⚠️ Limited coach data available")
        print("   Consider using lineup data for basic coach tracking")


if __name__ == "__main__":
    main()
