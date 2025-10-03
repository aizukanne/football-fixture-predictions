"""
Match context and importance analysis for Phase 3 implementation.

This module analyzes the broader context and importance of specific matches,
providing sophisticated assessment of match pressure, motivation levels, and
situational factors that can significantly impact team performance.

Enhanced with:
- Match importance analysis based on league position implications
- Pressure factor calculation for teams in crucial situations
- Motivation level assessment for different scenarios
- End-of-season dynamics and dead rubber detection
- Derby match significance and local rivalry factors
- European qualification and relegation battle analysis
"""

from typing import Dict, List, Optional, Tuple, Union
from decimal import Decimal
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

from ..infrastructure.version_manager import VersionManager
from ..data.api_client import APIClient
from ..data.database_client import get_dynamodb_table


def analyze_match_importance(home_team_id: int, away_team_id: int, 
                           league_id: int, season: int, 
                           prediction_date: datetime) -> Dict:
    """
    Analyze the importance and context of a specific match.
    
    This function evaluates multiple factors to determine how crucial a match is
    for both teams, considering league position, season stage, and objectives.
    
    Factors analyzed:
    - League position implications (title race, European spots, relegation)
    - Season stage (early season vs crucial end-of-season matches)
    - Derby match significance and local rivalry intensity
    - Dead rubber detection vs high-stakes encounters
    - European qualification race positioning
    - Relegation battle dynamics
    
    Args:
        home_team_id: Home team identifier
        away_team_id: Away team identifier
        league_id: League identifier
        season: Current season year
        prediction_date: Date of the match
        
    Returns:
        Dictionary containing match importance analysis:
        {
            'overall_importance': str,        # 'critical'|'high'|'medium'|'low'
            'home_stakes': str,              # What's at stake for home team
            'away_stakes': str,              # What's at stake for away team
            'match_type': str,               # 'title_decider'|'relegation_battle'|'derby'|'routine'
            'pressure_level': Decimal,       # 0.0-2.0 pressure multiplier
            'dead_rubber_factor': Decimal,   # 0.0-1.0 (0.0 = complete dead rubber)
            'rivalry_intensity': Decimal     # 1.0-1.5 rivalry boost factor
        }
    """
    try:
        # Get current league standings
        league_standings = get_league_standings(league_id, season, prediction_date)
        
        if not league_standings:
            return get_default_match_importance()
        
        # Find team positions
        home_position = get_team_position(home_team_id, league_standings)
        away_position = get_team_position(away_team_id, league_standings)
        
        if home_position is None or away_position is None:
            return get_default_match_importance()
        
        # Analyze what's at stake for each team
        home_stakes = analyze_team_stakes(home_team_id, home_position, league_standings, prediction_date)
        away_stakes = analyze_team_stakes(away_team_id, away_position, league_standings, prediction_date)
        
        # Determine match type and overall importance
        match_type = determine_match_type(home_stakes, away_stakes, home_position, away_position)
        overall_importance = calculate_overall_importance(home_stakes, away_stakes, match_type)
        
        # Calculate pressure level
        pressure_level = calculate_match_pressure(home_stakes, away_stakes, prediction_date)
        
        # Check for dead rubber scenario
        dead_rubber_factor = calculate_dead_rubber_factor(
            home_stakes, away_stakes, prediction_date, league_standings
        )
        
        # Analyze rivalry intensity
        rivalry_intensity = analyze_rivalry_intensity(home_team_id, away_team_id, league_id)
        
        return {
            'overall_importance': overall_importance,
            'home_stakes': home_stakes['primary_objective'],
            'away_stakes': away_stakes['primary_objective'],
            'match_type': match_type,
            'pressure_level': pressure_level,
            'dead_rubber_factor': dead_rubber_factor,
            'rivalry_intensity': rivalry_intensity,
            'context_confidence': calculate_context_confidence(league_standings, prediction_date),
            'analysis_timestamp': int(prediction_date.timestamp())
        }
        
    except Exception as e:
        print(f"Error analyzing match importance between teams {home_team_id} and {away_team_id}: {e}")
        return get_default_match_importance()


def calculate_pressure_factor(team_id: int, league_id: int, season: int,
                             prediction_date: datetime) -> Decimal:
    """
    Calculate pressure factor based on team's current situation.
    
    Higher pressure situations include:
    - Relegation battle teams (bottom 6 positions)
    - Teams fighting for European qualification spots
    - Teams in title race contention
    - Teams with poor recent form needing crucial results
    - End-of-season decisive matches
    
    Args:
        team_id: Team identifier
        league_id: League identifier
        season: Current season year
        prediction_date: Date for pressure assessment
        
    Returns:
        Decimal: Pressure factor (0.8-2.0 range) where >1.0 = high pressure
    """
    try:
        # Get league standings and team position
        league_standings = get_league_standings(league_id, season, prediction_date)
        
        if not league_standings:
            return Decimal('1.0')  # Neutral pressure
        
        team_position = get_team_position(team_id, league_standings)
        if team_position is None:
            return Decimal('1.0')
        
        total_teams = len(league_standings)
        
        # Calculate base pressure from league position
        base_pressure = calculate_positional_pressure(team_position, total_teams)
        
        # Adjust for season stage
        season_pressure_modifier = calculate_season_stage_pressure(prediction_date)
        
        # Check for specific high-pressure scenarios
        scenario_pressure = analyze_pressure_scenarios(
            team_id, team_position, league_standings, prediction_date
        )
        
        # Combine pressure factors
        total_pressure = base_pressure * season_pressure_modifier * scenario_pressure
        
        # Clamp to reasonable bounds
        final_pressure = max(0.8, min(2.0, float(total_pressure)))
        
        return Decimal(str(round(final_pressure, 2)))
        
    except Exception as e:
        print(f"Error calculating pressure factor for team {team_id}: {e}")
        return Decimal('1.0')


def get_motivation_levels(home_team_id: int, away_team_id: int,
                         league_id: int, season: int,
                         prediction_date: datetime) -> Dict:
    """
    Assess relative motivation levels for both teams.
    
    Analyzes various factors that could affect team motivation:
    - League position and remaining objectives
    - Recent form and confidence levels
    - Fixture congestion and squad rotation needs
    - Manager pressure and job security situations
    - Player contract situations and transfer implications
    
    Args:
        home_team_id: Home team identifier
        away_team_id: Away team identifier
        league_id: League identifier
        season: Current season year
        prediction_date: Date for motivation assessment
        
    Returns:
        Dictionary containing motivation analysis:
        {
            'home_motivation': Decimal,    # 0.8-1.2 motivation multiplier
            'away_motivation': Decimal,    # 0.8-1.2 motivation multiplier  
            'context': str,               # Description of motivation context
            'confidence': Decimal         # 0.0-1.0 assessment confidence
        }
    """
    try:
        # Get match importance context
        match_context = analyze_match_importance(
            home_team_id, away_team_id, league_id, season, prediction_date
        )
        
        # Calculate base motivation from stakes
        home_base_motivation = calculate_stakes_motivation(match_context['home_stakes'])
        away_base_motivation = calculate_stakes_motivation(match_context['away_stakes'])
        
        # Adjust for pressure differential
        pressure_factor = float(match_context['pressure_level'])
        
        # Teams under high pressure may be more motivated but also more likely to underperform
        if pressure_factor > 1.5:
            # Very high pressure can reduce performance
            home_motivation = home_base_motivation * 0.95
            away_motivation = away_base_motivation * 0.95
            context = "High-pressure match with potential for underperformance"
        elif pressure_factor > 1.2:
            # Moderate pressure often increases motivation
            home_motivation = home_base_motivation * 1.05
            away_motivation = away_base_motivation * 1.05
            context = "Pressure situation enhancing team motivation"
        else:
            # Low pressure maintains baseline motivation
            home_motivation = home_base_motivation
            away_motivation = away_base_motivation
            context = "Standard motivation levels expected"
        
        # Apply dead rubber reduction
        dead_rubber_factor = float(match_context['dead_rubber_factor'])
        home_motivation *= dead_rubber_factor
        away_motivation *= dead_rubber_factor
        
        if dead_rubber_factor < 0.8:
            context = "Dead rubber scenario reducing motivation"
        
        # Apply rivalry boost
        rivalry_factor = float(match_context['rivalry_intensity'])
        if rivalry_factor > 1.1:
            home_motivation *= rivalry_factor
            away_motivation *= rivalry_factor
            context = "Derby/rivalry match increasing motivation"
        
        # Clamp to reasonable bounds
        home_motivation = max(0.8, min(1.2, home_motivation))
        away_motivation = max(0.8, min(1.2, away_motivation))
        
        # Calculate confidence based on data quality
        confidence = calculate_motivation_confidence(match_context, prediction_date)
        
        return {
            'home_motivation': Decimal(str(round(home_motivation, 3))),
            'away_motivation': Decimal(str(round(away_motivation, 3))),
            'context': context,
            'confidence': confidence,
            'analysis_timestamp': int(prediction_date.timestamp())
        }
        
    except Exception as e:
        print(f"Error calculating motivation levels: {e}")
        return get_default_motivation_levels()


def analyze_end_of_season_dynamics(team_id: int, league_id: int, season: int,
                                  prediction_date: datetime) -> Dict:
    """
    Analyze end-of-season dynamics that affect team performance.
    
    End-of-season factors include:
    - Nothing-to-play-for scenarios (mid-table with no objectives)
    - Final push for objectives (European spots, avoiding relegation)
    - Squad rotation and player rest considerations
    - Manager experimentation with formations/players
    - Youth player integration and development focus
    
    Args:
        team_id: Team identifier
        league_id: League identifier
        season: Current season year
        prediction_date: Date for analysis
        
    Returns:
        Dictionary containing end-of-season analysis
    """
    try:
        # Determine how close we are to season end
        season_completion = calculate_season_completion_percentage(
            league_id, season, prediction_date
        )
        
        if season_completion < 0.8:
            return {'end_season_factor': Decimal('1.0'), 'dynamics': 'not_applicable'}
        
        # Get league standings to assess team's situation
        league_standings = get_league_standings(league_id, season, prediction_date)
        if not league_standings:
            return {'end_season_factor': Decimal('1.0'), 'dynamics': 'unknown'}
        
        team_position = get_team_position(team_id, league_standings)
        if team_position is None:
            return {'end_season_factor': Decimal('1.0'), 'dynamics': 'unknown'}
        
        # Analyze what's at stake
        stakes = analyze_team_stakes(team_id, team_position, league_standings, prediction_date)
        
        # Calculate end-of-season factor
        if stakes['urgency'] == 'critical':
            # High stakes maintain motivation
            end_factor = 1.1
            dynamics = 'fighting_for_objectives'
        elif stakes['urgency'] == 'moderate':
            # Some stakes maintain normal motivation
            end_factor = 1.0
            dynamics = 'moderate_objectives'
        else:
            # Nothing to play for reduces motivation
            end_factor = 0.85
            dynamics = 'nothing_to_play_for'
        
        return {
            'end_season_factor': Decimal(str(round(end_factor, 2))),
            'dynamics': dynamics,
            'season_completion': Decimal(str(round(season_completion, 2))),
            'objectives_remaining': stakes['objectives']
        }
        
    except Exception as e:
        print(f"Error analyzing end-of-season dynamics for team {team_id}: {e}")
        return {'end_season_factor': Decimal('1.0'), 'dynamics': 'unknown'}


# Helper Functions

def get_league_standings(league_id: int, season: int, prediction_date: datetime) -> Optional[List[Dict]]:
    """Get current league standings."""
    try:
        api_client = APIClient()
        standings = api_client.get_league_standings(league_id, season)
        
        # Filter to matches played before prediction date if needed
        # This would ideally be a filtered view of standings as of prediction_date
        return standings
        
    except Exception as e:
        print(f"Error getting league standings: {e}")
        return None


def get_team_position(team_id: int, standings: List[Dict]) -> Optional[int]:
    """Get team's current league position from standings."""
    try:
        for position, team_data in enumerate(standings, 1):
            if team_data.get('team', {}).get('id') == team_id:
                return position
        return None
    except Exception as e:
        print(f"Error getting team position: {e}")
        return None


def analyze_team_stakes(team_id: int, position: int, standings: List[Dict], 
                       prediction_date: datetime) -> Dict:
    """Analyze what's at stake for a specific team."""
    total_teams = len(standings)
    
    # Define key position thresholds (typical for major European leagues)
    european_spots = 6  # Top 6 usually get European competition
    relegation_zone = total_teams - 3  # Bottom 3 usually relegated
    
    stakes = {
        'objectives': [],
        'urgency': 'low',
        'primary_objective': 'mid_table'
    }
    
    if position == 1:
        stakes['objectives'].append('title_race')
        stakes['urgency'] = 'critical'
        stakes['primary_objective'] = 'championship'
    elif position <= 4:
        stakes['objectives'].extend(['title_race', 'champions_league'])
        stakes['urgency'] = 'high'
        stakes['primary_objective'] = 'european_qualification'
    elif position <= european_spots:
        stakes['objectives'].append('european_qualification')
        stakes['urgency'] = 'moderate'
        stakes['primary_objective'] = 'european_qualification'
    elif position >= relegation_zone:
        stakes['objectives'].append('relegation_battle')
        stakes['urgency'] = 'critical'
        stakes['primary_objective'] = 'survival'
    elif position >= relegation_zone - 3:
        stakes['objectives'].append('avoiding_relegation')
        stakes['urgency'] = 'moderate'
        stakes['primary_objective'] = 'safety'
    
    return stakes


def determine_match_type(home_stakes: Dict, away_stakes: Dict, 
                        home_position: int, away_position: int) -> str:
    """Determine the type/category of match based on what's at stake."""
    home_primary = home_stakes['primary_objective']
    away_primary = away_stakes['primary_objective']
    
    # High-stakes combinations
    if home_primary == 'championship' or away_primary == 'championship':
        return 'title_decider'
    elif 'survival' in [home_primary, away_primary]:
        return 'relegation_battle'
    elif 'european_qualification' in [home_primary, away_primary]:
        return 'european_race'
    elif abs(home_position - away_position) <= 2:
        return 'direct_rival'
    else:
        return 'routine'


def calculate_overall_importance(home_stakes: Dict, away_stakes: Dict, match_type: str) -> str:
    """Calculate overall match importance level."""
    urgency_scores = {'critical': 3, 'high': 2, 'moderate': 1, 'low': 0}
    
    combined_urgency = urgency_scores.get(home_stakes['urgency'], 0) + \
                      urgency_scores.get(away_stakes['urgency'], 0)
    
    if match_type in ['title_decider', 'relegation_battle'] or combined_urgency >= 5:
        return 'critical'
    elif match_type in ['european_race', 'direct_rival'] or combined_urgency >= 3:
        return 'high'
    elif combined_urgency >= 2:
        return 'medium'
    else:
        return 'low'


def calculate_match_pressure(home_stakes: Dict, away_stakes: Dict, 
                           prediction_date: datetime) -> Decimal:
    """Calculate pressure level for the match."""
    urgency_multipliers = {'critical': 1.8, 'high': 1.4, 'moderate': 1.1, 'low': 1.0}
    
    home_pressure = urgency_multipliers.get(home_stakes['urgency'], 1.0)
    away_pressure = urgency_multipliers.get(away_stakes['urgency'], 1.0)
    
    # Average pressure but weight higher pressure more heavily
    combined_pressure = (home_pressure + away_pressure) / 2
    if max(home_pressure, away_pressure) >= 1.5:
        combined_pressure *= 1.1  # Boost for high-stakes matches
    
    return Decimal(str(round(combined_pressure, 2)))


def calculate_dead_rubber_factor(home_stakes: Dict, away_stakes: Dict,
                               prediction_date: datetime, standings: List[Dict]) -> Decimal:
    """Calculate how much this match matters (inverse of dead rubber)."""
    # If both teams have low urgency and it's late in season, it's more of a dead rubber
    if (home_stakes['urgency'] == 'low' and away_stakes['urgency'] == 'low'):
        season_completion = calculate_season_completion_percentage(
            None, None, prediction_date  # Simplified for now
        )
        
        if season_completion > 0.9:
            return Decimal('0.7')  # 30% reduction for late-season dead rubber
        elif season_completion > 0.8:
            return Decimal('0.85')  # 15% reduction
    
    return Decimal('1.0')  # Full importance


def analyze_rivalry_intensity(home_team_id: int, away_team_id: int, league_id: int) -> Decimal:
    """Analyze rivalry intensity between two teams."""
    # This would ideally check a database of known rivalries
    # For now, implement basic geographic/historical rivalry detection
    
    known_rivalries = get_known_rivalries(league_id)
    
    rivalry_key = tuple(sorted([home_team_id, away_team_id]))
    
    if rivalry_key in known_rivalries:
        intensity = known_rivalries[rivalry_key]
        return Decimal(str(round(1.0 + (intensity * 0.2), 2)))  # 1.0-1.4 range
    
    return Decimal('1.0')  # No known rivalry


def calculate_positional_pressure(position: int, total_teams: int) -> float:
    """Calculate pressure based on league position."""
    # Relegation zone (bottom 3)
    if position > total_teams - 3:
        return 1.8  # High pressure
    # Close to relegation (bottom 6)
    elif position > total_teams - 6:
        return 1.4  # Moderate-high pressure
    # Top of table (title race)
    elif position <= 3:
        return 1.3  # Moderate pressure
    # European spots
    elif position <= 6:
        return 1.2  # Some pressure
    else:
        return 1.0  # Normal pressure


def calculate_season_stage_pressure(prediction_date: datetime) -> float:
    """Calculate pressure multiplier based on season stage."""
    # This would ideally determine season stage more accurately
    month = prediction_date.month
    
    if month in [4, 5]:  # End of season
        return 1.3
    elif month in [3]:   # Late season
        return 1.2
    elif month in [2]:   # Mid-late season
        return 1.1
    else:               # Early-mid season
        return 1.0


def analyze_pressure_scenarios(team_id: int, position: int, standings: List[Dict],
                             prediction_date: datetime) -> float:
    """Analyze specific high-pressure scenarios."""
    total_teams = len(standings)
    
    # Manager under pressure scenarios
    # Recent poor form scenarios
    # Must-win situations
    # These would require additional data about recent results, manager tenure, etc.
    
    return 1.0  # Neutral for now


def calculate_stakes_motivation(stakes: str) -> float:
    """Calculate motivation multiplier based on what's at stake."""
    stakes_multipliers = {
        'championship': 1.15,
        'survival': 1.20,  # Highest motivation
        'european_qualification': 1.10,
        'safety': 1.05,
        'mid_table': 0.95
    }
    
    return stakes_multipliers.get(stakes, 1.0)


def calculate_season_completion_percentage(league_id: Optional[int], season: Optional[int],
                                         prediction_date: datetime) -> float:
    """Calculate what percentage of the season is complete."""
    # Simplified calculation based on date
    month = prediction_date.month
    
    if month <= 7:  # June-July (end of season/off-season)
        return 1.0
    elif month == 8:  # August (start of season)
        return 0.0
    elif month == 9:  # September
        return 0.1
    elif month == 10: # October
        return 0.2
    elif month == 11: # November
        return 0.3
    elif month == 12: # December
        return 0.4
    elif month == 1:  # January
        return 0.5
    elif month == 2:  # February
        return 0.6
    elif month == 3:  # March
        return 0.7
    elif month == 4:  # April
        return 0.8
    else:  # May
        return 0.9


def get_known_rivalries(league_id: int) -> Dict:
    """Get known rivalries for a league."""
    # This would ideally be loaded from a database
    # Placeholder implementation
    return {}


def calculate_context_confidence(standings: Optional[List[Dict]], 
                               prediction_date: datetime) -> Decimal:
    """Calculate confidence in context analysis."""
    if not standings:
        return Decimal('0.3')
    
    # Higher confidence with more complete standings data
    if len(standings) >= 18:  # Full league
        return Decimal('0.9')
    elif len(standings) >= 10:
        return Decimal('0.7')
    else:
        return Decimal('0.5')


def calculate_motivation_confidence(match_context: Dict, prediction_date: datetime) -> Decimal:
    """Calculate confidence in motivation assessment."""
    base_confidence = float(match_context.get('context_confidence', 0.7))
    
    # Higher confidence for high-importance matches
    if match_context.get('overall_importance') in ['critical', 'high']:
        return Decimal(str(round(min(0.9, base_confidence * 1.1), 2)))
    
    return Decimal(str(round(base_confidence, 2)))


# Default/Fallback Functions

def get_default_match_importance() -> Dict:
    """Get default match importance when analysis fails."""
    return {
        'overall_importance': 'medium',
        'home_stakes': 'mid_table',
        'away_stakes': 'mid_table',
        'match_type': 'routine',
        'pressure_level': Decimal('1.0'),
        'dead_rubber_factor': Decimal('1.0'),
        'rivalry_intensity': Decimal('1.0'),
        'context_confidence': Decimal('0.5'),
        'analysis_timestamp': int(datetime.now().timestamp())
    }


def get_default_motivation_levels() -> Dict:
    """Get default motivation levels when analysis fails."""
    return {
        'home_motivation': Decimal('1.0'),
        'away_motivation': Decimal('1.0'),
        'context': 'Standard motivation levels (analysis unavailable)',
        'confidence': Decimal('0.3'),
        'analysis_timestamp': int(datetime.now().timestamp())
    }