"""
Brier score feedback functions for adaptive Bayesian prior weight adjustment.

Each Wednesday parameter update cycle the team handler calls these functions to:
  1. Blend the current week's Brier score into a running EMA (update_brier_ema).
  2. Compare the EMA against the league average and nudge k_goals / k_score
     by ±1 if the team is consistently easier or harder to predict (compute_k_adjustment).

This gives the grid-search-optimised k values a memory: teams that have been
noisier than the league over many weeks accumulate stronger regularisation
(higher k → prior pulled harder toward the league mean), while teams with stable,
predictable scoring drift toward trusting their own data more (lower k).
"""


def update_brier_ema(
    current_brier: float,
    prev_brier_ema: float,
    ema_alpha: float = 0.3,
) -> float:
    """
    Exponential moving average of weekly Brier scores.

    Args:
        current_brier:  Brier score from this week's grid search.
        prev_brier_ema: EMA value stored from the previous update cycle.
                        On the very first call (no history) pass current_brier
                        so the EMA starts at the observed value.
        ema_alpha:      Weight given to the current week (default 0.3).
                        Retains 70 % of accumulated history per cycle.
                        At alpha=0.3 the EMA reaches ~95 % maturity after ~10 weeks.

    Returns:
        Updated EMA value (float).
    """
    return ema_alpha * current_brier + (1.0 - ema_alpha) * prev_brier_ema


def compute_k_adjustment(
    brier_ema: float,
    league_brier: float,
    base_k_goals: int,
    base_k_score: int,
    games_played: int,
    k_goals_bounds: tuple = (3, 8),
    k_score_bounds: tuple = (4, 10),
) -> dict:
    """
    Apply a bounded ±1 correction to grid-search k values based on how the
    team's Brier EMA compares to the current league average Brier.

    Adjustment rules (one step per weekly cycle):
        brier_ema - league_brier >  0.02  → step = +1
            Team is noisier than the league on average.
            Increase k to pull predictions harder toward the league prior.

        brier_ema - league_brier < -0.02  → step = -1
            Team is more predictable than the league on average.
            Decrease k to rely more on the team's own historical data.

        within ±0.02                      → step =  0  (no change)

    Requires games_played >= 10 before any adjustment is applied; below that
    threshold there is not enough data to distinguish signal from noise.

    Args:
        brier_ema:      Team's current Brier EMA (from update_brier_ema).
        league_brier:   League average Brier for this update cycle
                        (from football_league_parameters_prod).
        base_k_goals:   k_goals suggested by this week's grid search.
        base_k_score:   k_score suggested by this week's grid search.
        games_played:   Total games played by the team this season.
        k_goals_bounds: (min, max) inclusive bounds for k_goals.
        k_score_bounds: (min, max) inclusive bounds for k_score.

    Returns:
        dict with keys:
            k_goals          – feedback-adjusted value (int)
            k_score          – feedback-adjusted value (int)
            k_feedback_step  – correction applied: -1, 0, or +1 (int)
            k_feedback_reason – one of:
                'insufficient_games'  – games_played < 10, no adjustment
                'above_league_avg'    – step = +1
                'below_league_avg'    – step = -1
                'within_tolerance'    – step =  0
    """
    if games_played < 10:
        return {
            'k_goals': base_k_goals,
            'k_score': base_k_score,
            'k_feedback_step': 0,
            'k_feedback_reason': 'insufficient_games',
        }

    delta = brier_ema - league_brier

    if delta > 0.02:
        step = 1
        reason = 'above_league_avg'
    elif delta < -0.02:
        step = -1
        reason = 'below_league_avg'
    else:
        step = 0
        reason = 'within_tolerance'

    return {
        'k_goals': max(k_goals_bounds[0], min(k_goals_bounds[1], base_k_goals + step)),
        'k_score': max(k_score_bounds[0], min(k_score_bounds[1], base_k_score + step)),
        'k_feedback_step': step,
        'k_feedback_reason': reason,
    }
