"""
Parameter extraction service for GenAI Pundit v2.0.
Extracts Phase 0-6 parameters from team_parameters table for AI analysis.
"""

from decimal import Decimal
from typing import Dict, Any, Optional


def extract_ai_relevant_parameters(team_params: dict) -> dict:
    """
    Extract only AI-relevant parameters from full team parameters.
    Focuses on critical nested values from Phase 0-6 architecture.
    
    Args:
        team_params: Complete team parameters from DynamoDB
        
    Returns:
        Filtered dictionary with AI-relevant parameters
    """
    if not team_params:
        return {}
    
    extracted = {
        'team_id': team_params.get('team_id'),
        'league_id': team_params.get('league_id'),
        'season': team_params.get('season'),
    }
    
    # PHASE 5: Classification Parameters - Team Identity
    if 'classification_params' in team_params:
        classification = team_params['classification_params']
        extracted['classification_params'] = {
            'archetype': classification.get('archetype'),
            'evolution_trend': classification.get('evolution_trend'),
            'archetype_stability': _to_float(classification.get('archetype_stability')),
            'secondary_traits': classification.get('secondary_traits', []),
            'archetype_confidence': _to_float(classification.get('archetype_confidence')),
        }
        
        # Performance profile (nested within classification_params)
        if 'performance_profile' in classification:
            profile = classification['performance_profile']
            extracted['classification_params']['performance_profile'] = {
                'attacking_profile': {
                    'goal_scoring_consistency': _to_float(
                        profile.get('attacking_profile', {}).get('goal_scoring_consistency')
                    )
                },
                'defensive_profile': {
                    'defensive_stability': _to_float(
                        profile.get('defensive_profile', {}).get('defensive_stability')
                    )
                },
                'mentality_profile': {
                    'away_resilience': _to_float(
                        profile.get('mentality_profile', {}).get('away_resilience')
                    )
                },
                'tactical_profile': {
                    'tactical_flexibility': _to_float(
                        profile.get('tactical_profile', {}).get('tactical_flexibility')
                    )
                }
            }
    
    # PHASE 3: Temporal Parameters - Current Form & Momentum
    if 'temporal_params' in team_params:
        temporal = team_params['temporal_params']
        extracted['temporal_params'] = {
            'form_trend': temporal.get('form_trend'),
            'recent_form': _to_float(temporal.get('recent_form')),
            'momentum_factor': _to_float(temporal.get('momentum_factor')),
            'form_confidence': _to_float(temporal.get('form_confidence'))
        }
    
    # PHASE 4: Tactical Parameters - Style of Play
    if 'tactical_params' in team_params:
        tactical = team_params['tactical_params']
        extracted['tactical_params'] = {
            'defensive_solidity': _to_float(tactical.get('defensive_solidity')),  # KEY metric
            'attacking_intensity': _to_float(tactical.get('attacking_intensity')),
            'preferred_formation': tactical.get('preferred_formation'),
            'formation_confidence': _to_float(tactical.get('formation_confidence')),
            'tactical_consistency': _to_float(tactical.get('tactical_consistency')),
            'possession_style': tactical.get('possession_style')
        }
    
    # PHASE 2: Venue Parameters - Home/Away Split
    if 'venue_params' in team_params:
        venue = team_params['venue_params']
        extracted['venue_params'] = {
            'home_advantage': _to_float(venue.get('home_advantage')),
            'away_resilience': _to_float(venue.get('away_resilience')),
            'confidence_level': _to_float(venue.get('confidence_level'))
        }
    
    # PHASE 1: Segmented Parameters - Opponent-Specific Performance
    if 'segmented_params' in team_params:
        segmented = team_params['segmented_params']
        extracted['segmented_params'] = {}
        
        for tier in ['vs_bottom', 'vs_middle', 'vs_top']:
            if tier in segmented:
                tier_data = segmented[tier]
                extracted['segmented_params'][tier] = {
                    'mu_home': _to_float(tier_data.get('mu_home')),
                    'mu_away': _to_float(tier_data.get('mu_away')),
                    'p_score_home': _to_float(tier_data.get('p_score_home')),
                    'p_score_away': _to_float(tier_data.get('p_score_away')),
                    'segment_sample_size': tier_data.get('segment_sample_size'),
                    'using_segment_home': tier_data.get('using_segment_home'),
                    'using_segment_away': tier_data.get('using_segment_away'),
                    'variance_home': _to_float(tier_data.get('variance_home')),
                    'variance_away': _to_float(tier_data.get('variance_away'))
                }
    
    return extracted


def build_ai_context(fixture_data: dict, home_params: dict, away_params: dict, 
                     league_params: dict) -> dict:
    """
    Build complete context for AI analysis.
    
    Args:
        fixture_data: Fixture data from game_fixtures table
        home_params: Extracted home team parameters
        away_params: Extracted away team parameters
        league_params: League parameters and conformance data
        
    Returns:
        Complete context dictionary for AI provider
    """
    context = {
        'fixture_info': {
            'fixture_id': fixture_data.get('fixture_id'),
            'date': fixture_data.get('date'),
            'league': fixture_data.get('league'),
            'venue': fixture_data.get('venue'),
            'timestamp': fixture_data.get('timestamp')
        },
        'home_team': {
            'team_name': fixture_data.get('home', {}).get('team_name'),
            'team_id': fixture_data.get('home', {}).get('team_id'),
            'predictions': fixture_data.get('home'),
            'parameters': home_params
        },
        'away_team': {
            'team_name': fixture_data.get('away', {}).get('team_name'),
            'team_id': fixture_data.get('away', {}).get('team_id'),
            'predictions': fixture_data.get('away'),
            'parameters': away_params
        },
        'match_predictions': fixture_data.get('predictions', {}),
        'league_conformance': league_params.get('league_conformance', {}),
        'weather': fixture_data.get('weather')  # If available
    }
    
    return context


def _to_float(value: Any) -> Optional[float]:
    """
    Convert Decimal or numeric value to float for JSON serialization.
    
    Args:
        value: Value to convert
        
    Returns:
        Float value or None
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def validate_extracted_parameters(params: dict) -> tuple:
    """
    Validate that extracted parameters contain minimum required data.
    
    Args:
        params: Extracted parameters dictionary
        
    Returns:
        Tuple of (is_valid, missing_fields)
    """
    required_fields = ['team_id', 'league_id', 'season']
    missing = [field for field in required_fields if not params.get(field)]
    
    if missing:
        return False, missing
    
    # Check for at least some phase parameters
    phase_params = ['classification_params', 'temporal_params', 'tactical_params', 
                    'venue_params', 'segmented_params']
    has_params = any(params.get(param) for param in phase_params)
    
    if not has_params:
        return False, ['At least one phase parameter required']
    
    return True, []


def get_parameter_summary(params: dict) -> dict:
    """
    Get a summary of available parameters for logging/debugging.
    
    Args:
        params: Extracted parameters dictionary
        
    Returns:
        Summary dictionary with availability flags
    """
    return {
        'team_id': params.get('team_id'),
        'has_classification': 'classification_params' in params,
        'has_temporal': 'temporal_params' in params,
        'has_tactical': 'tactical_params' in params,
        'has_venue': 'venue_params' in params,
        'has_segmented': 'segmented_params' in params,
        'archetype': params.get('classification_params', {}).get('archetype'),
        'form_trend': params.get('temporal_params', {}).get('form_trend')
    }