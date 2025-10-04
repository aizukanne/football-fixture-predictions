"""
Simple Phase 5 test to isolate and fix issues.
"""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

def test_basic_imports():
    """Test basic imports work."""
    print("Testing basic imports...")
    
    try:
        from src.features.team_classifier import determine_team_archetypes, get_archetype_prediction_weights
        print("✅ Team classifier imports working")
        
        from src.features.strategy_router import get_archetype_matchup_dynamics
        print("✅ Strategy router imports working")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_archetype_definitions():
    """Test archetype definitions work."""
    print("\nTesting archetype definitions...")
    
    try:
        from src.features.team_classifier import determine_team_archetypes
        
        archetypes = determine_team_archetypes()
        print(f"✅ Found {len(archetypes)} archetypes: {list(archetypes.keys())}")
        
        for name, config in archetypes.items():
            print(f"  - {name}: {config.get('description', 'No description')}")
        
        return True
    except Exception as e:
        print(f"❌ Archetype definitions failed: {e}")
        return False

def test_prediction_weights():
    """Test prediction weights work."""
    print("\nTesting prediction weights...")
    
    try:
        from src.features.team_classifier import get_archetype_prediction_weights
        
        weights = get_archetype_prediction_weights('ELITE_CONSISTENT')
        print(f"✅ ELITE_CONSISTENT weights: {dict(weights)}")
        
        weights = get_archetype_prediction_weights('UNPREDICTABLE_CHAOS')
        print(f"✅ UNPREDICTABLE_CHAOS weights: {dict(weights)}")
        
        return True
    except Exception as e:
        print(f"❌ Prediction weights failed: {e}")
        return False

def test_matchup_dynamics():
    """Test matchup dynamics work."""
    print("\nTesting matchup dynamics...")
    
    try:
        from src.features.strategy_router import get_archetype_matchup_dynamics
        
        dynamics = get_archetype_matchup_dynamics('ELITE_CONSISTENT', 'HOME_FORTRESS')
        print(f"✅ Matchup dynamics: {dynamics.get('matchup_type', 'UNKNOWN')}")
        print(f"  Volatility: {dynamics.get('volatility_level', 'UNKNOWN')}")
        
        return True
    except Exception as e:
        print(f"❌ Matchup dynamics failed: {e}")
        return False

if __name__ == "__main__":
    print("🔍 SIMPLE PHASE 5 TEST")
    print("=" * 50)
    
    tests = [
        test_basic_imports,
        test_archetype_definitions, 
        test_prediction_weights,
        test_matchup_dynamics
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ Basic functionality working!")
    else:
        print("❌ Issues found, need fixing")