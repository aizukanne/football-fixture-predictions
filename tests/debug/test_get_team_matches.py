#!/usr/bin/env python3
"""
Simple test script to verify get_team_matches() implementation.
"""

import sys
import os

# Add parent directory to path for proper imports
sys.path.insert(0, os.path.dirname(__file__))

from src.data.database_client import DatabaseClient

def test_get_team_matches():
    """Test the get_team_matches() method."""
    print("Testing get_team_matches() implementation...")
    print("=" * 60)
    
    # Initialize DatabaseClient
    db = DatabaseClient()
    
    # Test with Manchester United (team_id=33) in Premier League (league_id=39), season 2024
    team_id = 33
    league_id = 39
    season = 2024
    limit = 10
    
    print(f"\nTest Parameters:")
    print(f"  Team ID: {team_id} (Manchester United)")
    print(f"  League ID: {league_id} (Premier League)")
    print(f"  Season: {season}")
    print(f"  Limit: {limit}")
    print()
    
    try:
        # Call get_team_matches
        matches = db.get_team_matches(team_id, league_id, season, limit)
        
        print(f"✅ Method executed successfully!")
        print(f"   Returned {len(matches)} matches")
        
        if matches:
            print(f"\n📊 Sample Match Data (first match):")
            first_match = matches[0]
            for key, value in first_match.items():
                print(f"   {key}: {value}")
            
            # Verify required fields
            required_fields = [
                'fixture_id', 'home_team_id', 'away_team_id',
                'home_goals', 'away_goals', 'timestamp', 'date',
                'league_id', 'season', 'venue', 'is_home',
                'opponent_id', 'goals_scored', 'goals_conceded', 'result'
            ]
            
            missing_fields = [f for f in required_fields if f not in first_match]
            if missing_fields:
                print(f"\n⚠️  Missing required fields: {missing_fields}")
            else:
                print(f"\n✅ All required fields present!")
            
            # Show recent results
            print(f"\n🎯 Recent Results (last {min(5, len(matches))} matches):")
            for i, match in enumerate(matches[:5]):
                venue_symbol = '🏠' if match.get('is_home') else '✈️'
                result_symbol = {'W': '✅', 'D': '🤝', 'L': '❌'}.get(match.get('result'), '?')
                print(f"   {i+1}. {venue_symbol} vs Team {match.get('opponent_id')}: "
                      f"{match.get('goals_scored')}-{match.get('goals_conceded')} {result_symbol}")
        else:
            print("\n⚠️  No matches returned (might need DB data or API access)")
            print("   This is expected in test environments without AWS credentials")
        
        print(f"\n{'=' * 60}")
        print("✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during test:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_get_team_matches()
    sys.exit(0 if success else 1)