#!/usr/bin/env python3
"""
Phase 0 Verification Test: Multiplier Contamination Prevention

This test verifies that the Phase 0 version tracking infrastructure successfully
prevents multiplier contamination and implements the hierarchical fallback strategy.

CRITICAL TEST SCENARIOS:
1. Version compatibility validation prevents contamination
2. Hierarchical fallback strategy works correctly
3. Version metadata is properly tracked
4. Legacy multipliers are filtered out
5. Transition manager prevents mixing v1.0 and v2.0 data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from decimal import Decimal
from datetime import datetime
import json

# Import the Phase 0 infrastructure
from src.infrastructure.version_manager import VersionManager, validate_multiplier_compatibility
from src.infrastructure.transition_manager import TransitionManager, get_transition_multipliers
from src.parameters.multiplier_calculator import MultiplierCalculator, calculate_team_multipliers
from src.parameters.team_calculator import fit_team_params, get_default_team_params
from src.parameters.league_calculator import fit_league_params, get_default_league_params
from src.prediction.prediction_engine import validate_prediction_inputs, create_prediction_with_metadata

print("=" * 80)
print("PHASE 0 MULTIPLIER CONTAMINATION PREVENTION TEST")
print("=" * 80)
print()

# Test 1: Version Compatibility Validation
print("TEST 1: Version Compatibility Validation")
print("-" * 50)

version_manager = VersionManager()
current_version = version_manager.get_current_version()

print(f"Current architecture version: {current_version}")

# Test v1.0 vs v2.0 compatibility (should FAIL)
compatible, reason = validate_multiplier_compatibility("1.0", "2.0")
print(f"v1.0 → v2.0 compatibility: {compatible} ({reason})")
assert not compatible, "v1.0 and v2.0 should NOT be compatible"

# Test v2.0 vs v2.0 compatibility (should PASS)
compatible, reason = validate_multiplier_compatibility("2.0", "2.0")
print(f"v2.0 → v2.0 compatibility: {compatible} ({reason})")
assert compatible, "v2.0 and v2.0 should be compatible"

print("✅ Version compatibility validation working correctly")
print()

# Test 2: Parameter Version Tracking
print("TEST 2: Parameter Version Tracking")
print("-" * 50)

# Create mock DataFrame for testing
import pandas as pd
mock_data = pd.DataFrame({
    'home_goals': [1, 2, 0, 3, 1],
    'away_goals': [0, 1, 1, 2, 2],
    'home_team_id': [1, 1, 1, 1, 1],
    'away_team_id': [2, 3, 4, 5, 6]
})

# Test team parameter calculation with version tracking
team_params = fit_team_params(mock_data, team_id=1, league_id=100)
print("Team parameters with version tracking:")
print(f"- Architecture version: {team_params.get('architecture_version')}")
print(f"- Calculation timestamp: {team_params.get('calculation_timestamp')}")
print(f"- Baseline flag: {team_params.get('baseline_flag')}")
print(f"- Contamination prevented: {team_params.get('contamination_prevented')}")

assert team_params.get('architecture_version') == current_version
assert team_params.get('contamination_prevented') == True
print("✅ Team parameters include proper version tracking")

# Test league parameter calculation with version tracking
league_params = fit_league_params(mock_data)
print(f"League architecture version: {league_params.get('architecture_version')}")
assert league_params.get('architecture_version') == current_version
print("✅ League parameters include proper version tracking")
print()

# Test 3: Hierarchical Fallback Strategy
print("TEST 3: Hierarchical Fallback Strategy")
print("-" * 50)

transition_manager = TransitionManager()

# Scenario 1: No compatible team or league multipliers → neutral baseline
empty_team_params = {'sample_size': 0}
empty_league_params = {'sample_size': 0}

result = transition_manager.get_effective_multipliers(empty_team_params, empty_league_params)
print("Scenario 1 - No compatible data:")
print(f"- Source: {result.get('source')}")
print(f"- Home multiplier: {result.get('home_multiplier')}")
print(f"- Confidence: {result.get('confidence')}")
assert result.get('source') == 'neutral_baseline_insufficient_clean_data'
assert result.get('home_multiplier') == Decimal('1.0')
print("✅ Falls back to neutral baseline correctly")

# Scenario 2: Valid team v2.0 parameters → use team level
good_team_params = {
    'architecture_version': '2.0',
    'sample_size': 20,
    'home_multiplier': Decimal('1.15'),
    'away_multiplier': Decimal('1.05'),
    'total_multiplier': Decimal('1.10'),
    'confidence': Decimal('0.8')
}

result = transition_manager.get_effective_multipliers(good_team_params, empty_league_params)
print("\nScenario 2 - Valid team v2.0 parameters:")
print(f"- Source: {result.get('source')}")
print(f"- Home multiplier: {result.get('home_multiplier')}")
assert result.get('source') == 'team_level_v2'
assert result.get('home_multiplier') == Decimal('1.15')
print("✅ Uses team-level v2.0 parameters correctly")

# Scenario 3: Contaminated v1.0 team parameters → fallback to neutral
contaminated_team_params = {
    'architecture_version': '1.0',  # Wrong version!
    'sample_size': 20,
    'home_multiplier': Decimal('1.50'),  # This would contaminate v2.0 predictions
    'away_multiplier': Decimal('1.30'),
    'total_multiplier': Decimal('1.40'),
    'confidence': Decimal('0.8')
}

result = transition_manager.get_effective_multipliers(contaminated_team_params, empty_league_params)
print("\nScenario 3 - Contaminated v1.0 team parameters:")
print(f"- Source: {result.get('source')}")
print(f"- Home multiplier: {result.get('home_multiplier')}")
print(f"- Fallback reasons: {result.get('fallback_reasons')}")
assert result.get('source') == 'neutral_baseline_insufficient_clean_data'
assert result.get('home_multiplier') == Decimal('1.0')  # Neutral, not contaminated 1.50
print("✅ Prevents contamination from v1.0 parameters")
print()

# Test 4: Multiplier Calculation with Version Filtering
print("TEST 4: Multiplier Calculation with Version Filtering")
print("-" * 50)

calculator = MultiplierCalculator()

# Mock fixture data with mixed versions
mixed_fixtures = [
    {
        'fixture_id': 1,
        'home': {'team_id': 1, 'predicted_goals': 1.5},
        'away': {'team_id': 2, 'predicted_goals': 1.2},
        'goals': {'home': 2, 'away': 1},
        'prediction_metadata': {'architecture_version': '1.0'}  # OLD VERSION
    },
    {
        'fixture_id': 2,
        'home': {'team_id': 1, 'predicted_goals': 1.8},
        'away': {'team_id': 3, 'predicted_goals': 1.0},
        'goals': {'home': 2, 'away': 0},
        'prediction_metadata': {'architecture_version': '2.0'}  # CURRENT VERSION
    },
    {
        'fixture_id': 3,
        'home': {'team_id': 1, 'predicted_goals': 1.6},
        'away': {'team_id': 4, 'predicted_goals': 1.1},
        'goals': {'home': 1, 'away': 2},
        'prediction_metadata': {'architecture_version': '2.0'}  # CURRENT VERSION
    }
]

# Test filtering to v2.0 only (should exclude fixture 1)
filtered_fixtures = calculator._filter_fixtures_by_version(mixed_fixtures, '2.0')
print(f"Original fixtures: {len(mixed_fixtures)}")
print(f"v2.0 filtered fixtures: {len(filtered_fixtures)}")
assert len(filtered_fixtures) == 2, "Should filter out v1.0 fixture"

# Test filtering to v1.0 only (should exclude fixtures 2 and 3)
filtered_fixtures = calculator._filter_fixtures_by_version(mixed_fixtures, '1.0')
print(f"v1.0 filtered fixtures: {len(filtered_fixtures)}")
assert len(filtered_fixtures) == 1, "Should filter out v2.0 fixtures"

print("✅ Version filtering prevents cross-contamination")
print()

# Test 5: Prediction Input Validation
print("TEST 5: Prediction Input Validation")
print("-" * 50)

# Test with valid v2.0 parameters
valid_params = {
    'mu_home': 1.5, 'mu_away': 1.2,
    'architecture_version': '2.0',
    'sample_size': 15
}

is_valid, message, (p1, p2) = validate_prediction_inputs(valid_params, valid_params)
print(f"Valid v2.0 parameters: {is_valid} ({message})")
assert is_valid, "Valid v2.0 parameters should pass validation"

# Test with contaminated v1.0 parameters
contaminated_params = {
    'mu_home': 1.5, 'mu_away': 1.2,
    'architecture_version': '1.0',  # CONTAMINATION RISK
    'sample_size': 15
}

is_valid, message, (p1, p2) = validate_prediction_inputs(contaminated_params, contaminated_params)
print(f"Contaminated v1.0 parameters: {is_valid} ({message})")
assert not is_valid, "v1.0 parameters should be rejected"
assert p1['architecture_version'] == '2.0', "Should return sanitized v2.0 parameters"
print("✅ Input validation prevents contaminated parameters")
print()

# Test 6: Complete Integration Test
print("TEST 6: Complete Integration Test")
print("-" * 50)

# Simulate a complete prediction workflow with contamination prevention
print("Simulating prediction workflow with contamination prevention...")

# Step 1: Calculate parameters (automatically get v2.0 version tracking)
team_params = get_default_team_params()
league_params = get_default_league_params()

# Step 2: Get effective multipliers through transition manager
effective_multipliers = get_transition_multipliers(team_params, league_params)
print(f"Effective multipliers source: {effective_multipliers.get('source')}")

# Step 3: Create prediction with metadata
mock_home_probs = {0: 0.1, 1: 0.3, 2: 0.4, 3: 0.2}
mock_away_probs = {0: 0.2, 1: 0.4, 2: 0.3, 3: 0.1}

prediction = create_prediction_with_metadata(
    mock_home_probs, mock_away_probs, 1.8, 1.3, effective_multipliers
)

# Verify prediction includes contamination prevention metadata
metadata = prediction.get('prediction_metadata', {})
print(f"Prediction architecture version: {metadata.get('architecture_version')}")
print(f"Contamination prevented: {metadata.get('contamination_prevented')}")

assert metadata.get('architecture_version') == current_version
assert metadata.get('contamination_prevented') == True

print("✅ Complete integration prevents contamination end-to-end")
print()

# Test 7: Baseline Definition Verification
print("TEST 7: Baseline Definition Verification")
print("-" * 50)

baseline_def = transition_manager.get_baseline_definition()
print("Baseline definition:")
print(f"- Definition: {baseline_def['definition']}")
print(f"- Components: {baseline_def['components']}")
print(f"- Excluded: {baseline_def['excluded_components']}")

assert 'correction_multipliers' in baseline_def['excluded_components']
assert 'segmented_parameter_by_opponent_tier' in baseline_def['components']
print("✅ Baseline excludes multipliers and includes enhanced components")
print()

# FINAL VERIFICATION
print("=" * 80)
print("PHASE 0 CONTAMINATION PREVENTION: ALL TESTS PASSED ✅")
print("=" * 80)
print()
print("VERIFIED CAPABILITIES:")
print("✅ Version compatibility validation prevents v1.0/v2.0 mixing")
print("✅ Hierarchical fallback strategy works correctly")
print("✅ Parameter calculations include version metadata")
print("✅ Multiplier calculations filter by version")
print("✅ Prediction engine validates input compatibility")
print("✅ Transition manager prevents contamination")
print("✅ Baseline definition excludes multipliers")
print()
print("CRITICAL RESULT: Multiplier contamination PREVENTED")
print("System ready for Phase 1 deployment with version tracking foundation!")
print()

# Save test results
test_results = {
    'timestamp': int(datetime.now().timestamp()),
    'architecture_version': current_version,
    'test_status': 'PASSED',
    'contamination_prevention': 'VERIFIED',
    'hierarchical_fallback': 'WORKING',
    'version_tracking': 'IMPLEMENTED',
    'ready_for_phase_1': True
}

with open('phase0_test_results.json', 'w') as f:
    json.dump(test_results, f, indent=2, default=str)

print(f"Test results saved to phase0_test_results.json")
print("Phase 0 implementation is COMPLETE and VERIFIED! 🎉")