"""
Manager Multiplier Utilities
Extracts and applies manager tactical multipliers from team parameters.
"""

from decimal import Decimal
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


def get_manager_multiplier_from_params(
    team_params: Dict,
    opponent_tier: str = 'middle',
    venue: str = 'home'
) -> Decimal:
    """
    Extract manager tactical multiplier from team parameters.

    Args:
        team_params: Team parameters dict containing tactical_params
        opponent_tier: 'top', 'middle', or 'bottom'
        venue: 'home' or 'away'

    Returns:
        Decimal multiplier (typically 0.92-1.08 range)
    """
    try:
        # Get tactical params
        tactical_params = team_params.get('tactical_params', {})

        # Check if manager profile is available
        if not tactical_params.get('manager_profile_available', False):
            return Decimal('1.0')  # Neutral multiplier

        # Calculate multiplier based on manager characteristics
        multiplier = Decimal('1.0')

        # 1. Tactical philosophy impact
        philosophy = tactical_params.get('manager_tactical_philosophy', 'balanced')
        if philosophy == 'attacking':
            if opponent_tier == 'bottom':
                multiplier *= Decimal('1.05')  # More aggressive vs weak teams
            elif opponent_tier == 'top':
                multiplier *= Decimal('0.98')  # Slight vulnerability vs strong teams
        elif philosophy == 'defensive':
            if opponent_tier == 'top':
                multiplier *= Decimal('1.03')  # Better organization vs strong teams
            elif opponent_tier == 'bottom':
                multiplier *= Decimal('0.97')  # May struggle to break down weaker teams

        # 2. Experience factor
        experience = tactical_params.get('manager_experience', 0)
        if experience > 10:
            multiplier *= Decimal('1.02')  # Experienced managers get slight boost
        elif experience < 3:
            multiplier *= Decimal('0.98')  # Inexperienced managers slight penalty

        # 3. Tactical flexibility impact
        flexibility = Decimal(str(tactical_params.get('manager_tactical_flexibility', 0.5)))
        if flexibility > Decimal('0.7'):
            # High flexibility = slight unpredictability penalty
            multiplier *= Decimal('0.99')
        elif flexibility < Decimal('0.3'):
            # Low flexibility = slight predictability penalty
            multiplier *= Decimal('0.99')

        # 4. Big game approach (when facing top teams)
        if opponent_tier == 'top':
            big_game_approach = tactical_params.get('manager_big_game_approach', 'standard')
            if big_game_approach == 'attacking':
                multiplier *= Decimal('1.04')  # Fearless approach
            elif big_game_approach == 'cautious':
                multiplier *= Decimal('0.96')  # Defensive shell

        # 5. Home/Away consideration
        # Managers with specific home/away strategies get adjustments
        tactical_rigidity = Decimal(str(tactical_params.get('manager_tactical_rigidity', 0.5)))
        if venue == 'away' and tactical_rigidity > Decimal('0.7'):
            # Rigid managers may struggle to adapt away from home
            multiplier *= Decimal('0.98')

        # Clamp multiplier to reasonable range (0.90 - 1.10)
        multiplier = max(Decimal('0.90'), min(Decimal('1.10'), multiplier))

        logger.info(f"Manager multiplier: {multiplier} (philosophy={philosophy}, exp={experience}, opp={opponent_tier}, venue={venue})")

        return multiplier

    except Exception as e:
        logger.error(f"Error calculating manager multiplier: {e}")
        return Decimal('1.0')


def apply_manager_adjustments(
    home_params: Dict,
    away_params: Dict,
    home_opponent_tier: str = 'middle',
    away_opponent_tier: str = 'middle'
) -> Tuple[Dict, Dict]:
    """
    Apply manager tactical multipliers to team parameters.

    Modifies mu_home, mu_away, and p_score parameters based on manager profiles.

    Args:
        home_params: Home team parameters (will be modified)
        away_params: Away team parameters (will be modified)
        home_opponent_tier: Strength tier of away team from home's perspective
        away_opponent_tier: Strength tier of home team from away's perspective

    Returns:
        Tuple of (adjusted_home_params, adjusted_away_params)
    """
    try:
        # Get manager multipliers
        home_multiplier = get_manager_multiplier_from_params(
            home_params,
            opponent_tier=home_opponent_tier,
            venue='home'
        )

        away_multiplier = get_manager_multiplier_from_params(
            away_params,
            opponent_tier=away_opponent_tier,
            venue='away'
        )

        # Apply to home team parameters
        if 'mu_home' in home_params:
            home_params['mu_home'] = float(Decimal(str(home_params['mu_home'])) * home_multiplier)
        if 'mu' in home_params:
            home_params['mu'] = float(Decimal(str(home_params['mu'])) * home_multiplier)
        if 'p_score_home' in home_params:
            # Smaller adjustment for probabilities
            p_adjustment = Decimal('1.0') + (home_multiplier - Decimal('1.0')) * Decimal('0.5')
            home_params['p_score_home'] = float(Decimal(str(home_params['p_score_home'])) * p_adjustment)
            home_params['p_score_home'] = max(0.1, min(0.9, home_params['p_score_home']))

        # Apply to away team parameters
        if 'mu_away' in away_params:
            away_params['mu_away'] = float(Decimal(str(away_params['mu_away'])) * away_multiplier)
        if 'mu' in away_params:
            away_params['mu'] = float(Decimal(str(away_params['mu'])) * away_multiplier)
        if 'p_score_away' in away_params:
            # Smaller adjustment for probabilities
            p_adjustment = Decimal('1.0') + (away_multiplier - Decimal('1.0')) * Decimal('0.5')
            away_params['p_score_away'] = float(Decimal(str(away_params['p_score_away'])) * p_adjustment)
            away_params['p_score_away'] = max(0.1, min(0.9, away_params['p_score_away']))

        # Add metadata about manager adjustments
        home_params['manager_multiplier_applied'] = float(home_multiplier)
        away_params['manager_multiplier_applied'] = float(away_multiplier)

        logger.info(f"Applied manager multipliers - Home: {home_multiplier}, Away: {away_multiplier}")

        return home_params, away_params

    except Exception as e:
        logger.error(f"Error applying manager adjustments: {e}")
        return home_params, away_params


def get_opponent_tier_from_standings(team_position: int, total_teams: int) -> str:
    """
    Determine opponent tier from league standings.

    Args:
        team_position: Current league position (1-based)
        total_teams: Total number of teams in league

    Returns:
        'top', 'middle', or 'bottom'
    """
    if total_teams == 0:
        return 'middle'

    # Top 30% = top tier
    # Bottom 30% = bottom tier
    # Middle 40% = middle tier
    top_threshold = int(total_teams * 0.3)
    bottom_threshold = int(total_teams * 0.7)

    if team_position <= top_threshold:
        return 'top'
    elif team_position > bottom_threshold:
        return 'bottom'
    else:
        return 'middle'
