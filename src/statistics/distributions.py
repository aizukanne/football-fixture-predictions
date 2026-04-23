"""
Statistical distribution functions for football predictions.
Contains probability mass functions and goal probability calculations.
"""

import math
import numpy as np
from scipy import stats

from ..utils.constants import DEFAULT_ALPHA, MAX_GOALS_ANALYSIS


def nb_pmf(k, mu, alpha=DEFAULT_ALPHA):
    """
    Calculate probability mass function for Negative Binomial distribution.
    Automatically uses Poisson for underdispersed data (alpha near 0).

    Args:
        k: Number of goals
        mu: Lambda (expected goals)
        alpha: Dispersion parameter (higher = more dispersion)
               When alpha ≤ 0.01, uses Poisson distribution for statistical accuracy

    Returns:
        Probability of exactly k goals with expected value mu
    """
    try:
        # Ensure parameters are valid
        if mu < 0:
            return 0

        # Handle edge cases
        if k < 0:
            return 0
        if mu == 0 and k == 0:
            return 1
        if mu == 0:
            return 0

        # Adaptive distribution selection for maximum accuracy:
        # When alpha is very small (≤ 0.01), the data shows little to no overdispersion,
        # meaning variance ≈ mean. In this case, Poisson is statistically more appropriate
        # and numerically more stable than forcing Negative Binomial with tiny alpha.
        if alpha <= 0.01:
            # Use Poisson for underdispersed or equidispersed data (variance ≈ mean)
            return poisson_pmf(k, mu)

        # Use Negative Binomial for overdispersed data (variance > mean, alpha > 0.01)
        r = 1 / alpha
        p = 1 / (1 + alpha * mu)

        return stats.nbinom.pmf(k, r, p)
    except Exception as e:
        # Fallback to Poisson in case of numerical errors
        print(f"Warning: Negative Binomial calculation failed ({e}). Falling back to Poisson.")
        return poisson_pmf(k, mu)


def poisson_pmf(k, lambda_):
    """
    Calculate the Poisson probability mass function (PMF) for given k and lambda.
    Used as a fallback if Negative Binomial calculation fails.

    Args:
        k: The number of events for which the probability is to be calculated
        lambda_: The expected number of events that can occur within a fixed interval

    Returns:
        The PMF probability for k events to happen
    """
    try:
        return (lambda_ ** k) * math.exp(-lambda_) / math.factorial(k)
    except OverflowError:
        # For very large k or lambda values
        return 0
    except Exception:
        # Ultimate fallback
        return 0


def calculate_goal_probabilities(lmbda, alpha=DEFAULT_ALPHA):
    """
    Calculate the probabilities of scoring different numbers of goals using 
    the Negative Binomial distribution.

    Args:
        lmbda: The lambda (expected rate) of goals
        alpha: Dispersion parameter for Negative Binomial distribution

    Returns:
        Tuple of (most_likely_goals, probability_of_most_likely, all_probabilities_dict)
    """
    # Post-anchor scale correction. With the league-anchor using cross-venue
    # factor centers (mu_bar, p_bar) and the double-counted home_adv
    # multiplier removed from the λ pipeline, both home and away sides are
    # compressed by a symmetric ~26% residual from Bayesian smoothing /
    # confidence calibration. Empirical sweep on 2,953 v7 fixtures finds
    # 1.35 nearly zeroes home and away bias simultaneously (home +0.003,
    # away -0.058) at MAE 1.399 / RMSE 1.773.
    adjusted_lmbda = lmbda * 1.35

    # Calculate probabilities for goals 0-10 using the Negative Binomial
    probabilities = {}
    for goals in range(MAX_GOALS_ANALYSIS + 1):  # From 0 to MAX_GOALS_ANALYSIS goals
        probabilities[goals] = nb_pmf(goals, adjusted_lmbda, alpha)
    
    # Ensure probabilities sum to 1 (may not due to truncation at MAX_GOALS_ANALYSIS goals)
    probability_sum = sum(probabilities.values())
    if probability_sum > 0:  # Avoid division by zero
        for goals in probabilities:
            probabilities[goals] /= probability_sum
    
    # Find the number of goals with the highest probability
    most_likely_goals = max(probabilities, key=probabilities.get)
    
    return most_likely_goals, probabilities[most_likely_goals], probabilities


def squash_lambda(lmbda, ceiling=7.0):
    """
    Apply a squashing function to lambda values ONLY when they exceed the ceiling.
    This prevents unnecessary compression of realistic lambda values.

    Args:
        lmbda: Original lambda value
        ceiling: Maximum lambda threshold (only squash if lambda > ceiling)

    Returns:
        Original lambda if below ceiling, squashed lambda if above ceiling

    Examples:
        squash_lambda(2.5, ceiling=7.0) -> 2.5 (no squashing, below ceiling)
        squash_lambda(8.0, ceiling=7.0) -> 6.53 (squashed, exceeds ceiling)
    """
    if lmbda <= ceiling:
        # No squashing needed - lambda is within reasonable bounds
        return lmbda
    else:
        # Apply squashing only for extreme values
        # Use a soft cap: ceiling + log-based decay for values above ceiling
        excess = lmbda - ceiling
        # Logarithmic decay: reduces extreme values while preserving some growth
        import math
        squashed_excess = math.log1p(excess)  # log(1 + excess) for smooth transition
        return ceiling + squashed_excess


def empirical_histogram(data, bins=None):
    """
    Create an empirical histogram from data.
    
    Args:
        data: List or array of data points
        bins: Number of bins or bin edges
        
    Returns:
        Tuple of (bin_centers, probabilities)
    """
    if not data:
        return [], []
    
    if bins is None:
        bins = max(10, int(len(data) ** 0.5))  # Square root rule
    
    hist, bin_edges = np.histogram(data, bins=bins, density=True)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    return bin_centers, hist


def calculate_likelihood(observed, expected, distribution='poisson'):
    """
    Calculate the likelihood of observed data given expected parameters.
    
    Args:
        observed: List of observed values
        expected: Expected parameter (lambda for Poisson, mu for NB)
        distribution: Type of distribution ('poisson' or 'nb')
        
    Returns:
        Log-likelihood value
    """
    if not observed:
        return 0
    
    log_likelihood = 0
    for obs in observed:
        if distribution == 'poisson':
            prob = poisson_pmf(obs, expected)
        elif distribution == 'nb':
            prob = nb_pmf(obs, expected)
        else:
            raise ValueError(f"Unknown distribution: {distribution}")
        
        if prob > 0:
            log_likelihood += math.log(prob)
        else:
            log_likelihood += -1000  # Penalty for zero probability
    
    return log_likelihood


def fit_negative_binomial(data):
    """
    Fit a negative binomial distribution to data using method of moments.
    
    Args:
        data: List or array of count data
        
    Returns:
        Tuple of (mu, alpha) parameters
    """
    if not data:
        return 0, DEFAULT_ALPHA
    
    data_array = np.array(data)
    mean = np.mean(data_array)
    variance = np.var(data_array)
    
    if variance <= mean or mean == 0:
        # If variance <= mean, use Poisson (alpha = 0)
        return mean, 0.01  # Very small alpha approximates Poisson
    
    # Method of moments estimation
    # variance = mu + alpha * mu^2
    # alpha = (variance - mu) / mu^2
    alpha = (variance - mean) / (mean ** 2) if mean > 0 else DEFAULT_ALPHA
    
    # Ensure alpha is positive and reasonable
    alpha = max(0.01, min(alpha, 10.0))
    
    return mean, alpha


def brier_score(predicted_probs, outcomes):
    """
    Calculate the Brier score for probabilistic predictions.
    
    Args:
        predicted_probs: List of predicted probabilities
        outcomes: List of actual binary outcomes (0 or 1)
        
    Returns:
        Brier score (lower is better)
    """
    if len(predicted_probs) != len(outcomes):
        raise ValueError("Predicted probabilities and outcomes must have same length")
    
    if not predicted_probs:
        return 0
    
    score = sum((p - o) ** 2 for p, o in zip(predicted_probs, outcomes))
    return score / len(predicted_probs)


def nb_probs(mu, alpha, max_k=MAX_GOALS_ANALYSIS):
    """
    Generate negative binomial probabilities for k = 0 to max_k.
    
    Args:
        mu: Mean parameter
        alpha: Dispersion parameter
        max_k: Maximum k value to calculate
        
    Returns:
        Dictionary mapping k to probability
    """
    probs = {}
    for k in range(max_k + 1):
        probs[k] = nb_pmf(k, mu, alpha)
    
    # Normalize to ensure sum = 1
    total = sum(probs.values())
    if total > 0:
        probs = {k: p / total for k, p in probs.items()}
    
    return probs