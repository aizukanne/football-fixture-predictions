"""
Bayesian smoothing functions for football predictions.
Provides smoothing techniques to handle small sample sizes and improve predictions.
"""

import numpy as np
from ..utils.constants import DEFAULT_SMOOTHING_ALPHA, DEFAULT_PRIOR_WEIGHT


def bayesian_smooth_rate(observed_values, prior_mean=None, prior_weight=DEFAULT_PRIOR_WEIGHT):
    """
    Apply Bayesian smoothing to a series of observed values.
    
    Args:
        observed_values: List of observed values (e.g., goals per game)
        prior_mean: Prior belief about the mean (defaults to average across all teams)
        prior_weight: Weight of the prior (equivalent sample size)
    
    Returns:
        Smoothed estimate of the rate
    """
    if not observed_values:
        return 0
    
    # Calculate observed statistics
    observed_mean = np.mean(observed_values) if observed_values else 0
    sample_size = len(observed_values)
    
    # If prior_mean is not provided, use a reasonable default
    if prior_mean is None:
        # Default to league average or a conservative estimate
        prior_mean = 1.0  # Can be replaced with actual league average
    
    # Apply Bayesian smoothing formula: weighted average of prior and observed data
    smoothed_rate = (prior_mean * prior_weight + observed_mean * sample_size) / (prior_weight + sample_size)
    
    return smoothed_rate


def bayesian_smooth_binary(binary_values, prior_probability=None, prior_weight=DEFAULT_PRIOR_WEIGHT):
    """
    Apply Bayesian smoothing to binary outcomes (e.g., scored/didn't score).
    
    Args:
        binary_values: List of 1s and 0s representing binary outcomes
        prior_probability: Prior belief about the probability (defaults to average)
        prior_weight: Weight of the prior (equivalent sample size)
    
    Returns:
        Smoothed estimate of the probability
    """
    if not binary_values:
        return 0
    
    # Calculate observed proportion
    successes = sum(binary_values)
    sample_size = len(binary_values)
    observed_prob = successes / sample_size if sample_size > 0 else 0
    
    # If prior_probability is not provided, use a reasonable default
    if prior_probability is None:
        # Default to league average or a moderate estimate
        prior_probability = 0.5  # Can be replaced with actual league average
    
    # Apply Bayesian smoothing formula
    smoothed_prob = (prior_probability * prior_weight + observed_prob * sample_size) / (prior_weight + sample_size)
    
    return smoothed_prob


def apply_smoothing_to_team_data(raw_scores, alpha=DEFAULT_SMOOTHING_ALPHA, prior_mean=None, prior_weight=DEFAULT_PRIOR_WEIGHT, use_bayesian=True):
    """
    Apply smoothing to a list of raw goal data, with option for either
    exponential or Bayesian smoothing.
    
    Args:
        raw_scores: A list of goal counts per match (most recent first)
        alpha: Smoothing factor for exponential smoothing
        prior_mean: Prior mean for Bayesian smoothing
        prior_weight: Weight of the prior for Bayesian smoothing
        use_bayesian: If True, use Bayesian smoothing; otherwise use exponential
    
    Returns:
        The smoothed average goals per game
    """
    if not raw_scores:
        return 0  # If no data, assume 0 goals
    
    if use_bayesian:
        return bayesian_smooth_rate(raw_scores, prior_mean, prior_weight)
    else:
        # Original exponential smoothing logic
        smoothed_value = raw_scores[0]  # Start with the most recent game
        for score in raw_scores[1:]:  # Apply smoothing to the rest
            smoothed_value = alpha * score + (1 - alpha) * smoothed_value
        return smoothed_value


def apply_smoothing_to_binary_rate(binary_data, total_games, alpha=DEFAULT_SMOOTHING_ALPHA, prior_prob=None, prior_weight=DEFAULT_PRIOR_WEIGHT, use_bayesian=True):
    """
    Apply smoothing to binary outcomes (e.g., scored/didn't score, clean sheets),
    with option for either exponential or Bayesian smoothing.
    
    Args:
        binary_data: List of 0s and 1s (e.g., games scored, clean sheets)
        total_games: Total number of games played
        alpha: Smoothing factor for exponential smoothing
        prior_prob: Prior probability for Bayesian smoothing
        prior_weight: Weight of the prior for Bayesian smoothing
        use_bayesian: If True, use Bayesian smoothing; otherwise use exponential
    
    Returns:
        The smoothed rate/probability
    """
    if not binary_data or total_games == 0:
        return 0
    
    if use_bayesian:
        return bayesian_smooth_binary(binary_data, prior_prob, prior_weight)
    else:
        # Original exponential smoothing logic
        if not binary_data:
            return 0
        
        smoothed_value = binary_data[0]  # Start with the most recent outcome
        for outcome in binary_data[1:]:  # Apply smoothing to the rest
            smoothed_value = alpha * outcome + (1 - alpha) * smoothed_value
        return smoothed_value


def calculate_confidence_interval(sample_mean, sample_size, confidence_level=0.95):
    """
    Calculate confidence interval for a sample mean using normal approximation.
    
    Args:
        sample_mean: Sample mean
        sample_size: Sample size
        confidence_level: Confidence level (default 0.95 for 95% CI)
    
    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    if sample_size <= 1:
        return sample_mean, sample_mean
    
    # For large samples, use normal approximation
    # For small samples, this is just an approximation
    from scipy import stats
    
    # Standard error (assuming Poisson-like variance = mean for goals)
    standard_error = np.sqrt(sample_mean / sample_size) if sample_mean > 0 else 0
    
    # Critical value for confidence level
    alpha = 1 - confidence_level
    z_critical = stats.norm.ppf(1 - alpha/2)
    
    margin_of_error = z_critical * standard_error
    
    lower_bound = max(0, sample_mean - margin_of_error)  # Goals can't be negative
    upper_bound = sample_mean + margin_of_error
    
    return lower_bound, upper_bound


def empirical_bayes_estimation(observed_means, observed_sizes):
    """
    Perform empirical Bayes estimation to shrink individual estimates toward the overall mean.
    
    Args:
        observed_means: List of observed means for each entity (team, etc.)
        observed_sizes: List of sample sizes corresponding to each mean
    
    Returns:
        List of shrunk estimates
    """
    if not observed_means or not observed_sizes:
        return []
    
    observed_means = np.array(observed_means)
    observed_sizes = np.array(observed_sizes)
    
    # Overall mean across all entities
    overall_mean = np.average(observed_means, weights=observed_sizes)
    
    # Estimate between-entity variance
    weighted_var = np.average((observed_means - overall_mean) ** 2, weights=observed_sizes)
    
    # Within-entity variance (assuming Poisson-like: variance = mean)
    within_var = overall_mean
    
    # Shrinkage factor
    between_var = max(0, weighted_var - within_var / observed_sizes.mean())
    shrinkage_factors = between_var / (between_var + within_var / observed_sizes)
    
    # Apply shrinkage
    shrunk_estimates = shrinkage_factors * observed_means + (1 - shrinkage_factors) * overall_mean
    
    return shrunk_estimates.tolist()


def adaptive_smoothing_weight(sample_size, min_weight=0.1, max_weight=1.0):
    """
    Calculate adaptive smoothing weight based on sample size.
    Smaller samples get more smoothing.
    
    Args:
        sample_size: Number of observations
        min_weight: Minimum weight for raw data (maximum smoothing)
        max_weight: Maximum weight for raw data (minimum smoothing)
    
    Returns:
        Weight for raw data (0 = full smoothing, 1 = no smoothing)
    """
    if sample_size <= 0:
        return min_weight
    
    # Logistic function to map sample size to weight
    # More samples = higher weight (less smoothing)
    weight = min_weight + (max_weight - min_weight) / (1 + np.exp(-(sample_size - 10) / 5))
    
    return np.clip(weight, min_weight, max_weight)


def hierarchical_smoothing(team_data, league_mean, team_sample_sizes=None):
    """
    Apply hierarchical Bayesian smoothing where team estimates are shrunk toward league mean.
    
    Args:
        team_data: Dictionary of team_id -> observed values
        league_mean: League-wide average
        team_sample_sizes: Dictionary of team_id -> sample size
    
    Returns:
        Dictionary of team_id -> smoothed estimates
    """
    if not team_data:
        return {}
    
    if team_sample_sizes is None:
        team_sample_sizes = {team: len(values) for team, values in team_data.items()}
    
    smoothed_estimates = {}
    
    for team_id, values in team_data.items():
        if not values:
            smoothed_estimates[team_id] = league_mean
            continue
        
        sample_size = team_sample_sizes.get(team_id, len(values))
        
        # Use adaptive weight based on sample size
        raw_weight = adaptive_smoothing_weight(sample_size)
        
        team_mean = np.mean(values)
        smoothed_estimate = raw_weight * team_mean + (1 - raw_weight) * league_mean
        
        smoothed_estimates[team_id] = smoothed_estimate
    
    return smoothed_estimates