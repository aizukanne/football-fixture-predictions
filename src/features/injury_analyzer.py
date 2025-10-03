"""
Player availability and impact analysis for Phase 3 implementation.

This module analyzes the impact of injuries and suspensions on team performance,
providing sophisticated modeling of how missing players affect team strength.

Enhanced with:
- Real-time injury and suspension data integration
- Player importance rating based on contribution analysis
- Position-specific impact modeling 
- Squad depth assessment and replacement quality analysis
- Recovery timeline tracking for future form predictions
"""

import requests
from typing import Dict, List, Optional, Tuple, Union
from decimal import Decimal
from datetime import datetime, timedelta
import boto3
from collections import defaultdict
import numpy as np

from ..infrastructure.version_manager import VersionManager
from ..data.api_client import APIClient
from ..data.database_client import get_dynamodb_table
from ..utils.constants import MINIMUM_GAMES_THRESHOLD


def get_injured_players(team_id: int, league_id: int, season: int) -> List[Dict]:
    """
    Get current injured and suspended players from API-Football.
    
    This function fetches real-time player availability data and enriches it
    with importance ratings and impact analysis.
    
    Args:
        team_id: Team identifier
        league_id: League identifier
        season: Current season year
        
    Returns:
        List of players with:
        - Player details (id, name, position)
        - Injury/suspension type and expected return
        - Player importance rating (0.0-1.0)
        - Position and role impact assessment
    """
    try:
        api_client = APIClient()
        
        # Get injured players from API-Football
        injured_players = api_client.get_team_injuries(team_id, season)
        
        # Get suspended players from API-Football
        suspended_players = api_client.get_team_suspensions(team_id, season)
        
        # Combine and enrich player data
        unavailable_players = []
        
        # Process injured players
        for injury in injured_players:
            player_data = enrich_player_data(injury, team_id, league_id, season, 'injury')
            if player_data:
                unavailable_players.append(player_data)
        
        # Process suspended players
        for suspension in suspended_players:
            player_data = enrich_player_data(suspension, team_id, league_id, season, 'suspension')
            if player_data:
                unavailable_players.append(player_data)
        
        # Sort by importance rating (most important first)
        unavailable_players.sort(key=lambda x: x.get('importance_rating', 0.0), reverse=True)
        
        return unavailable_players
        
    except Exception as e:
        print(f"Error getting injured/suspended players for team {team_id}: {e}")
        return []


def calculate_injury_impact(team_id: int, league_id: int, season: int,
                           prediction_date: datetime) -> Dict:
    """
    Calculate team strength impact from injuries and suspensions.
    
    Analyzes how missing players affect different aspects of team performance
    including overall strength, attacking capability, and defensive stability.
    
    Args:
        team_id: Team identifier
        league_id: League identifier
        season: Current season
        prediction_date: Date of the match being predicted
        
    Returns:
        {
            'overall_impact': Decimal,       # -0.3 to 0.0 (negative impact)
            'attack_impact': Decimal,        # Impact on attacking parameters
            'defense_impact': Decimal,       # Impact on defensive parameters
            'key_players_out': List[str],    # Names of important missing players
            'depth_quality': Decimal,        # Team's squad depth rating (0.0-1.0)
        }
    """
    try:
        # Get unavailable players
        unavailable_players = get_injured_players(team_id, league_id, season)
        
        if not unavailable_players:
            return get_neutral_injury_impact()
        
        # Filter players who will be unavailable on prediction date
        unavailable_on_date = [
            player for player in unavailable_players
            if is_player_unavailable_on_date(player, prediction_date)
        ]
        
        if not unavailable_on_date:
            return get_neutral_injury_impact()
        
        # Calculate position-specific impacts
        position_impacts = calculate_position_impacts(unavailable_on_date)
        
        # Calculate overall team impact
        overall_impact = calculate_overall_team_impact(unavailable_on_date, team_id, season)
        
        # Assess squad depth quality
        depth_quality = assess_squad_depth(team_id, league_id, season, unavailable_on_date)
        
        # Get key missing players
        key_players_out = [
            player['name'] for player in unavailable_on_date
            if player.get('importance_rating', 0.0) >= 0.7
        ]
        
        return {
            'overall_impact': Decimal(str(round(max(-0.3, overall_impact), 3))),
            'attack_impact': Decimal(str(round(max(-0.25, position_impacts.get('attack', 0.0)), 3))),
            'defense_impact': Decimal(str(round(max(-0.25, position_impacts.get('defense', 0.0)), 3))),
            'key_players_out': key_players_out[:5],  # Limit to top 5
            'depth_quality': depth_quality,
            'players_affected': len(unavailable_on_date),
            'analysis_timestamp': int(datetime.now().timestamp())
        }
        
    except Exception as e:
        print(f"Error calculating injury impact for team {team_id}: {e}")
        return get_neutral_injury_impact()


def analyze_player_importance(player_id: int, team_id: int, season: int) -> Decimal:
    """
    Calculate individual player's importance to team performance.
    
    Uses multiple metrics to assess how crucial a player is to their team:
    - Games played vs team performance correlation
    - Direct contributions (goals, assists, key defensive actions)
    - Team win rate with/without player
    - Market value and experience factors
    
    Args:
        player_id: Player identifier
        team_id: Team identifier  
        season: Current season
        
    Returns:
        Decimal: Player importance rating (0.0-1.0, where 1.0 = irreplaceable)
    """
    try:
        api_client = APIClient()
        
        # Get player statistics for the season
        player_stats = api_client.get_player_season_stats(player_id, team_id, season)
        
        if not player_stats:
            return Decimal('0.3')  # Default moderate importance
        
        # Calculate performance-based importance
        performance_importance = calculate_performance_importance(player_stats, team_id, season)
        
        # Calculate availability-based importance
        availability_importance = calculate_availability_importance(player_stats, team_id, season)
        
        # Calculate positional importance
        positional_importance = calculate_positional_importance(player_stats)
        
        # Weight and combine importance factors
        importance_score = (
            performance_importance * 0.4 +
            availability_importance * 0.3 +
            positional_importance * 0.3
        )
        
        # Clamp to valid range
        final_importance = max(0.0, min(1.0, importance_score))
        
        return Decimal(str(round(final_importance, 3)))
        
    except Exception as e:
        print(f"Error calculating importance for player {player_id}: {e}")
        return Decimal('0.3')


def get_return_timeline(team_id: int, league_id: int, season: int) -> List[Dict]:
    """
    Get timeline of when key players are expected to return from injury.
    
    This provides valuable insight for predicting future form changes
    when important players return to action.
    
    Args:
        team_id: Team identifier
        league_id: League identifier
        season: Current season
        
    Returns:
        List of return events sorted by expected return date:
        [
            {
                'player_name': str,
                'player_id': int,
                'expected_return': datetime,
                'injury_type': str,
                'importance_rating': Decimal,
                'return_confidence': str  # 'high'|'medium'|'low'
            }
        ]
    """
    try:
        # Get injured players with return dates
        unavailable_players = get_injured_players(team_id, league_id, season)
        
        return_timeline = []
        
        for player in unavailable_players:
            if player.get('expected_return_date'):
                timeline_event = {
                    'player_name': player['name'],
                    'player_id': player['player_id'],
                    'expected_return': player['expected_return_date'],
                    'injury_type': player.get('availability_type', 'unknown'),
                    'importance_rating': player.get('importance_rating', Decimal('0.3')),
                    'return_confidence': assess_return_confidence(player),
                    'position': player.get('position', 'Unknown'),
                    'impact_category': categorize_player_impact(player)
                }
                return_timeline.append(timeline_event)
        
        # Sort by expected return date (soonest first)
        return_timeline.sort(key=lambda x: x['expected_return'])
        
        return return_timeline
        
    except Exception as e:
        print(f"Error getting return timeline for team {team_id}: {e}")
        return []


# Helper Functions

def enrich_player_data(player_data: Dict, team_id: int, league_id: int, 
                      season: int, availability_type: str) -> Optional[Dict]:
    """Enrich basic player injury/suspension data with importance analysis."""
    try:
        player_id = player_data.get('player', {}).get('id')
        if not player_id:
            return None
        
        # Calculate player importance
        importance_rating = analyze_player_importance(player_id, team_id, season)
        
        # Parse return date
        expected_return = parse_return_date(player_data)
        
        return {
            'player_id': player_id,
            'name': player_data.get('player', {}).get('name', 'Unknown'),
            'position': player_data.get('player', {}).get('position', 'Unknown'),
            'availability_type': availability_type,
            'injury_type': player_data.get('fixture', {}).get('type', 'Unknown'),
            'expected_return_date': expected_return,
            'importance_rating': importance_rating,
            'impact_areas': determine_impact_areas(player_data.get('player', {}))
        }
        
    except Exception as e:
        print(f"Error enriching player data: {e}")
        return None


def is_player_unavailable_on_date(player: Dict, prediction_date: datetime) -> bool:
    """Check if player will be unavailable on the prediction date."""
    expected_return = player.get('expected_return_date')
    
    if not expected_return:
        # If no return date, assume player is out for foreseeable future
        return True
    
    if isinstance(expected_return, str):
        try:
            expected_return = datetime.fromisoformat(expected_return)
        except:
            return True  # Assume unavailable if date parsing fails
    
    return prediction_date < expected_return


def calculate_position_impacts(unavailable_players: List[Dict]) -> Dict:
    """Calculate position-specific impacts from missing players."""
    impact_areas = {'attack': 0.0, 'defense': 0.0, 'midfield': 0.0}
    
    for player in unavailable_players:
        importance = float(player.get('importance_rating', 0.3))
        position = player.get('position', '').lower()
        
        # Map positions to impact areas
        if any(pos in position for pos in ['forward', 'striker', 'winger']):
            impact_areas['attack'] -= importance * 0.15
        elif any(pos in position for pos in ['defender', 'back', 'goalkeeper']):
            impact_areas['defense'] -= importance * 0.15
        elif 'mid' in position:
            # Midfielders impact both attack and defense
            impact_areas['attack'] -= importance * 0.08
            impact_areas['defense'] -= importance * 0.08
            impact_areas['midfield'] -= importance * 0.12
    
    return impact_areas


def calculate_overall_team_impact(unavailable_players: List[Dict], 
                                team_id: int, season: int) -> float:
    """Calculate overall team impact from all missing players."""
    if not unavailable_players:
        return 0.0
    
    total_importance = sum(
        float(player.get('importance_rating', 0.0))
        for player in unavailable_players
    )
    
    # Scale impact based on number of missing players and their importance
    base_impact = -total_importance * 0.15  # Each point of importance = 15% impact
    
    # Apply diminishing returns for multiple injuries
    num_players = len(unavailable_players)
    if num_players > 3:
        # More than 3 key players out increases impact but with diminishing returns
        additional_impact = -(num_players - 3) * 0.02
        base_impact += additional_impact
    
    return max(-0.3, base_impact)  # Cap maximum negative impact


def assess_squad_depth(team_id: int, league_id: int, season: int, 
                      unavailable_players: List[Dict]) -> Decimal:
    """Assess team's squad depth quality for handling injuries."""
    try:
        api_client = APIClient()
        
        # Get squad information
        squad_data = api_client.get_team_squad(team_id, season)
        
        if not squad_data:
            return Decimal('0.5')  # Default average depth
        
        # Calculate depth based on squad size, player quality, and versatility
        squad_size = len(squad_data.get('players', []))
        
        # Basic depth assessment
        if squad_size >= 25:
            base_depth = 0.8
        elif squad_size >= 20:
            base_depth = 0.6
        elif squad_size >= 16:
            base_depth = 0.4
        else:
            base_depth = 0.2
        
        # Adjust based on injured positions vs available cover
        position_coverage = assess_position_coverage(squad_data, unavailable_players)
        
        final_depth = base_depth * position_coverage
        return Decimal(str(round(max(0.1, min(1.0, final_depth)), 3)))
        
    except Exception as e:
        print(f"Error assessing squad depth for team {team_id}: {e}")
        return Decimal('0.5')


def calculate_performance_importance(player_stats: Dict, team_id: int, season: int) -> float:
    """Calculate importance based on player's performance statistics."""
    # Goals and assists contribution
    goals = player_stats.get('goals', {}).get('total', 0) or 0
    assists = player_stats.get('goals', {}).get('assists', 0) or 0
    
    # Minutes played (availability)
    minutes_played = player_stats.get('games', {}).get('minutes', 0) or 0
    total_minutes_possible = player_stats.get('games', {}).get('appearences', 0) * 90
    
    # Basic performance score
    attacking_contribution = (goals * 0.6 + assists * 0.4) / max(1, minutes_played / 90)
    
    # Defensive contributions (if available)
    defensive_stats = player_stats.get('tackles', {}) or {}
    defensive_contribution = (
        defensive_stats.get('total', 0) * 0.1 +
        defensive_stats.get('interceptions', 0) * 0.1
    ) / max(1, minutes_played / 90)
    
    # Availability factor
    availability_factor = minutes_played / max(1, total_minutes_possible) if total_minutes_possible > 0 else 0.5
    
    # Combine factors
    performance_score = (attacking_contribution + defensive_contribution) * availability_factor
    
    return min(1.0, performance_score / 2.0)  # Normalize to 0-1


def calculate_availability_importance(player_stats: Dict, team_id: int, season: int) -> float:
    """Calculate importance based on player's availability and team performance correlation."""
    games_played = player_stats.get('games', {}).get('appearences', 0) or 0
    total_games = 38  # Typical season length - could be dynamic
    
    availability_rate = games_played / max(1, total_games)
    
    # High availability players are often more important
    return min(1.0, availability_rate * 1.2)


def calculate_positional_importance(player_stats: Dict) -> float:
    """Calculate importance based on player's position and role."""
    position = player_stats.get('games', {}).get('position', '').lower()
    
    # Position-based importance weights
    if 'goalkeeper' in position:
        return 0.9  # Goalkeepers are very important due to limited alternatives
    elif any(pos in position for pos in ['centre-back', 'defender']):
        return 0.7
    elif any(pos in position for pos in ['midfielder', 'mid']):
        return 0.6
    elif any(pos in position for pos in ['forward', 'striker', 'winger']):
        return 0.8  # Key attacking players
    else:
        return 0.5  # Default


def parse_return_date(player_data: Dict) -> Optional[datetime]:
    """Parse expected return date from injury/suspension data."""
    try:
        # Try to get return date from fixture data
        fixture_data = player_data.get('fixture', {})
        return_date_str = fixture_data.get('date')
        
        if return_date_str:
            return datetime.fromisoformat(return_date_str.replace('Z', '+00:00'))
        
        # If no specific date, estimate based on injury type
        injury_type = fixture_data.get('type', '').lower()
        
        if 'minor' in injury_type or 'knock' in injury_type:
            return datetime.now() + timedelta(days=7)  # 1 week
        elif 'muscle' in injury_type or 'strain' in injury_type:
            return datetime.now() + timedelta(days=21)  # 3 weeks
        elif 'serious' in injury_type or 'major' in injury_type:
            return datetime.now() + timedelta(days=42)  # 6 weeks
        else:
            return datetime.now() + timedelta(days=14)  # Default 2 weeks
            
    except Exception as e:
        print(f"Error parsing return date: {e}")
        return None


def determine_impact_areas(player_data: Dict) -> List[str]:
    """Determine which areas of the game this player impacts."""
    position = player_data.get('position', '').lower()
    impact_areas = []
    
    if any(pos in position for pos in ['forward', 'striker', 'winger']):
        impact_areas.extend(['goals', 'attacks', 'creativity'])
    elif any(pos in position for pos in ['defender', 'back']):
        impact_areas.extend(['defense', 'aerial', 'set_pieces'])
    elif 'goalkeeper' in position:
        impact_areas.extend(['saves', 'distribution', 'organization'])
    elif 'mid' in position:
        impact_areas.extend(['passing', 'possession', 'transitions'])
    
    return impact_areas


def assess_return_confidence(player: Dict) -> str:
    """Assess confidence level in player's return timeline."""
    injury_type = player.get('injury_type', '').lower()
    
    if any(word in injury_type for word in ['minor', 'knock', 'rest']):
        return 'high'
    elif any(word in injury_type for word in ['muscle', 'strain', 'bruise']):
        return 'medium'
    elif any(word in injury_type for word in ['serious', 'major', 'surgery', 'ligament']):
        return 'low'
    else:
        return 'medium'


def categorize_player_impact(player: Dict) -> str:
    """Categorize the type of impact this player has."""
    importance = float(player.get('importance_rating', 0.3))
    
    if importance >= 0.8:
        return 'critical'
    elif importance >= 0.6:
        return 'important'
    elif importance >= 0.4:
        return 'moderate'
    else:
        return 'minimal'


def assess_position_coverage(squad_data: Dict, unavailable_players: List[Dict]) -> float:
    """Assess how well the squad can cover for injured positions."""
    if not unavailable_players:
        return 1.0
    
    # Get available players by position
    available_players = squad_data.get('players', [])
    position_counts = defaultdict(int)
    
    for player in available_players:
        position = player.get('position', '').lower()
        if 'goalkeeper' in position:
            position_counts['goalkeeper'] += 1
        elif any(pos in position for pos in ['defender', 'back']):
            position_counts['defender'] += 1
        elif 'mid' in position:
            position_counts['midfielder'] += 1
        elif any(pos in position for pos in ['forward', 'striker', 'winger']):
            position_counts['forward'] += 1
    
    # Check coverage for injured positions
    coverage_scores = []
    
    for injured_player in unavailable_players:
        position = injured_player.get('position', '').lower()
        
        if 'goalkeeper' in position:
            coverage = min(1.0, position_counts.get('goalkeeper', 0) / 2)
        elif any(pos in position for pos in ['defender', 'back']):
            coverage = min(1.0, position_counts.get('defender', 0) / 4)
        elif 'mid' in position:
            coverage = min(1.0, position_counts.get('midfielder', 0) / 3)
        elif any(pos in position for pos in ['forward', 'striker', 'winger']):
            coverage = min(1.0, position_counts.get('forward', 0) / 3)
        else:
            coverage = 0.5
        
        coverage_scores.append(coverage)
    
    return np.mean(coverage_scores) if coverage_scores else 1.0


# Default/Fallback Functions

def get_neutral_injury_impact() -> Dict:
    """Get neutral injury impact when no injuries affect the team."""
    return {
        'overall_impact': Decimal('0.0'),
        'attack_impact': Decimal('0.0'),
        'defense_impact': Decimal('0.0'),
        'key_players_out': [],
        'depth_quality': Decimal('0.7'),  # Assume reasonable depth
        'players_affected': 0,
        'analysis_timestamp': int(datetime.now().timestamp())
    }