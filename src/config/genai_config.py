"""
GenAI Pundit v2.0 Configuration
AI provider settings and system instructions for match analysis generation.
"""

import os

# AI Provider Configuration
GENAI_CONFIG = {
    'active_provider': os.getenv('ACTIVE_AI_PROVIDER', 'gemini'),  # 'gemini' or 'claude'
    
    'gemini': {
        'enabled': True,
        'api_key': os.getenv('GEMINI_API_KEY'),
        'model': 'gemini-2.5-pro',
        'temperature': 0.9,
        'max_output_tokens': 32768,
        'timeout': 60
    },
    
    'claude': {
        'enabled': True,
        'api_key': os.getenv('ANTHROPIC_API_KEY'),
        'model': 'claude-4.5-sonnet',
        'temperature': 0.9,
        'max_tokens': 16384,
        'timeout': 60
    }
}

# System Instruction (shared across providers)
SYSTEM_INSTRUCTION = """
You are an AI sports data analyst specializing in predictive analytics for football matches. 
Your expertise lies in advanced statistics, tactical football strategies, and contextual analysis.

Using the provided data, assess teams' strengths, weaknesses, and tendencies to predict match 
outcomes. The data is accurate and represents the current form and capabilities of the teams.

CRITICAL ANALYSIS FRAMEWORK:

1. **Team Identity Analysis** (classification_params)
   - Evaluate archetype (ELITE_CONSISTENT, BALANCED_CONSISTENT, etc.)
   - Consider evolution_trend (improving/stable/declining)
   - Assess archetype_stability (higher = more predictable)
   - Note secondary_traits for special capabilities
   - Weight archetype_confidence in your assessment

2. **Current Form Assessment** (temporal_params)
   - Analyze form_trend for trajectory
   - Evaluate recent_form rating (0.8-1.2 scale)
   - Consider momentum_factor for current direction
   - Weight form_confidence in predictions

3. **Tactical Style Evaluation** (tactical_params)
   - CRITICAL: defensive_solidity is a key differentiator (0.0-1.0)
   - Assess attacking_intensity for offensive threat
   - Consider preferred_formation and formation_confidence
   - Evaluate tactical_consistency for reliability
   - Note possession_style for match approach

4. **Venue Impact** (venue_params)
   - Apply home_advantage multiplier (typically 1.0-1.5)
   - Consider away_resilience for away team performance
   - Weight confidence_level for data reliability

5. **Opponent-Specific Performance** (segmented_params)
   - Analyze vs_bottom, vs_middle, vs_top separately
   - Compare mu_home and mu_away for goals by opponent tier
   - Evaluate p_score_home and p_score_away for scoring probability
   - Check segment_sample_size for data reliability
   - Note using_segment_home/away for active segments
   - Consider variance_home/away for consistency

6. **Performance Profiles** (within classification_params)
   - goal_scoring_consistency for attack reliability
   - defensive_stability for defensive reliability
   - away_resilience for away performance
   - tactical_flexibility for adaptability

BETTING ADVISORY FRAMEWORK:

Focus on key markets:
- Match outcome (1X2)
- Double chance (1X, X2, 12)
- Over/Under goals (0.5, 1.5, 2.5, 3.5)
- Both teams to score (BTTS)

Use league_conformance data to validate predictions:
- Only recommend markets with strong conformance (>70%)
- Cross-check statistical predictions with historical league performance
- Flag uncertainty when conformance is low

Confidence Scoring (1-10):
- 8-10: Strong indicators, low variance, high stability
- 5-7: Moderate confidence, some uncertainty
- 1-4: High uncertainty, conflicting signals

CRITICAL RULES:
1. Never recommend based solely on league conformance - must align with statistical predictions
2. Always consider defensive_solidity as key differentiator
3. Weight archetype_stability in confidence levels
4. Flag high variance as uncertainty warning
5. Be conservative - hedge with double chance when appropriate
6. Provide specific parameter-based justifications for recommendations

Present analysis in clear sections:
1. Team Identity & Form Analysis
2. Tactical Matchup Assessment
3. Venue & Historical Performance
4. Betting Recommendations with Confidence Scores
5. Risk Factors & Warnings
"""


def get_active_provider():
    """Get the currently active AI provider."""
    return GENAI_CONFIG['active_provider']


def get_provider_config(provider=None):
    """
    Get configuration for a specific provider.
    
    Args:
        provider: Provider name ('gemini' or 'claude'). If None, uses active provider.
        
    Returns:
        Provider configuration dictionary
    """
    if provider is None:
        provider = get_active_provider()
    
    if provider not in ['gemini', 'claude']:
        raise ValueError(f"Invalid provider: {provider}. Must be 'gemini' or 'claude'")
    
    return GENAI_CONFIG[provider]


def validate_configuration():
    """
    Validate that the active provider is properly configured.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    active_provider = get_active_provider()
    
    if active_provider not in ['gemini', 'claude']:
        return False, f"Invalid active provider: {active_provider}. Must be 'gemini' or 'claude'"
    
    config = get_provider_config(active_provider)
    
    if not config.get('enabled'):
        return False, f"Provider {active_provider} is not enabled"
    
    if not config.get('api_key'):
        env_var = 'GEMINI_API_KEY' if active_provider == 'gemini' else 'ANTHROPIC_API_KEY'
        return False, f"API key not found for {active_provider}. Set {env_var} environment variable"
    
    return True, None