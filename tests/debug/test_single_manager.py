#!/usr/bin/env python3
"""
Quick test to check if we can get real manager data for one team.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("\n" + "="*80)
print("QUICK MANAGER API TEST")
print("="*80)

try:
    print("\n1. Testing API client direct call...")
    from src.data.api_client import get_coach_by_team

    team_id = 50  # Manchester City

    print(f"   Calling get_coach_by_team({team_id})")

    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError("API call timed out after 30 seconds")

    # Set 30 second timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)

    try:
        coach_data = get_coach_by_team(team_id)
        signal.alarm(0)  # Cancel alarm

        if coach_data:
            print(f"\n✅ API Response received!")
            print(f"   Response type: {type(coach_data)}")

            # Handle both dict and list responses
            if isinstance(coach_data, dict):
                coach = coach_data
            elif isinstance(coach_data, list) and len(coach_data) > 0:
                coach = coach_data[0]
            else:
                print(f"\n⚠️  Unexpected format: {coach_data}")
                coach = None

            if coach:
                name = coach.get('name', 'Unknown')
                coach_id = coach.get('id', 0)

                print(f"\n   Coach ID: {coach_id}")
                print(f"   Coach Name: {name}")
                print(f"   Age: {coach.get('age', 'N/A')}")
                print(f"   Nationality: {coach.get('nationality', 'N/A')}")

                # Show full response
                print(f"\n   Full Response:")
                import json
                print(json.dumps(coach, indent=2, default=str))

                if name and name != 'Unknown' and coach_id != 0:
                    print(f"\n🎉 SUCCESS! Real manager data is available!")
                    print(f"   Manager: {name}")
                else:
                    print(f"\n⚠️  API returned but data is default/unknown")
        else:
            print(f"\n❌ API returned None/empty")

    except TimeoutError as e:
        signal.alarm(0)
        print(f"\n⏱️  Timeout: {e}")
        print("   API call took too long (>30s)")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)

print("""
If you saw real manager names (e.g., "Pep Guardiola"):
  ✅ API integration is working
  ✅ Real manager data will be used in predictions

If you saw "Unknown" or timeout:
  ⚠️  API credentials may be invalid or rate-limited
  ℹ️  System will use neutral defaults (no impact on stability)
  ℹ️  Manager multipliers will be 1.0 (neutral, no adjustment)
""")
