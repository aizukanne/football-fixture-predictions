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

# DynamoDB Table Names
GAME_FIXTURES_TABLE = 'game_fixtures'
LEAGUE_PARAMETERS_TABLE = 'league_parameters'
TEAM_PARAMETERS_TABLE = 'team_parameters'

# SQS Queue URLs
FIXTURES_QUEUE_URL = 'https://sqs.eu-west-2.amazonaws.com/985019772236/fixturesQueue'

# Default Values
DEFAULT_LAMBDA_CEILING = 4.0
MINIMUM_GAMES_THRESHOLD = 10
MINIMUM_LEAGUE_GAMES = 50
MAX_SEASON_LOOKBACK = 3