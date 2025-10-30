"""
Time-based parameter weighting algorithms for Phase 3 implementation.

This module provides sophisticated temporal weighting strategies to emphasize
recent performance data and account for seasonal patterns, fixture congestion,
and time-based performance decay in team parameter calculations.

Enhanced with:
- Exponential decay weights for historical matches (recent = more important)
- Seasonal performance adjustments for time-of-year effects
- Fixture congestion impact modeling for fatigue and rotation effects
- Multiple weighting methodologies for different analysis needs
- Time-aware parameter adjustment algorithms
"""

import requests
from typing import Dict, List, Optional, Tuple, Union
from decimal import Decimal
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict, deque
import math

from ..infrastructure.version_manager import VersionManager
from ..data.api_client import APIClient
from ..utils.constants import MINIMUM_GAMES_THRESHOLD


def calculate_exponential_decay_weights(matches: List[Dict], 
                                       prediction_date: datetime,
                                       decay_rate: float = 0.95) -> List[Decimal]:
    """
    Calculate exponential decay weights for historical matches.
    
    More recent matches get higher weights in parameter calculations.
    Each match gets exponentially less weight based on time elapsed.
    
    Args:
        matches: List of match dictionaries with 'match_date' field
        prediction_date: Date for which prediction is being made
        decay_rate: Decay factor per match (default 0.95 = 5% decay per match)
        
    Returns:
        List of weights (Decimals) corresponding to each match, recent first
    """
    try:
        if not matches:
            return []
        
        # Ensure matches are sorted by date (most recent first)
        sorted_matches = sorted(
            matches, 
            key=lambda x: parse_match_date(x.get('match_date', '')), 
            reverse=True
        )
        
        weights = []
        
        for i, match in enumerate(sorted_matches):
            # Calculate exponential decay weight
            weight = decay_rate ** i
            weights.append(Decimal(str(round(weight, 4))))
        
        # Normalize weights to sum to 1.0
        total_weight = sum(weights)
        if total_weight > 0:
            normalized_weights = [w / total_weight for w in weights]
            return normalized_weights
        
        return [Decimal('0.0')] * len(matches)
        
    except Exception as e:
        print(f"Error calculating exponential decay weights: {e}")
        return [Decimal(str(1.0 / len(matches)))] * len(matches)  # Equal weights fallback


def apply_seasonal_adjustments(base_params: Dict, team_id: int, 
                              league_id: int, season: int,
                              current_date: datetime) -> Dict:
    """
    Apply seasonal performance adjustments to base parameters.
    
    Accounts for different performance patterns throughout the season:
    - Teams that start seasons strong vs weak
    - Teams that improve throughout season
    - Christmas fixture congestion impact (European leagues)
    - End-of-season motivation factors
    
    Args:
        base_params: Base team parameters to adjust
        team_id: Team identifier
        league_id: League identifier
        season: Current season
        current_date: Current date for seasonal context
        
    Returns:
        Parameters with seasonal adjustments applied
    """
    try:
        # Determine current season period
        season_period = get_season_period(current_date)
        
        # Get seasonal multipliers for this team
        seasonal_multipliers = get_team_seasonal_multipliers(
            team_id, league_id, season, season_period
        )
        
        # Apply adjustments to parameters
        adjusted_params = base_params.copy()
        
        # Apply to goal scoring parameters
        for param in ['mu_home', 'mu_away', 'mu']:
            if param in adjusted_params:
                multiplier = seasonal_multipliers.get('scoring', Decimal('1.0'))
                current_value = adjusted_params[param]
                adjusted_value = float(current_value) * float(multiplier)
                adjusted_params[param] = round(adjusted_value, 4)
        
        # Apply to probability parameters (smaller adjustments)
        for param in ['p_score_home', 'p_score_away', 'p_score']:
            if param in adjusted_params:
                multiplier = seasonal_multipliers.get('form', Decimal('1.0'))
                current_value = adjusted_params[param]
                # Smaller adjustment for probabilities
                adjustment_factor = 1.0 + (float(multiplier) - 1.0) * 0.5
                adjusted_value = float(current_value) * adjustment_factor
                adjusted_params[param] = round(max(0.1, min(0.9, adjusted_value)), 4)
        
        # Add seasonal metadata
        adjusted_params['seasonal_adjustments'] = {
            'season_period': season_period,
            'scoring_multiplier': seasonal_multipliers.get('scoring', Decimal('1.0')),
            'form_multiplier': seasonal_multipliers.get('form', Decimal('1.0')),
            'adjustment_confidence': seasonal_multipliers.get('confidence', Decimal('0.7')),
            'adjustment_timestamp': int(current_date.timestamp())
        }
        
        return adjusted_params
        
    except Exception as e:
        print(f"Error applying seasonal adjustments for team {team_id}: {e}")
        return base_params


def calculate_fixture_congestion_impact(team_id: int, league_id: int, season: int,
                                       prediction_date: datetime) -> Decimal:
    """
    Calculate impact of fixture congestion on team performance.
    
    Analyzes recent fixture density and travel to determine fatigue effects:
    - Number of games in last 7/14 days
    - Travel distance for recent fixtures
    - Competition importance (league vs cup)
    - Squad depth and rotation capability
    
    Args:
        team_id: Team identifier
        league_id: League identifier
        season: Current season
        prediction_date: Date of the match being predicted
        
    Returns:
        Decimal: Congestion impact factor (0.95-1.0 range, where <1.0 = negative impact)
    """
    try:
        # Normalize prediction_date to timezone-naive for consistent date comparisons
        if prediction_date.tzinfo is not None:
            prediction_date = prediction_date.replace(tzinfo=None)
        
        # Get recent fixtures for congestion analysis
        recent_fixtures = get_recent_fixtures_for_congestion(
            team_id, league_id, season, prediction_date
        )
        
        if not recent_fixtures:
            return Decimal('1.0')  # No congestion impact
        
        # Calculate games in different time windows
        games_last_7_days = count_games_in_period(recent_fixtures, prediction_date, 7)
        games_last_14_days = count_games_in_period(recent_fixtures, prediction_date, 14)
        
        # Calculate base congestion factor
        congestion_factor = calculate_base_congestion_factor(
            games_last_7_days, games_last_14_days
        )
        
        # Adjust for travel distance
        travel_factor = calculate_travel_congestion_factor(
            recent_fixtures, prediction_date
        )
        
        # Adjust for competition importance
        competition_factor = calculate_competition_congestion_factor(recent_fixtures)
        
        # Combine factors
        final_impact = congestion_factor * travel_factor * competition_factor
        
        # Clamp to reasonable bounds
        final_impact = max(0.95, min(1.0, final_impact))
        
        return Decimal(str(round(final_impact, 3)))
        
    except Exception as e:
        print(f"Error calculating fixture congestion for team {team_id}: {e}")
        return Decimal('1.0')


def apply_temporal_weightings(historical_data: List[Dict],
                             prediction_date: datetime,
                             weighting_method: str = 'exponential') -> List[Dict]:
    """
    Apply temporal weightings to historical match data.
    
    Transforms historical data by adding time-based weights that emphasize
    recent performance and account for various temporal factors.
    
    Methods available:
    - 'exponential': Exponential decay based on time
    - 'linear': Linear decay based on time  
    - 'form_based': Weight based on team form periods
    - 'seasonal': Weight based on seasonal patterns
    
    Args:
        historical_data: List of historical match data
        prediction_date: Date for which weights are calculated
        weighting_method: Method to use for weighting
        
    Returns:
        List of match data with added 'temporal_weight' field
    """
    try:
        if not historical_data:
            return []
        
        weighted_data = []
        
        if weighting_method == 'exponential':
            weights = calculate_exponential_decay_weights(historical_data, prediction_date)
        elif weighting_method == 'linear':
            weights = calculate_linear_decay_weights(historical_data, prediction_date)
        elif weighting_method == 'form_based':
            weights = calculate_form_based_weights(historical_data, prediction_date)
        elif weighting_method == 'seasonal':
            weights = calculate_seasonal_weights(historical_data, prediction_date)
        else:
            # Default to exponential
            weights = calculate_exponential_decay_weights(historical_data, prediction_date)
        
        # Apply weights to data
        for i, match in enumerate(historical_data):
            weighted_match = match.copy()
            weighted_match['temporal_weight'] = weights[i] if i < len(weights) else Decimal('0.01')
            weighted_match['weighting_method'] = weighting_method
            weighted_data.append(weighted_match)
        
        return weighted_data
        
    except Exception as e:
        print(f"Error applying temporal weightings: {e}")
        # Return original data with equal weights
        equal_weight = Decimal(str(1.0 / len(historical_data))) if historical_data else Decimal('0.0')
        return [
            {**match, 'temporal_weight': equal_weight, 'weighting_method': 'equal'}
            for match in historical_data
        ]


def calculate_time_decay_multiplier(match_date: datetime, prediction_date: datetime,
                                  half_life_days: int = 30) -> Decimal:
    """
    Calculate time-based decay multiplier for a single match.
    
    Uses half-life decay where match importance halves every N days.
    More sophisticated than simple exponential decay.
    
    Args:
        match_date: Date of the historical match
        prediction_date: Date for which prediction is being made
        half_life_days: Number of days for importance to halve (default 30)
        
    Returns:
        Decimal: Decay multiplier (0.0-1.0)
    """
    try:
        days_ago = (prediction_date - match_date).days
        
        if days_ago < 0:
            return Decimal('0.0')  # Future matches have no weight
        
        # Calculate half-life decay
        decay_multiplier = 0.5 ** (days_ago / half_life_days)
        
        return Decimal(str(round(decay_multiplier, 4)))
        
    except Exception as e:
        print(f"Error calculating time decay multiplier: {e}")
        return Decimal('0.5')


def get_recency_weighted_average(values: List[float], weights: List[Decimal]) -> float:
    """
    Calculate weighted average using temporal weights.
    
    Args:
        values: List of numeric values to average
        weights: List of temporal weights
        
    Returns:
        Weighted average considering recency
    """
    try:
        if not values or not weights or len(values) != len(weights):
            return np.mean(values) if values else 0.0
        
        weighted_sum = sum(val * float(weight) for val, weight in zip(values, weights))
        total_weight = sum(float(weight) for weight in weights)
        
        if total_weight > 0:
            return weighted_sum / total_weight
        else:
            return np.mean(values)
            
    except Exception as e:
        print(f"Error calculating recency weighted average: {e}")
        return np.mean(values) if values else 0.0


def apply_momentum_weighting(matches: List[Dict], prediction_date: datetime) -> List[Dict]:
    """
    Apply momentum-based weighting that emphasizes streaks and trends.
    
    Recent winning/losing streaks get enhanced weighting to capture momentum.
    
    Args:
        matches: List of match data (most recent first)
        prediction_date: Date for prediction
        
    Returns:
        Matches with momentum-adjusted weights
    """
    try:
        if not matches:
            return []
        
        # Calculate base exponential weights
        base_weights = calculate_exponential_decay_weights(matches, prediction_date)
        
        # Detect current streak
        streak_type, streak_length = detect_current_streak(matches)
        
        # Apply momentum adjustment
        momentum_adjusted_weights = []
        
        for i, base_weight in enumerate(base_weights):
            # Enhance weight for recent matches if in a strong streak
            if i < streak_length and streak_type in ['winning', 'losing']:
                if streak_type == 'winning' and streak_length >= 3:
                    # Boost recent matches during winning streak
                    momentum_multiplier = min(1.3, 1.0 + (streak_length - 2) * 0.05)
                elif streak_type == 'losing' and streak_length >= 3:
                    # Also boost recent matches during losing streak (captures current form)
                    momentum_multiplier = min(1.2, 1.0 + (streak_length - 2) * 0.03)
                else:
                    momentum_multiplier = 1.0
            else:
                momentum_multiplier = 1.0
            
            adjusted_weight = base_weight * Decimal(str(momentum_multiplier))
            momentum_adjusted_weights.append(adjusted_weight)
        
        # Renormalize weights
        total_weight = sum(momentum_adjusted_weights)
        if total_weight > 0:
            normalized_weights = [w / total_weight for w in momentum_adjusted_weights]
        else:
            normalized_weights = momentum_adjusted_weights
        
        # Apply to matches
        weighted_matches = []
        for i, match in enumerate(matches):
            weighted_match = match.copy()
            weighted_match['momentum_weight'] = normalized_weights[i] if i < len(normalized_weights) else Decimal('0.01')
            weighted_match['streak_type'] = streak_type
            weighted_match['streak_length'] = streak_length
            weighted_matches.append(weighted_match)
        
        return weighted_matches
        
    except Exception as e:
        print(f"Error applying momentum weighting: {e}")
        return matches


# Helper Functions

def parse_match_date(date_str: str) -> datetime:
    """Parse match date string to datetime object (returns timezone-naive datetime)."""
    try:
        if not date_str:
            return datetime.min
        
        # Handle various date formats
        if 'T' in date_str:
            # Parse and convert to timezone-naive for consistent comparison
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.replace(tzinfo=None)  # Remove timezone info for consistency
        else:
            return datetime.strptime(date_str, '%Y-%m-%d')
            
    except Exception as e:
        print(f"Error parsing date '{date_str}': {e}")
        return datetime.min


def get_season_period(current_date: datetime) -> str:
    """Determine which period of the season we're currently in."""
    month = current_date.month
    
    # European football season calendar
    if month in [8, 9, 10]:
        return 'early_season'  # Aug-Oct: Season start
    elif month in [11, 12, 1, 2]:
        return 'mid_season'    # Nov-Feb: Middle period
    elif month in [3, 4, 5]:
        return 'late_season'   # Mar-May: Season end
    elif month in [6, 7]:
        return 'off_season'    # Jun-Jul: Off season
    else:
        return 'mid_season'    # Default


def get_team_seasonal_multipliers(team_id: int, league_id: int, season: int, 
                                season_period: str) -> Dict:
    """Get seasonal performance multipliers for a team."""
    try:
        # This would ideally fetch from historical analysis
        # For now, return conservative adjustments
        
        base_multipliers = {
            'early_season': {'scoring': Decimal('1.0'), 'form': Decimal('1.0')},
            'mid_season': {'scoring': Decimal('1.0'), 'form': Decimal('1.0')},
            'late_season': {'scoring': Decimal('1.0'), 'form': Decimal('1.0')},
            'off_season': {'scoring': Decimal('1.0'), 'form': Decimal('1.0')}
        }
        
        multipliers = base_multipliers.get(season_period, base_multipliers['mid_season']).copy()
        multipliers['confidence'] = Decimal('0.7')  # Medium confidence in adjustments
        
        return multipliers
        
    except Exception as e:
        print(f"Error getting seasonal multipliers for team {team_id}: {e}")
        return {'scoring': Decimal('1.0'), 'form': Decimal('1.0'), 'confidence': Decimal('0.5')}


def get_recent_fixtures_for_congestion(team_id: int, league_id: int, season: int,
                                     prediction_date: datetime) -> List[Dict]:
    """Get recent fixtures for congestion analysis."""
    try:
        api_client = APIClient()
        
        # Look back 21 days for congestion analysis
        start_date = prediction_date - timedelta(days=21)
        
        fixtures = api_client.get_team_fixtures_in_period(
            team_id, league_id, season, start_date, prediction_date
        )
        
        return fixtures or []
        
    except Exception as e:
        print(f"Error getting recent fixtures for team {team_id}: {e}")
        return []


def count_games_in_period(fixtures: List[Dict], prediction_date: datetime, 
                         days_back: int) -> int:
    """Count number of games played in the last N days."""
    cutoff_date = prediction_date - timedelta(days=days_back)
    
    count = 0
    for fixture in fixtures:
        fixture_date = parse_match_date(fixture.get('match_date', ''))
        if fixture_date >= cutoff_date and fixture_date < prediction_date:
            count += 1
    
    return count


def calculate_base_congestion_factor(games_7_days: int, games_14_days: int) -> float:
    """Calculate base congestion factor from recent game counts."""
    # Ideal is 1 game per week, adjust for deviations
    
    if games_7_days >= 3:
        return 0.95  # 5% penalty for 3+ games in week
    elif games_7_days >= 2:
        return 0.97  # 3% penalty for 2 games in week
    elif games_14_days >= 5:
        return 0.96  # 4% penalty for very busy 2 weeks
    elif games_14_days >= 4:
        return 0.98  # 2% penalty for busy 2 weeks
    else:
        return 1.0   # No congestion penalty


def calculate_travel_congestion_factor(fixtures: List[Dict], 
                                     prediction_date: datetime) -> float:
    """Calculate additional congestion from travel distance."""
    # Placeholder - would need actual travel distance data
    # For now, assume moderate impact
    return 0.99


def calculate_competition_congestion_factor(fixtures: List[Dict]) -> float:
    """Calculate congestion factor based on competition importance."""
    # More important competitions = more effort = more fatigue
    # For now, assume all competitions are equally important
    return 1.0


def calculate_linear_decay_weights(matches: List[Dict], 
                                 prediction_date: datetime) -> List[Decimal]:
    """Calculate linear decay weights (alternative to exponential)."""
    try:
        if not matches:
            return []
        
        n_matches = len(matches)
        weights = []
        
        # Linear decay: most recent gets weight n, second gets n-1, etc.
        for i in range(n_matches):
            weight = (n_matches - i) / n_matches
            weights.append(Decimal(str(round(weight, 4))))
        
        return weights
        
    except Exception as e:
        print(f"Error calculating linear decay weights: {e}")
        return [Decimal(str(1.0 / len(matches)))] * len(matches)


def calculate_form_based_weights(matches: List[Dict], 
                               prediction_date: datetime) -> List[Decimal]:
    """Calculate weights based on form periods rather than pure time decay."""
    try:
        if not matches:
            return []
        
        # Divide matches into form periods (every 5 matches)
        period_size = 5
        weights = []
        
        for i, match in enumerate(matches):
            period = i // period_size
            # Each period gets exponentially less weight
            period_weight = 0.8 ** period
            weights.append(Decimal(str(round(period_weight, 4))))
        
        # Normalize
        total_weight = sum(weights)
        if total_weight > 0:
            return [w / total_weight for w in weights]
        
        return weights
        
    except Exception as e:
        print(f"Error calculating form-based weights: {e}")
        return [Decimal(str(1.0 / len(matches)))] * len(matches)


def calculate_seasonal_weights(matches: List[Dict], 
                             prediction_date: datetime) -> List[Decimal]:
    """Calculate weights that emphasize same-season matches."""
    try:
        if not matches:
            return []
        
        current_season_year = prediction_date.year
        if prediction_date.month <= 7:  # Before August = previous season
            current_season_year -= 1
        
        weights = []
        
        for match in matches:
            match_date = parse_match_date(match.get('match_date', ''))
            match_season_year = match_date.year
            if match_date.month <= 7:
                match_season_year -= 1
            
            if match_season_year == current_season_year:
                # Same season gets higher weight
                base_weight = 1.0
            elif match_season_year == current_season_year - 1:
                # Previous season gets moderate weight
                base_weight = 0.5
            else:
                # Older seasons get low weight
                base_weight = 0.2
            
            weights.append(Decimal(str(round(base_weight, 4))))
        
        # Normalize
        total_weight = sum(weights)
        if total_weight > 0:
            return [w / total_weight for w in weights]
        
        return weights
        
    except Exception as e:
        print(f"Error calculating seasonal weights: {e}")
        return [Decimal(str(1.0 / len(matches)))] * len(matches)


def detect_current_streak(matches: List[Dict]) -> Tuple[str, int]:
    """Detect current winning/losing/drawing streak from recent matches."""
    if not matches:
        return 'none', 0
    
    # Get results from most recent matches
    results = []
    for match in matches:
        result = determine_match_result(match)
        if result:
            results.append(result)
    
    if not results:
        return 'none', 0
    
    # Count current streak
    current_result = results[0]
    streak_length = 1
    
    for result in results[1:]:
        if result == current_result:
            streak_length += 1
        else:
            break
    
    # Classify streak type
    if current_result == 'W':
        return 'winning', streak_length
    elif current_result == 'L':
        return 'losing', streak_length
    elif current_result == 'D':
        return 'drawing', streak_length
    else:
        return 'none', 0


def determine_match_result(match: Dict) -> Optional[str]:
    """Determine match result from match data."""
    try:
        home_goals = match.get('home_goals')
        away_goals = match.get('away_goals')
        
        if home_goals is None or away_goals is None:
            return None
        
        if home_goals > away_goals:
            return 'W' if match.get('home_team_id') == match.get('team_id') else 'L'
        elif away_goals > home_goals:
            return 'L' if match.get('home_team_id') == match.get('team_id') else 'W'
        else:
            return 'D'
            
    except Exception as e:
        print(f"Error determining match result: {e}")
        return None