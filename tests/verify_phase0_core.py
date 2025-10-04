#!/usr/bin/env python3
"""
Phase 0 Core Verification: Multiplier Contamination Prevention

This is a minimal verification test that doesn't require external dependencies
and focuses on testing the core Phase 0 contamination prevention logic.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from decimal import Decimal
from datetime import datetime

# Import only the core Phase 0 infrastructure (no numpy dependencies)
from src.infrastructure.version_manager import VersionManager
from src.infrastructure.transition_manager import TransitionManager

print("=" * 80)
print("PHASE 0 CORE CONTAMINATION PREVENTION VERIFICATION")
print("=" * 80)
print()

def test_version_compatibility():
    """Test version compatibility validation."""
    print("TEST 1: Version Compatibility Validation")
    print("-" * 50)
    
    version_manager = VersionManager()
    current_version = version_manager.get_current_version()
    print(f"Current architecture version: {current_version}")
    
    # Test v1.0 vs v2.0 compatibility (should FAIL - prevents contamination)
    compatible, reason = version_manager.validate_multiplier_compatibility("1.0", "2.0")
    print(f"v1.0 → v2.0 compatibility: {compatible} ({reason})")
    
    if not compatible:
        print("✅ CRITICAL: v1.0 and v2.0 are correctly identified as incompatible")
    else:
        print("❌ ERROR: v1.0 and v2.0 should NOT be compatible!")
        return False
    
    # Test v2.0 vs v2.0 compatibility (should PASS)
    compatible, reason = version_manager.validate_multiplier_compatibility("2.0", "2.0")
    print(f"v2.0 → v2.0 compatibility: {compatible} ({reason})")
    
    if compatible:
        print("✅ v2.0 versions are correctly compatible")
    else:
        print("❌ ERROR: v2.0 should be compatible with itself!")
        return False
    
    print()
    return True

def test_hierarchical_fallback():
    """Test hierarchical fallback strategy."""
    print("TEST 2: Hierarchical Fallback Strategy")
    print("-" * 50)
    
    transition_manager = TransitionManager()
    
    # Test Case 1: No valid data → neutral baseline
    empty_team_params = {'sample_size': 0}
    empty_league_params = {'sample_size': 0}
    
    result = transition_manager.get_effective_multipliers(empty_team_params, empty_league_params)
    print("Case 1 - No valid data:")
    print(f"- Source: {result.get('source')}")
    print(f"- Home multiplier: {result.get('home_multiplier')}")
    print(f"- Confidence: {result.get('confidence')}")
    
    if (result.get('source') == 'neutral_baseline_insufficient_clean_data' and 
        result.get('home_multiplier') == Decimal('1.0')):
        print("✅ Correctly falls back to neutral baseline")
    else:
        print("❌ ERROR: Should fallback to neutral baseline!")
        return False
    
    # Test Case 2: Valid v2.0 team data → use team level
    good_team_params = {
        'architecture_version': '2.0',
        'sample_size': 20,
        'home_multiplier': Decimal('1.15'),
        'away_multiplier': Decimal('1.05'),
        'total_multiplier': Decimal('1.10'),
        'confidence': Decimal('0.8')
    }
    
    result = transition_manager.get_effective_multipliers(good_team_params, empty_league_params)
    print("\nCase 2 - Valid v2.0 team data:")
    print(f"- Source: {result.get('source')}")
    print(f"- Home multiplier: {result.get('home_multiplier')}")
    
    if (result.get('source') == 'team_level_v2' and 
        result.get('home_multiplier') == Decimal('1.15')):
        print("✅ Correctly uses team-level v2.0 data")
    else:
        print("❌ ERROR: Should use team-level v2.0 data!")
        return False
    
    # Test Case 3: Contaminated v1.0 data → reject and use neutral
    contaminated_params = {
        'architecture_version': '1.0',  # CONTAMINATION RISK!
        'sample_size': 20,
        'home_multiplier': Decimal('1.50'),  # Would contaminate v2.0 predictions
        'away_multiplier': Decimal('1.30'),
        'confidence': Decimal('0.8')
    }
    
    result = transition_manager.get_effective_multipliers(contaminated_params, empty_league_params)
    print("\nCase 3 - Contaminated v1.0 data:")
    print(f"- Source: {result.get('source')}")
    print(f"- Home multiplier: {result.get('home_multiplier')}")
    print(f"- Fallback reasons: {result.get('fallback_reasons', [])}")
    
    if (result.get('source') == 'neutral_baseline_insufficient_clean_data' and 
        result.get('home_multiplier') == Decimal('1.0')):
        print("✅ CRITICAL: Contaminated v1.0 data correctly rejected!")
    else:
        print("❌ CRITICAL ERROR: Contaminated data was not rejected!")
        return False
    
    print()
    return True

def test_version_metadata():
    """Test version metadata generation."""
    print("TEST 3: Version Metadata Generation")
    print("-" * 50)
    
    version_manager = VersionManager()
    metadata = version_manager.get_version_metadata()
    
    print("Version metadata:")
    for key, value in metadata.items():
        print(f"- {key}: {value}")
    
    required_fields = ['version', 'features', 'compatible_versions']
    missing_fields = [field for field in required_fields if field not in metadata]
    
    if not missing_fields:
        print("✅ All required metadata fields present")
    else:
        print(f"❌ ERROR: Missing metadata fields: {missing_fields}")
        return False
    
    # Check v2.0 features
    features = metadata.get('features', {})
    expected_v2_features = {
        'segmentation': True,
        'form_adjustment': True,
        'tactical_features': True
    }
    
    features_match = all(features.get(key) == value for key, value in expected_v2_features.items())
    
    if features_match:
        print("✅ v2.0 features correctly defined")
    else:
        print("❌ ERROR: v2.0 features mismatch!")
        return False
    
    print()
    return True

def test_baseline_definition():
    """Test baseline definition."""
    print("TEST 4: Baseline Definition")
    print("-" * 50)
    
    transition_manager = TransitionManager()
    baseline = transition_manager.get_baseline_definition()
    
    print("Baseline definition:")
    print(f"- Definition: {baseline.get('definition')}")
    print(f"- Components: {baseline.get('components', [])}")
    print(f"- Excluded: {baseline.get('excluded_components', [])}")
    
    # Critical check: multipliers should be EXCLUDED from baseline
    excluded = baseline.get('excluded_components', [])
    if 'correction_multipliers' in excluded:
        print("✅ CRITICAL: Multipliers correctly excluded from baseline")
    else:
        print("❌ CRITICAL ERROR: Multipliers not excluded from baseline!")
        return False
    
    # Check that enhanced components are included
    components = baseline.get('components', [])
    if 'segmented_parameter_by_opponent_tier' in components:
        print("✅ Enhanced v2.0 components included in baseline")
    else:
        print("❌ ERROR: Enhanced components missing from baseline!")
        return False
    
    print()
    return True

def test_data_integrity_validation():
    """Test data integrity validation."""
    print("TEST 5: Data Integrity Validation")
    print("-" * 50)
    
    transition_manager = TransitionManager()
    
    # Test valid v2.0 data
    valid_data = {
        'architecture_version': '2.0',
        'sample_size': 15,
        'calculation_count': 15,
        'contamination_prevented': True
    }
    
    is_valid, message = transition_manager.validate_data_integrity(valid_data, '2.0')
    print(f"Valid v2.0 data: {is_valid} ({message})")
    
    if is_valid:
        print("✅ Valid data passes integrity check")
    else:
        print("❌ ERROR: Valid data failed integrity check!")
        return False
    
    # Test contaminated data (missing version)
    contaminated_data = {
        'sample_size': 15,
        'home_multiplier': Decimal('1.5')
        # Missing 'architecture_version' - contamination risk!
    }
    
    is_valid, message = transition_manager.validate_data_integrity(contaminated_data, '2.0')
    print(f"Contaminated data: {is_valid} ({message})")
    
    if not is_valid:
        print("✅ CRITICAL: Contaminated data correctly rejected")
    else:
        print("❌ CRITICAL ERROR: Contaminated data was accepted!")
        return False
    
    print()
    return True

# Run all tests
def main():
    tests = [
        test_version_compatibility,
        test_hierarchical_fallback,
        test_version_metadata,
        test_baseline_definition,
        test_data_integrity_validation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print("TEST FAILED!")
        except Exception as e:
            print(f"TEST ERROR: {e}")
    
    print("=" * 80)
    print(f"PHASE 0 VERIFICATION RESULTS: {passed}/{total} TESTS PASSED")
    print("=" * 80)
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print()
        print("VERIFIED CAPABILITIES:")
        print("✅ Version compatibility prevents v1.0/v2.0 contamination")
        print("✅ Hierarchical fallback strategy working correctly")
        print("✅ Version metadata properly generated")
        print("✅ Baseline definition excludes multipliers")
        print("✅ Data integrity validation prevents contamination")
        print()
        print("🚀 PHASE 0 IMPLEMENTATION IS COMPLETE AND VERIFIED!")
        print("   System is ready for Phase 1 deployment!")
        print("   Multiplier contamination has been PREVENTED!")
        
        return True
    else:
        print("❌ SOME TESTS FAILED!")
        print("   Phase 0 implementation needs fixes before Phase 1 deployment.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)