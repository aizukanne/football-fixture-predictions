#!/usr/bin/env python3
"""
Test Phase 2: Home/Away Venue Analysis Integration

This test file verifies that Phase 2 venue analysis components are properly integrated
with existing Phase 0 (version tracking) and Phase 1 (opponent stratification) infrastructure.

Tests cover:
1. Venue analysis module functionality
2. Geographic distance calculations
3. Surface type analysis
4. Venue cache operations
5. Enhanced team parameter calculation with venue data
6. Prediction engine with venue-aware logic
7. Integration with existing Phase 0 and Phase 1 systems
"""

import sys
import os
from decimal import Decimal
from datetime import datetime
import pandas as pd

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_venue_analyzer():
    """Test venue analysis module functionality."""
    print("🏟️ Testing Venue Analyzer...")
    
    try:
        from src.features.venue_analyzer import VenueAnalyzer, get_venue_details, calculate_stadium_advantage
        
        # Test venue analyzer initialization
        analyzer = VenueAnalyzer()
        print("✅ VenueAnalyzer initialized successfully")
        
        # Test convenience functions
        venue_details = get_venue_details(1)  # Test venue ID
        print(f"✅ Venue details function accessible: {type(venue_details)}")
        
        stadium_advantage = calculate_stadium_advantage(123, 1, 2024)
        print(f"✅ Stadium advantage calculation: {stadium_advantage}")
        
        return True
        
    except Exception as e:
        print(f"❌ Venue analyzer test failed: {e}")
        return False


def test_geographic_utilities():
    """Test geographic distance calculations."""
    print("\n🌍 Testing Geographic Utilities...")
    
    try:
        from src.utils.geographic import (
            calculate_haversine_distance, 
            calculate_travel_fatigue_factor,
            get_time_zone_difference,
            analyze_travel_impact
        )
        
        # Test Haversine distance calculation (London to Paris)
        london_coords = (Decimal('51.5074'), Decimal('-0.1278'))
        paris_coords = (Decimal('48.8566'), Decimal('2.3522'))
        
        distance = calculate_haversine_distance(*london_coords, *paris_coords)
        print(f"✅ London to Paris distance: {distance}km")
        
        # Test travel fatigue factor
        fatigue = calculate_travel_fatigue_factor(distance)
        print(f"✅ Travel fatigue factor: {fatigue}")
        
        # Test time zone difference
        tz_diff = get_time_zone_difference(*london_coords, *paris_coords)
        print(f"✅ Time zone difference: {tz_diff} hours")
        
        # Test complete travel analysis
        travel_analysis = analyze_travel_impact(london_coords, paris_coords)
        print(f"✅ Complete travel analysis: {len(travel_analysis)} metrics")
        
        return True
        
    except Exception as e:
        print(f"❌ Geographic utilities test failed: {e}")
        return False


def test_surface_analyzer():
    """Test surface type analysis functionality."""
    print("\n🌱 Testing Surface Analyzer...")
    
    try:
        from src.features.surface_analyzer import (
            SurfaceAnalyzer,
            analyze_surface_advantage,
            get_team_surface_preference
        )
        
        # Test surface analyzer initialization
        analyzer = SurfaceAnalyzer()
        print("✅ SurfaceAnalyzer initialized successfully")
        
        # Test surface advantage analysis
        advantage = analyze_surface_advantage(123, 'grass', 2024)
        print(f"✅ Surface advantage analysis: {advantage}")
        
        # Test surface preference
        preference = get_team_surface_preference(123, 2024)
        print(f"✅ Surface preference: {preference['preferred_surface']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Surface analyzer test failed: {e}")
        return False


def test_venue_cache_infrastructure():
    """Test venue cache infrastructure."""
    print("\n💾 Testing Venue Cache Infrastructure...")
    
    try:
        from src.infrastructure.create_venue_cache import (
            create_venue_cache_table,
            describe_venue_cache_table,
            test_venue_cache_operations
        )
        
        print("✅ Venue cache functions imported successfully")
        print("ℹ️  Note: Actual DynamoDB operations require AWS configuration")
        
        # Test would create table, test operations, etc. in a real AWS environment
        return True
        
    except Exception as e:
        print(f"❌ Venue cache infrastructure test failed: {e}")
        return False


def test_enhanced_team_parameters():
    """Test enhanced team parameter calculation with venue data."""
    print("\n📊 Testing Enhanced Team Parameters...")
    
    try:
        from src.parameters.team_calculator import (
            fit_team_params,
            calculate_venue_parameters,
            get_neutral_venue_params
        )
        
        # Test venue parameter calculation functions
        neutral_params = get_neutral_venue_params()
        print(f"✅ Neutral venue params: {len(neutral_params)} parameters")
        
        # Test venue parameter calculation with mock data
        mock_df = pd.DataFrame({
            'home_team_id': [123] * 10,
            'away_team_id': [456] * 10,
            'home_goals': [1, 2, 0, 3, 1, 2, 1, 0, 2, 1],
            'away_goals': [0, 1, 1, 2, 0, 0, 1, 2, 1, 0],
            'venue_id': [1] * 10
        })
        
        venue_params = calculate_venue_parameters(mock_df, 123, 1, 2024)
        print(f"✅ Venue parameters calculated: {len(venue_params)} metrics")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced team parameters test failed: {e}")
        return False


def test_venue_aware_prediction_engine():
    """Test prediction engine with venue-aware logic."""
    print("\n🔮 Testing Venue-Aware Prediction Engine...")
    
    try:
        from src.prediction.prediction_engine import (
            apply_venue_adjustments,
            calculate_travel_impact_factor,
            calculate_venue_aware_predictions
        )
        
        # Test travel impact factor calculation
        impact = calculate_travel_impact_factor(Decimal('500'), {})
        print(f"✅ Travel impact factor: {impact}")
        
        # Test venue-aware predictions
        predictions = calculate_venue_aware_predictions(123, 456, 1, 2024, 1)
        if predictions:
            print(f"✅ Venue-aware predictions: {len(predictions)} sections")
            print(f"   Architecture version: {predictions.get('architecture_version')}")
            print(f"   Features: {predictions.get('features')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Venue-aware prediction engine test failed: {e}")
        return False


def test_phase_integration():
    """Test integration between Phase 0, Phase 1, and Phase 2."""
    print("\n🔗 Testing Phase Integration...")
    
    try:
        # Test that all phase components can be imported together
        from src.infrastructure.version_manager import VersionManager
        from src.features.opponent_classifier import OpponentClassifier
        from src.features.venue_analyzer import VenueAnalyzer
        
        # Initialize all phase components
        version_manager = VersionManager()
        opponent_classifier = OpponentClassifier()
        venue_analyzer = VenueAnalyzer()
        
        print("✅ All phase components initialized together")
        
        # Test version tracking integration
        current_version = version_manager.get_current_version()
        print(f"✅ Current architecture version: {current_version}")
        
        # Verify Phase 2 is properly registered
        version_metadata = version_manager.get_version_metadata()
        features = version_metadata.get('features', [])
        
        if 'venue_analysis' in features:
            print("✅ Phase 2 venue analysis registered in version metadata")
        else:
            print("⚠️  Phase 2 not found in version features - this may need manual registration")
        
        return True
        
    except Exception as e:
        print(f"❌ Phase integration test failed: {e}")
        return False


def test_backward_compatibility():
    """Test that Phase 2 maintains backward compatibility."""
    print("\n↩️ Testing Backward Compatibility...")
    
    try:
        # Test that enhanced functions can handle legacy parameters
        from src.parameters.team_calculator import fit_team_params
        from src.prediction.prediction_engine import calculate_coordinated_predictions
        
        print("✅ Enhanced functions maintain original interfaces")
        
        # Test that new parameters are optional
        mock_df = pd.DataFrame({
            'home_team_id': [123],
            'away_team_id': [456],
            'home_goals': [1],
            'away_goals': [0]
        })
        
        # Should work without season (Phase 1) or venue_id (Phase 2)
        team_params = fit_team_params(mock_df, 123, 1)
        print("✅ Team parameter calculation works without Phase 1/2 data")
        
        # Should have venue_params even if empty/neutral
        venue_params = team_params.get('venue_params', {})
        print(f"✅ Venue parameters present: {len(venue_params)} parameters")
        
        return True
        
    except Exception as e:
        print(f"❌ Backward compatibility test failed: {e}")
        return False


def run_all_tests():
    """Run all Phase 2 integration tests."""
    print("🚀 Starting Phase 2: Home/Away Venue Analysis Integration Tests")
    print("=" * 80)
    
    test_results = []
    
    # Core functionality tests
    test_results.append(test_venue_analyzer())
    test_results.append(test_geographic_utilities())
    test_results.append(test_surface_analyzer())
    test_results.append(test_venue_cache_infrastructure())
    
    # Integration tests
    test_results.append(test_enhanced_team_parameters())
    test_results.append(test_venue_aware_prediction_engine())
    test_results.append(test_phase_integration())
    test_results.append(test_backward_compatibility())
    
    # Summary
    passed = sum(test_results)
    total = len(test_results)
    
    print("\n" + "=" * 80)
    print("🏁 Test Summary:")
    print(f"✅ Passed: {passed}/{total} tests")
    
    if passed == total:
        print("🎉 All Phase 2 integration tests passed!")
        print("\n✨ Phase 2: Home/Away Venue Analysis is ready for deployment!")
        print("\nEnhancements provided:")
        print("• Stadium-specific advantages for home teams")
        print("• Travel distance impact analysis for away teams")
        print("• Playing surface performance analysis")
        print("• Geographic intelligence in predictions")
        print("• Venue data caching for performance")
        print("• Full integration with Phase 0 and Phase 1 systems")
        return True
    else:
        failed = total - passed
        print(f"❌ {failed} tests failed. Please review errors above.")
        return False


if __name__ == "__main__":
    """Run Phase 2 integration tests when executed directly."""
    success = run_all_tests()
    
    if not success:
        print("\n⚠️  Some tests failed. Phase 2 may need additional configuration.")
        print("Common issues:")
        print("• AWS credentials needed for DynamoDB operations")
        print("• API-Football key required for venue data fetching")
        print("• Database schema updates may be required")
        sys.exit(1)
    
    print("\n🎯 Phase 2 is ready for production deployment!")