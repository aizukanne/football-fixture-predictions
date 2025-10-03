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
    
    Args:
        df: DataFrame with match data
        mu: Fitted parameters dictionary
        alpha_nb: Negative binomial alpha parameter
        ref_games: Reference number of games
        k_grid: Tuple of (goals_grid, score_grid) for grid search
        defaults: Default values if optimization fails
        
    Returns:
        Dictionary with optimized weights and performance metrics
    """
    if df.empty or len(df) < MINIMUM_GAMES_THRESHOLD:
        print("Insufficient data for weight tuning. Using defaults.")
        return {
            'k_goals': defaults[0],
            'k_score': defaults[1], 
            'goal_prior_weight': defaults[0],
            'score_prior_weight': defaults[1],
            'brier': 0.25  # Default Brier score
        }
    
    k_goals_grid, k_score_grid = k_grid
    best_brier = float('inf')
    best_params = None
    
    # Grid search over weight combinations
    for k_goals in k_goals_grid:
        for k_score in k_score_grid:
            try:
                brier_score_val = calculate_brier_score_for_weights(
                    df, mu, alpha_nb, k_goals, k_score, ref_games
                )
                
                if brier_score_val < best_brier:
                    best_brier = brier_score_val
                    best_params = {
                        'k_goals': int(k_goals),
                        'k_score': int(k_score),
                        'goal_prior_weight': int(k_goals), 
                        'score_prior_weight': int(k_score),
                        'brier': float(best_brier)
                    }
            except Exception as e:
                print(f"Error in weight tuning for k_goals={k_goals}, k_score={k_score}: {e}")
                continue
    
    if best_params is None:
        print("Grid search failed. Using default weights.")
        return {
            'k_goals': defaults[0],
            'k_score': defaults[1],
            'goal_prior_weight': defaults[0], 
            'score_prior_weight': defaults[1],
            'brier': 0.25
        }
    
    print(f"Best weights found: k_goals={best_params['k_goals']}, k_score={best_params['k_score']}, brier={best_params['brier']:.4f}")
    return best_params


def tune_weights_grid_team(df, mu, alpha_nb, ref_games, k_grid=(np.arange(3, 9), np.arange(4, 11)), defaults=(5, 6)):
    """
    Tune smoothing weights for team-specific parameters using grid search.
    Originally from computeTeamParameters.py.
    
    Args:
        df: DataFrame with team match data
        mu: Fitted parameters dictionary  
        alpha_nb: Negative binomial alpha parameter
        ref_games: Reference number of games
        k_grid: Tuple of (goals_grid, score_grid) for grid search
        defaults: Default values if optimization fails
        
    Returns:
        Dictionary with optimized weights and performance metrics
    """
    return tune_weights_grid(df, mu, alpha_nb, ref_games, k_grid, defaults)


def calculate_brier_score_for_weights(df, mu, alpha_nb, k_goals, k_score, ref_games):
    """
    Calculate Brier score for given smoothing weights.
    
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
    predictions = []
    actuals = []
    
    for _, match in df.iterrows():
        try:
            # Apply smoothing with given weights
            home_lambda = apply_smoothing(
                mu.get('home_offense', 1.0), 
                mu.get('league_home_offense', 1.0), 
                k_goals, 
                ref_games
            )
            away_lambda = apply_smoothing(
                mu.get('away_offense', 1.0),
                mu.get('league_away_offense', 1.0), 
                k_goals,
                ref_games
            )
            
            # Calculate probability of home team scoring
            home_score_prob = 1 - nb_pmf(0, home_lambda, alpha_nb)
            
            # Actual outcome (1 if home team scored, 0 otherwise)
            actual = 1 if match.get('home_goals', 0) > 0 else 0
            
            predictions.append(home_score_prob)
            actuals.append(actual)
            
        except Exception as e:
            print(f"Error calculating prediction for match: {e}")
            continue
    
    if not predictions:
        return float('inf')  # Return worst possible score if no predictions
        
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