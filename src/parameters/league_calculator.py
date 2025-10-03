"""
League parameter calculation functions with version tracking.
Calculates league-wide statistical parameters for football predictions.

Enhanced with Phase 0 version tracking infrastructure to prevent multiplier
contamination across different architecture versions.
"""

import numpy as np
import pandas as pd
from collections import Counter
from decimal import Decimal
from datetime import datetime, timedelta

from ..statistics.distributions import nb_probs
from ..statistics.optimization import tune_weights_grid
from ..data.database_client import query_dynamodb_records
from ..utils.converters import convert_for_dynamodb, decimal_to_float
from ..utils.constants import MINIMUM_LEAGUE_GAMES
from ..infrastructure.version_manager import VersionManager
from ..infrastructure.transition_manager import TransitionManager
from .multiplier_calculator import calculate_league_multipliers as calculate_league_multipliers_safe


def fit_league_params(df):
    """
    Fit league parameters from match data with version tracking.
    
    Enhanced with Phase 0 version tracking to prevent multiplier contamination.
    
    Args:
        df: DataFrame with match data containing 'home_goals' and 'away_goals'
        
    Returns:
        Dictionary with fitted league parameters and version metadata
    """
    if df.empty:
        return get_default_league_params()
    
    # Add home/away specific parameters
    g_home = df['home_goals']
    g_away = df['away_goals']
    
    # Calculate separate means and variances
    mu_home = g_home.mean()
    mu_away = g_away.mean()
    mu = (mu_home + mu_away) / 2  # Overall mean
    
    var_home = g_home.var()
    var_away = g_away.var()
    
    # Different alpha parameters for home and away
    alpha_home = max((var_home - mu_home) / mu_home**2, 0) if mu_home > 0 else 0
    alpha_away = max((var_away - mu_away) / mu_away**2, 0) if mu_away > 0 else 0
    
    # Overall alpha as weighted average
    alpha_nb = (alpha_home + alpha_away) / 2
    
    # Calculate scoring probabilities separately
    p_score_home = (g_home > 0).mean()
    p_score_away = (g_away > 0).mean()
    p_score = (p_score_home + p_score_away) / 2
    
    # Home advantage
    home_adv = mu_home / mu_away if mu_away != 0 else 1.0
    
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


def get_default_league_params():
    """
    Get default league parameters when no data is available, with version tracking.
    
    Returns:
        Dictionary with default league parameters and version metadata
    """
    # Get version tracking metadata
    version_manager = VersionManager()
    current_version = version_manager.get_current_version()
    version_metadata = version_manager.get_version_metadata()
    
    return {
        'mu': 1.5,
        'mu_home': 1.7,
        'mu_away': 1.3,
        'p_score': 0.75,
        'p_score_home': 0.80,
        'p_score_away': 0.70,
        'alpha': 0.3,
        'alpha_home': 0.3,
        'alpha_away': 0.3,
        'home_adv': 1.31,  # Typical home advantage
        'variance_home': 2.0,
        'variance_away': 1.5,
        # Phase 0 version tracking fields
        'architecture_version': current_version,
        'architecture_features': version_metadata['features'],
        'calculation_timestamp': int(datetime.now().timestamp()),
        'baseline_flag': True,
        'sample_size': 0,
        'fallback_source': 'default_parameters',
        'contamination_prevented': True
    }


def empirical_hist(goal_series, max_g=6):
    """
    Calculate empirical histogram of goals.
    
    Args:
        goal_series: Series or array of goal counts
        max_g: Maximum goals to consider
        
    Returns:
        Numpy array of probabilities for 0 to max_g goals
    """
    if goal_series.empty:
        # Return uniform distribution as fallback
        return np.ones(max_g + 1) / (max_g + 1)
    
    counts = Counter(np.clip(goal_series, 0, max_g))
    total = sum(counts.values())
    
    if total == 0:
        return np.ones(max_g + 1) / (max_g + 1)
    
    return np.array([counts[g]/total for g in range(max_g+1)])


def brier_score_goals(obs, exp):
    """
    Calculate Brier score for goal predictions.
    
    Args:
        obs: Observed probabilities
        exp: Expected probabilities
        
    Returns:
        Brier score (lower is better)
    """
    return np.mean((obs-exp)**2)


def calculate_league_multipliers_legacy(country, league, start_time=None, end_time=None, min_sample_size=20):
    """
    DEPRECATED: Legacy league multiplier calculation without version filtering.
    
    This function is kept for backward compatibility but should not be used
    in Phase 0+ architecture due to contamination risk.
    
    Use multiplier_calculator.calculate_league_multipliers() instead.
    """
    print(f"WARNING: Using legacy multiplier calculation for league {league}. This may cause contamination!")
    
    # Query historical fixtures with predictions
    fixtures = query_dynamodb_records(country, league, start_time, end_time)
    
    # Use the new version-safe calculator
    return calculate_league_multipliers_safe(f"{country}_{league}", fixtures, None, min_sample_size)


def get_default_multipliers():
    """
    Get default multiplier values when insufficient data is available, with version tracking.
    
    Returns:
        Dictionary with default multiplier values and version metadata
    """
    # Get version tracking metadata
    version_manager = VersionManager()
    current_version = version_manager.get_current_version()
    version_metadata = version_manager.get_version_metadata()
    
    return {
        'home_multiplier': Decimal('1.0'),
        'away_multiplier': Decimal('1.0'),
        'total_multiplier': Decimal('1.0'),
        'home_std': Decimal('0.5'),
        'away_std': Decimal('0.5'),
        'confidence': Decimal('0.1'),  # Low confidence for defaults
        'sample_size': 0,
        'timestamp': int(datetime.now().timestamp()),
        # Phase 0 version tracking fields
        'architecture_version': current_version,
        'architecture_features': version_metadata['features'],
        'calculation_timestamp': int(datetime.now().timestamp()),
        'baseline_flag': True,
        'fallback_source': 'default_multipliers',
        'contamination_prevented': True
    }


def validate_league_parameters(params):
    """
    Validate and sanitize league parameters.
    
    Args:
        params: Dictionary of league parameters
        
    Returns:
        Validated and sanitized parameters dictionary
    """
    validated = {}
    
    # Required numeric parameters with reasonable defaults and bounds
    param_specs = {
        'mu': (1.5, 0.1, 5.0),
        'mu_home': (1.7, 0.1, 5.0),
        'mu_away': (1.3, 0.1, 5.0),
        'p_score': (0.75, 0.1, 0.99),
        'p_score_home': (0.80, 0.1, 0.99),
        'p_score_away': (0.70, 0.1, 0.99),
        'alpha': (0.3, 0.01, 2.0),
        'alpha_home': (0.3, 0.01, 2.0),
        'alpha_away': (0.3, 0.01, 2.0),
        'home_adv': (1.31, 0.8, 2.0),
        'variance_home': (2.0, 0.1, 10.0),
        'variance_away': (1.5, 0.1, 10.0)
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
    
    return validated


def calculate_league_strength(df):
    """
    Calculate relative league strength metrics.
    
    Args:
        df: DataFrame with match data
        
    Returns:
        Dictionary with league strength metrics
    """
    if df.empty:
        return {'strength': 1.0, 'goals_per_game': 2.5, 'home_advantage': 1.3}
    
    total_goals = df['home_goals'].sum() + df['away_goals'].sum()
    total_matches = len(df)
    goals_per_game = total_goals / total_matches if total_matches > 0 else 2.5
    
    home_points = ((df['home_goals'] > df['away_goals']).sum() * 3 + 
                   (df['home_goals'] == df['away_goals']).sum() * 1)
    total_points = total_matches * 3
    home_advantage = (home_points / total_points) / 0.5 if total_points > 0 else 1.3  # Normalize to expected 50%
    
    # Relative strength based on goals per game (normalized to typical range)
    strength = min(2.0, max(0.5, goals_per_game / 2.5))
    
    return {
        'strength': strength,
        'goals_per_game': goals_per_game,
        'home_advantage': home_advantage,
        'total_matches': total_matches
    }


def update_league_parameters(league_id, new_match_data):
    """
    Update league parameters with new match data using incremental learning.
    
    Args:
        league_id: League identifier
        new_match_data: New match data to incorporate
        
    Returns:
        Updated parameters dictionary
    """
    from ..data.database_client import get_league_params_from_db, put_league_parameters
    
    # Get existing parameters
    existing_params = get_league_params_from_db(league_id)
    
    if existing_params is None:
        # First time - calculate from scratch
        updated_params = fit_league_params(new_match_data)
    else:
        # Incremental update with exponential smoothing
        new_params = fit_league_params(new_match_data)
        updated_params = {}
        
        # Smooth update with 0.1 learning rate
        alpha = 0.1
        for key in new_params:
            if key in existing_params:
                old_val = float(existing_params[key])
                new_val = float(new_params[key])
                updated_params[key] = alpha * new_val + (1 - alpha) * old_val
            else:
                updated_params[key] = new_params[key]
    
    # Get version tracking metadata
    version_manager = VersionManager()
    current_version = version_manager.get_current_version()
    version_metadata = version_manager.get_version_metadata()
    
    # Add metadata with version tracking
    updated_params['last_updated'] = int(datetime.now().timestamp())
    updated_params['match_count'] = len(new_match_data)
    updated_params['architecture_version'] = current_version
    updated_params['architecture_features'] = version_metadata['features']
    updated_params['calculation_timestamp'] = int(datetime.now().timestamp())
    updated_params['baseline_flag'] = True
    updated_params['contamination_prevented'] = True
    
    # Store updated parameters
    put_league_parameters(league_id, updated_params)
    
    return updated_params