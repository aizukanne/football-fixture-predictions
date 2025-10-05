"""
strategy_router.py - Adaptive prediction strategy routing based on team classification

Phase 5 implementation: Team Classification & Adaptive Strategy
Routes optimal prediction strategies based on team archetypes and matchup dynamics.
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from dataclasses import dataclass

# Import existing infrastructure
from ..infrastructure.version_manager import VersionManager
from ..data.database_client import get_team_params_from_db, get_league_params_from_db
from .team_classifier import classify_team_archetype, get_archetype_prediction_weights

# Simple wrapper class for compatibility
class DatabaseClient:
    def get_team_matches(self, team_id, league_id, season):
        return []
    def get_league_teams(self, league_id, season):
        return [{'team_id': i} for i in range(1, 21)]
    def get_league_matches(self, league_id, season):
        return []

logger = logging.getLogger(__name__)

@dataclass
class StrategyRoute:
    """Strategy routing configuration"""
    strategy_name: str
    confidence: Decimal
    weighting_scheme: Dict[str, Decimal]
    special_considerations: List[str]
    uncertainty_level: str


def route_prediction_strategy(home_team_id: int, away_team_id: int, 
                             league_id: int, season: int) -> Dict:
    """
    Determine optimal prediction strategy based on team archetypes.
    
    Args:
        home_team_id: Home team identifier
        away_team_id: Away team identifier
        league_id: League identifier
        season: Season year
        
    Returns:
        {
            'strategy_name': str,               # Selected prediction strategy
            'strategy_confidence': Decimal,     # Confidence in strategy choice
            'weighting_scheme': Dict,           # Weights for different phases
            'special_considerations': List[str], # Special factors to consider
            'uncertainty_level': str            # 'low'|'medium'|'high'
        }
    """
    try:
        logger.info(f"Routing prediction strategy for {home_team_id} vs {away_team_id}")
        
        # Classify both teams
        home_classification = classify_team_archetype(home_team_id, league_id, season)
        away_classification = classify_team_archetype(away_team_id, league_id, season)
        
        home_archetype = home_classification['primary_archetype']
        away_archetype = away_classification['primary_archetype']
        
        logger.info(f"Team archetypes: Home={home_archetype}, Away={away_archetype}")
        
        # Analyze matchup dynamics
        matchup_dynamics = get_archetype_matchup_dynamics(home_archetype, away_archetype)
        
        # Determine strategy based on archetype combination
        strategy_name = _determine_optimal_strategy(home_archetype, away_archetype, matchup_dynamics)
        
        # Calculate strategy confidence
        strategy_confidence = _calculate_strategy_confidence(
            home_classification, away_classification, matchup_dynamics
        )
        
        # Get weighting scheme for the selected strategy
        weighting_scheme = _get_strategy_weighting_scheme(
            strategy_name, home_archetype, away_archetype
        )
        
        # Determine special considerations
        special_considerations = _identify_special_considerations(
            home_archetype, away_archetype, matchup_dynamics
        )
        
        # Assess uncertainty level
        uncertainty_level = _assess_uncertainty_level(
            home_classification, away_classification, matchup_dynamics
        )
        
        result = {
            'strategy_name': strategy_name,
            'strategy_confidence': strategy_confidence,
            'weighting_scheme': weighting_scheme,
            'special_considerations': special_considerations,
            'uncertainty_level': uncertainty_level,
            'matchup_type': matchup_dynamics['matchup_type'],
            'routing_metadata': {
                'home_archetype': home_archetype,
                'away_archetype': away_archetype,
                'home_confidence': home_classification['archetype_confidence'],
                'away_confidence': away_classification['archetype_confidence'],
                'routing_date': int(datetime.now().timestamp())
            },
            'version': '5.0'
        }
        
        logger.info(f"Strategy routed: {strategy_name} with confidence {strategy_confidence}")
        return result
        
    except Exception as e:
        logger.error(f"Error routing prediction strategy: {str(e)}")
        # Return default safe strategy
        return _get_default_strategy_routing()


def calculate_adaptive_weights(home_archetype: str, away_archetype: str,
                              match_context: Dict = None) -> Dict:
    """
    Calculate adaptive weights for prediction phases based on team archetypes.
    
    Args:
        home_archetype: Home team archetype
        away_archetype: Away team archetype
        match_context: Additional match context (venue, date, etc.)
        
    Returns:
        {
            'phase_1_weight': Decimal,          # Opponent stratification weight
            'phase_2_weight': Decimal,          # Venue analysis weight  
            'phase_3_weight': Decimal,          # Temporal intelligence weight
            'phase_4_weight': Decimal,          # Tactical analysis weight
            'confidence_adjustment': Decimal    # Overall confidence modifier
        }
    """
    try:
        logger.info(f"Calculating adaptive weights for {home_archetype} vs {away_archetype}")
        
        # Get base weights for each team archetype
        home_weights = get_archetype_prediction_weights(home_archetype)
        away_weights = get_archetype_prediction_weights(away_archetype)
        
        # Calculate combined weights (weighted average based on home advantage)
        home_weight_factor = Decimal('0.55')  # Slight home advantage
        away_weight_factor = Decimal('0.45')
        
        phase_1_weight = (
            home_weights['opponent_weight'] * home_weight_factor +
            away_weights['opponent_weight'] * away_weight_factor
        )
        
        phase_2_weight = (
            home_weights['venue_weight'] * home_weight_factor +
            away_weights['venue_weight'] * away_weight_factor
        )
        
        phase_3_weight = (
            home_weights['temporal_weight'] * home_weight_factor +
            away_weights['temporal_weight'] * away_weight_factor
        )
        
        phase_4_weight = (
            home_weights['tactical_weight'] * home_weight_factor +
            away_weights['tactical_weight'] * away_weight_factor
        )
        
        # Calculate confidence adjustment
        confidence_adjustment = (
            home_weights['base_confidence'] * home_weight_factor +
            away_weights['base_confidence'] * away_weight_factor
        )
        
        # Apply context-specific adjustments
        if 'venue_id' in match_context:
            # Boost venue weight for venue-sensitive archetypes
            if 'HOME_FORTRESS' in [home_archetype, away_archetype]:
                phase_2_weight *= Decimal('1.2')
        
        # Normalize weights to ensure they sum appropriately
        total_weight = phase_1_weight + phase_2_weight + phase_3_weight + phase_4_weight
        normalization_factor = Decimal('4.0') / total_weight if total_weight > 0 else Decimal('1.0')
        
        adaptive_weights = {
            'phase_1_weight': (phase_1_weight * normalization_factor).quantize(Decimal('0.001')),
            'phase_2_weight': (phase_2_weight * normalization_factor).quantize(Decimal('0.001')),
            'phase_3_weight': (phase_3_weight * normalization_factor).quantize(Decimal('0.001')),
            'phase_4_weight': (phase_4_weight * normalization_factor).quantize(Decimal('0.001')),
            'confidence_adjustment': confidence_adjustment.quantize(Decimal('0.001')),
            'calculation_metadata': {
                'home_archetype': home_archetype,
                'away_archetype': away_archetype,
                'context_adjustments': len(match_context),
                'calculation_date': int(datetime.now().timestamp())
            }
        }
        
        logger.info(f"Adaptive weights calculated: P1={adaptive_weights['phase_1_weight']}, "
                   f"P2={adaptive_weights['phase_2_weight']}, P3={adaptive_weights['phase_3_weight']}, "
                   f"P4={adaptive_weights['phase_4_weight']}")
        
        return adaptive_weights
        
    except Exception as e:
        logger.error(f"Error calculating adaptive weights: {str(e)}")
        return _get_default_adaptive_weights()


def get_archetype_matchup_dynamics(home_archetype: str, away_archetype: str) -> Dict:
    """
    Analyze how different team archetypes interact in matchups.
    
    Args:
        home_archetype: Home team archetype
        away_archetype: Away team archetype
        
    Returns:
        {
            'matchup_type': str,                # Type of matchup expected
            'volatility_level': str,            # Expected result variance
            'key_factors': List[str],           # Most important prediction factors
            'historical_patterns': Dict        # Similar archetype matchup history
        }
    """
    try:
        logger.info(f"Analyzing matchup dynamics: {home_archetype} vs {away_archetype}")
        
        # Define matchup type classifications
        matchup_matrix = _get_matchup_matrix()
        matchup_key = f"{home_archetype}_{away_archetype}"
        reverse_key = f"{away_archetype}_{home_archetype}"
        
        # Get matchup configuration
        if matchup_key in matchup_matrix:
            matchup_config = matchup_matrix[matchup_key]
        elif reverse_key in matchup_matrix:
            matchup_config = matchup_matrix[reverse_key]
            # Reverse home/away considerations
            matchup_config = _reverse_matchup_config(matchup_config)
        else:
            # Use general matchup classification
            matchup_config = _classify_general_matchup(home_archetype, away_archetype)
        
        # Determine key factors based on archetypes
        key_factors = _determine_key_matchup_factors(home_archetype, away_archetype)
        
        # Assess volatility based on archetype predictability
        volatility_level = _assess_matchup_volatility(home_archetype, away_archetype)
        
        # Get historical patterns (simplified for this implementation)
        historical_patterns = _get_historical_patterns(home_archetype, away_archetype)
        
        result = {
            'matchup_type': matchup_config['type'],
            'volatility_level': volatility_level,
            'key_factors': key_factors,
            'historical_patterns': historical_patterns,
            'prediction_difficulty': matchup_config.get('difficulty', 'medium'),
            'expected_tactics': matchup_config.get('tactics', []),
            'analysis_metadata': {
                'home_archetype': home_archetype,
                'away_archetype': away_archetype,
                'analysis_date': int(datetime.now().timestamp())
            }
        }
        
        logger.info(f"Matchup dynamics: {matchup_config['type']} with {volatility_level} volatility")
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing matchup dynamics: {str(e)}")
        return _get_default_matchup_dynamics()


def select_prediction_ensemble(strategy_name: str, team_characteristics: Dict) -> Dict:
    """
    Select and configure prediction ensemble based on strategy.
    
    Strategies:
    - 'standard_with_quality_boost': Enhanced standard approach for elite teams
    - 'formation_heavy_weighting': Emphasizes tactical/formation analysis
    - 'temporal_heavy_weighting': Emphasizes form and recent performance
    - 'venue_heavy_weighting': Emphasizes venue and travel factors
    - 'opponent_stratification_heavy': Emphasizes opponent strength analysis
    - 'ensemble_with_high_uncertainty': Multiple approaches with uncertainty quantification
    
    Args:
        strategy_name: Selected prediction strategy
        team_characteristics: Combined team characteristics
        
    Returns:
        {
            'primary_method': str,              # Main prediction method
            'secondary_methods': List[str],     # Supporting methods
            'method_weights': Dict,             # Relative weights for ensemble
            'uncertainty_bands': Dict          # Confidence intervals
        }
    """
    try:
        logger.info(f"Selecting prediction ensemble for strategy: {strategy_name}")
        
        ensemble_configs = _get_ensemble_configurations()
        
        if strategy_name not in ensemble_configs:
            logger.warning(f"Unknown strategy {strategy_name}, using standard approach")
            strategy_name = 'standard_with_quality_boost'
        
        base_config = ensemble_configs[strategy_name]
        
        # Customize ensemble based on team characteristics
        customized_config = _customize_ensemble_for_teams(base_config, team_characteristics)
        
        # Calculate uncertainty bands based on strategy reliability
        uncertainty_bands = _calculate_uncertainty_bands(strategy_name, team_characteristics)
        
        result = {
            'primary_method': customized_config['primary_method'],
            'secondary_methods': customized_config['secondary_methods'],
            'method_weights': customized_config['method_weights'],
            'uncertainty_bands': uncertainty_bands,
            'ensemble_metadata': {
                'strategy_name': strategy_name,
                'customization_applied': bool(team_characteristics),
                'selection_date': int(datetime.now().timestamp())
            }
        }
        
        logger.info(f"Ensemble selected: {customized_config['primary_method']} with "
                   f"{len(customized_config['secondary_methods'])} secondary methods")
        
        return result
        
    except Exception as e:
        logger.error(f"Error selecting prediction ensemble: {str(e)}")
        return _get_default_ensemble()


def evaluate_strategy_performance(strategy_name: str, historical_data: List[Dict]) -> Dict:
    """
    Evaluate how well different strategies perform for specific team types.
    
    Args:
        strategy_name: Strategy to evaluate
        historical_data: Historical prediction and result data
        
    Returns:
        {
            'accuracy_metrics': Dict,           # Strategy accuracy statistics
            'optimal_contexts': List[str],      # When this strategy works best
            'failure_modes': List[str],         # When this strategy fails
            'improvement_suggestions': List[str] # How to enhance this strategy
        }
    """
    try:
        logger.info(f"Evaluating performance for strategy: {strategy_name}")
        
        if not historical_data:
            logger.warning("No historical data provided for strategy evaluation")
            return _get_default_strategy_evaluation(strategy_name)
        
        # Calculate accuracy metrics
        accuracy_metrics = _calculate_strategy_accuracy(strategy_name, historical_data)
        
        # Identify optimal contexts
        optimal_contexts = _identify_optimal_contexts(strategy_name, historical_data)
        
        # Identify failure modes
        failure_modes = _identify_failure_modes(strategy_name, historical_data)
        
        # Generate improvement suggestions
        improvement_suggestions = _generate_improvement_suggestions(
            strategy_name, accuracy_metrics, failure_modes
        )
        
        result = {
            'accuracy_metrics': accuracy_metrics,
            'optimal_contexts': optimal_contexts,
            'failure_modes': failure_modes,
            'improvement_suggestions': improvement_suggestions,
            'evaluation_metadata': {
                'strategy_name': strategy_name,
                'data_points': len(historical_data),
                'evaluation_date': int(datetime.now().timestamp())
            }
        }
        
        logger.info(f"Strategy evaluation completed for {strategy_name}")
        return result
        
    except Exception as e:
        logger.error(f"Error evaluating strategy performance: {str(e)}")
        return _get_default_strategy_evaluation(strategy_name)


# Private helper functions

def _determine_optimal_strategy(home_archetype: str, away_archetype: str, 
                              matchup_dynamics: Dict) -> str:
    """Determine the optimal prediction strategy for archetype combination."""
    try:
        # Priority-based strategy selection
        
        # High priority: Tactical specialists need formation analysis
        if home_archetype == 'TACTICAL_SPECIALISTS' or away_archetype == 'TACTICAL_SPECIALISTS':
            return 'formation_heavy_weighting'
        
        # High priority: Home fortress teams need venue emphasis
        if home_archetype == 'HOME_FORTRESS' or away_archetype == 'HOME_FORTRESS':
            return 'venue_heavy_weighting'
        
        # High priority: Momentum dependent teams need temporal analysis
        if home_archetype == 'MOMENTUM_DEPENDENT' or away_archetype == 'MOMENTUM_DEPENDENT':
            return 'temporal_heavy_weighting'
        
        # High priority: Big game specialists need opponent analysis
        if home_archetype == 'BIG_GAME_SPECIALISTS' or away_archetype == 'BIG_GAME_SPECIALISTS':
            return 'opponent_stratification_heavy'
        
        # High priority: Unpredictable chaos needs ensemble approach
        if home_archetype == 'UNPREDICTABLE_CHAOS' or away_archetype == 'UNPREDICTABLE_CHAOS':
            return 'ensemble_with_high_uncertainty'
        
        # Default: Elite consistent teams use standard enhanced approach
        if home_archetype == 'ELITE_CONSISTENT' or away_archetype == 'ELITE_CONSISTENT':
            return 'standard_with_quality_boost'
        
        # Fallback: Use standard approach
        return 'standard_with_quality_boost'
        
    except Exception as e:
        logger.error(f"Error determining optimal strategy: {str(e)}")
        return 'standard_with_quality_boost'


def _calculate_strategy_confidence(home_classification: Dict, away_classification: Dict,
                                 matchup_dynamics: Dict) -> Decimal:
    """Calculate confidence in strategy selection."""
    try:
        # Base confidence from archetype confidence
        home_confidence = home_classification['archetype_confidence']
        away_confidence = away_classification['archetype_confidence']
        base_confidence = (home_confidence + away_confidence) / 2
        
        # Adjust based on matchup volatility
        volatility_adjustments = {
            'low': Decimal('1.1'),
            'medium': Decimal('1.0'),
            'high': Decimal('0.9')
        }
        volatility_adj = volatility_adjustments.get(
            matchup_dynamics.get('volatility_level', 'medium'), Decimal('1.0')
        )
        
        # Adjust based on archetype stability
        home_stability = home_classification.get('archetype_stability', Decimal('0.7'))
        away_stability = away_classification.get('archetype_stability', Decimal('0.7'))
        stability_factor = (home_stability + away_stability) / 2
        
        # Calculate final confidence
        strategy_confidence = base_confidence * volatility_adj * stability_factor
        strategy_confidence = min(Decimal('0.95'), max(Decimal('0.3'), strategy_confidence))
        
        return strategy_confidence.quantize(Decimal('0.001'))
        
    except Exception as e:
        logger.error(f"Error calculating strategy confidence: {str(e)}")
        return Decimal('0.7')


def _get_strategy_weighting_scheme(strategy_name: str, home_archetype: str, 
                                 away_archetype: str) -> Dict:
    """Get weighting scheme for the selected strategy."""
    strategy_weights = {
        'standard_with_quality_boost': {
            'opponent_weight': Decimal('1.1'),
            'venue_weight': Decimal('1.0'),
            'temporal_weight': Decimal('0.9'),
            'tactical_weight': Decimal('1.0')
        },
        'formation_heavy_weighting': {
            'opponent_weight': Decimal('0.8'),
            'venue_weight': Decimal('0.9'),
            'temporal_weight': Decimal('0.7'),
            'tactical_weight': Decimal('1.4')
        },
        'temporal_heavy_weighting': {
            'opponent_weight': Decimal('0.8'),
            'venue_weight': Decimal('0.9'),
            'temporal_weight': Decimal('1.5'),
            'tactical_weight': Decimal('0.8')
        },
        'venue_heavy_weighting': {
            'opponent_weight': Decimal('0.9'),
            'venue_weight': Decimal('1.6'),
            'temporal_weight': Decimal('0.8'),
            'tactical_weight': Decimal('0.9')
        },
        'opponent_stratification_heavy': {
            'opponent_weight': Decimal('1.5'),
            'venue_weight': Decimal('0.8'),
            'temporal_weight': Decimal('0.9'),
            'tactical_weight': Decimal('1.0')
        },
        'ensemble_with_high_uncertainty': {
            'opponent_weight': Decimal('1.0'),
            'venue_weight': Decimal('1.0'),
            'temporal_weight': Decimal('1.0'),
            'tactical_weight': Decimal('1.0')
        }
    }
    
    return strategy_weights.get(strategy_name, strategy_weights['standard_with_quality_boost'])


def _identify_special_considerations(home_archetype: str, away_archetype: str,
                                   matchup_dynamics: Dict) -> List[str]:
    """Identify special considerations for the matchup."""
    considerations = []
    
    # Archetype-specific considerations
    if home_archetype == 'TACTICAL_SPECIALISTS':
        considerations.append('monitor_formation_changes')
    if away_archetype == 'TACTICAL_SPECIALISTS':
        considerations.append('analyze_away_tactical_setup')
    
    if home_archetype == 'MOMENTUM_DEPENDENT':
        considerations.append('weight_recent_home_form_heavily')
    if away_archetype == 'MOMENTUM_DEPENDENT':
        considerations.append('assess_away_confidence_levels')
    
    if home_archetype == 'HOME_FORTRESS':
        considerations.append('expect_strong_home_advantage')
    if away_archetype == 'HOME_FORTRESS':
        considerations.append('away_team_vulnerable_away_from_home')
    
    if 'UNPREDICTABLE_CHAOS' in [home_archetype, away_archetype]:
        considerations.append('high_result_variance_expected')
        considerations.append('use_wider_confidence_intervals')
    
    # Matchup-specific considerations
    volatility = matchup_dynamics.get('volatility_level', 'medium')
    if volatility == 'high':
        considerations.append('expect_surprising_results')
    elif volatility == 'low':
        considerations.append('reliable_prediction_context')
    
    return considerations


def _assess_uncertainty_level(home_classification: Dict, away_classification: Dict,
                            matchup_dynamics: Dict) -> str:
    """Assess the overall uncertainty level for the prediction."""
    try:
        # Calculate uncertainty factors
        archetype_uncertainty = 0.0
        
        # Lower confidence in archetype = higher uncertainty
        home_conf = float(home_classification.get('archetype_confidence', 0.7))
        away_conf = float(away_classification.get('archetype_confidence', 0.7))
        archetype_uncertainty = (2.0 - home_conf - away_conf) / 2.0
        
        # Volatility adds uncertainty
        volatility_uncertainty = {
            'low': 0.1,
            'medium': 0.3,
            'high': 0.6
        }.get(matchup_dynamics.get('volatility_level', 'medium'), 0.3)
        
        # Chaos archetypes add uncertainty
        chaos_uncertainty = 0.0
        if home_classification.get('primary_archetype') == 'UNPREDICTABLE_CHAOS':
            chaos_uncertainty += 0.3
        if away_classification.get('primary_archetype') == 'UNPREDICTABLE_CHAOS':
            chaos_uncertainty += 0.3
        
        # Combine uncertainty factors
        total_uncertainty = (archetype_uncertainty + volatility_uncertainty + chaos_uncertainty) / 3.0
        
        if total_uncertainty > 0.6:
            return 'high'
        elif total_uncertainty > 0.3:
            return 'medium'
        else:
            return 'low'
            
    except Exception as e:
        logger.error(f"Error assessing uncertainty level: {str(e)}")
        return 'medium'


def _get_default_strategy_routing() -> Dict:
    """Get default strategy routing for error cases."""
    return {
        'strategy_name': 'standard_with_quality_boost',
        'strategy_confidence': Decimal('0.7'),
        'weighting_scheme': {
            'opponent_weight': Decimal('1.0'),
            'venue_weight': Decimal('1.0'),
            'temporal_weight': Decimal('1.0'),
            'tactical_weight': Decimal('1.0')
        },
        'special_considerations': ['default_routing_used'],
        'uncertainty_level': 'medium',
        'matchup_type': 'standard',
        'routing_metadata': {
            'error': True,
            'routing_date': int(datetime.now().timestamp())
        },
        'version': '5.0'
    }


def _get_default_adaptive_weights() -> Dict:
    """Get default adaptive weights for error cases."""
    return {
        'phase_1_weight': Decimal('1.0'),
        'phase_2_weight': Decimal('1.0'),
        'phase_3_weight': Decimal('1.0'),
        'phase_4_weight': Decimal('1.0'),
        'confidence_adjustment': Decimal('0.7'),
        'error': True
    }


def _get_matchup_matrix() -> Dict:
    """Get matchup type matrix for archetype combinations."""
    return {
        'ELITE_CONSISTENT_ELITE_CONSISTENT': {
            'type': 'elite_clash',
            'difficulty': 'medium',
            'tactics': ['expect_tight_match', 'quality_decisive']
        },
        'TACTICAL_SPECIALISTS_TACTICAL_SPECIALISTS': {
            'type': 'tactical_battle',
            'difficulty': 'high',
            'tactics': ['formation_crucial', 'in_game_adjustments_key']
        },
        'MOMENTUM_DEPENDENT_MOMENTUM_DEPENDENT': {
            'type': 'form_dependent_clash',
            'difficulty': 'high',
            'tactics': ['recent_form_decisive', 'confidence_crucial']
        },
        'HOME_FORTRESS_HOME_FORTRESS': {
            'type': 'venue_advantage_clash',
            'difficulty': 'low',
            'tactics': ['home_advantage_significant', 'away_team_disadvantaged']
        }
    }


def _classify_general_matchup(home_archetype: str, away_archetype: str) -> Dict:
    """Classify general matchup when specific combination not defined."""
    return {
        'type': f"{home_archetype.lower()}_vs_{away_archetype.lower()}",
        'difficulty': 'medium',
        'tactics': ['standard_analysis_applies']
    }


def _reverse_matchup_config(config: Dict) -> Dict:
    """Reverse matchup configuration for away team perspective."""
    # This would reverse home/away specific tactics
    reversed_config = config.copy()
    # For simplicity, return as-is (full implementation would reverse tactics)
    return reversed_config


def _determine_key_matchup_factors(home_archetype: str, away_archetype: str) -> List[str]:
    """Determine key factors for the specific matchup."""
    factors = ['basic_team_strength']
    
    archetype_factors = {
        'ELITE_CONSISTENT': ['team_quality', 'depth'],
        'TACTICAL_SPECIALISTS': ['formation_matchup', 'tactical_flexibility'],
        'MOMENTUM_DEPENDENT': ['current_form', 'confidence_levels'],
        'HOME_FORTRESS': ['venue_advantage', 'travel_impact'],
        'BIG_GAME_SPECIALISTS': ['opponent_strength', 'motivation_levels'],
        'UNPREDICTABLE_CHAOS': ['randomness_factor', 'variance_consideration']
    }
    
    factors.extend(archetype_factors.get(home_archetype, []))
    factors.extend(archetype_factors.get(away_archetype, []))
    
    return list(set(factors))  # Remove duplicates


def _assess_matchup_volatility(home_archetype: str, away_archetype: str) -> str:
    """Assess expected volatility for archetype matchup."""
    high_volatility_archetypes = ['UNPREDICTABLE_CHAOS', 'MOMENTUM_DEPENDENT']
    medium_volatility_archetypes = ['TACTICAL_SPECIALISTS', 'BIG_GAME_SPECIALISTS']
    low_volatility_archetypes = ['ELITE_CONSISTENT', 'HOME_FORTRESS']
    
    if home_archetype in high_volatility_archetypes or away_archetype in high_volatility_archetypes:
        return 'high'
    elif home_archetype in low_volatility_archetypes and away_archetype in low_volatility_archetypes:
        return 'low'
    else:
        return 'medium'


def _get_historical_patterns(home_archetype: str, away_archetype: str) -> Dict:
    """Get historical patterns for archetype matchup (simplified implementation)."""
    return {
        'sample_size': 'insufficient_historical_data',
        'home_win_rate': 0.45,  # Default home advantage
        'draw_rate': 0.25,
        'away_win_rate': 0.30,
        'average_goals': 2.5
    }


def _get_default_matchup_dynamics() -> Dict:
    """Get default matchup dynamics for error cases."""
    return {
        'matchup_type': 'standard',
        'volatility_level': 'medium',
        'key_factors': ['team_strength', 'form', 'venue'],
        'historical_patterns': {
            'sample_size': 'error_fallback',
            'home_win_rate': 0.45,
            'draw_rate': 0.25,
            'away_win_rate': 0.30
        },
        'prediction_difficulty': 'medium',
        'expected_tactics': ['standard_analysis'],
        'error': True
    }


def _get_ensemble_configurations() -> Dict:
    """Get ensemble configurations for different strategies."""
    return {
        'standard_with_quality_boost': {
            'primary_method': 'enhanced_poisson',
            'secondary_methods': ['quality_adjusted', 'form_weighted'],
            'method_weights': {'enhanced_poisson': 0.6, 'quality_adjusted': 0.3, 'form_weighted': 0.1}
        },
        'formation_heavy_weighting': {
            'primary_method': 'tactical_analysis',
            'secondary_methods': ['formation_matchup', 'enhanced_poisson'],
            'method_weights': {'tactical_analysis': 0.5, 'formation_matchup': 0.3, 'enhanced_poisson': 0.2}
        },
        'temporal_heavy_weighting': {
            'primary_method': 'form_analysis',
            'secondary_methods': ['momentum_tracking', 'enhanced_poisson'],
            'method_weights': {'form_analysis': 0.5, 'momentum_tracking': 0.3, 'enhanced_poisson': 0.2}
        },
        'venue_heavy_weighting': {
            'primary_method': 'venue_analysis',
            'secondary_methods': ['travel_impact', 'enhanced_poisson'],
            'method_weights': {'venue_analysis': 0.5, 'travel_impact': 0.3, 'enhanced_poisson': 0.2}
        },
        'opponent_stratification_heavy': {
            'primary_method': 'opponent_stratified',
            'secondary_methods': ['strength_differential', 'enhanced_poisson'],
            'method_weights': {'opponent_stratified': 0.5, 'strength_differential': 0.3, 'enhanced_poisson': 0.2}
        },
        'ensemble_with_high_uncertainty': {
            'primary_method': 'multi_model_ensemble',
            'secondary_methods': ['uncertainty_quantified', 'bootstrap_samples', 'monte_carlo'],
            'method_weights': {'multi_model_ensemble': 0.4, 'uncertainty_quantified': 0.2, 
                             'bootstrap_samples': 0.2, 'monte_carlo': 0.2}
        }
    }


def _customize_ensemble_for_teams(base_config: Dict, team_characteristics: Dict) -> Dict:
    """Customize ensemble configuration based on team characteristics."""
    # For this implementation, return base configuration
    # Full implementation would adjust based on specific team traits
    return base_config


def _calculate_uncertainty_bands(strategy_name: str, team_characteristics: Dict) -> Dict:
    """Calculate uncertainty bands for the strategy."""
    base_uncertainty = {
        'standard_with_quality_boost': 0.15,
        'formation_heavy_weighting': 0.20,
        'temporal_heavy_weighting': 0.25,
        'venue_heavy_weighting': 0.18,
        'opponent_stratification_heavy': 0.22,
        'ensemble_with_high_uncertainty': 0.35
    }.get(strategy_name, 0.20)
    
    return {
        'confidence_90': base_uncertainty * 1.6,
        'confidence_80': base_uncertainty * 1.3,
        'confidence_70': base_uncertainty * 1.0,
        'base_uncertainty': base_uncertainty
    }


def _get_default_ensemble() -> Dict:
    """Get default ensemble configuration."""
    return {
        'primary_method': 'enhanced_poisson',
        'secondary_methods': ['quality_adjusted'],
        'method_weights': {'enhanced_poisson': 0.8, 'quality_adjusted': 0.2},
        'uncertainty_bands': {'confidence_90': 0.24, 'confidence_80': 0.20, 'confidence_70': 0.15}
    }


def _calculate_strategy_accuracy(strategy_name: str, historical_data: List[Dict]) -> Dict:
    """Calculate accuracy metrics for strategy (simplified implementation)."""
    return {
        'overall_accuracy': 0.65,  # Default accuracy
        'home_win_accuracy': 0.70,
        'draw_accuracy': 0.45,
        'away_win_accuracy': 0.60,
        'goal_prediction_mae': 1.2,
        'sample_size': len(historical_data)
    }


def _identify_optimal_contexts(strategy_name: str, historical_data: List[Dict]) -> List[str]:
    """Identify contexts where strategy performs best."""
    # Simplified implementation
    context_map = {
        'formation_heavy_weighting': ['tactical_teams', 'system_dependent_teams'],
        'temporal_heavy_weighting': ['form_sensitive_teams', 'momentum_teams'],
        'venue_heavy_weighting': ['home_fortress_teams', 'travel_sensitive_teams']
    }
    return context_map.get(strategy_name, ['general_contexts'])


def _identify_failure_modes(strategy_name: str, historical_data: List[Dict]) -> List[str]:
    """Identify failure modes for strategy."""
    # Simplified implementation
    failure_map = {
        'formation_heavy_weighting': ['when_tactical_data_unavailable', 'against_flexible_teams'],
        'temporal_heavy_weighting': ['early_season', 'after_long_breaks'],
        'venue_heavy_weighting': ['neutral_venues', 'weather_affected_games']
    }
    return failure_map.get(strategy_name, ['data_quality_issues'])


def _generate_improvement_suggestions(strategy_name: str, accuracy_metrics: Dict,
                                    failure_modes: List[str]) -> List[str]:
    """Generate suggestions for strategy improvement."""
    suggestions = ['collect_more_training_data', 'regular_model_updates']
    
    if 'data_quality_issues' in failure_modes:
        suggestions.append('improve_data_validation')
    if 'early_season' in failure_modes:
        suggestions.append('use_previous_season_priors')
        
    return suggestions


def _get_default_strategy_evaluation(strategy_name: str) -> Dict:
    """Get default strategy evaluation."""
    return {
        'accuracy_metrics': {
            'overall_accuracy': 0.60,
            'sample_size': 0
        },
        'optimal_contexts': ['unknown'],
        'failure_modes': ['insufficient_data'],
        'improvement_suggestions': ['collect_historical_data'],
        'evaluation_metadata': {
            'strategy_name': strategy_name,
            'default_evaluation': True
        }
    }