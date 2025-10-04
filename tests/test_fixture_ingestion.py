"""
Unit tests for fixture ingestion system.

Tests the fixture retrieval, formatting, and handler components
with mocked API responses and SQS interactions.

Author: Football Fixture Prediction System
Phase: Fixture Ingestion Implementation - Testing
Version: 1.0
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from decimal import Decimal


class TestFixtureRetrieval:
    """Test suite for FixtureRetriever class."""

    @patch('src.data.fixture_retrieval.requests.get')
    @patch.dict('os.environ', {'RAPIDAPI_KEY': 'test_key_12345'})
    def test_retrieve_fixtures_success(self, mock_get):
        """Test successful fixture retrieval from API."""
        from src.data.fixture_retrieval import FixtureRetriever

        # Mock API responses
        # First call: get league season
        season_response = Mock()
        season_response.status_code = 200
        season_response.json.return_value = {
            'response': [{
                'seasons': [
                    {'current': True, 'start': '2024-08-01'}
                ]
            }]
        }

        # Second call: get fixtures
        fixtures_response = Mock()
        fixtures_response.status_code = 200
        fixtures_response.json.return_value = {
            'response': [
                {
                    'fixture': {
                        'id': 123,
                        'date': '2024-01-01T15:00:00+00:00',
                        'timestamp': 1704117600,
                        'venue': {'id': 1, 'name': 'Stadium A'}
                    },
                    'teams': {
                        'home': {'id': 1, 'name': 'Team A'},
                        'away': {'id': 2, 'name': 'Team B'}
                    },
                    'league': {
                        'id': 39,
                        'name': 'Premier League',
                        'season': 2024,
                        'round': 'Regular Season - 1'
                    }
                }
            ]
        }

        # Set side_effect to return different responses for each call
        mock_get.side_effect = [season_response, fixtures_response]

        retriever = FixtureRetriever()
        fixtures = retriever.get_league_fixtures(39, '2024-01-01', '2024-01-02')

        assert len(fixtures) == 1
        assert fixtures[0]['fixture_id'] == 123
        assert fixtures[0]['home_team'] == 'Team A'
        assert fixtures[0]['away_team'] == 'Team B'
        assert fixtures[0]['league_id'] == 39
        assert fixtures[0]['season'] == 2024

    @patch('src.data.fixture_retrieval.requests.get')
    @patch.dict('os.environ', {'RAPIDAPI_KEY': 'test_key_12345'})
    def test_rate_limit_handling(self, mock_get):
        """Test rate limit retry logic."""
        from src.data.fixture_retrieval import FixtureRetriever

        # First response: rate limit
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429

        # Second response: success
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            'response': [{
                'seasons': [{'current': True, 'start': '2024-08-01'}]
            }]
        }

        mock_get.side_effect = [rate_limit_response, success_response]

        retriever = FixtureRetriever()
        season = retriever._get_league_season(39)

        assert season == '2024'
        assert mock_get.call_count == 2

    @patch.dict('os.environ', {}, clear=True)
    def test_missing_api_key(self):
        """Test that missing API key raises error."""
        from src.data.fixture_retrieval import FixtureRetriever

        with pytest.raises(ValueError, match="RAPIDAPI_KEY"):
            FixtureRetriever()


class TestFixtureFormatter:
    """Test suite for FixtureFormatter class."""

    def test_format_fixtures_for_queue(self):
        """Test fixture formatting for SQS queue."""
        from src.utils.fixture_formatter import FixtureFormatter

        formatter = FixtureFormatter()

        raw_fixtures = [
            {
                'fixture_id': 123,
                'date': '2024-01-01T15:00:00+00:00',
                'timestamp': 1704117600,
                'venue_id': 1,
                'venue_name': 'Stadium A',
                'home_team': 'Team A',
                'home_id': 1,
                'away_team': 'Team B',
                'away_id': 2,
                'league_id': 39,
                'league_name': 'Premier League',
                'season': 2024,
                'round': 'Regular Season - 1'
            }
        ]

        league_info = {
            'id': 39,
            'name': 'Premier League',
            'country': 'England'
        }

        formatted = formatter.format_fixtures_for_queue(raw_fixtures, league_info)

        assert len(formatted) == 1
        assert formatted[0]['fixture_id'] == 123
        assert formatted[0]['country'] == 'England'
        assert 'ingestion_timestamp' in formatted[0]
        assert formatted[0]['source'] == 'fixture_ingestion_handler'

    def test_validate_fixture_valid(self):
        """Test fixture validation with valid data."""
        from src.utils.fixture_formatter import FixtureFormatter

        formatter = FixtureFormatter()

        valid_fixture = {
            'fixture_id': 123,
            'date': '2024-01-01T15:00:00+00:00',
            'timestamp': 1704117600,
            'home_team': 'Team A',
            'home_id': 1,
            'away_team': 'Team B',
            'away_id': 2,
            'league_id': 39,
            'season': 2024
        }

        assert formatter._validate_fixture(valid_fixture) == True

    def test_validate_fixture_missing_field(self):
        """Test fixture validation with missing required field."""
        from src.utils.fixture_formatter import FixtureFormatter

        formatter = FixtureFormatter()

        invalid_fixture = {
            'fixture_id': 123,
            'date': '2024-01-01T15:00:00+00:00'
            # Missing required fields
        }

        assert formatter._validate_fixture(invalid_fixture) == False

    def test_validate_fixture_invalid_type(self):
        """Test fixture validation with invalid data type."""
        from src.utils.fixture_formatter import FixtureFormatter

        formatter = FixtureFormatter()

        invalid_fixture = {
            'fixture_id': 'not_a_number',  # Should be int
            'date': '2024-01-01T15:00:00+00:00',
            'timestamp': 1704117600,
            'home_team': 'Team A',
            'home_id': 1,
            'away_team': 'Team B',
            'away_id': 2,
            'league_id': 39,
            'season': 2024
        }

        assert formatter._validate_fixture(invalid_fixture) == False

    def test_format_date_for_display(self):
        """Test date formatting for display."""
        from src.utils.fixture_formatter import FixtureFormatter

        formatter = FixtureFormatter()

        iso_date = '2024-01-01T15:00:00+00:00'
        formatted = formatter.format_date_for_display(iso_date)

        assert '2024-01-01' in formatted
        assert 'UTC' in formatted

    def test_extract_match_summary(self):
        """Test match summary generation."""
        from src.utils.fixture_formatter import FixtureFormatter

        formatter = FixtureFormatter()

        fixture = {
            'fixture_id': 123,
            'date': '2024-01-01T15:00:00+00:00',
            'home_team': 'Manchester United',
            'away_team': 'Liverpool',
            'league_name': 'Premier League',
            'round': 'Regular Season - 20'
        }

        summary = formatter.extract_match_summary(fixture)

        assert 'Manchester United' in summary
        assert 'Liverpool' in summary
        assert 'Premier League' in summary


class TestLeaguesConfig:
    """Test suite for leagues configuration module."""

    def test_get_all_leagues(self):
        """Test retrieving all configured leagues."""
        from src.config.leagues_config import get_all_leagues

        leagues = get_all_leagues()

        assert isinstance(leagues, list)
        assert len(leagues) > 0
        # Each league should have id, name, type, and country
        assert all('id' in league for league in leagues)
        assert all('name' in league for league in leagues)
        assert all('country' in league for league in leagues)

    def test_get_leagues_by_country(self):
        """Test retrieving leagues for a specific country."""
        from src.config.leagues_config import get_leagues_by_country

        england_leagues = get_leagues_by_country('England')

        assert isinstance(england_leagues, list)
        assert len(england_leagues) > 0
        # Should include Premier League
        assert any(league['id'] == 39 for league in england_leagues)

    def test_get_league_info(self):
        """Test retrieving info for a specific league."""
        from src.config.leagues_config import get_league_info

        # Premier League
        league = get_league_info(39)

        assert league is not None
        assert league['id'] == 39
        assert league['name'] == 'Premier League'
        assert league['country'] == 'England'

    def test_get_league_info_not_found(self):
        """Test retrieving info for non-existent league."""
        from src.config.leagues_config import get_league_info

        league = get_league_info(999999)

        assert league is None

    def test_get_league_count(self):
        """Test getting total league count."""
        from src.config.leagues_config import get_league_count

        count = get_league_count()

        assert isinstance(count, int)
        assert count > 0

    def test_get_leagues_by_type(self):
        """Test filtering leagues by type."""
        from src.config.leagues_config import get_leagues_by_type

        league_competitions = get_leagues_by_type('League')
        cup_competitions = get_leagues_by_type('Cup')

        assert isinstance(league_competitions, list)
        assert isinstance(cup_competitions, list)
        assert len(league_competitions) > 0
        assert len(cup_competitions) >= 0  # May or may not have cups


class TestFixtureIngestionHandler:
    """Test suite for fixture ingestion Lambda handler."""

    @patch('src.handlers.fixture_ingestion_handler.boto3.client')
    @patch('src.handlers.fixture_ingestion_handler.FixtureRetriever')
    @patch('src.handlers.fixture_ingestion_handler.get_all_leagues')
    def test_lambda_handler_success(self, mock_get_leagues, mock_retriever_class, mock_boto3):
        """Test successful execution of Lambda handler."""
        from src.handlers.fixture_ingestion_handler import lambda_handler

        # Mock leagues
        mock_get_leagues.return_value = [
            {'id': 39, 'name': 'Premier League', 'country': 'England'}
        ]

        # Mock fixture retriever
        mock_retriever = Mock()
        mock_retriever.get_league_fixtures.return_value = [
            {
                'fixture_id': 123,
                'date': '2024-01-01T15:00:00+00:00',
                'timestamp': 1704117600,
                'venue_id': 1,
                'venue_name': 'Stadium A',
                'home_team': 'Team A',
                'home_id': 1,
                'away_team': 'Team B',
                'away_id': 2,
                'league_id': 39,
                'league_name': 'Premier League',
                'season': 2024,
                'round': 'Round 1'
            }
        ]
        mock_retriever_class.return_value = mock_retriever

        # Mock SQS client
        mock_sqs = Mock()
        mock_sqs.send_message.return_value = {'MessageId': 'test_message_id'}
        mock_boto3.return_value = mock_sqs

        # Execute handler
        event = {'trigger_type': 'daily_schedule'}
        context = {}

        result = lambda_handler(event, context)

        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['successful_leagues'] == 1
        assert body['total_fixtures'] == 1
        assert body['failed_leagues'] == 0

    @patch('src.handlers.fixture_ingestion_handler.get_all_leagues')
    def test_lambda_handler_config_error(self, mock_get_leagues):
        """Test handler with configuration error."""
        from src.handlers.fixture_ingestion_handler import lambda_handler

        # Mock configuration error
        mock_get_leagues.side_effect = Exception("Config load failed")

        event = {}
        context = {}

        result = lambda_handler(event, context)

        assert result['statusCode'] == 500
        assert 'error' in json.loads(result['body'])


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
