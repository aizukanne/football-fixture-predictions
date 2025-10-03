"""
Team parameter calculation functions with version tracking.
Calculates team-specific statistical parameters for football predictions.

Enhanced with Phase 0 version tracking infrastructure to prevent multiplier
contamination across different architecture versions.
"""

import math
import numpy as np
import pandas as pd
from collections import Counter
from decimal import Decimal
from datetime import datetime

from ..statistics.distributions import nb_probs
from ..statistics.optimization import tune_weights_grid_team
from ..data.database_client import fetch_league_parameters
from ..utils.constants import MINIMUM_GAMES_THRESHOLD
from ..infrastructure.version_manager import VersionManager
from ..infrastructure.transition_manager import TransitionManager
from .multiplier_calculator import calculate_team_multipliers


def fit_team_params(df, team_id, league_id):
    """
    Calculate team-specific parameters from match data with version tracking.
    If insufficient data, use league parameters.
    
    Enhanced with Phase 0 version tracking to prevent multiplier contamination.
    
    Args:
        df: DataFrame containing match data with team IDs
        team_id: ID of the team to analyze
        league_id: ID of the league this team belongs to
    
    Returns:
        Dictionary of team parameters with version metadata
    """
    # Define the minimum matches needed for reliable parameter calculation
    MIN_HOME_MATCHES = 5
    MIN_AWAY_MATCHES = 5
    
    # Fetch league parameters to use as fallback
    league_params = fetch_league_parameters(league_id)
    
    if df.empty or len(df) < MINIMUM_GAMES_THRESHOLD:  # Too little data overall
        if league_params:
            print(f"Insufficient match data for team {team_id}. Using league parameters for league {league_id}.")
            # Get version tracking metadata
            version_manager = VersionManager()
            current_version = version_manager.get_current_version()
            version_metadata = version_manager.get_version_metadata()
            
            return {
                'mu': league_params.get('mu', 1.35),
                'mu_home': league_params.get('mu_home', 1.5),
                'mu_away': league_params.get('mu_away', 1.2),
                'p_score': league_params.get('p_score', 0.7),
                'p_score_home': league_params.get('p_score_home', 0.75),
                'p_score_away': league_params.get('p_score_away', 0.65),
                'alpha': league_params.get('alpha', 0.1),
                'alpha_home': league_params.get('alpha_home', 0.1),
                'alpha_away': league_params.get('alpha_away', 0.1),
                'home_adv': league_params.get('home_adv', 1.25),
                'variance_home': league_params.get('variance_home', 1.0),
                'variance_away': league_params.get('variance_away', 1.0),
                # Phase 0 version tracking fields
                'architecture_version': current_version,
                'architecture_features': version_metadata['features'],
                'calculation_timestamp': int(datetime.now().timestamp()),
                'baseline_flag': True,
                'sample_size': 0,
                'fallback_source': 'league_parameters',
                'contamination_prevented': True
            }
        else:
            print(f"Insufficient match data for team {team_id} and no league parameters found. Using default values.")
            return get_default_team_params()
    
    # Split into home and away matches
    home_matches = df[df['home_team_id'] == team_id]
    away_matches = df[df['away_team_id'] == team_id]
    
    # Calculate team scoring when playing at home
    g_home = home_matches['home_goals'] if not home_matches.empty else pd.Series([])
    
    # Calculate team scoring when playing away
    g_away = away_matches['away_goals'] if not away_matches.empty else pd.Series([])
    
    # Calculate conceding (goals against)
    g_home_against = home_matches['away_goals'] if not home_matches.empty else pd.Series([])
    g_away_against = away_matches['home_goals'] if not away_matches.empty else pd.Series([])
    
    # Initialize using league parameters if available, otherwise use reasonable defaults
    if league_params:
        mu_home = league_params.get('mu_home', 1.5)
        mu_away = league_params.get('mu_away', 1.2)
        p_score_home = league_params.get('p_score_home', 0.75)
        p_score_away = league_params.get('p_score_away', 0.65)
        alpha_home = league_params.get('alpha_home', 0.1)
        alpha_away = league_params.get('alpha_away', 0.1)
        home_adv = league_params.get('home_adv', 1.25)
    else:
        mu_home = 1.5
        mu_away = 1.2
        p_score_home = 0.75
        p_score_away = 0.65
        alpha_home = 0.1
        alpha_away = 0.1
        home_adv = 1.25
    
    # Initialize variance values
    var_home = 1.65
    var_away = 1.3
    
    # Flag to track if team-specific values are used
    using_team_home = False
    using_team_away = False
    
    # Calculate parameters if we have enough data
    if len(g_home) >= MIN_HOME_MATCHES:
        mu_home = g_home.mean()
        var_home = g_home.var() if len(g_home) > 1 else 1.65
        p_score_home = (g_home > 0).mean()
        using_team_home = True
    else:
        print(f"Insufficient home match data for team {team_id} ({len(g_home)} < {MIN_HOME_MATCHES}). Using league values.")
    
    if len(g_away) >= MIN_AWAY_MATCHES:
        mu_away = g_away.mean()
        var_away = g_away.var() if len(g_away) > 1 else 1.3
        p_score_away = (g_away > 0).mean()
        using_team_away = True
    else:
        print(f"Insufficient away match data for team {team_id} ({len(g_away)} < {MIN_AWAY_MATCHES}). Using league values.")
    
    # Overall averages (weighted by sample size)
    home_weight = len(g_home) / max(len(g_home) + len(g_away), 1)
    away_weight = len(g_away) / max(len(g_home) + len(g_away), 1)
    
    # Calculate weighted mu and p_score
    mu = (mu_home * home_weight + mu_away * away_weight) / (home_weight + away_weight)
    p_score = (p_score_home * home_weight + p_score_away * away_weight) / (home_weight + away_weight)
    
    # Calculate home advantage as ratio of scoring at home vs away
    if mu_away > 0:
        home_adv = mu_home / mu_away
    
    # Calculate alpha parameters (overdispersion)
    if using_team_home:
        alpha_home = max((var_home - mu_home) / mu_home**2, 0) if mu_home > 0 else 0.1
    
    if using_team_away:
        alpha_away = max((var_away - mu_away) / mu_away**2, 0) if mu_away > 0 else 0.1
    
    # Use weighted average for overall alpha
    if using_team_home or using_team_away:
        weights_sum = (home_weight if using_team_home else 0) + (away_weight if using_team_away else 0)
        if weights_sum > 0:
            alpha_nb = ((alpha_home * home_weight if using_team_home else 0) + 
                        (alpha_away * away_weight if using_team_away else 0)) / weights_sum
        else:
            alpha_nb = league_params.get('alpha', 0.1) if league_params else 0.1
    else:
        alpha_nb = league_params.get('alpha', 0.1) if league_params else 0.1
    
    # Get version tracking metadata
    version_manager = VersionManager()
    current_version = version_manager.get_current_version()
    version_metadata = version_manager.get_version_metadata()
    
    return {
        'mu': mu,
        'mu_home': mu_home,
        'mu_away': mu_away,
        'p_score': p_score,
        'p_score_home': p_score_home,
        'p_score_away': p_score_away,
        'alpha': alpha_nb,
        'alpha_home': alpha_home,
        'alpha_away': alpha_away,
        'home_adv': home_adv,
        'using_team_home': using_team_home,
        'using_team_away': using_team_away,
        'variance_home': var_home,
        'variance_away': var_away,
        # Phase 0 version tracking fields
        'architecture_version': current_version,
        'architecture_features': version_metadata['features'],
        'calculation_timestamp': int(datetime.now().timestamp()),
        'baseline_flag': True,  # These are baseline parameters without multipliers
        'sample_size': len(df) if not df.empty else 0,
        'contamination_prevented': True
    }


def get_default_team_params():
    """
    Get default team parameters when no data is available, with version tracking.
    
    Returns:
        Dictionary with default team parameters and version metadata
    """
    # Get version tracking metadata
    version_manager = VersionManager()
    current_version = version_manager.get_current_version()
    version_metadata = version_manager.get_version_metadata()
    
    return {
        'mu': 1.35,
        'mu_home': 1.5,
        'mu_away': 1.2,
        'p_score': 0.7,
        'p_score_home': 0.75,
        'p_score_away': 0.65,
        'alpha': 0.1,
        'alpha_home': 0.1,
        'alpha_away': 0.1,
        'home_adv': 1.25,
        'variance_home': 1.0,
        'variance_away': 1.0,
        # Phase 0 version tracking fields
        'architecture_version': current_version,
        'architecture_features': version_metadata['features'],
        'calculation_timestamp': int(datetime.now().timestamp()),
        'baseline_flag': True,
        'sample_size': 0,
        'fallback_source': 'default_parameters',
        'contamination_prevented': True
    }


def calculate_team_multipliers_legacy(team_id, fixtures_data, min_sample_size=10):
    """
    DEPRECATED: Legacy team multiplier calculation without version filtering.
    
    This function is kept for backward compatibility but should not be used
    in Phase 0+ architecture due to contamination risk.
    
    Use multiplier_calculator.calculate_team_multipliers() instead.
    """
    print(f"WARNING: Using legacy multiplier calculation for team {team_id}. This may cause contamination!")
    
    # Import the new version-safe calculator
    from .multiplier_calculator import calculate_team_multipliers as new_calculator
    
    # Use the new calculator with current version filtering
    return new_calculator(team_id, fixtures_data, None, min_sample_size)


def confidence_weighted_multiplier(raw_ratio, confidence, max_adjustment=0.5):
    """
    Apply confidence weighting to raw multiplier ratios.
    
    Args:
        raw_ratio: Raw multiplier ratio from data
        confidence: Confidence level (0-1)
        max_adjustment: Maximum adjustment from 1.0
    
    Returns:
        Confidence-weighted multiplier
    """
    if confidence <= 0:
        return 1.0
    
    # Clamp raw ratio to reasonable bounds
    clamped_ratio = max(0.5, min(2.0, raw_ratio))
    
    # Weight towards 1.0 based on confidence
    # Lower confidence = closer to 1.0
    weighted_ratio = confidence * clamped_ratio + (1 - confidence) * 1.0
    
    # Further clamp the final result
    final_multiplier = max(1.0 - max_adjustment, min(1.0 + max_adjustment, weighted_ratio))
    
    return final_multiplier


def filter_team_matches(df, team_id):
    """
    Filter matches DataFrame to only include matches involving the specified team.
    
    Args:
        df: DataFrame with match data
        team_id: Team ID to filter for
        
    Returns:
        Filtered DataFrame with only matches involving the team
    """
    if df.empty:
        return df
    
    team_matches = df[
        (df['home_team_id'] == team_id) | 
        (df['away_team_id'] == team_id)
    ]
    
    return team_matches


def games_played_per_team(league_id, season, team_id):
    """
    Get the number of games played by a team in a specific league and season.
    
    Args:
        league_id: League identifier
        season: Season year
        team_id: Team identifier
        
    Returns:
        Number of games played
    """
    from ..data.api_client import get_team_statistics
    
    try:
        team_stats = get_team_statistics(league_id, season, team_id)
        if team_stats and 'response' in team_stats and team_stats['response']:
            fixtures = team_stats['response'].get('fixtures', {})
            played = fixtures.get('played', {})
            return played.get('total', 0)
        return 0
    except Exception as e:
        print(f"Error getting games played for team {team_id}: {e}")
        return 0


def calculate_team_form(recent_matches, weight_decay=0.9):
    """
    Calculate team form based on recent match results with exponential decay.
    
    Args:
        recent_matches: List of recent match results (1 for win, 0.5 for draw, 0 for loss)
        weight_decay: Decay factor for older matches
        
    Returns:
        Form score (0-1, higher is better)
    """
    if not recent_matches:
        return 0.5  # Neutral form
    
    weighted_sum = 0
    total_weight = 0
    
    for i, result in enumerate(recent_matches):
        weight = weight_decay ** i  # More recent matches have higher weight
        weighted_sum += result * weight
        total_weight += weight
    
    return weighted_sum / total_weight if total_weight > 0 else 0.5


def validate_team_parameters(params):
    """
    Validate and sanitize team parameters.
    
    Args:
        params: Dictionary of team parameters
        
    Returns:
        Validated and sanitized parameters dictionary
    """
    validated = {}
    
    # Required numeric parameters with reasonable defaults and bounds
    param_specs = {
        'mu': (1.35, 0.1, 5.0),
        'mu_home': (1.5, 0.1, 5.0),
        'mu_away': (1.2, 0.1, 5.0),
        'p_score': (0.7, 0.1, 0.99),
        'p_score_home': (0.75, 0.1, 0.99),
        'p_score_away': (0.65, 0.1, 0.99),
        'alpha': (0.1, 0.01, 2.0),
        'alpha_home': (0.1, 0.01, 2.0),
        'alpha_away': (0.1, 0.01, 2.0),
        'home_adv': (1.25, 0.8, 2.0),
        'variance_home': (1.0, 0.1, 10.0),
        'variance_away': (1.0, 0.1, 10.0)
    }
    
    for param_name, (default, min_val, max_val) in param_specs.items():
        value = params.get(param_name, default)
        
        try:
            # Convert to float and validate range
            value = float(value)
            value = max(min_val, min(max_val, value))
            validated[param_name] = value
        except (TypeError, ValueError):
            print(f"Invalid value for {param_name}: {value}. Using default: {default}")
            validated[param_name] = default
    
    # Handle boolean flags
    validated['using_team_home'] = bool(params.get('using_team_home', False))
    validated['using_team_away'] = bool(params.get('using_team_away', False))
    
    return validated