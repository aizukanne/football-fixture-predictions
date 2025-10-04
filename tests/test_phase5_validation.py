"""
Phase 5 validation test - focuses on structural correctness rather than data operations.
"""

import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# Add src to path for imports
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

def test_team_classifier_structure():
    """Test team classifier has correct structure and functions."""
    print("Testing team classifier structure...")
    
    try:
        from src.features import team_classifier
        
        # Check required functions exist
        required_functions = [
            'classify_team_archetype',
            'get_team_performance_profile',
            'determine_team_archetypes',
            'get_archetype_prediction_weights'
        ]
        
        for func_name in required_functions:
            assert hasattr(team_classifier, func_name), f"Missing function: {func_name}"
        
        print("✅ All required functions present")
        
        # Test archetypes structure
        archetypes = team_classifier.determine_team_archetypes()
        assert len(archetypes) == 6, f"Expected 6 archetypes, got {len(archetypes)}"
        
        expected_archetypes = [
            'ELITE_CONSISTENT', 'TACTICAL_SPECIALISTS', 'MOMENTUM_DEPENDENT',
            'HOME_FORTRESS', 'BIG_GAME_SPECIALISTS', 'UNPREDICTABLE_CHAOS'
        ]
        
        for archetype in expected_archetypes:
            assert archetype in archetypes, f"Missing archetype: {archetype}"
            config = archetypes[archetype]
            assert 'description' in config, f"Missing description for {archetype}"
            assert 'prediction_strategy' in config, f"Missing prediction_strategy for {archetype}"
            assert 'confidence_modifier' in config, f"Missing confidence_modifier for {archetype}"
        
        print("✅ All 6 archetypes properly configured")
        return True
        
    except Exception as e:
        print(f"❌ Team classifier structure test failed: {e}")
        return False


def test_strategy_router_structure():
    """Test strategy router has correct structure."""
    print("\nTesting strategy router structure...")
    
    try:
        from src.features import strategy_router
        
        # Check required functions exist
        required_functions = [
            'route_prediction_strategy',
            'calculate_adaptive_weights',
            'get_archetype_matchup_dynamics',
            'select_prediction_ensemble'
        ]
        
        for func_name in required_functions:
            assert hasattr(strategy_router, func_name), f"Missing function: {func_name}"
        
        print("✅ All required functions present")
        
        # Test matchup dynamics work
        dynamics = strategy_router.get_archetype_matchup_dynamics('ELITE_CONSISTENT', 'HOME_FORTRESS')
        assert 'matchup_type' in dynamics, "Missing matchup_type"
        assert 'volatility_level' in dynamics, "Missing volatility_level"
        assert 'key_factors' in dynamics, "Missing key_factors"
        
        print("✅ Matchup dynamics structure correct")
        return True
        
    except Exception as e:
        print(f"❌ Strategy router structure test failed: {e}")
        return False


def test_enhanced_parameters_structure():
    """Test enhanced parameters structure."""
    print("\nTesting enhanced parameters structure...")
    
    try:
        from src.parameters import team_calculator
        
        # Check Phase 5 functions exist
        phase5_functions = [
            'calculate_classification_parameters',
            'get_neutral_classification_params',
            'apply_classification_adjustments_to_params',
            'get_classification_multiplier_for_prediction'
        ]
        
        for func_name in phase5_functions:
            assert hasattr(team_calculator, func_name), f"Missing Phase 5 function: {func_name}"
        
        print("✅ Phase 5 parameter functions present")
        
        # Test neutral classification params structure
        neutral_params = team_calculator.get_neutral_classification_params()
        
        required_keys = [
            'archetype', 'archetype_confidence', 'performance_profile',
            'prediction_weights', 'consistency_metrics', 'archetype_adjustments'
        ]
        
        for key in required_keys:
            assert key in neutral_params, f"Missing key in neutral params: {key}"
        
        print("✅ Classification parameters structure correct")
        return True
        
    except Exception as e:
        print(f"❌ Enhanced parameters structure test failed: {e}")
        return False


def test_prediction_engine_enhancements():
    """Test prediction engine has Phase 5 enhancements."""
    print("\nTesting prediction engine enhancements...")
    
    try:
        from src.prediction import prediction_engine
        
        # Check Phase 5 functions exist
        phase5_functions = [
            'calculate_adaptive_predictions',
            'analyze_archetype_based_predictions',
            'compare_prediction_strategies'
        ]
        
        for func_name in phase5_functions:
            assert hasattr(prediction_engine, func_name), f"Missing Phase 5 function: {func_name}"
        
        print("✅ Phase 5 prediction functions present")
        return True
        
    except Exception as e:
        print(f"❌ Prediction engine enhancement test failed: {e}")
        return False


def test_analytics_structure():
    """Test analytics module structure."""
    print("\nTesting analytics structure...")
    
    try:
        from src.analytics import archetype_performance
        
        # Check required functions exist
        required_functions = [
            'analyze_strategy_effectiveness',
            'track_archetype_accuracy',
            'optimize_archetype_weights',
            'generate_archetype_insights_report'
        ]
        
        for func_name in required_functions:
            assert hasattr(archetype_performance, func_name), f"Missing function: {func_name}"
        
        print("✅ Analytics functions present")
        return True
        
    except Exception as e:
        print(f"❌ Analytics structure test failed: {e}")
        return False


def test_integration_compatibility():
    """Test Phase 5 integration with existing phases."""
    print("\nTesting integration compatibility...")
    
    try:
        # Test that all Phase 5 imports work together
        from src.features.team_classifier import determine_team_archetypes, get_archetype_prediction_weights
        from src.features.strategy_router import get_archetype_matchup_dynamics, calculate_adaptive_weights
        from src.parameters.team_calculator import get_neutral_classification_params
        
        # Test archetype workflow
        archetypes = determine_team_archetypes()
        first_archetype = list(archetypes.keys())[0]
        
        # Test weights
        weights = get_archetype_prediction_weights(first_archetype)
        assert isinstance(weights, dict), "Weights should be dictionary"
        assert 'opponent_weight' in weights, "Missing opponent_weight"
        
        # Test adaptive weights
        match_context = {'venue_id': 1, 'prediction_date': datetime.now()}
        adaptive_weights = calculate_adaptive_weights('ELITE_CONSISTENT', 'HOME_FORTRESS', match_context)
        assert isinstance(adaptive_weights, dict), "Adaptive weights should be dictionary"
        
        # Test neutral params
        neutral = get_neutral_classification_params()
        assert neutral['archetype'] == 'UNPREDICTABLE_CHAOS', "Neutral archetype should be UNPREDICTABLE_CHAOS"
        
        print("✅ Phase 5 integration working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Integration compatibility test failed: {e}")
        return False


def run_validation():
    """Run all validation tests."""
    print("🧪 PHASE 5 VALIDATION TEST")
    print("=" * 60)
    
    tests = [
        ("Team Classifier Structure", test_team_classifier_structure),
        ("Strategy Router Structure", test_strategy_router_structure),
        ("Enhanced Parameters Structure", test_enhanced_parameters_structure),
        ("Prediction Engine Enhancements", test_prediction_engine_enhancements),
        ("Analytics Structure", test_analytics_structure),
        ("Integration Compatibility", test_integration_compatibility)
    ]
    
    passed = 0
    results = []
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                passed += 1
        except Exception as e:
            print(f"❌ Test crashed: {e}")
            results.append((test_name, False))
    
    print(f"\n{'='*60}")
    print("📊 VALIDATION RESULTS")
    print(f"{'='*60}")
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    total = len(tests)
    success_rate = (passed / total) * 100
    
    print(f"\n📈 Success Rate: {passed}/{total} tests passed ({success_rate:.1f}%)")
    
    if success_rate == 100:
        print("🎉 PHASE 5 VALIDATION SUCCESSFUL!")
        print("✅ All structural requirements met")
        print("✅ All integration points working")
        print("✅ Implementation is structurally complete")
        status = "VALIDATION_SUCCESS"
    elif success_rate >= 80:
        print("⚠️ PHASE 5 MOSTLY WORKING - Minor issues")
        status = "VALIDATION_MOSTLY_SUCCESS" 
    else:
        print("❌ PHASE 5 VALIDATION FAILED - Major issues")
        status = "VALIDATION_FAILED"
    
    return status, success_rate


if __name__ == "__main__":
    status, rate = run_validation()
    exit(0 if status == "VALIDATION_SUCCESS" else 1)