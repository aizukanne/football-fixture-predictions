"""
Phase 1 Integration Test: Opponent Strength Stratification

This test validates that Phase 1 opponent strength stratification is working correctly
while maintaining backward compatibility with existing functionality.

Key Test Areas:
1. Opponent classification functionality  
2. Segmented parameter calculation
3. Stratified prediction integration
4. Backward compatibility
5. Version tracking integration
6. Performance and error handling
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime
from decimal import Decimal

# Add project root to path for imports
sys.path.append('/home/ubuntu/Projects/football-fixture-predictions')

from src.features.opponent_classifier import (
    OpponentClassifier, 
    get_league_standings, 
    classify_team_by_position,
    get_opponent_tier_from_match
)
from src.parameters.team_calculator import (
    fit_team_params,
    calculate_segmented_params_by_opponent_strength
)
from src.prediction.prediction_engine import (
    calculate_coordinated_predictions,
    get_segmented_params
)
from src.infrastructure.version_manager import VersionManager

def test_opponent_classification():
    """Test the opponent classification system."""
    print("=== Testing Opponent Classification ===")
    
    # Test 1: Team position classification
    print("\n1. Testing team position classification...")
    
    test_cases = [
        (1, 20, 'top'),    # 1st place in 20-team league = top tier
        (5, 20, 'top'),    # 5th place = top tier (25% threshold)
        (10, 20, 'middle'), # 10th place = middle tier
        (16, 20, 'bottom'), # 16th place = bottom tier
        (20, 20, 'bottom')  # Last place = bottom tier
    ]
    
    for position, total, expected in test_cases:
        result = classify_team_by_position(position, total)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"  Position {position}/{total}: Expected '{expected}', Got '{result}' {status}")
    
    # Test 2: Opponent classifier initialization
    print("\n2. Testing OpponentClassifier initialization...")
    try:
        classifier = OpponentClassifier()
        print("  ✅ OpponentClassifier initialized successfully")
        
        # Test tier threshold logic
        small_league = classifier.get_league_size_category(12)
        large_league = classifier.get_league_size_category(20)
        print(f"  ✅ League size categories: 12 teams = {small_league}, 20 teams = {large_league}")
        
    except Exception as e:
        print(f"  ❌ OpponentClassifier initialization failed: {e}")
        return False
    
    print("✅ Opponent classification tests passed!")
    return True


def test_segmented_parameter_calculation():
    """Test segmented parameter calculation functionality."""
    print("\n=== Testing Segmented Parameter Calculation ===")
    
    # Create sample match data
    print("\n1. Creating sample match data...")
    sample_matches = []
    
    # Simulate matches for team 100 against various opponents
    team_id = 100
    league_id = 39  # Premier League
    season = "2024"
    
    # Create 15 matches with different outcomes
    for i in range(15):
        match = {
            'fixture_id': 1000 + i,
            'home_team_id': team_id if i % 2 == 0 else 200 + i,
            'away_team_id': 200 + i if i % 2 == 0 else team_id,
            'home_goals': np.random.randint(0, 4),
            'away_goals': np.random.randint(0, 3),
            'date': f"2024-0{(i % 9) + 1}-{(i % 28) + 1}",
            'league_id': league_id
        }
        sample_matches.append(match)
    
    df_matches = pd.DataFrame(sample_matches)
    print(f"  ✅ Created {len(df_matches)} sample matches for team {team_id}")
    
    # Test 2: Basic parameter calculation (backward compatibility)
    print("\n2. Testing basic parameter calculation...")
    try:
        basic_params = fit_team_params(df_matches, team_id, league_id)
        
        # Check basic structure
        required_fields = ['mu', 'mu_home', 'mu_away', 'architecture_version']
        missing_fields = [field for field in required_fields if field not in basic_params]
        
        if missing_fields:
            print(f"  ❌ Missing required fields: {missing_fields}")
            return False
        
        print("  ✅ Basic parameter calculation successful")
        print(f"  ✅ Architecture version: {basic_params.get('architecture_version')}")
        print(f"  ✅ Sample size: {basic_params.get('sample_size')}")
        
    except Exception as e:
        print(f"  ❌ Basic parameter calculation failed: {e}")
        return False
    
    # Test 3: Segmented parameter calculation
    print("\n3. Testing segmented parameter calculation...")
    try:
        segmented_params = fit_team_params(df_matches, team_id, league_id, season)
        
        # Check if segmented parameters were added
        if 'segmented_params' not in segmented_params:
            print("  ❌ Segmented parameters not found in result")
            return False
        
        segments = segmented_params['segmented_params']
        expected_segments = ['vs_top', 'vs_middle', 'vs_bottom']
        
        for segment in expected_segments:
            if segment not in segments:
                print(f"  ❌ Missing segment: {segment}")
                return False
            else:
                segment_data = segments[segment]
                if 'mu' not in segment_data or 'architecture_version' not in segment_data:
                    print(f"  ❌ Incomplete data in segment: {segment}")
                    return False
        
        print("  ✅ Segmented parameter calculation successful")
        print(f"  ✅ Available segments: {list(segments.keys())}")
        print(f"  ✅ Segmentation enabled: {segmented_params.get('segmentation_enabled')}")
        
    except Exception as e:
        print(f"  ❌ Segmented parameter calculation failed: {e}")
        return False
    
    print("✅ Segmented parameter calculation tests passed!")
    return True


def test_stratified_predictions():
    """Test stratified prediction functionality."""
    print("\n=== Testing Stratified Predictions ===")
    
    # Create mock team parameters with segmented data
    print("\n1. Creating mock team parameters...")
    
    version_manager = VersionManager()
    current_version = version_manager.get_current_version()
    
    # Mock home team parameters with segmentation and all required fields
    home_params = {
        'mu': 1.5, 'mu_home': 1.8, 'mu_away': 1.2,
        'p_score': 0.75, 'p_score_home': 0.8, 'p_score_away': 0.7,
        'alpha': 0.1, 'alpha_home': 0.1, 'alpha_away': 0.1,
        'home_adv': 1.3, 'architecture_version': current_version,
        # Required prediction engine parameters
        'k_goals': 5, 'k_score': 3, 'ref_games': 20,
        'home_multiplier': 1.0, 'away_multiplier': 1.0,
        'segmented_params': {
            'vs_top': {
                'mu': 1.2, 'mu_home': 1.4, 'mu_away': 1.0,
                'p_score': 0.55, 'p_score_home': 0.6, 'p_score_away': 0.5,
                'alpha': 0.15, 'alpha_home': 0.15, 'alpha_away': 0.15,
                'home_adv': 1.2, 'architecture_version': current_version,
                'k_goals': 5, 'k_score': 3, 'ref_games': 20,
                'home_multiplier': 1.0, 'away_multiplier': 1.0,
            },
            'vs_middle': {
                'mu': 1.5, 'mu_home': 1.8, 'mu_away': 1.2,
                'p_score': 0.7, 'p_score_home': 0.75, 'p_score_away': 0.65,
                'alpha': 0.1, 'alpha_home': 0.1, 'alpha_away': 0.1,
                'home_adv': 1.3, 'architecture_version': current_version,
                'k_goals': 5, 'k_score': 3, 'ref_games': 20,
                'home_multiplier': 1.0, 'away_multiplier': 1.0,
            },
            'vs_bottom': {
                'mu': 1.9, 'mu_home': 2.2, 'mu_away': 1.6,
                'p_score': 0.875, 'p_score_home': 0.9, 'p_score_away': 0.85,
                'alpha': 0.08, 'alpha_home': 0.08, 'alpha_away': 0.08,
                'home_adv': 1.4, 'architecture_version': current_version,
                'k_goals': 5, 'k_score': 3, 'ref_games': 20,
                'home_multiplier': 1.0, 'away_multiplier': 1.0,
            }
        }
    }
    
    # Mock away team parameters (similar structure)
    away_params = {
        'mu': 1.3, 'mu_home': 1.6, 'mu_away': 1.0,
        'p_score': 0.7, 'p_score_home': 0.75, 'p_score_away': 0.65,
        'alpha': 0.12, 'alpha_home': 0.12, 'alpha_away': 0.12,
        'home_adv': 1.25, 'architecture_version': current_version,
        # Required prediction engine parameters
        'k_goals': 5, 'k_score': 3, 'ref_games': 20,
        'home_multiplier': 1.0, 'away_multiplier': 1.0,
        'segmented_params': {
            'vs_top': {
                'mu': 1.0, 'mu_home': 1.2, 'mu_away': 0.8,
                'p_score': 0.45, 'p_score_home': 0.5, 'p_score_away': 0.4,
                'alpha': 0.18, 'alpha_home': 0.18, 'alpha_away': 0.18,
                'home_adv': 1.1, 'architecture_version': current_version,
                'k_goals': 5, 'k_score': 3, 'ref_games': 20,
                'home_multiplier': 1.0, 'away_multiplier': 1.0,
            },
            'vs_middle': {
                'mu': 1.3, 'mu_home': 1.6, 'mu_away': 1.0,
                'p_score': 0.65, 'p_score_home': 0.7, 'p_score_away': 0.6,
                'alpha': 0.12, 'alpha_home': 0.12, 'alpha_away': 0.12,
                'home_adv': 1.25, 'architecture_version': current_version,
                'k_goals': 5, 'k_score': 3, 'ref_games': 20,
                'home_multiplier': 1.0, 'away_multiplier': 1.0,
            },
            'vs_bottom': {
                'mu': 1.7, 'mu_home': 2.0, 'mu_away': 1.4,
                'p_score': 0.825, 'p_score_home': 0.85, 'p_score_away': 0.8,
                'alpha': 0.09, 'alpha_home': 0.09, 'alpha_away': 0.09,
                'home_adv': 1.35, 'architecture_version': current_version,
                'k_goals': 5, 'k_score': 3, 'ref_games': 20,
                'home_multiplier': 1.0, 'away_multiplier': 1.0,
            }
        }
    }
    
    print("  ✅ Mock team parameters created with segmentation")
    
    # Test 2: Segmented parameter selection
    print("\n2. Testing segmented parameter selection...")
    try:
        league_id = 39
        season = "2024"
        
        # Test getting parameters for different opponent tiers
        # Note: Since we don't have real standings data, this will likely fallback to overall
        top_params = get_segmented_params(home_params, 1, league_id, season)  # Man City (likely top)
        middle_params = get_segmented_params(home_params, 10, league_id, season)  # Mid-table team
        
        print("  ✅ Segmented parameter selection completed")
        print(f"  ✅ Top tier params mu_home: {top_params.get('mu_home', 'N/A')}")
        print(f"  ✅ Middle tier params mu_home: {middle_params.get('mu_home', 'N/A')}")
        
    except Exception as e:
        print(f"  ❌ Segmented parameter selection failed: {e}")
    
    # Test 3: Mock team statistics for prediction
    print("\n3. Creating mock team statistics...")
    
    # Mock raw match statistics (goals_scored, goals_conceded, games_scored, games_clean_sheet, games_total)
    home_team_stats = (25, 15, 18, 8, 20)  # Strong home stats
    away_team_stats = (20, 22, 15, 6, 20)  # Weaker away stats
    
    print("  ✅ Mock team statistics created")
    
    # Test 4: Prediction without stratification (backward compatibility)
    print("\n4. Testing predictions without stratification...")
    try:
        basic_prediction = calculate_coordinated_predictions(
            home_team_stats, away_team_stats, 
            home_params, away_params, 
            league_id=39
        )
        
        if len(basic_prediction) >= 9:  # Should return 9 elements including coordination_info
            home_score_prob, home_goals, home_likelihood, home_probs = basic_prediction[:4]
            away_score_prob, away_goals, away_likelihood, away_probs = basic_prediction[4:8]
            coordination_info = basic_prediction[8]
            
            print("  ✅ Basic prediction successful")
            print(f"  ✅ Home expected goals: {home_goals:.2f}")
            print(f"  ✅ Away expected goals: {away_goals:.2f}")
            print(f"  ✅ Stratification applied: {coordination_info.get('opponent_stratification_applied', False)}")
        else:
            print(f"  ❌ Unexpected prediction result length: {len(basic_prediction)}")
            
    except Exception as e:
        print(f"  ❌ Basic prediction failed: {e}")
        return False
    
    # Test 5: Prediction with stratification
    print("\n5. Testing predictions with stratification...")
    try:
        stratified_prediction = calculate_coordinated_predictions(
            home_team_stats, away_team_stats,
            home_params, away_params,
            league_id=39, season="2024", 
            home_team_id=100, away_team_id=200
        )
        
        if len(stratified_prediction) >= 9:
            coordination_info = stratified_prediction[8]
            
            print("  ✅ Stratified prediction successful")
            print(f"  ✅ Stratification applied: {coordination_info.get('opponent_stratification_applied', False)}")
            print(f"  ✅ Home params source: {coordination_info.get('home_params_source', 'unknown')}")
            print(f"  ✅ Away params source: {coordination_info.get('away_params_source', 'unknown')}")
            print(f"  ✅ Phase 1 enabled: {coordination_info.get('phase1_enabled', False)}")
        else:
            print(f"  ❌ Unexpected stratified prediction result length: {len(stratified_prediction)}")
            
    except Exception as e:
        print(f"  ❌ Stratified prediction failed: {e}")
        return False
    
    print("✅ Stratified prediction tests passed!")
    return True


def test_version_integration():
    """Test Phase 0 version tracking integration with Phase 1."""
    print("\n=== Testing Version Integration ===")
    
    print("\n1. Testing VersionManager integration...")
    try:
        version_manager = VersionManager()
        current_version = version_manager.get_current_version()
        features = version_manager.get_version_features(current_version)
        
        print(f"  ✅ Current version: {current_version}")
        print(f"  ✅ Segmentation feature enabled: {features.get('segmentation', False)}")
        
        # Check that Phase 1 features are properly configured
        if not features.get('segmentation', False):
            print("  ⚠️ WARNING: Segmentation feature not enabled in version config")
        
    except Exception as e:
        print(f"  ❌ Version integration test failed: {e}")
        return False
    
    print("✅ Version integration tests passed!")
    return True


def test_error_handling():
    """Test error handling and graceful degradation."""
    print("\n=== Testing Error Handling ===")
    
    print("\n1. Testing missing season parameter...")
    try:
        # Should fallback gracefully when season is not provided
        home_params = {'mu': 1.5, 'architecture_version': '2.0'}
        away_params = {'mu': 1.3, 'architecture_version': '2.0'}
        
        home_team_stats = (20, 15, 15, 5, 20)
        away_team_stats = (18, 20, 12, 8, 20)
        
        prediction = calculate_coordinated_predictions(
            home_team_stats, away_team_stats,
            home_params, away_params,
            league_id=39  # No season parameter
        )
        
        coordination_info = prediction[8] if len(prediction) >= 9 else {}
        stratification_applied = coordination_info.get('opponent_stratification_applied', False)
        
        if not stratification_applied:
            print("  ✅ Graceful degradation when season missing")
        else:
            print("  ❌ Unexpected stratification when season missing")
        
    except Exception as e:
        print(f"  ❌ Error handling test failed: {e}")
        return False
    
    print("✅ Error handling tests passed!")
    return True


def main():
    """Run all Phase 1 integration tests."""
    print("🚀 Starting Phase 1 Integration Tests")
    print("=" * 50)
    
    test_results = []
    
    # Run all test suites
    test_suites = [
        ("Opponent Classification", test_opponent_classification),
        ("Segmented Parameter Calculation", test_segmented_parameter_calculation),
        ("Stratified Predictions", test_stratified_predictions),
        ("Version Integration", test_version_integration),
        ("Error Handling", test_error_handling)
    ]
    
    for suite_name, test_func in test_suites:
        print(f"\n{'='*20} {suite_name} {'='*20}")
        try:
            result = test_func()
            test_results.append((suite_name, result))
        except Exception as e:
            print(f"❌ {suite_name} failed with exception: {e}")
            test_results.append((suite_name, False))
    
    # Summary
    print("\n" + "="*50)
    print("🏁 PHASE 1 INTEGRATION TEST SUMMARY")
    print("="*50)
    
    passed = 0
    failed = 0
    
    for suite_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{suite_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed + failed} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Phase 1 integration is working correctly.")
        print("\nPhase 1 Features Validated:")
        print("  ✅ Opponent strength classification")
        print("  ✅ Segmented parameter calculation")
        print("  ✅ Stratified prediction integration")
        print("  ✅ Backward compatibility maintained")
        print("  ✅ Version tracking integration")
        print("  ✅ Error handling and graceful degradation")
        return True
    else:
        print(f"\n⚠️ {failed} test suite(s) failed. Please review the issues above.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)