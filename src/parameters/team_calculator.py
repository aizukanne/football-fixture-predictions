"""
Team parameter calculation functions with version tracking and opponent stratification.
Calculates team-specific statistical parameters for football predictions.

Enhanced with:
- Phase 0 version tracking infrastructure to prevent multiplier contamination
- Phase 1 opponent strength stratification for segmented parameter calculation
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
from ..features.opponent_classifier import get_opponent_tier_from_match


def fit_team_params(df, team_id, league_id, season=None):
    """
    Calculate team-specific parameters from match data with version tracking and opponent stratification.
    If insufficient data, use league parameters.
    
    Enhanced with:
    - Phase 0 version tracking to prevent multiplier contamination
    - Phase 1 opponent strength stratification for segmented parameters
    
    Args:
        df: DataFrame containing match data with team IDs and dates
        team_id: ID of the team to analyze
        league_id: ID of the league this team belongs to
        season: Season year for opponent classification (e.g., "2024")
    
    Returns:
        Dictionary with overall parameters and segmented parameters by opponent strength:
        {
            'overall': {traditional parameters},
            'segmented_params': {
                'vs_top': {parameters against top-tier opponents},
                'vs_middle': {parameters against middle-tier opponents},
                'vs_bottom': {parameters against bottom-tier opponents}
            }
        }
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
    
    # Create overall parameters (maintaining backward compatibility)
    overall_params = {
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
    
    # Phase 1 Enhancement: Calculate segmented parameters by opponent strength
    segmented_params = {}
    if season and not df.empty and len(df) >= MINIMUM_GAMES_THRESHOLD:
        try:
            segmented_params = calculate_segmented_params_by_opponent_strength(
                df, team_id, league_id, season, league_params
            )
        except Exception as e:
            print(f"Warning: Failed to calculate segmented parameters for team {team_id}: {e}")
            print("Falling back to overall parameters for all segments")
            # Fallback: use overall parameters for all segments
            segmented_params = {
                'vs_top': overall_params.copy(),
                'vs_middle': overall_params.copy(),
                'vs_bottom': overall_params.copy()
            }
    else:
        # Use overall parameters for all segments when insufficient data or no season provided
        segmented_params = {
            'vs_top': overall_params.copy(),
            'vs_middle': overall_params.copy(),
            'vs_bottom': overall_params.copy()
        }
    
    # Return enhanced structure with both overall and segmented parameters
    return {
        # Maintain backward compatibility by keeping overall parameters at root level
        **overall_params,
        
        # Phase 1 enhancement: segmented parameters
        'segmented_params': segmented_params,
        
        # Metadata about segmentation
        'segmentation_enabled': bool(season and not df.empty),
        'segmentation_version': '1.0'
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


def calculate_segmented_params_by_opponent_strength(df, team_id, league_id, season, league_params):
    """
    Calculate segmented team parameters by opponent strength tiers.
    
    This is the core Phase 1 enhancement that enables opponent-specific
    parameter calculation for more accurate predictions.
    
    Args:
        df: DataFrame containing match data with team IDs
        team_id: ID of the team to analyze
        league_id: ID of the league
        season: Season year for opponent classification
        league_params: League parameters for fallback
        
    Returns:
        Dict with parameters for each opponent strength tier
    """
    MIN_SEGMENT_MATCHES = 3  # Minimum matches required per segment
    
    # Segment matches by opponent strength tier
    matches_vs_top = []
    matches_vs_middle = []
    matches_vs_bottom = []
    
    print(f"Segmenting {len(df)} matches for team {team_id} by opponent strength...")
    
    for _, match in df.iterrows():
        try:
            # Get opponent tier from match perspective
            opponent_tier = get_opponent_tier_from_match(
                match['home_team_id'], match['away_team_id'],
                league_id, season, team_id
            )
            
            # Categorize match by opponent strength
            if opponent_tier == 'top':
                matches_vs_top.append(match)
            elif opponent_tier == 'middle':
                matches_vs_middle.append(match)
            elif opponent_tier == 'bottom':
                matches_vs_bottom.append(match)
            else:
                # Default to middle tier for unknown classifications
                matches_vs_middle.append(match)
                
        except Exception as e:
            print(f"Warning: Failed to classify opponent for match {match.get('fixture_id', 'unknown')}: {e}")
            # Default to middle tier on error
            matches_vs_middle.append(match)
    
    # Convert back to DataFrames
    df_vs_top = pd.DataFrame(matches_vs_top) if matches_vs_top else pd.DataFrame()
    df_vs_middle = pd.DataFrame(matches_vs_middle) if matches_vs_middle else pd.DataFrame()
    df_vs_bottom = pd.DataFrame(matches_vs_bottom) if matches_vs_bottom else pd.DataFrame()
    
    print(f"Segmentation results: vs_top={len(df_vs_top)}, vs_middle={len(df_vs_middle)}, vs_bottom={len(df_vs_bottom)}")
    
    # Calculate parameters for each segment
    segmented_params = {}
    
    # VS TOP TIER OPPONENTS
    if len(df_vs_top) >= MIN_SEGMENT_MATCHES:
        try:
            segmented_params['vs_top'] = calculate_segment_parameters(
                df_vs_top, team_id, league_params, segment_name='vs_top'
            )
        except Exception as e:
            print(f"Error calculating vs_top parameters: {e}")
            segmented_params['vs_top'] = get_fallback_segment_params(league_params, 'vs_top')
    else:
        print(f"Insufficient matches vs top opponents ({len(df_vs_top)} < {MIN_SEGMENT_MATCHES}), using fallback")
        segmented_params['vs_top'] = get_fallback_segment_params(league_params, 'vs_top')
    
    # VS MIDDLE TIER OPPONENTS
    if len(df_vs_middle) >= MIN_SEGMENT_MATCHES:
        try:
            segmented_params['vs_middle'] = calculate_segment_parameters(
                df_vs_middle, team_id, league_params, segment_name='vs_middle'
            )
        except Exception as e:
            print(f"Error calculating vs_middle parameters: {e}")
            segmented_params['vs_middle'] = get_fallback_segment_params(league_params, 'vs_middle')
    else:
        print(f"Insufficient matches vs middle opponents ({len(df_vs_middle)} < {MIN_SEGMENT_MATCHES}), using fallback")
        segmented_params['vs_middle'] = get_fallback_segment_params(league_params, 'vs_middle')
    
    # VS BOTTOM TIER OPPONENTS
    if len(df_vs_bottom) >= MIN_SEGMENT_MATCHES:
        try:
            segmented_params['vs_bottom'] = calculate_segment_parameters(
                df_vs_bottom, team_id, league_params, segment_name='vs_bottom'
            )
        except Exception as e:
            print(f"Error calculating vs_bottom parameters: {e}")
            segmented_params['vs_bottom'] = get_fallback_segment_params(league_params, 'vs_bottom')
    else:
        print(f"Insufficient matches vs bottom opponents ({len(df_vs_bottom)} < {MIN_SEGMENT_MATCHES}), using fallback")
        segmented_params['vs_bottom'] = get_fallback_segment_params(league_params, 'vs_bottom')
    
    return segmented_params


def calculate_segment_parameters(df_segment, team_id, league_params, segment_name):
    """
    Calculate parameters for a specific opponent strength segment.
    
    Args:
        df_segment: DataFrame with matches against specific opponent tier
        team_id: Team ID being analyzed
        league_params: League parameters for fallback values
        segment_name: Name of the segment (for logging)
        
    Returns:
        Dict with calculated parameters for this segment
    """
    MIN_HOME_MATCHES = 2  # Lower threshold for segments
    MIN_AWAY_MATCHES = 2
    
    # Split into home and away matches for this segment
    home_matches = df_segment[df_segment['home_team_id'] == team_id]
    away_matches = df_segment[df_segment['away_team_id'] == team_id]
    
    # Calculate team scoring in this segment
    g_home = home_matches['home_goals'] if not home_matches.empty else pd.Series([])
    g_away = away_matches['away_goals'] if not away_matches.empty else pd.Series([])
    
    # Calculate conceding in this segment
    g_home_against = home_matches['away_goals'] if not home_matches.empty else pd.Series([])
    g_away_against = away_matches['home_goals'] if not away_matches.empty else pd.Series([])
    
    # Initialize with league parameters if available
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
    
    # Calculate segment-specific parameters if we have enough data
    using_segment_home = False
    using_segment_away = False
    
    if len(g_home) >= MIN_HOME_MATCHES:
        mu_home = g_home.mean()
        var_home = g_home.var() if len(g_home) > 1 else 1.65
        p_score_home = (g_home > 0).mean()
        alpha_home = max((var_home - mu_home) / mu_home**2, 0.01) if mu_home > 0 else 0.1
        using_segment_home = True
    
    if len(g_away) >= MIN_AWAY_MATCHES:
        mu_away = g_away.mean()
        var_away = g_away.var() if len(g_away) > 1 else 1.3
        p_score_away = (g_away > 0).mean()
        alpha_away = max((var_away - mu_away) / mu_away**2, 0.01) if mu_away > 0 else 0.1
        using_segment_away = True
    
    # Calculate segment averages
    total_matches = len(g_home) + len(g_away)
    if total_matches > 0:
        home_weight = len(g_home) / total_matches
        away_weight = len(g_away) / total_matches
        
        mu = (mu_home * home_weight + mu_away * away_weight)
        p_score = (p_score_home * home_weight + p_score_away * away_weight)
        
        # Weighted alpha calculation
        if using_segment_home or using_segment_away:
            weights_sum = (home_weight if using_segment_home else 0) + (away_weight if using_segment_away else 0)
            if weights_sum > 0:
                alpha_nb = ((alpha_home * home_weight if using_segment_home else 0) +
                           (alpha_away * away_weight if using_segment_away else 0)) / weights_sum
            else:
                alpha_nb = league_params.get('alpha', 0.1) if league_params else 0.1
        else:
            alpha_nb = league_params.get('alpha', 0.1) if league_params else 0.1
    else:
        mu = (mu_home + mu_away) / 2
        p_score = (p_score_home + p_score_away) / 2
        alpha_nb = (alpha_home + alpha_away) / 2
    
    # Calculate home advantage for this segment
    if mu_away > 0:
        home_adv = mu_home / mu_away
    
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
        'using_segment_home': using_segment_home,
        'using_segment_away': using_segment_away,
        'segment_name': segment_name,
        'segment_sample_size': total_matches,
        'home_matches': len(g_home),
        'away_matches': len(g_away),
        # Phase 0 version tracking
        'architecture_version': current_version,
        'architecture_features': version_metadata['features'],
        'calculation_timestamp': int(datetime.now().timestamp()),
        'baseline_flag': True,
        'contamination_prevented': True
    }


def get_fallback_segment_params(league_params, segment_name):
    """
    Get fallback parameters for a segment when insufficient data is available.
    
    Args:
        league_params: League parameters to use as fallback
        segment_name: Name of the segment
        
    Returns:
        Dict with fallback parameters
    """
    # Get version tracking metadata
    version_manager = VersionManager()
    current_version = version_manager.get_current_version()
    version_metadata = version_manager.get_version_metadata()
    
    if league_params:
        base_params = {
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
            'variance_home': league_params.get('variance_home', 1.65),
            'variance_away': league_params.get('variance_away', 1.3)
        }
    else:
        base_params = {
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
            'variance_home': 1.65,
            'variance_away': 1.3
        }
    
    return {
        **base_params,
        'using_segment_home': False,
        'using_segment_away': False,
        'segment_name': segment_name,
        'segment_sample_size': 0,
        'home_matches': 0,
        'away_matches': 0,
        'fallback_source': 'league_parameters' if league_params else 'default_parameters',
        # Phase 0 version tracking
        'architecture_version': current_version,
        'architecture_features': version_metadata['features'],
        'calculation_timestamp': int(datetime.now().timestamp()),
        'baseline_flag': True,
        'contamination_prevented': True
    }


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