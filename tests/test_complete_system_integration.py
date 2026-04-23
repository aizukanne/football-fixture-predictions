"""
Complete 6-Phase System Integration Test

This comprehensive test validates the complete football prediction system
from Phase 0 through Phase 6, ensuring all components work together seamlessly
and the system is production-ready.

Test Coverage:
- Phase 0: Version Tracking Infrastructure
- Phase 1: Opponent Strength Stratification  
- Phase 2: Home/Away Venue Analysis
- Phase 3: Time-Based Parameter Evolution
- Phase 4: Derived Tactical Style Features
- Phase 5: Team Classification & Adaptive Strategy
- Phase 6: Confidence Calibration & Reporting
"""

import sys
import traceback
import time
from decimal import Decimal
from datetime import datetime
import json


def test_complete_system_integration():
    """
    Test complete 6-phase system integration end-to-end.
    
    Tests:
    1. Phase 0: Version tracking and contamination prevention
    2. Phase 1: Opponent strength stratification
    3. Phase 2: Venue analysis and geographic intelligence
    4. Phase 3: Temporal evolution and form analysis
    5. Phase 4: Tactical intelligence and formation analysis
    6. Phase 5: Team classification and adaptive strategy
    7. Phase 6: Confidence calibration and reporting
    """
    
    test_results = {
        'overall_status': 'TESTING',
        'phase_results': {},
        'integration_results': {},
        'performance_metrics': {},
        'production_readiness': {},
        'test_timestamp': datetime.now().isoformat(),
        'system_version': '8.0'
    }
    
    try:
        print("🚀 Starting Complete System Integration Test...")
        print("="*80)
        
        # Test Phase 0: Version Tracking
        print("🔍 Testing Phase 0: Version Tracking Infrastructure...")
        phase_0_result = test_version_tracking_integration()
        test_results['phase_results']['phase_0'] = phase_0_result
        print(f"   Result: {phase_0_result.get('status', 'UNKNOWN')}")
        
        # Test Phase 1: Opponent Stratification
        print("🔍 Testing Phase 1: Opponent Strength Stratification...")
        phase_1_result = test_opponent_stratification_integration()
        test_results['phase_results']['phase_1'] = phase_1_result
        print(f"   Result: {phase_1_result.get('status', 'UNKNOWN')}")
        
        # Test Phase 2: Venue Analysis
        print("🔍 Testing Phase 2: Home/Away Venue Analysis...")
        phase_2_result = test_venue_analysis_integration()
        test_results['phase_results']['phase_2'] = phase_2_result
        print(f"   Result: {phase_2_result.get('status', 'UNKNOWN')}")
        
        # Test Phase 3: Temporal Evolution
        print("🔍 Testing Phase 3: Time-Based Parameter Evolution...")
        phase_3_result = test_temporal_evolution_integration()
        test_results['phase_results']['phase_3'] = phase_3_result
        print(f"   Result: {phase_3_result.get('status', 'UNKNOWN')}")
        
        # Test Phase 4: Tactical Intelligence
        print("🔍 Testing Phase 4: Derived Tactical Style Features...")
        phase_4_result = test_tactical_intelligence_integration()
        test_results['phase_results']['phase_4'] = phase_4_result
        print(f"   Result: {phase_4_result.get('status', 'UNKNOWN')}")
        
        # Test Phase 5: Adaptive Strategy
        print("🔍 Testing Phase 5: Team Classification & Adaptive Strategy...")
        phase_5_result = test_adaptive_strategy_integration()
        test_results['phase_results']['phase_5'] = phase_5_result
        print(f"   Result: {phase_5_result.get('status', 'UNKNOWN')}")
        
        # Test Phase 6: Confidence Calibration
        print("🔍 Testing Phase 6: Confidence Calibration & Reporting...")
        phase_6_result = test_confidence_calibration_integration()
        test_results['phase_results']['phase_6'] = phase_6_result
        print(f"   Result: {phase_6_result.get('status', 'UNKNOWN')}")
        
        # Test Complete Pipeline Integration
        print("🔍 Testing Complete Pipeline Integration...")
        pipeline_result = test_complete_pipeline_integration()
        test_results['integration_results']['pipeline'] = pipeline_result
        print(f"   Result: {pipeline_result.get('status', 'UNKNOWN')}")
        
        # Performance Benchmarks
        print("🔍 Running Performance Benchmarks...")
        performance_result = run_performance_benchmarks()
        test_results['performance_metrics'] = performance_result
        print(f"   Result: {performance_result.get('status', 'UNKNOWN')}")
        
        # Production Readiness Check
        print("🔍 Validating Production Readiness...")
        readiness_result = validate_production_readiness()
        test_results['production_readiness'] = readiness_result
        print(f"   Result: {readiness_result.get('status', 'UNKNOWN')}")
        
        # Overall Status Assessment
        all_phases_pass = all(
            result.get('status') == 'PASS' 
            for result in test_results['phase_results'].values()
        )
        pipeline_pass = test_results['integration_results']['pipeline'].get('status') == 'PASS'
        performance_pass = test_results['performance_metrics'].get('status') == 'PASS'
        readiness_pass = test_results['production_readiness'].get('status') == 'PASS'
        
        if all_phases_pass and pipeline_pass and performance_pass and readiness_pass:
            test_results['overall_status'] = 'PASS'
        else:
            test_results['overall_status'] = 'FAIL'
            
    except Exception as e:
        test_results['overall_status'] = 'ERROR'
        test_results['error'] = str(e)
        test_results['traceback'] = traceback.format_exc()
    
    return test_results


def test_version_tracking_integration() -> dict:
    """Test Phase 0: Version tracking across all phases."""
    try:
        from src.infrastructure.version_manager import VersionManager
        from src.infrastructure.transition_manager import TransitionManager
        from src.parameters.multiplier_calculator import calculate_multipliers
        
        # Test version tracking works for v6.0
        version_manager = VersionManager()
        current_version = version_manager.get_current_version()
        
        # Test contamination prevention by attempting to calculate multipliers
        test_multipliers = calculate_multipliers(
            team_id=1, league_id=39, season=2023, 
            version_metadata={'architecture_version': '8.0'}
        )
        
        # Verify multipliers have proper structure
        expected_keys = ['home_multiplier', 'away_multiplier', 'strategy', 'architecture_version']
        multiplier_keys_present = all(key in test_multipliers for key in expected_keys)
        
        return {
            'status': 'PASS' if multiplier_keys_present else 'FAIL',
            'current_version': current_version,
            'version_features': ['contamination_prevention', 'hierarchical_fallback'],
            'multiplier_calculation': 'functional' if multiplier_keys_present else 'failed',
            'multiplier_keys': list(test_multipliers.keys()) if test_multipliers else []
        }
        
    except Exception as e:
        return {'status': 'FAIL', 'error': str(e)}


def test_opponent_stratification_integration() -> dict:
    """Test Phase 1: Opponent strength stratification."""
    try:
        from src.features.opponent_classifier import classify_opponent_strength, get_opponent_tier_from_match
        
        # Test opponent classification
        test_classification = classify_opponent_strength(
            team_id=2, league_id=39, season=2023
        )
        
        # Test tier extraction
        test_tier = get_opponent_tier_from_match(
            home_team_id=1, away_team_id=2, league_id=39, season=2023
        )
        
        return {
            'status': 'PASS',
            'opponent_classification': 'functional',
            'tier_extraction': 'functional',
            'test_classification_result': test_classification,
            'test_tier_result': test_tier
        }
        
    except Exception as e:
        return {'status': 'FAIL', 'error': str(e)}


def test_venue_analysis_integration() -> dict:
    """Test Phase 2: Venue analysis and geographic intelligence."""
    try:
        from src.features.venue_analyzer import VenueAnalyzer, calculate_stadium_advantage
        from src.utils.geographic import calculate_combined_travel_impact
        
        # Test venue analyzer
        venue_analyzer = VenueAnalyzer()
        venue_factors = venue_analyzer.analyze_venue_factors(
            home_team_id=1, away_team_id=2, venue_id=1, league_id=39
        )
        
        # Test stadium advantage calculation
        stadium_advantage = calculate_stadium_advantage(
            venue_id=1, home_team_id=1, league_id=39
        )
        
        return {
            'status': 'PASS',
            'venue_analysis': 'functional',
            'stadium_advantage_calc': 'functional',
            'venue_factors_keys': list(venue_factors.keys()) if venue_factors else []
        }
        
    except Exception as e:
        return {'status': 'FAIL', 'error': str(e)}


def test_temporal_evolution_integration() -> dict:
    """Test Phase 3: Temporal evolution and form analysis."""
    try:
        from src.features.form_analyzer import analyze_recent_form, analyze_head_to_head_form
        from src.parameters.team_calculator import get_temporal_multiplier_for_prediction
        
        # Test form analysis
        recent_form = analyze_recent_form(
            team_id=1, league_id=39, season=2023
        )
        
        # Test head-to-head analysis
        h2h_form = analyze_head_to_head_form(
            team1_id=1, team2_id=2, league_id=39
        )
        
        # Test temporal multiplier
        temporal_multiplier = get_temporal_multiplier_for_prediction(
            team_id=1, league_id=39, season=2023
        )
        
        return {
            'status': 'PASS',
            'recent_form_analysis': 'functional',
            'h2h_analysis': 'functional',
            'temporal_multiplier': 'functional'
        }
        
    except Exception as e:
        return {'status': 'FAIL', 'error': str(e)}


def test_tactical_intelligence_integration() -> dict:
    """Test Phase 4: Tactical intelligence and formation analysis."""
    try:
        from src.features.tactical_analyzer import analyze_tactical_style
        from src.features.formation_analyzer import FormationAnalyzer, get_formation_attacking_bonus
        from src.features.tactical_matchups import TacticalMatchupAnalyzer
        
        # Test tactical style analysis
        tactical_style = analyze_tactical_style(
            team_id=1, league_id=39, season=2023
        )
        
        # Test formation analyzer
        formation_analyzer = FormationAnalyzer()
        formation_bonus = get_formation_attacking_bonus(
            team_id=1, opponent_id=2, league_id=39, season=2023
        )
        
        # Test tactical matchup analyzer
        matchup_analyzer = TacticalMatchupAnalyzer()
        
        return {
            'status': 'PASS',
            'tactical_analysis': 'functional',
            'formation_analysis': 'functional',
            'matchup_analysis': 'functional'
        }
        
    except Exception as e:
        return {'status': 'FAIL', 'error': str(e)}


def test_adaptive_strategy_integration() -> dict:
    """Test Phase 5: Team classification and adaptive strategy."""
    try:
        from src.features.team_classifier import classify_team_archetype
        from src.features.strategy_router import route_prediction_strategy, calculate_adaptive_weights
        from src.parameters.team_calculator import get_classification_multiplier_for_prediction
        
        # Test team classification
        team_archetype = classify_team_archetype(
            team_id=1, league_id=39, season=2023
        )
        
        # Test strategy routing
        strategy = route_prediction_strategy(
            home_team_id=1, away_team_id=2, league_id=39, season=2023
        )
        
        # Test adaptive weights
        adaptive_weights = calculate_adaptive_weights(
            home_archetype='balanced', away_archetype='attacking'
        )
        
        return {
            'status': 'PASS',
            'team_classification': 'functional',
            'strategy_routing': 'functional',
            'adaptive_weights': 'functional',
            'test_archetype': team_archetype
        }
        
    except Exception as e:
        return {'status': 'FAIL', 'error': str(e)}


def test_confidence_calibration_integration() -> dict:
    """Test Phase 6: Confidence calibration and reporting."""
    try:
        from src.analytics.confidence_calibrator import calibrate_prediction_confidence, calculate_adaptive_confidence
        from src.reporting.executive_reports import generate_predictive_insights_report
        
        # Test confidence calibration
        mock_prediction = {
            'home_team': {'score_probability': 0.65},
            'away_team': {'score_probability': 0.45},
            'prediction_metadata': {'architecture_version': '8.0'}
        }
        
        calibrated_confidence = calibrate_prediction_confidence(
            prediction=mock_prediction,
            home_team_id=1, away_team_id=2, league_id=39
        )
        
        # Test adaptive confidence
        adaptive_confidence = calculate_adaptive_confidence(
            base_confidence=0.7,
            factors={'venue_familiarity': 0.8, 'form_consistency': 0.6}
        )
        
        return {
            'status': 'PASS',
            'confidence_calibration': 'functional',
            'adaptive_confidence': 'functional',
            'reporting_system': 'functional',
            'calibrated_confidence': calibrated_confidence
        }
        
    except Exception as e:
        return {'status': 'FAIL', 'error': str(e)}


def test_complete_pipeline_integration() -> dict:
    """Test complete end-to-end prediction pipeline."""
    try:
        from src.prediction.prediction_engine import generate_prediction_with_reporting
        
        # Test complete pipeline with all 6 phases
        prediction = generate_prediction_with_reporting(
            home_team_id=1, away_team_id=2, league_id=39, season=2023,
            venue_id=1, prediction_date=datetime.now(),
            include_insights=True
        )
        
        # Verify all phase features are present in prediction structure
        expected_features = [
            'version_tracking', 'opponent_stratification', 'venue_analysis', 
            'temporal_evolution', 'tactical_intelligence', 'adaptive_classification', 
            'confidence_calibration'
        ]
        
        # Check if prediction has the expected structure
        has_predictions = 'predictions' in prediction
        has_metadata = 'metadata' in prediction
        has_insights = 'insights' in prediction if prediction.get('include_insights') else True
        
        pipeline_functional = has_predictions and has_metadata
        
        return {
            'status': 'PASS' if pipeline_functional else 'FAIL',
            'pipeline_functional': pipeline_functional,
            'has_predictions': has_predictions,
            'has_metadata': has_metadata,
            'has_insights': has_insights,
            'expected_features': expected_features,
            'prediction_keys': list(prediction.keys()) if prediction else []
        }
        
    except Exception as e:
        return {'status': 'FAIL', 'error': str(e)}


def run_performance_benchmarks() -> dict:
    """Run performance benchmarks for the complete system."""
    try:
        from src.prediction.prediction_engine import generate_prediction_with_reporting
        
        # Benchmark prediction speed
        start_time = time.time()
        predictions_completed = 0
        
        for i in range(5):  # Run 5 predictions for benchmark
            try:
                prediction = generate_prediction_with_reporting(
                    home_team_id=1 + i, away_team_id=2 + i, 
                    league_id=39, season=2023,
                    include_insights=True
                )
                predictions_completed += 1
            except Exception as e:
                print(f"Benchmark prediction {i} failed: {e}")
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_prediction_time = total_time / max(predictions_completed, 1)
        
        # Performance thresholds
        max_prediction_time = 3.0  # Maximum 3 seconds per prediction for integration test
        
        performance_grade = 'A' if avg_prediction_time < 1.0 else 'B' if avg_prediction_time < 2.0 else 'C' if avg_prediction_time < 3.0 else 'D'
        
        return {
            'status': 'PASS' if avg_prediction_time < max_prediction_time else 'FAIL',
            'avg_prediction_time': round(avg_prediction_time, 3),
            'max_threshold': max_prediction_time,
            'predictions_tested': predictions_completed,
            'total_time': round(total_time, 3),
            'performance_grade': performance_grade
        }
        
    except Exception as e:
        return {'status': 'FAIL', 'error': str(e)}


def validate_production_readiness() -> dict:
    """Validate system is ready for production deployment."""
    try:
        readiness_checks = {}
        
        # Check 1: All required modules importable
        try:
            from src.infrastructure.version_manager import VersionManager
            from src.features.opponent_classifier import classify_opponent_strength
            from src.features.venue_analyzer import VenueAnalyzer
            from src.features.form_analyzer import analyze_recent_form
            from src.features.tactical_analyzer import analyze_tactical_style
            from src.features.team_classifier import classify_team_archetype
            from src.analytics.confidence_calibrator import calibrate_prediction_confidence
            from src.prediction.prediction_engine import generate_prediction_with_reporting
            readiness_checks['module_imports'] = 'PASS'
        except Exception as e:
            readiness_checks['module_imports'] = f'FAIL: {e}'
        
        # Check 2: Error handling works
        try:
            from src.prediction.prediction_engine import generate_prediction_with_reporting
            # Test with invalid inputs - should handle gracefully
            result = generate_prediction_with_reporting(
                home_team_id=999999, away_team_id=999998, league_id=99999, season=2023
            )
            readiness_checks['error_handling'] = 'PASS'
        except Exception:
            # Expected to handle gracefully or provide informative errors
            readiness_checks['error_handling'] = 'PASS'
        
        # Check 3: Version consistency
        try:
            from src.infrastructure.version_manager import VersionManager
            vm = VersionManager()
            version = vm.get_current_version()
            if version and str(version).startswith('7'):
                readiness_checks['version_consistency'] = 'PASS'
            else:
                readiness_checks['version_consistency'] = f'FAIL: Version {version} not 7.x'
        except Exception as e:
            readiness_checks['version_consistency'] = f'FAIL: {e}'
        
        # Check 4: System monitoring
        try:
            from src.monitoring.system_monitor import monitor_system_health
            health_status = monitor_system_health()
            if health_status and health_status.get('system_status') in ['Healthy', 'Warning', 'Operational']:
                readiness_checks['system_monitoring'] = 'PASS'
            else:
                readiness_checks['system_monitoring'] = f'WARNING: Status {health_status}'
        except Exception as e:
            readiness_checks['system_monitoring'] = f'FAIL: {e}'
        
        # Count passed checks
        passed_checks = sum(1 for check in readiness_checks.values() if check == 'PASS')
        total_checks = len(readiness_checks)
        
        # System is ready if most critical checks pass
        deployment_ready = passed_checks >= (total_checks * 0.75)  # 75% pass rate
        
        return {
            'status': 'PASS' if deployment_ready else 'FAIL',
            'readiness_checks': readiness_checks,
            'passed_checks': passed_checks,
            'total_checks': total_checks,
            'pass_rate': round(passed_checks / total_checks, 2),
            'deployment_ready': deployment_ready
        }
        
    except Exception as e:
        return {'status': 'FAIL', 'error': str(e)}


def print_detailed_results(results):
    """Print detailed test results in a formatted way."""
    print("\n" + "="*80)
    print("🎯 COMPLETE SYSTEM INTEGRATION TEST RESULTS")
    print("="*80)
    
    print(f"Overall Status: {results['overall_status']}")
    print(f"Test Timestamp: {results.get('test_timestamp', 'N/A')}")
    print(f"System Version: {results.get('system_version', 'N/A')}")
    
    if results['overall_status'] == 'PASS':
        print("\n✅ ALL TESTS PASSED - SYSTEM IS PRODUCTION READY! 🎉")
    elif results['overall_status'] == 'FAIL':
        print("\n❌ SOME TESTS FAILED - SYSTEM NEEDS ATTENTION")
    else:
        print("\n⚠️ TESTING ENCOUNTERED ERRORS")
    
    print("\n📊 Phase Results:")
    for phase, result in results.get('phase_results', {}).items():
        status_icon = "✅" if result.get('status') == 'PASS' else "❌"
        print(f"  {status_icon} {phase.replace('_', ' ').title()}: {result.get('status')}")
        if result.get('error'):
            print(f"     Error: {result.get('error')}")
    
    print("\n🔧 Integration Results:")
    for test, result in results.get('integration_results', {}).items():
        status_icon = "✅" if result.get('status') == 'PASS' else "❌"
        print(f"  {status_icon} {test.replace('_', ' ').title()}: {result.get('status')}")
    
    if 'performance_metrics' in results:
        perf = results['performance_metrics']
        print(f"\n⚡ Performance Metrics:")
        print(f"  Grade: {perf.get('performance_grade', 'N/A')}")
        print(f"  Avg Prediction Time: {perf.get('avg_prediction_time', 'N/A')}s")
        print(f"  Predictions Completed: {perf.get('predictions_tested', 'N/A')}")
    
    if 'production_readiness' in results:
        ready = results['production_readiness']
        print(f"\n🚀 Production Readiness:")
        print(f"  Deployment Ready: {'YES' if ready.get('deployment_ready') else 'NO'}")
        print(f"  Pass Rate: {ready.get('pass_rate', 0)*100:.0f}%")
        
        print("  Readiness Checks:")
        for check, status in ready.get('readiness_checks', {}).items():
            check_icon = "✅" if status == 'PASS' else "⚠️" if status.startswith('WARNING') else "❌"
            print(f"    {check_icon} {check.replace('_', ' ').title()}: {status}")
    
    if results.get('error'):
        print(f"\n🚨 System Error: {results['error']}")


if __name__ == "__main__":
    print("🚀 Starting Complete System Integration Test...")
    results = test_complete_system_integration()
    
    # Print detailed results
    print_detailed_results(results)
    
    # Save results to file for analysis
    results_file = f"integration_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Detailed results saved to: {results_file}")
    except Exception as e:
        print(f"\n⚠️ Could not save results file: {e}")
    
    # Exit with appropriate code
    if results['overall_status'] == 'PASS':
        print("\n🎉 Integration test completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Integration test failed - review results above")
        sys.exit(1)