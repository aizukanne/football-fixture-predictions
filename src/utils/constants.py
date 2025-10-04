"""
Shared constants for the football fixture predictions system.
"""

# API Configuration
API_FOOTBALL_BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
API_FOOTBALL_HOST = "api-football-v1.p.rapidapi.com"

# API Keys (should be set via environment variables)
import os
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4')

# Retry Configuration
DEFAULT_MAX_RETRIES = 5
MIN_WAIT_TIME = 5
MAX_WAIT_TIME = 30

# Statistical Constants
DEFAULT_ALPHA = 0.3  # Dispersion parameter for Negative Binomial
DEFAULT_SMOOTHING_ALPHA = 0.15  # Exponential smoothing factor
DEFAULT_PRIOR_WEIGHT = 5  # Bayesian smoothing prior weight

# Points System
HOME_WIN_POINTS = 3
AWAY_WIN_POINTS = 4
HOME_DRAW_POINTS = 1
AWAY_DRAW_POINTS = 2
HOME_LOSS_POINTS = -1
AWAY_LOSS_POINTS = 0

# Goal Analysis
MAX_GOALS_ANALYSIS = 10  # Maximum goals to analyze in probability calculations

# Environment Configuration for Table Isolation
TABLE_PREFIX = os.getenv('TABLE_PREFIX', '')
TABLE_SUFFIX = os.getenv('TABLE_SUFFIX', '')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')

def _get_table_name(base_name: str) -> str:
    """
    Generate environment-specific table name with optional prefix and suffix.

    Args:
        base_name: Base table name (e.g., 'game_fixtures')

    Returns:
        Fully qualified table name with prefix and suffix if configured

    Examples:
        - Base: 'game_fixtures', Prefix: 'myapp_', Suffix: '_prod' -> 'myapp_game_fixtures_prod'
        - Base: 'game_fixtures', No prefix/suffix -> 'game_fixtures'
    """
    parts = []
    if TABLE_PREFIX:
        parts.append(TABLE_PREFIX.rstrip('_'))
    parts.append(base_name)
    if TABLE_SUFFIX:
        parts.append(TABLE_SUFFIX.lstrip('_'))
    return '_'.join(parts)

def get_table_config() -> dict:
    """
    Get current table configuration for debugging and deployment.

    Returns:
        Dictionary containing table names and environment configuration
    """
    return {
        'environment': ENVIRONMENT,
        'prefix': TABLE_PREFIX,
        'suffix': TABLE_SUFFIX,
        'tables': {
            'game_fixtures': _get_table_name('game_fixtures'),
            'league_parameters': _get_table_name('league_parameters'),
            'team_parameters': _get_table_name('team_parameters'),
            'venue_cache': _get_table_name('venue_cache'),
            'tactical_cache': _get_table_name('tactical_cache'),
            'league_standings_cache': _get_table_name('league_standings_cache')
        }
    }

# DynamoDB Table Names
GAME_FIXTURES_TABLE = _get_table_name('game_fixtures')
LEAGUE_PARAMETERS_TABLE = _get_table_name('league_parameters')
TEAM_PARAMETERS_TABLE = _get_table_name('team_parameters')

# SQS Queue URLs
FIXTURES_QUEUE_URL = 'https://sqs.eu-west-2.amazonaws.com/985019772236/fixturesQueue'

# Default Values
DEFAULT_LAMBDA_CEILING = 4.0
MINIMUM_GAMES_THRESHOLD = 10
MINIMUM_LEAGUE_GAMES = 50
MAX_SEASON_LOOKBACK = 3