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
# Default queue URL - will be updated by infrastructure setup script
# Or set via environment variable for different environments
FIXTURES_QUEUE_URL = os.getenv(
    'FIXTURES_QUEUE_URL',
    'https://sqs.eu-west-2.amazonaws.com/{account_id}/football-fixture-predictions'
    # Note: Replace {account_id} with your AWS account ID or run:
    # python -m src.infrastructure.create_all_sqs_queues --update-constants
)

BEST_BETS_QUEUE_URL = os.getenv(
    'BEST_BETS_QUEUE_URL',
    f'https://sqs.eu-west-2.amazonaws.com/{{account_id}}/{_get_table_name("football-best-bets")}'
)

# Default Values
DEFAULT_LAMBDA_CEILING = 7.0  # Increased from 4.0 to allow for higher-scoring predictions
MINIMUM_GAMES_THRESHOLD = 6
MINIMUM_LEAGUE_GAMES = 50
MAX_SEASON_LOOKBACK = 3

# Fixture Ingestion Configuration
FIXTURE_INGESTION_SETTINGS = {
    'default_hours_ahead': 12,
    'default_days_range': {
        'monday': 2,
        'thursday': 3,
        'default': 2
    },
    'rate_limit_wait_seconds': 60,
    'max_retries': 3
}

# Queue Configuration
FIXTURES_QUEUE_CONFIG = {
    'batch_size': 1,  # Process one league at a time
    'visibility_timeout': 300,  # 5 minutes
    'message_retention_period': 1209600  # 14 days
}

# Required Environment Variables
REQUIRED_ENV_VARS = [
    'RAPIDAPI_KEY',
    'FIXTURES_QUEUE_URL'
]

# API Service Configuration
API_SERVICE_CONFIG = {
    'max_page_size': 1000,
    'default_page_size': 100,
    'default_date_range_days': 4,
    'cache_control_max_age': 300,  # 5 minutes
    'enable_cors': True
}

# API Gateway Configuration
API_GATEWAY_CONFIG = {
    'rate_limit': 10.0,  # requests per second
    'burst_limit': 20,  # burst capacity
    'quota_limit': 10000,  # requests per month
    'quota_period': 'MONTH'
}

# API Response Configuration
API_RESPONSE_CONFIG = {
    'include_metadata': True,
    'include_query_info': True,
    'decimal_places': 2
}