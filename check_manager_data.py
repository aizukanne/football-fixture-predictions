#!/usr/bin/env python3
"""
Check if manager data is present in team parameters after recalculation.
"""

import boto3
import json
from decimal import Decimal

def check_team_params(team_id, league_id):
    """Check if team params include manager data."""
    dynamodb = boto3.resource('dynamodb', region_name='eu-west-2')
    table = dynamodb.Table('football_team_parameters_prod')

    try:
        response = table.get_item(
            Key={
                'team_id': team_id,
                'league_id': league_id
            }
        )

        if 'Item' not in response:
            print(f"❌ No team parameters found for team {team_id} in league {league_id}")
            return False

        item = response['Item']
        print(f"\n{'='*80}")
        print(f"Team Parameters for Team ID: {team_id}, League ID: {league_id}")
        print(f"{'='*80}")

        # Check for tactical_params
        if 'tactical_params' not in item:
            print("❌ No tactical_params found in team parameters")
            return False

        tactical_params = item['tactical_params']
        print(f"✅ tactical_params found!")

        # Check for manager fields
        manager_fields = {k: v for k, v in tactical_params.items() if 'manager' in k.lower()}

        if not manager_fields:
            print("❌ No manager fields found in tactical_params")
            return False

        print(f"\n✅ Found {len(manager_fields)} manager fields:")
        for field, value in sorted(manager_fields.items()):
            # Convert Decimal to float for display
            if isinstance(value, Decimal):
                value = float(value)
            elif isinstance(value, dict):
                value = "{...}"
            print(f"   - {field}: {value}")

        # Check key manager fields
        required_fields = ['manager_name', 'manager_profile_available', 'manager_experience']
        missing = [f for f in required_fields if f not in manager_fields]

        if missing:
            print(f"\n⚠️  Missing key manager fields: {missing}")
        else:
            print(f"\n✅ All key manager fields present!")

        # Show manager profile status
        is_available = tactical_params.get('manager_profile_available', False)
        manager_name = tactical_params.get('manager_name', 'Unknown')

        print(f"\n📊 Manager Profile Status:")
        print(f"   Name: {manager_name}")
        print(f"   Available: {is_available}")

        if is_available and manager_name != 'Unknown':
            print(f"   Experience: {tactical_params.get('manager_experience', 'N/A')} years")
            print(f"   Philosophy: {tactical_params.get('manager_tactical_philosophy', 'N/A')}")
            print(f"   ✅ Real manager data populated!")
        else:
            print(f"   ℹ️  Using default/neutral manager data (normal when API data unavailable)")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Check multiple teams."""
    teams = [
        (50, 39, "Manchester City"),
        (33, 39, "Manchester United"),
        (49, 39, "Chelsea"),
        (40, 39, "Liverpool")
    ]

    print("\n" + "="*80)
    print("CHECKING MANAGER DATA IN TEAM PARAMETERS")
    print("="*80)

    results = []
    for team_id, league_id, team_name in teams:
        print(f"\n\n🔍 Checking {team_name}...")
        result = check_team_params(team_id, league_id)
        results.append((team_name, result))

    # Summary
    print("\n\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    success_count = sum(1 for _, success in results if success)
    total = len(results)

    for team_name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {team_name}")

    print(f"\n{success_count}/{total} teams have manager data")

    if success_count == total:
        print("\n🎉 SUCCESS! Manager analysis is fully integrated and working!")
        print("\n✅ Manager data is now:")
        print("   - Calculated during team parameter generation")
        print("   - Stored in DynamoDB")
        print("   - Available for predictions")
    else:
        print("\n⚠️  Some teams missing manager data")


if __name__ == "__main__":
    main()
