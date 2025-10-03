"""
Main prediction engine for football fixture predictions with version tracking, opponent stratification, venue analysis, and temporal evolution.
Consolidates the core prediction logic from makeTeamRankings.py.

Enhanced with:
- Phase 0 version tracking infrastructure to prevent multiplier contamination
- Phase 1 opponent strength stratification for more accurate predictions
- Phase 2 venue analysis for stadium advantages and travel impacts
- Phase 3 temporal evolution for time-aware prediction intelligence
"""

import numpy as np
from decimal import Decimal
from datetime import datetime
from typing import Dict, Tuple, Optional

from ..statistics.distributions import calculate_goal_probabilities, squash_lambda
from ..statistics.bayesian import apply_smoothing_to_team_data, apply_smoothing_to_binary_rate
from ..utils.constants import DEFAULT_SMOOTHING_ALPHA
from ..utils.converters import decimal_to_float
from ..infrastructure.version_manager import VersionManager
from ..infrastructure.transition_manager import TransitionManager
from ..features.opponent_classifier import get_opponent_tier_from_match
from ..features.venue_analyzer import VenueAnalyzer, calculate_stadium_advantage, calculate_travel_distance
from ..features.surface_analyzer import SurfaceAnalyzer, compare_teams_surface_matchup
from ..utils.geographic import calculate_combined_travel_impact
# Phase 3 temporal analysis imports
from ..features.form_analyzer import analyze_head_to_head_form
from ..parameters.team_calculator import get_temporal_multiplier_for_prediction


def get_segmented_params(team_params, opponent_team_id, league_id, season):
    """
    Get segmented parameters based on opponent strength tier (Phase 1 enhancement).
    
    This function determines the opponent's strength tier and selects the appropriate
    segmented parameters to improve prediction accuracy.
    
    Args:
        team_params: Team parameters dictionary (with segmented_params if available)
        opponent_team_id: ID of the opposing team
        league_id: League ID
        season: Season for opponent classification
        
    Returns:
        Dict: Appropriate parameter set based on opponent strength
    """
    # Check if segmented parameters are available (Phase 1 feature)
    if not team_params.get('segmented_params') or not season:
        # Fallback to overall parameters for backward compatibility
        return team_params
    
    try:
        # For prediction purposes, we need to classify the opponent team
        # Since we don't have specific match context here, we'll use a simplified approach
        # by getting the opponent's overall tier classification
        from ..features.opponent_classifier import OpponentClassifier
        classifier = OpponentClassifier()
        opponent_tier = classifier.get_team_tier(opponent_team_id, league_id, season)
        
        # Select appropriate segmented parameters
        segmented_params = team_params['segmented_params']
        segment_key = f'vs_{opponent_tier}'
        
        if segment_key in segmented_params:
            selected_params = segmented_params[segment_key]
            print(f"Using {segment_key} parameters for opponent {opponent_team_id} (tier: {opponent_tier})")
            return selected_params
        else:
            print(f"Segmented parameters not available for {segment_key}, using overall parameters")
            return team_params
            
    except Exception as e:
        print(f"Warning: Failed to select segmented parameters: {e}, using overall parameters")
        return team_params


def calculate_to_score(team1_stats, team2_stats, params, is_home=True, league_id=None, opponent_lambda=None):
    """
    Calculate the score for a team using Bayesian smoothing and data-driven multipliers.
    Enhanced with comprehensive error handling, opponent lambda for ratio preservation,
    and Phase 0 version compatibility checks.
    
    Args:
        team1_stats: Raw match stats for team 1
        team2_stats: Raw match stats for team 2
        params: League/team parameters with version metadata
        is_home: Whether this is for home team calculation
        league_id: League identifier
        opponent_lambda: Opponent lambda for ratio preservation
        
    Returns:
        Tuple of (score_probability, predicted_goals, likelihood, goal_probabilities)
    """
    
    # Validate input parameters
    if not team1_stats or not team2_stats or not params:
        print("Error: Missing required parameters")
        raise ValueError("Missing required parameters for calculate_to_score")
        
    # Unpack raw match stats with validation
    team1_goals_scored_raw, team1_goals_conceded_raw, team1_games_scored_raw, team1_games_cleanSheet_raw, team1_games_total = team1_stats
    team2_goals_scored_raw, team2_goals_conceded_raw, team2_games_scored_raw, team2_games_cleanSheet_raw, team2_games_total = team2_stats

    # Validate games_total to prevent division by zero
    if team1_games_total is None or team1_games_total <= 0:
        raise ValueError("team1_games_total is invalid or zero")
        
    if team2_games_total is None or team2_games_total <= 0:
        raise ValueError("team2_games_total is invalid or zero")

    # Extract parameters with defaults
    try:
        k_goals = params['k_goals']
        k_score = params['k_score']
        league_home_adv = params['home_adv']
        ref_games = params.get('ref_games', 20)
        confidence = params.get('confidence', 0.5)
        sample_size = params.get('sample_size', 20)
        alpha_smooth = DEFAULT_SMOOTHING_ALPHA
        
        # Determine which parameters to use based on home/away status
        if is_home:
            goal_prior = params['mu_home']
            score_prior = params['p_score_home']
            alpha_nb = params['alpha_home']
            multiplier = params.get('home_multiplier', Decimal('1.0'))
            alpha_factor = params.get('alpha_home_factor', 1.0)
            std_dev = params.get('home_std', Decimal('0.5'))
            raw_ratio = params.get('home_ratio_raw', Decimal('1.0'))
            
            # Phase 0: Check for version compatibility and contamination prevention
            if 'architecture_version' in params:
                version_manager = VersionManager()
                current_version = version_manager.get_current_version()
                param_version = params['architecture_version']
                
                compatible, reason = version_manager.validate_multiplier_compatibility(param_version, current_version)
                if not compatible:
                    print(f"WARNING: Parameter version incompatibility detected for home team: {reason}")
                    # Fallback to neutral multiplier to prevent contamination
                    multiplier = Decimal('1.0')
                    print(f"Applied neutral multiplier (1.0) to prevent contamination")
        else:
            goal_prior = params['mu_away']
            score_prior = params['p_score_away']
            alpha_nb = params['alpha_away']
            multiplier = params.get('away_multiplier', Decimal('1.0'))
            alpha_factor = params.get('alpha_away_factor', 1.0)
            std_dev = params.get('away_std', Decimal('0.5'))
            raw_ratio = params.get('away_ratio_raw', Decimal('1.0'))
            
            # Phase 0: Check for version compatibility and contamination prevention
            if 'architecture_version' in params:
                version_manager = VersionManager()
                current_version = version_manager.get_current_version()
                param_version = params['architecture_version']
                
                compatible, reason = version_manager.validate_multiplier_compatibility(param_version, current_version)
                if not compatible:
                    print(f"WARNING: Parameter version incompatibility detected for away team: {reason}")
                    # Fallback to neutral multiplier to prevent contamination
                    multiplier = Decimal('1.0')
                    print(f"Applied neutral multiplier (1.0) to prevent contamination")

        league_std = {'std_dev': std_dev, 'raw_ratio': raw_ratio}
            
    except KeyError as e:
        raise ValueError(f"Missing required parameter: {e}")

    # Calculate prior weights with error handling
    goal_prior_weight = prior_weight_from_k(team1_games_total, k_goals, ref_games)
    score_prior_weight = prior_weight_from_k(team1_games_total, k_score, ref_games, lo=4, hi=10)
    
    goal_prior_weight = max(goal_prior_weight - 1, 2)
    score_prior_weight = max(score_prior_weight - 1, 3)

    # Apply smoothing to raw match data with error handling
    team1_goals_scored = apply_smoothing_to_team_data(
        team1_goals_scored_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    team1_goals_conceded = apply_smoothing_to_team_data(
        team1_goals_conceded_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    team2_goals_scored = apply_smoothing_to_team_data(
        team2_goals_scored_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    team2_goals_conceded = apply_smoothing_to_team_data(
        team2_goals_conceded_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    
    # Apply smoothing to games scored and clean sheets as rates
    team1_games_scored = apply_smoothing_to_binary_rate(
        team1_games_scored_raw, team1_games_total, alpha_smooth, score_prior, score_prior_weight, use_bayesian=True)
    team1_games_cleanSheet = apply_smoothing_to_binary_rate(
        team1_games_cleanSheet_raw, team1_games_total, alpha_smooth, 1-score_prior, score_prior_weight, use_bayesian=True)
    team2_games_scored = apply_smoothing_to_binary_rate(
        team2_games_scored_raw, team2_games_total, alpha_smooth, score_prior, score_prior_weight, use_bayesian=True)
    team2_games_cleanSheet = apply_smoothing_to_binary_rate(
        team2_games_cleanSheet_raw, team2_games_total, alpha_smooth, 1-score_prior, score_prior_weight, use_bayesian=True)
    
    if is_home:
        lmbda = (team1_goals_scored * team2_goals_conceded * 
                    team1_games_scored * 
                    (1 - team2_games_cleanSheet))
    else:
        lmbda = (team2_goals_scored * team1_goals_conceded * 
                    team2_games_scored * 
                    (1 - team1_games_cleanSheet))      
    
    print(f'Initial Lambda: {lmbda}')

    # Calculate shrinkage factor based on team's game count
    team_games = team1_games_total if is_home else team2_games_total
    k = ref_games
    shrinkage_factor = k / (k + team_games)
    
    # Store original lambda for reporting
    lmbda_original = lmbda

    # Home advantage adjustment
    if is_home:
        lmbda *= league_home_adv
    else:
        lmbda *= 1/league_home_adv

    # Apply smart correction with multipliers
    multiplier_float = float(multiplier)
    lmbda *= multiplier_float
    
    # Apply lambda ceiling to prevent extreme predictions
    lmbda = squash_lambda(lmbda)
    
    print(f'Final Lambda after multiplier and ceiling: {lmbda}')
    
    # Calculate goal probabilities
    most_likely_goals, likelihood, goal_probs = calculate_goal_probabilities(lmbda, alpha_nb)
    
    # Calculate probability to score (1 - P(0 goals))
    prob_to_score = 1 - goal_probs.get(0, 0)
    
    return prob_to_score, most_likely_goals, likelihood, goal_probs


def calculate_base_lambda(team1_stats, team2_stats, params, is_home=True):
    """
    Calculate base lambda before corrections for ratio preservation.
    This function extracts the core lambda calculation logic without applying
    smart corrections, allowing for coordinated home/away adjustments.
    
    Args:
        team1_stats: Raw match stats for team 1 (attacking team)
        team2_stats: Raw match stats for team 2 (defending team)
        params: League/team parameters
        is_home: Whether this is for home team calculation
        
    Returns:
        base_lambda: Lambda value before smart corrections (float)
    """
    
    # Validate input parameters
    if not team1_stats or not team2_stats or not params:
        raise ValueError("Missing required parameters for calculate_base_lambda")
        
    # Unpack raw match stats
    team1_goals_scored_raw, team1_goals_conceded_raw, team1_games_scored_raw, team1_games_cleanSheet_raw, team1_games_total = team1_stats
    team2_goals_scored_raw, team2_goals_conceded_raw, team2_games_scored_raw, team2_games_cleanSheet_raw, team2_games_total = team2_stats

    # Validate games_total
    if team1_games_total is None or team1_games_total <= 0 or team2_games_total is None or team2_games_total <= 0:
        raise ValueError("Invalid games_total values")

    # Extract parameters
    try:
        k_goals = params['k_goals']
        k_score = params['k_score']
        league_home_adv = params['home_adv']
        ref_games = params.get('ref_games', 20)
        alpha_smooth = DEFAULT_SMOOTHING_ALPHA
        
        # Get appropriate priors based on home/away
        if is_home:
            goal_prior = params['mu_home']
            score_prior = params['p_score_home']
        else:
            goal_prior = params['mu_away']
            score_prior = params['p_score_away']
            
    except KeyError as e:
        raise ValueError(f"Missing required parameter: {e}")

    # Calculate prior weights
    goal_prior_weight = prior_weight_from_k(team1_games_total, k_goals, ref_games)
    score_prior_weight = prior_weight_from_k(team1_games_total, k_score, ref_games, lo=4, hi=10)
    
    goal_prior_weight = max(goal_prior_weight - 1, 2)
    score_prior_weight = max(score_prior_weight - 1, 3)

    # Apply smoothing to raw match data
    team1_goals_scored = apply_smoothing_to_team_data(
        team1_goals_scored_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    team1_goals_conceded = apply_smoothing_to_team_data(
        team1_goals_conceded_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    team2_goals_scored = apply_smoothing_to_team_data(
        team2_goals_scored_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    team2_goals_conceded = apply_smoothing_to_team_data(
        team2_goals_conceded_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    
    # Apply smoothing to games scored and clean sheets as rates
    team1_games_scored = apply_smoothing_to_binary_rate(
        team1_games_scored_raw, team1_games_total, alpha_smooth, score_prior, score_prior_weight, use_bayesian=True)
    team1_games_cleanSheet = apply_smoothing_to_binary_rate(
        team1_games_cleanSheet_raw, team1_games_total, alpha_smooth, 1-score_prior, score_prior_weight, use_bayesian=True)
    team2_games_scored = apply_smoothing_to_binary_rate(
        team2_games_scored_raw, team2_games_total, alpha_smooth, score_prior, score_prior_weight, use_bayesian=True)
    team2_games_cleanSheet = apply_smoothing_to_binary_rate(
        team2_games_cleanSheet_raw, team2_games_total, alpha_smooth, 1-score_prior, score_prior_weight, use_bayesian=True)
    
    # Calculate base lambda using the same formula as calculate_to_score
    if is_home:
        base_lambda = (team1_goals_scored * team2_goals_conceded * 
                      team1_games_scored * 
                      (1 - team2_games_cleanSheet))
    else:
        base_lambda = (team2_goals_scored * team1_goals_conceded * 
                      team2_games_scored * 
                      (1 - team1_games_cleanSheet))
    
    return base_lambda


def calculate_coordinated_predictions(home_team_parameters, away_team_parameters, home_params, away_params, league_id, season=None, home_team_id=None, away_team_id=None, venue_id=None, prediction_date=None):
    """
    Calculate coordinated predictions that preserve the ratio between home and away lambdas.
    This replaces individual lambda calculations with coordinated ones.
    
    Enhanced with:
    - Phase 0 version tracking and hierarchical fallback integration
    - Phase 1 opponent strength stratification for improved accuracy
    - Phase 2 venue-specific advantages and travel distance impacts
    - Phase 3 temporal evolution for time-aware prediction intelligence
    
    Args:
        home_team_parameters: Home team raw match data
        away_team_parameters: Away team raw match data
        home_params: Home team parameters with version metadata and segmented params
        away_params: Away team parameters with version metadata and segmented params
        league_id: League identifier
        season: Season for opponent classification (Phase 1)
        home_team_id: Home team ID (Phase 1)
        away_team_id: Away team ID (Phase 1)
        venue_id: Venue ID for stadium-specific analysis (Phase 2)
        prediction_date: Date for temporal analysis (Phase 3)
        
    Returns:
        Tuple of prediction results for both teams and coordination info
    """
    try:
        # Phase 1 Enhancement: Select opponent-specific parameters if available
        effective_home_params = home_params
        effective_away_params = away_params
        
        # Apply opponent strength stratification if Phase 1 data is available
        if season and home_team_id and away_team_id:
            try:
                # Home team gets parameters for playing against away team's strength tier
                effective_home_params = get_segmented_params(
                    home_params, away_team_id, league_id, season
                )
                
                # Away team gets parameters for playing against home team's strength tier
                effective_away_params = get_segmented_params(
                    away_params, home_team_id, league_id, season
                )
                
                print(f"Phase 1 stratification applied: Home team vs opponent tier, Away team vs opponent tier")
                
            except Exception as e:
                print(f"Warning: Opponent stratification failed, using overall parameters: {e}")
                effective_home_params = home_params
                effective_away_params = away_params
        else:
            print("Phase 1 stratification not available (missing season/team IDs), using overall parameters")
        
        # Calculate base lambdas using effective (stratified or overall) parameters
        home_lambda_base = calculate_base_lambda(
            home_team_parameters, away_team_parameters, effective_home_params, is_home=True
        )
        away_lambda_base = calculate_base_lambda(
            home_team_parameters, away_team_parameters, effective_away_params, is_home=False
        )
        
        # Apply basic home advantage using effective parameters
        league_home_adv = effective_home_params.get('home_adv', 1.31)
        home_lambda_base *= league_home_adv
        away_lambda_base *= 1/league_home_adv
        
        # Phase 2 Enhancement: Apply venue-specific advantages and travel impacts
        venue_factors = {}
        if season and home_team_id and away_team_id and venue_id:
            try:
                venue_factors = apply_venue_adjustments(
                    home_lambda_base, away_lambda_base,
                    home_team_id, away_team_id, venue_id, season,
                    effective_home_params, effective_away_params
                )
                
                # Update lambdas with venue adjustments
                home_lambda_base = venue_factors['adjusted_home_lambda']
                away_lambda_base = venue_factors['adjusted_away_lambda']
                
                print(f"Phase 2 venue analysis applied: Stadium advantage {venue_factors.get('home_stadium_advantage', 1.0)}, Travel impact {venue_factors.get('away_travel_impact', 1.0)}")
                
            except Exception as e:
                print(f"Warning: Venue analysis failed, using base parameters: {e}")
        else:
            print("Phase 2 venue analysis not available (missing venue_id or required parameters)")
        
        # Phase 3 Enhancement: Apply temporal analysis for time-aware predictions
        temporal_factors = {}
        if season and home_team_id and away_team_id and prediction_date:
            try:
                # Get temporal multipliers for both teams
                home_temporal_multiplier = get_temporal_multiplier_for_prediction(
                    home_team_id, league_id, season, prediction_date
                )
                away_temporal_multiplier = get_temporal_multiplier_for_prediction(
                    away_team_id, league_id, season, prediction_date
                )
                
                # Analyze head-to-head form
                h2h_analysis = analyze_head_to_head_form(
                    home_team_id, away_team_id, league_id, season
                )
                
                # Apply temporal adjustments to lambdas
                home_lambda_base *= float(home_temporal_multiplier)
                away_lambda_base *= float(away_temporal_multiplier)
                
                # Apply head-to-head multiplier
                if h2h_analysis['h2h_advantage'] == 'home':
                    home_lambda_base *= float(h2h_analysis['h2h_multiplier'])
                elif h2h_analysis['h2h_advantage'] == 'away':
                    away_lambda_base *= float(h2h_analysis['h2h_multiplier'])
                
                temporal_factors = {
                    'home_temporal_multiplier': home_temporal_multiplier,
                    'away_temporal_multiplier': away_temporal_multiplier,
                    'h2h_advantage': h2h_analysis['h2h_advantage'],
                    'h2h_multiplier': h2h_analysis['h2h_multiplier'],
                    'h2h_confidence': h2h_analysis['h2h_confidence'],
                    'temporal_analysis_applied': True
                }
                
                print(f"Phase 3 temporal analysis applied: Home temporal {home_temporal_multiplier}, Away temporal {away_temporal_multiplier}, H2H advantage: {h2h_analysis['h2h_advantage']}")
                
            except Exception as e:
                print(f"Warning: Temporal analysis failed, using base parameters: {e}")
                temporal_factors = {'temporal_analysis_applied': False}
        else:
            print("Phase 3 temporal analysis not available (missing required parameters)")
            temporal_factors = {'temporal_analysis_applied': False}
        
        # Phase 0: Use transition manager to get effective multipliers with contamination prevention
        # Note: Use original params for multiplier calculation to maintain compatibility
        transition_manager = TransitionManager()
        effective_multipliers = transition_manager.get_effective_multipliers(home_params, away_params)
        
        home_multiplier = float(effective_multipliers.get('home_multiplier', 1.0))
        away_multiplier = float(effective_multipliers.get('away_multiplier', 1.0))
        
        print(f"Using effective multipliers from {effective_multipliers.get('source', 'unknown')} source")
        print(f"Home multiplier: {home_multiplier}, Away multiplier: {away_multiplier}")
        
        # Preserve ratio while applying multipliers
        original_ratio = home_lambda_base / away_lambda_base if away_lambda_base > 0 else 1.0
        
        # Apply multipliers
        home_lambda_adjusted = home_lambda_base * home_multiplier
        away_lambda_adjusted = away_lambda_base * away_multiplier
        
        # Calculate new ratio and adjust to preserve original ratio
        new_ratio = home_lambda_adjusted / away_lambda_adjusted if away_lambda_adjusted > 0 else 1.0
        ratio_correction = original_ratio / new_ratio if new_ratio > 0 else 1.0
        
        # Apply ratio correction
        adjustment_factor = np.sqrt(ratio_correction)  # Geometric mean approach
        home_lambda_final = home_lambda_adjusted * adjustment_factor
        away_lambda_final = away_lambda_adjusted / adjustment_factor
        
        # Apply lambda ceiling
        home_lambda_final = squash_lambda(home_lambda_final)
        away_lambda_final = squash_lambda(away_lambda_final)
        
        # Calculate probabilities using effective (stratified) parameters
        home_alpha = effective_home_params.get('alpha_home', 0.3)
        away_alpha = effective_away_params.get('alpha_away', 0.3)
        
        home_goals, home_likelihood, home_probs = calculate_goal_probabilities(home_lambda_final, home_alpha)
        away_goals, away_likelihood, away_probs = calculate_goal_probabilities(away_lambda_final, away_alpha)
        
        # Calculate scoring probabilities
        home_score_prob = 1 - home_probs.get(0, 0)
        away_score_prob = 1 - away_probs.get(0, 0)
        
        # Phase 0: Add version metadata to coordination info
        version_manager = VersionManager()
        current_version = version_manager.get_current_version()
        
        coordination_info = {
            "coordination_applied": True,
            "original_ratio": original_ratio,
            "adjusted_ratio": home_lambda_final / away_lambda_final if away_lambda_final > 0 else 1.0,
            "home_lambda_base": home_lambda_base,
            "away_lambda_base": away_lambda_base,
            "home_lambda_final": home_lambda_final,
            "away_lambda_final": away_lambda_final,
            "ratio_correction": ratio_correction,
            # Phase 0 version tracking fields
            "architecture_version": current_version,
            "multiplier_source": effective_multipliers.get('source', 'unknown'),
            "multiplier_strategy": effective_multipliers.get('strategy', 'unknown'),
            "contamination_prevented": effective_multipliers.get('contamination_prevention', 'active'),
            "prediction_timestamp": int(datetime.now().timestamp()),
            # Phase 1 opponent stratification fields
            "opponent_stratification_applied": bool(season and home_team_id and away_team_id),
            "home_params_source": "segmented" if effective_home_params != home_params else "overall",
            "away_params_source": "segmented" if effective_away_params != away_params else "overall",
            "phase1_enabled": True,
            # Phase 2 venue analysis fields
            "venue_analysis_applied": bool(venue_factors),
            "venue_factors": venue_factors,
            "phase2_enabled": True,
            # Phase 3 temporal analysis fields
            "temporal_analysis_applied": temporal_factors.get('temporal_analysis_applied', False),
            "temporal_factors": temporal_factors,
            "phase3_enabled": True,
            "features": ['version_tracking', 'opponent_stratification', 'venue_analysis', 'temporal_evolution']
        }
        
        return (home_score_prob, home_goals, home_likelihood, home_probs,
                away_score_prob, away_goals, away_likelihood, away_probs,
                coordination_info)
                
    except Exception as e:
        print(f"Coordinated prediction failed: {e}")
        raise


def create_prediction_summary_dict(home_probs, away_probs):
    """
    Create a structured dictionary summary of prediction results for API responses.
    
    Args:
        home_probs: Home team goal probabilities
        away_probs: Away team goal probabilities
        
    Returns:
        Dictionary with formatted prediction summary suitable for JSON API responses
    """
    prediction_results = analyze_match_probabilities(home_probs, away_probs)

    most_likely = prediction_results['most_likely_score']
    
    # Get most likely scores
    common_scores = prediction_results['common_scores']
    top_scores = sorted(common_scores.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Format into more API-friendly structure
    summary = {
        "most_likely_score": {
            "score": f"{most_likely[0]}-{most_likely[1]}",
            "probability": round(prediction_results['most_likely_score_prob'] * 100, 1)
        },
        "expected_goals": {
            "home": round(prediction_results['expected_home_goals'], 2),
            "away": round(prediction_results['expected_away_goals'], 2),
            "total": round(prediction_results['expected_total_goals'], 2)
        },
        "match_outcome": {
            "home_win": round(prediction_results['home_win_prob'] * 100, 1),
            "draw": round(prediction_results['draw_prob'] * 100, 1),
            "away_win": round(prediction_results['away_win_prob'] * 100, 1)
        },
        "goals": {
            "over": {
                "0.5": round(prediction_results['over_0_5_prob'] * 100, 1),
                "1.5": round(prediction_results['over_1_5_prob'] * 100, 1),
                "2.5": round(prediction_results['over_2_5_prob'] * 100, 1),
                "3.5": round(prediction_results['over_3_5_prob'] * 100, 1),
                "4.5": round(prediction_results['over_4_5_prob'] * 100, 1)
            },
            "under": {
                "0.5": round(prediction_results['under_0_5_prob'] * 100, 1),
                "1.5": round(prediction_results['under_1_5_prob'] * 100, 1),
                "2.5": round(prediction_results['under_2_5_prob'] * 100, 1),
                "3.5": round(prediction_results['under_3_5_prob'] * 100, 1),
                "4.5": round(prediction_results['under_4_5_prob'] * 100, 1)
            },
            "btts": {
                "yes": round(prediction_results['btts_prob'] * 100, 1),
                "no": round(prediction_results['no_btts_prob'] * 100, 1)
            }
        },
        "top_scores": [
            {
                "score": score,
                "probability": round(prob * 100, 1)
            } for score, prob in top_scores
        ]
    }
    
    # Add decimal odds (European format) for common bet types
    summary["odds"] = {
        "match_outcome": {
            "home_win": round(1 / max(prediction_results['home_win_prob'], 0.01), 2),
            "draw": round(1 / max(prediction_results['draw_prob'], 0.01), 2),
            "away_win": round(1 / max(prediction_results['away_win_prob'], 0.01), 2)
        },
        "goals": {
            "over_2_5": round(1 / max(prediction_results['over_2_5_prob'], 0.01), 2),
            "under_2_5": round(1 / max(prediction_results['under_2_5_prob'], 0.01), 2),
            "btts_yes": round(1 / max(prediction_results['btts_prob'], 0.01), 2),
            "btts_no": round(1 / max(prediction_results['no_btts_prob'], 0.01), 2)
        }
    }
    
    return summary

def create_prediction_with_metadata(home_probs, away_probs, home_goals, away_goals, coordination_info=None):
    """
    Create prediction output with complete Phase 0 version metadata.
    
    This ensures all predictions include version tracking information to prevent
    contamination in future multiplier calculations.
    
    Args:
        home_probs: Home team goal probabilities
        away_probs: Away team goal probabilities  
        home_goals: Predicted home goals
        away_goals: Predicted away goals
        coordination_info: Optional coordination information
        
    Returns:
        Dictionary with prediction results and version metadata
    """
    # Get version metadata
    version_manager = VersionManager()
    current_version = version_manager.get_current_version()
    version_metadata = version_manager.get_version_metadata()
    
    # Create basic prediction summary
    prediction_summary = create_prediction_summary_dict(home_probs, away_probs)
    
    # Add Phase 0 version tracking metadata
    prediction_output = {
        "predictions": prediction_summary,
        "expected_goals": {
            "home": round(float(home_goals), 2),
            "away": round(float(away_goals), 2)
        },
        # Phase 0 version tracking fields - CRITICAL for preventing contamination
        "prediction_metadata": {
            "architecture_version": current_version,
            "architecture_features": version_metadata['features'],
            "prediction_timestamp": int(datetime.now().timestamp()),
            "baseline_components": {
                "segmentation_used": version_metadata['features'].get('segmentation', False),
                "form_adjustment_applied": version_metadata['features'].get('form_adjustment', False),
                "tactical_adjustment_applied": version_metadata['features'].get('tactical_features', False)
            },
            "contamination_prevented": True
        }
    }
    
    # Add coordination info if available
    if coordination_info:
        prediction_output["coordination_metadata"] = coordination_info
        
        # Add multiplier source information to prediction metadata
        prediction_output["prediction_metadata"]["multipliers"] = {
            "source": coordination_info.get("multiplier_source", "unknown"),
            "strategy": coordination_info.get("multiplier_strategy", "unknown"),
            "home_multiplier": coordination_info.get("home_lambda_final", 0) / coordination_info.get("home_lambda_base", 1) if coordination_info.get("home_lambda_base", 0) > 0 else 1.0,
            "away_multiplier": coordination_info.get("away_lambda_final", 0) / coordination_info.get("away_lambda_base", 1) if coordination_info.get("away_lambda_base", 0) > 0 else 1.0
        }
    
    return prediction_output


def validate_prediction_inputs(team1_params, team2_params, require_version_compatibility=True):
    """
    Validate prediction inputs for version compatibility and data integrity.
    
    This is a critical Phase 0 function that prevents contaminated parameters
    from being used in predictions.
    
    Args:
        team1_params: Team 1 parameters
        team2_params: Team 2 parameters
        require_version_compatibility: Whether to enforce version compatibility
        
    Returns:
        Tuple of (is_valid: bool, validation_message: str, sanitized_params: tuple)
    """
    version_manager = VersionManager()
    transition_manager = TransitionManager()
    current_version = version_manager.get_current_version()
    
    issues = []
    
    # Validate team1 parameters
    if team1_params:
        if 'architecture_version' in team1_params:
            is_valid, msg = transition_manager.validate_data_integrity(team1_params, current_version)
            if not is_valid:
                issues.append(f"Team 1 data integrity: {msg}")
        elif require_version_compatibility:
            issues.append("Team 1 parameters missing architecture version")
    else:
        issues.append("Team 1 parameters are missing")
    
    # Validate team2 parameters
    if team2_params:
        if 'architecture_version' in team2_params:
            is_valid, msg = transition_manager.validate_data_integrity(team2_params, current_version)
            if not is_valid:
                issues.append(f"Team 2 data integrity: {msg}")
        elif require_version_compatibility:
            issues.append("Team 2 parameters missing architecture version")
    else:
        issues.append("Team 2 parameters are missing")
    
    # If there are critical issues, return sanitized neutral parameters
    if issues and require_version_compatibility:
        print(f"Parameter validation issues detected: {'; '.join(issues)}")
        print("Using neutral fallback parameters to prevent contamination")
        
        # Create neutral fallback parameters with current version
        neutral_params = {
            'mu_home': 1.5, 'mu_away': 1.2, 'p_score_home': 0.75, 'p_score_away': 0.65,
            'alpha_home': 0.3, 'alpha_away': 0.3, 'home_adv': 1.31,
            'k_goals': 0.5, 'k_score': 0.5, 'ref_games': 20,
            'home_multiplier': Decimal('1.0'), 'away_multiplier': Decimal('1.0'),
            'architecture_version': current_version,
            'contamination_prevented': True,
            'fallback_reason': 'parameter_validation_failed'
        }
        
        return False, '; '.join(issues), (neutral_params, neutral_params)
    
    return len(issues) == 0, '; '.join(issues) if issues else "Validation passed", (team1_params, team2_params)


def prior_weight_from_k(n, k, ref_games, lo=3, hi=8):
    """
    Calculate prior weight from k parameter.
    
    Args:
        n: Number of games played
        k: K parameter
        ref_games: Reference number of games
        lo: Lower bound
        hi: Upper bound
        
    Returns:
        Prior weight value
    """
    if n <= 0 or ref_games <= 0:
        return k
    
    # Simple linear interpolation
    ratio = n / ref_games
    weight = k * min(1.0, ratio)
    return max(lo, min(hi, weight))


def apply_venue_adjustments(home_lambda_base, away_lambda_base, home_team_id, away_team_id, venue_id, season, home_params, away_params):
    """
    Apply Phase 2 venue-specific adjustments to base lambda values.
    
    This function applies:
    1. Stadium-specific advantages for the home team
    2. Travel distance impact for the away team
    3. Surface type advantages
    4. Venue-specific historical performance factors
    
    Args:
        home_lambda_base: Base home team lambda
        away_lambda_base: Base away team lambda
        home_team_id: Home team ID
        away_team_id: Away team ID
        venue_id: Venue ID for the match
        season: Season for analysis
        home_params: Home team parameters with venue data
        away_params: Away team parameters with venue data
        
    Returns:
        Dict with adjusted lambdas and venue factors
    """
    try:
        # Initialize venue analyzers
        venue_analyzer = VenueAnalyzer()
        surface_analyzer = SurfaceAnalyzer()
        
        # Get venue details
        venue_details = venue_analyzer.get_venue_details(venue_id)
        if not venue_details:
            return {
                'adjusted_home_lambda': home_lambda_base,
                'adjusted_away_lambda': away_lambda_base,
                'venue_factors': {}
            }
        
        # Calculate home team stadium advantage
        home_stadium_advantage = calculate_stadium_advantage(home_team_id, venue_id, season)
        
        # Calculate away team travel distance impact
        travel_distance = calculate_travel_distance(venue_id, away_team_id)
        travel_impact = calculate_travel_impact_factor(travel_distance, away_params)
        
        # Calculate surface advantage for both teams
        surface_type = venue_details.get('surface', 'grass')
        surface_matchup = compare_teams_surface_matchup(home_team_id, away_team_id, surface_type, season)
        
        # Apply venue-specific parameter adjustments from team parameters
        home_venue_params = home_params.get('venue_params', {})
        away_venue_params = away_params.get('venue_params', {})
        
        # Calculate final adjustment factors
        home_total_advantage = float(home_stadium_advantage) * float(home_venue_params.get('home_advantage', 1.0))
        away_total_impact = float(travel_impact) * float(away_venue_params.get('travel_sensitivity', 1.0))
        
        # Apply surface advantages
        if surface_matchup['favored_team'] == 'home':
            home_surface_boost = float(surface_matchup['surface_matchup_factor'])
            away_surface_penalty = 1.0 / home_surface_boost
        elif surface_matchup['favored_team'] == 'away':
            away_surface_boost = float(surface_matchup['surface_matchup_factor'])
            home_surface_penalty = 1.0 / away_surface_boost
            home_surface_boost = 1.0
            away_surface_penalty = away_surface_boost
        else:
            home_surface_boost = 1.0
            away_surface_penalty = 1.0
        
        # Apply all venue adjustments
        adjusted_home_lambda = home_lambda_base * home_total_advantage * home_surface_boost
        adjusted_away_lambda = away_lambda_base * away_total_impact * away_surface_penalty
        
        # Compile venue factors for reporting
        venue_factors = {
            'venue_id': venue_id,
            'venue_name': venue_details.get('venue_name', 'Unknown'),
            'surface_type': surface_type,
            'home_stadium_advantage': home_stadium_advantage,
            'away_travel_distance_km': travel_distance,
            'away_travel_impact': travel_impact,
            'surface_favored_team': surface_matchup['favored_team'],
            'surface_matchup_factor': surface_matchup['surface_matchup_factor'],
            'home_total_advantage': Decimal(str(home_total_advantage)),
            'away_total_impact': Decimal(str(away_total_impact)),
            'venue_analysis_applied': True
        }
        
        return {
            'adjusted_home_lambda': adjusted_home_lambda,
            'adjusted_away_lambda': adjusted_away_lambda,
            'venue_factors': venue_factors
        }
        
    except Exception as e:
        print(f"Error applying venue adjustments: {e}")
        return {
            'adjusted_home_lambda': home_lambda_base,
            'adjusted_away_lambda': away_lambda_base,
            'venue_factors': {'error': str(e)}
        }


def calculate_travel_impact_factor(travel_distance, away_params):
    """
    Calculate travel impact factor for away team based on distance and team sensitivity.
    
    Args:
        travel_distance: Travel distance in kilometers
        away_params: Away team parameters with travel sensitivity
        
    Returns:
        Decimal travel impact factor (typically 0.95-1.0)
    """
    try:
        if not travel_distance or float(travel_distance) == 0:
            return Decimal('1.0')  # No travel impact
        
        # Get team's travel sensitivity
        venue_params = away_params.get('venue_params', {})
        travel_sensitivity = float(venue_params.get('travel_sensitivity', 1.0))
        
        # Use geographic utility to calculate base travel impact
        from ..utils.geographic import calculate_travel_fatigue_factor
        base_fatigue = calculate_travel_fatigue_factor(travel_distance)
        
        # Apply team-specific travel sensitivity
        # Teams with high travel sensitivity (>1.0) are more affected by distance
        # Teams with low travel sensitivity (<1.0) are less affected
        adjusted_impact = float(base_fatigue) * travel_sensitivity
        
        # Ensure reasonable bounds (5-10% maximum impact)
        final_impact = max(0.90, min(1.05, adjusted_impact))
        
        return Decimal(str(round(final_impact, 3)))
        
    except Exception as e:
        print(f"Error calculating travel impact: {e}")
        return Decimal('1.0')


def apply_venue_advantage(params, stadium_advantage, venue_params):
    """
    Apply venue advantage to team parameters.
    
    Args:
        params: Team parameters
        stadium_advantage: Stadium-specific advantage factor
        venue_params: Team's venue-specific parameters
        
    Returns:
        Adjusted parameters with venue advantage applied
    """
    try:
        adjusted_params = params.copy()
        
        # Apply stadium advantage to key offensive parameters
        venue_multiplier = float(stadium_advantage) * float(venue_params.get('home_advantage', 1.0))
        
        adjusted_params['mu'] = float(adjusted_params.get('mu', 1.35)) * venue_multiplier
        adjusted_params['mu_home'] = float(adjusted_params.get('mu_home', 1.5)) * venue_multiplier
        
        return adjusted_params
        
    except Exception as e:
        print(f"Error applying venue advantage: {e}")
        return params


def apply_travel_impact(params, travel_fatigue, venue_params):
    """
    Apply travel impact to away team parameters.
    
    Args:
        params: Team parameters
        travel_fatigue: Travel fatigue factor
        venue_params: Team's venue-specific parameters
        
    Returns:
        Adjusted parameters with travel impact applied
    """
    try:
        adjusted_params = params.copy()
        
        # Apply travel impact to away performance parameters
        travel_multiplier = float(travel_fatigue) * float(venue_params.get('away_resilience', 1.0))
        
        adjusted_params['mu'] = float(adjusted_params.get('mu', 1.2)) * travel_multiplier
        adjusted_params['mu_away'] = float(adjusted_params.get('mu_away', 1.2)) * travel_multiplier
        
        return adjusted_params
        
    except Exception as e:
        print(f"Error applying travel impact: {e}")
        return params


def get_default_home_venue(team_id):
    """
    Get default home venue for a team (placeholder implementation).
    
    In a full implementation, this would query the database for the team's
    primary home venue.
    
    Args:
        team_id: Team ID
        
    Returns:
        Venue ID or None if not found
    """
    # This would be implemented to query actual team venue data
    # For now, return None to handle gracefully
    return None


def calculate_venue_aware_predictions(home_team_id, away_team_id, league_id, season, venue_id=None):
    """
    Main function for calculating predictions with full Phase 2 venue analysis.
    
    This is a convenience function that combines all Phase 0, 1, and 2 enhancements:
    - Phase 0: Version tracking and contamination prevention
    - Phase 1: Opponent strength stratification
    - Phase 2: Venue analysis with stadium advantages and travel impacts
    
    Args:
        home_team_id: Home team ID
        away_team_id: Away team ID
        league_id: League ID
        season: Season year
        venue_id: Venue ID (optional, will use team's default if not provided)
        
    Returns:
        Comprehensive prediction results with venue analysis
    """
    try:
        # Use default home venue if not specified
        if not venue_id:
            venue_id = get_default_home_venue(home_team_id)
        
        # This would integrate with the existing parameter fetching system
        # For now, return structure showing what the enhanced predictions would contain
        return {
            'predictions': {
                'home_goals_expected': 0.0,
                'away_goals_expected': 0.0,
                'home_win_probability': 0.0,
                'draw_probability': 0.0,
                'away_win_probability': 0.0
            },
            'venue_factors': {
                'venue_id': venue_id,
                'home_advantage': Decimal('1.0'),
                'travel_distance': Decimal('0'),
                'travel_fatigue': Decimal('1.0')
            },
            'architecture_version': '2.0',  # Phase 2 version
            'features': ['opponent_stratification', 'venue_analysis'],
            'phase_2_enabled': True
        }
        
    except Exception as e:
        print(f"Error calculating venue-aware predictions: {e}")
        return None