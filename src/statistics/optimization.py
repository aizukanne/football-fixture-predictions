"""
Optimization functions for parameter tuning in football predictions.
Contains grid search and weight tuning algorithms.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from ..utils.constants import MINIMUM_GAMES_THRESHOLD
from .distributions import nb_pmf, brier_score


def tune_weights_grid(df, mu, alpha_nb, ref_games, k_grid=(np.arange(3, 9), np.arange(4, 11)), defaults=(5, 6)):
    """
    Tune smoothing weights using grid search to optimize predictions.
    Originally from computeLeagueParameters.py.

    Runs the grid search **twice** — once scoring the home side
    (P(home scores >=1) vs home_goals > 0), once scoring the away side
    (mirror, but for the away team). The home and away k values are
    optimised independently so the smoothing constants applied to each
    side reflect the prediction error from that side.

    Returns:
        Dictionary with side-suffixed weights and Brier scores:
            k_goals_home, k_score_home, brier_home,
            k_goals_away, k_score_away, brier_away,
            goal_prior_weight_home/away, score_prior_weight_home/away.
    """
    if df.empty or len(df) < MINIMUM_GAMES_THRESHOLD:
        print("Insufficient data for weight tuning. Using defaults.")
        return _default_dual_side_params(defaults)

    k_goals_grid, k_score_grid = k_grid

    def _grid_search_one_side(side: str):
        best = float('inf')
        chosen = None
        for k_goals in k_goals_grid:
            for k_score in k_score_grid:
                try:
                    score = calculate_brier_score_for_weights(
                        df, mu, alpha_nb, k_goals, k_score, ref_games, side=side,
                    )
                    if score < best:
                        best = score
                        chosen = (int(k_goals), int(k_score), float(best))
                except Exception as e:
                    print(f"Error tuning {side} k_goals={k_goals} k_score={k_score}: {e}")
                    continue
        return chosen

    home_pick = _grid_search_one_side("home")
    away_pick = _grid_search_one_side("away")

    if home_pick is None and away_pick is None:
        print("Grid search failed for both sides. Using default weights.")
        return _default_dual_side_params(defaults)

    if home_pick is None:
        home_pick = (defaults[0], defaults[1], 0.25)
    if away_pick is None:
        away_pick = (defaults[0], defaults[1], 0.25)

    kg_h, ks_h, br_h = home_pick
    kg_a, ks_a, br_a = away_pick

    out = {
        'k_goals_home': kg_h,
        'k_score_home': ks_h,
        'goal_prior_weight_home': kg_h,
        'score_prior_weight_home': ks_h,
        'brier_home': br_h,
        'k_goals_away': kg_a,
        'k_score_away': ks_a,
        'goal_prior_weight_away': kg_a,
        'score_prior_weight_away': ks_a,
        'brier_away': br_a,
    }
    print(
        f"Best weights — home: k_goals={kg_h} k_score={ks_h} brier={br_h:.4f} | "
        f"away: k_goals={kg_a} k_score={ks_a} brier={br_a:.4f}"
    )
    return out


def _default_dual_side_params(defaults):
    """Default smoothing-weight dict when grid search can't run.

    Symmetric: same defaults applied to home and away. Brier defaults to
    0.25 (the no-information baseline of a binary brier).
    """
    kg, ks = defaults[0], defaults[1]
    return {
        'k_goals_home': kg, 'k_score_home': ks,
        'goal_prior_weight_home': kg, 'score_prior_weight_home': ks,
        'brier_home': 0.25,
        'k_goals_away': kg, 'k_score_away': ks,
        'goal_prior_weight_away': kg, 'score_prior_weight_away': ks,
        'brier_away': 0.25,
    }


def tune_weights_grid_team(df, mu, alpha_nb, ref_games, k_grid=(np.arange(3, 9), np.arange(4, 11)), defaults=(5, 6)):
    """
    Tune smoothing weights for team-specific parameters using grid search.
    Originally from computeTeamParameters.py.
    Same dual-side return shape as tune_weights_grid.
    """
    return tune_weights_grid(df, mu, alpha_nb, ref_games, k_grid, defaults)


def calculate_brier_score_for_weights(df, mu, alpha_nb, k_goals, k_score, ref_games, side="home"):
    """
    Calculate Brier score for given smoothing weights.

    The system measures whether a team scores at all (binary), not how
    many goals — the goal count is a byproduct.

    Args:
        side: "home" or "away".
            "home" -> P(home scores >=1) vs home_goals > 0
                      Smooths home_offense toward league_home_offense.
            "away" -> P(away scores >=1) vs away_goals > 0
                      Smooths away_offense toward league_away_offense.
        Other args unchanged.
    
    Args:
        df: Match data DataFrame
        mu: Parameter dictionary
        alpha_nb: Negative binomial alpha
        k_goals: Goals smoothing weight
        k_score: Score smoothing weight  
        ref_games: Reference games count
        
    Returns:
        Brier score for the given weights
    """
    if side not in ("home", "away"):
        raise ValueError(f"side must be 'home' or 'away', got {side!r}")

    predictions = []
    actuals = []

    for _, match in df.iterrows():
        try:
            if side == "home":
                lam = apply_smoothing(
                    mu.get('home_offense', 1.0),
                    mu.get('league_home_offense', 1.0),
                    k_goals, ref_games,
                )
                actual = 1 if match.get('home_goals', 0) > 0 else 0
            else:
                lam = apply_smoothing(
                    mu.get('away_offense', 1.0),
                    mu.get('league_away_offense', 1.0),
                    k_goals, ref_games,
                )
                actual = 1 if match.get('away_goals', 0) > 0 else 0

            score_prob = 1 - nb_pmf(0, lam, alpha_nb)
            predictions.append(score_prob)
            actuals.append(actual)

        except Exception as e:
            print(f"Error calculating prediction for match: {e}")
            continue

    if not predictions:
        return float('inf')

    return brier_score(predictions, actuals)


def apply_smoothing(team_value, league_value, k_weight, ref_games):
    """
    Apply Bayesian smoothing to a team parameter.
    
    Args:
        team_value: Team-specific parameter value
        league_value: League average parameter value
        k_weight: Smoothing weight (higher = less smoothing)
        ref_games: Reference number of games
        
    Returns:
        Smoothed parameter value
    """
    if ref_games <= 0:
        return league_value
    
    # Bayesian smoothing formula
    smoothed = (k_weight * league_value + ref_games * team_value) / (k_weight + ref_games)
    return smoothed


def optimize_lambda_parameters(home_goals, away_goals, method='mle'):
    """
    Optimize lambda parameters for goal prediction models.
    
    Args:
        home_goals: List of home team goals
        away_goals: List of away team goals  
        method: Optimization method ('mle' for maximum likelihood)
        
    Returns:
        Dictionary with optimized lambda parameters
    """
    if not home_goals or not away_goals:
        return {'home_lambda': 1.0, 'away_lambda': 1.0}
    
    if method == 'mle':
        # Maximum likelihood estimation
        home_lambda = np.mean(home_goals)
        away_lambda = np.mean(away_goals)
    else:
        # Could add other methods like method of moments, Bayesian, etc.
        home_lambda = np.mean(home_goals)
        away_lambda = np.mean(away_goals)
    
    return {
        'home_lambda': max(0.1, home_lambda),  # Ensure positive
        'away_lambda': max(0.1, away_lambda)
    }


def cross_validate_parameters(df, param_func, n_folds=5):
    """
    Perform cross-validation on parameter estimation.
    
    Args:
        df: DataFrame with match data
        param_func: Function to estimate parameters
        n_folds: Number of cross-validation folds
        
    Returns:
        Dictionary with cross-validation results
    """
    if len(df) < n_folds:
        return {'error': 'Insufficient data for cross-validation'}
    
    fold_size = len(df) // n_folds
    scores = []
    
    for fold in range(n_folds):
        start_idx = fold * fold_size
        end_idx = (fold + 1) * fold_size if fold < n_folds - 1 else len(df)
        
        # Split data
        test_data = df.iloc[start_idx:end_idx]
        train_data = pd.concat([df.iloc[:start_idx], df.iloc[end_idx:]])
        
        try:
            # Train parameters on training data
            params = param_func(train_data)
            
            # Evaluate on test data
            score = evaluate_parameters(test_data, params)
            scores.append(score)
            
        except Exception as e:
            print(f"Error in fold {fold}: {e}")
            continue
    
    if not scores:
        return {'error': 'Cross-validation failed'}
    
    return {
        'mean_score': np.mean(scores),
        'std_score': np.std(scores),
        'scores': scores
    }


def evaluate_parameters(test_data, params):
    """
    Evaluate parameter quality on test data.
    
    Args:
        test_data: DataFrame with test matches
        params: Parameter dictionary to evaluate
        
    Returns:
        Evaluation score (lower is better)
    """
    predictions = []
    actuals = []
    
    for _, match in test_data.iterrows():
        try:
            # Make prediction using parameters
            home_lambda = params.get('home_lambda', 1.0)
            away_lambda = params.get('away_lambda', 1.0)
            
            # Predict probability of home team scoring
            home_score_prob = 1 - nb_pmf(0, home_lambda, params.get('alpha', 0.3))
            
            # Actual outcome
            actual = 1 if match.get('home_goals', 0) > 0 else 0
            
            predictions.append(home_score_prob)
            actuals.append(actual)
            
        except Exception:
            continue
    
    if not predictions:
        return float('inf')
    
    return brier_score(predictions, actuals)


def gradient_descent_optimization(objective_func, initial_params, learning_rate=0.01, max_iter=1000, tolerance=1e-6):
    """
    Simple gradient descent optimization for parameter tuning.
    
    Args:
        objective_func: Function to minimize
        initial_params: Starting parameter values
        learning_rate: Step size for updates
        max_iter: Maximum iterations
        tolerance: Convergence tolerance
        
    Returns:
        Optimized parameters
    """
    params = np.array(initial_params)
    
    for iteration in range(max_iter):
        # Calculate gradient numerically
        gradient = numerical_gradient(objective_func, params)
        
        # Update parameters
        new_params = params - learning_rate * gradient
        
        # Check convergence
        if np.linalg.norm(new_params - params) < tolerance:
            print(f"Converged after {iteration} iterations")
            break
        
        params = new_params
    
    return params.tolist()


def numerical_gradient(func, params, epsilon=1e-5):
    """
    Calculate numerical gradient of a function.
    
    Args:
        func: Function to differentiate
        params: Parameter values
        epsilon: Small step for numerical differentiation
        
    Returns:
        Gradient vector
    """
    gradient = np.zeros_like(params)
    
    for i in range(len(params)):
        params_plus = params.copy()
        params_minus = params.copy()
        
        params_plus[i] += epsilon
        params_minus[i] -= epsilon
        
        gradient[i] = (func(params_plus) - func(params_minus)) / (2 * epsilon)
    
    return gradient


def find_optimal_alpha(goals_data, lambda_estimate):
    """
    Find optimal alpha parameter for negative binomial distribution.
    
    Args:
        goals_data: List of goal counts
        lambda_estimate: Estimated lambda (mean) parameter
        
    Returns:
        Optimal alpha parameter
    """
    if not goals_data or lambda_estimate <= 0:
        return 0.3  # Default alpha
    
    goals_array = np.array(goals_data)
    mean = np.mean(goals_array)
    variance = np.var(goals_array)
    
    if variance <= mean:
        return 0.01  # Close to Poisson
    
    # Method of moments estimate
    alpha = (variance - mean) / (mean ** 2) if mean > 0 else 0.3
    
    # Ensure alpha is in reasonable range
    return max(0.01, min(alpha, 2.0))