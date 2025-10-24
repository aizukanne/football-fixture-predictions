#!/usr/bin/env python3
"""
Simple unit test to verify manager analysis integration.
Tests the code structure without making external API calls.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_neutral_tactical_params():
    """Test that neutral tactical params include manager fields."""
    print("\n" + "="*80)
    print("TEST: Manager Fields in Neutral Tactical Parameters")
    print("="*80)

    from src.parameters.team_calculator import get_neutral_tactical_params

    neutral_params = get_neutral_tactical_params()

    print("\n✅ Neutral tactical parameters retrieved successfully")

    # Check for manager fields
    expected_manager_fields = [
        'manager_name',
        'manager_experience',
        'manager_tactical_philosophy',
        'manager_preferred_system',
        'manager_formation_preferences',
        'manager_tactical_flexibility',
        'manager_tactical_rigidity',
        'manager_big_game_approach',
        'manager_profile_available'
    ]

    manager_fields_found = [field for field in expected_manager_fields if field in neutral_params]

    print(f"\nExpected {len(expected_manager_fields)} manager fields")
    print(f"Found {len(manager_fields_found)} manager fields")

    if len(manager_fields_found) == len(expected_manager_fields):
        print("\n✅ ALL manager fields present in neutral parameters!")
        for field in manager_fields_found:
            print(f"   - {field}: {neutral_params[field]}")
        return True
    else:
        missing = set(expected_manager_fields) - set(manager_fields_found)
        print(f"\n❌ Missing manager fields: {missing}")
        return False


def test_tactical_version():
    """Test that tactical version was updated to 4.1."""
    print("\n" + "="*80)
    print("TEST: Tactical Version Updated to 4.1")
    print("="*80)

    from src.parameters.team_calculator import get_neutral_tactical_params

    neutral_params = get_neutral_tactical_params()
    version = neutral_params.get('tactical_version')

    print(f"\nTactical version: {version}")

    if version == '4.1':
        print("✅ Version correctly updated to 4.1 (includes manager integration)")
        return True
    else:
        print(f"❌ Version is {version}, expected 4.1")
        return False


def main():
    """Run all simple tests."""
    print("\n" + "="*80)
    print("MANAGER ANALYSIS INTEGRATION - SIMPLE TEST SUITE")
    print("(No external API calls required)")
    print("="*80)

    results = []

    # Test 1: Manager fields in neutral params
    results.append(("Manager Fields Present", test_neutral_tactical_params()))

    # Test 2: Version updated
    results.append(("Tactical Version Updated", test_tactical_version()))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n✅ Manager Analysis Integration Complete:")
        print("   ✓ Manager fields added to tactical parameters")
        print("   ✓ Neutral parameters include manager defaults")
        print("   ✓ Version updated to 4.1")
        print("\n📊 Next Steps:")
        print("   1. Team parameters will now include manager data when calculated")
        print("   2. Manager data will be stored in DynamoDB with team params")
        print("   3. Predictions can access manager profile from team_params['tactical_params']")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
