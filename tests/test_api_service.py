"""
Comprehensive tests for API Service Handler and related modules.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.handlers.api_service_handler import APIServiceHandler, lambda_handler
from src.services.query_service import QueryService
from src.services.data_formatter import DataFormatter
from src.services.validation_service import ValidationService, ValidationResult
from src.config.api_config import APIConfig
from src.utils.api_utils import APIResponse, APIError


class TestValidationService:
    """Test cases for Validation Service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = ValidationService()

    def test_validate_fixture_id_valid(self):
        """Test valid fixture ID validation."""
        result = self.validator.validate_query_params({'fixture_id': '123456'})
        assert result.is_valid is True
        assert result.error_message == ""

    def test_validate_fixture_id_invalid_format(self):
        """Test invalid fixture ID format."""
        result = self.validator.validate_query_params({'fixture_id': 'invalid'})
        assert result.is_valid is False
        assert 'valid integer' in result.error_message

    def test_validate_fixture_id_negative(self):
        """Test negative fixture ID."""
        result = self.validator.validate_query_params({'fixture_id': '-123'})
        assert result.is_valid is False
        assert 'positive integer' in result.error_message

    def test_validate_league_params_valid(self):
        """Test valid league parameters."""
        params = {
            'country': 'England',
            'league': 'Premier League'
        }
        result = self.validator.validate_query_params(params)
        assert result.is_valid is True

    def test_validate_league_params_missing_league(self):
        """Test missing league parameter."""
        params = {'country': 'England'}
        result = self.validator.validate_query_params(params)
        assert result.is_valid is False
        assert 'league' in result.error_message.lower()

    def test_validate_league_params_missing_country(self):
        """Test missing country parameter."""
        params = {'league': 'Premier League'}
        result = self.validator.validate_query_params(params)
        assert result.is_valid is False
        assert 'country' in result.error_message.lower()

    def test_validate_date_format_valid(self):
        """Test valid date format."""
        params = {
            'country': 'England',
            'league': 'Premier League',
            'startDate': '2024-01-01',
            'endDate': '2024-01-07'
        }
        result = self.validator.validate_query_params(params)
        assert result.is_valid is True

    def test_validate_date_format_invalid(self):
        """Test invalid date format."""
        params = {
            'country': 'England',
            'league': 'Premier League',
            'startDate': '01-01-2024'  # Wrong format
        }
        result = self.validator.validate_query_params(params)
        assert result.is_valid is False
        assert 'YYYY-MM-DD' in result.error_message

    def test_validate_date_range_invalid(self):
        """Test invalid date range (start after end)."""
        params = {
            'country': 'England',
            'league': 'Premier League',
            'startDate': '2024-01-07',
            'endDate': '2024-01-01'
        }
        result = self.validator.validate_query_params(params)
        assert result.is_valid is False
        assert 'before' in result.error_message.lower()

    def test_validate_limit_valid(self):
        """Test valid limit parameter."""
        params = {
            'country': 'England',
            'league': 'Premier League',
            'limit': '100'
        }
        result = self.validator.validate_query_params(params)
        assert result.is_valid is True

    def test_validate_limit_invalid(self):
        """Test invalid limit parameter."""
        params = {
            'country': 'England',
            'league': 'Premier League',
            'limit': '5000'  # Too large
        }
        result = self.validator.validate_query_params(params)
        assert result.is_valid is False
        assert 'limit' in result.error_message.lower()


class TestDataFormatter:
    """Test cases for Data Formatter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = DataFormatter()

    def test_format_single_fixture_basic(self):
        """Test basic fixture formatting."""
        fixture = {
            'fixture_id': 123456,
            'timestamp': Decimal('1704117600'),
            'date': '2024-01-01T15:00:00+00:00',
            'home': {
                'team_id': 1,
                'team_name': 'Team A',
                'team_logo': 'logo_a.png',
                'predicted_goals': Decimal('1.5')
            },
            'away': {
                'team_id': 2,
                'team_name': 'Team B',
                'team_logo': 'logo_b.png',
                'predicted_goals': Decimal('0.9')
            }
        }

        result = self.formatter._format_single_fixture(fixture)

        assert result['fixture_id'] == 123456
        assert result['timestamp'] == 1704117600
        assert result['has_best_bet'] is False
        assert result['home']['team_id'] == 1
        assert result['home']['predicted_goals'] == 1.5
        assert result['away']['team_id'] == 2

    def test_format_single_fixture_with_best_bet(self):
        """Test fixture formatting with best bet."""
        fixture = {
            'fixture_id': 123456,
            'timestamp': Decimal('1704117600'),
            'date': '2024-01-01T15:00:00+00:00',
            'home': {'team_id': 1, 'team_name': 'Team A'},
            'away': {'team_id': 2, 'team_name': 'Team B'},
            'best_bet': ['Over 2.5']
        }

        result = self.formatter._format_single_fixture(fixture)

        assert result['has_best_bet'] is True
        assert result['best_bet'] == ['Over 2.5']

    def test_format_league_response(self):
        """Test league response formatting."""
        query_result = {
            'items': [
                {
                    'fixture_id': 1,
                    'timestamp': Decimal('1704117600'),
                    'date': '2024-01-01',
                    'home': {'team_id': 1, 'team_name': 'Team A'},
                    'away': {'team_id': 2, 'team_name': 'Team B'}
                },
                {
                    'fixture_id': 2,
                    'timestamp': Decimal('1704204000'),
                    'date': '2024-01-02',
                    'home': {'team_id': 3, 'team_name': 'Team C'},
                    'away': {'team_id': 4, 'team_name': 'Team D'}
                }
            ],
            'last_evaluated_key': None
        }

        result = self.formatter.format_league_response(query_result)

        assert len(result['items']) == 2
        assert result['items'][0]['fixture_id'] == 1
        assert result['items'][1]['fixture_id'] == 2
        assert result['last_evaluated_key'] is None

    def test_safe_decimal_convert(self):
        """Test decimal conversion."""
        assert self.formatter._safe_decimal_convert(Decimal('1.5')) == 1.5
        assert self.formatter._safe_decimal_convert(Decimal('2')) == 2
        assert self.formatter._safe_decimal_convert(None) is None
        assert self.formatter._safe_decimal_convert('test') == 'test'


class TestAPIServiceHandler:
    """Test cases for API Service Handler."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = APIServiceHandler()

    @patch.dict('os.environ', {'MOBILE_APP_KEY': 'test-key-12345'})
    def test_authentication_success(self):
        """Test successful API key authentication."""
        event = {
            'headers': {
                'x-api-key': 'test-key-12345'
            },
            'queryStringParameters': {'fixture_id': '123456'}
        }

        assert self.handler._authenticate_request(event) is True

    @patch.dict('os.environ', {'MOBILE_APP_KEY': 'test-key-12345'})
    def test_authentication_failure(self):
        """Test failed API key authentication."""
        event = {
            'headers': {
                'x-api-key': 'invalid-key'
            },
            'queryStringParameters': {'fixture_id': '123456'}
        }

        assert self.handler._authenticate_request(event) is False

    @patch.dict('os.environ', {'MOBILE_APP_KEY': 'test-key-12345'})
    @patch('src.handlers.api_service_handler.QueryService.get_fixture_by_id')
    def test_fixture_query_success(self, mock_query):
        """Test successful single fixture query."""
        # Mock query result
        mock_fixture_data = [{
            'fixture_id': 123456,
            'timestamp': Decimal('1704117600'),
            'date': '2024-01-01T15:00:00+00:00',
            'home': {
                'team_id': 1,
                'team_name': 'Team A',
                'predicted_goals': Decimal('1.5')
            },
            'away': {
                'team_id': 2,
                'team_name': 'Team B',
                'predicted_goals': Decimal('0.9')
            }
        }]
        mock_query.return_value = mock_fixture_data

        event = {
            'headers': {'x-api-key': 'test-key-12345'},
            'queryStringParameters': {'fixture_id': '123456'}
        }
        context = Mock()

        response = self.handler.handle_request(event, context)

        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert len(body['items']) == 1
        assert body['items'][0]['fixture_id'] == 123456

    @patch.dict('os.environ', {'MOBILE_APP_KEY': 'test-key-12345'})
    @patch('src.handlers.api_service_handler.QueryService.get_fixture_by_id')
    def test_fixture_query_not_found(self, mock_query):
        """Test fixture not found."""
        mock_query.return_value = []

        event = {
            'headers': {'x-api-key': 'test-key-12345'},
            'queryStringParameters': {'fixture_id': '999999'}
        }
        context = Mock()

        response = self.handler.handle_request(event, context)

        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'error' in body

    @patch.dict('os.environ', {'MOBILE_APP_KEY': 'test-key-12345'})
    def test_validation_failure(self):
        """Test request validation failure."""
        event = {
            'headers': {'x-api-key': 'test-key-12345'},
            'queryStringParameters': {'country': 'England'}  # Missing league
        }
        context = Mock()

        response = self.handler.handle_request(event, context)

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'error' in body

    def test_authentication_required(self):
        """Test unauthenticated request."""
        event = {
            'headers': {},
            'queryStringParameters': {'fixture_id': '123456'}
        }
        context = Mock()

        response = self.handler.handle_request(event, context)

        assert response['statusCode'] == 401

    @patch.dict('os.environ', {'MOBILE_APP_KEY': 'test-key-12345'})
    def test_parse_date_range_provided(self):
        """Test parsing provided date range."""
        query_params = {
            'startDate': '2024-01-01',
            'endDate': '2024-01-07'
        }

        result = self.handler._parse_date_range(query_params)

        assert result['start'] == '2024-01-01'
        assert result['end'] == '2024-01-07'
        assert 'start_timestamp' in result
        assert 'end_timestamp' in result

    @patch.dict('os.environ', {'MOBILE_APP_KEY': 'test-key-12345'})
    def test_parse_date_range_default(self):
        """Test parsing default date range."""
        result = self.handler._parse_date_range({})

        assert 'start' in result
        assert 'end' in result
        assert 'start_timestamp' in result
        assert 'end_timestamp' in result


class TestAPIResponse:
    """Test cases for API Response utility."""

    def test_success_response(self):
        """Test success response builder."""
        data = {'message': 'Success'}
        response = APIResponse.success(data)

        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        body = json.loads(response['body'])
        assert body == data

    def test_bad_request_response(self):
        """Test bad request response."""
        message = 'Invalid parameter'
        response = APIResponse.bad_request(message)

        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] == message

    def test_unauthorized_response(self):
        """Test unauthorized response."""
        message = 'Authentication failed'
        response = APIResponse.unauthorized(message)

        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert body['error'] == message

    def test_not_found_response(self):
        """Test not found response."""
        message = 'Resource not found'
        response = APIResponse.not_found(message)

        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error'] == message

    def test_server_error_response(self):
        """Test server error response."""
        message = 'Internal server error'
        response = APIResponse.server_error(message)

        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['error'] == message

    def test_cors_headers_included(self):
        """Test CORS headers are included in all responses."""
        response = APIResponse.success({'test': 'data'})

        headers = response['headers']
        assert headers['Access-Control-Allow-Origin'] == '*'
        assert 'Access-Control-Allow-Headers' in headers
        assert 'Access-Control-Allow-Methods' in headers


class TestAPIConfig:
    """Test cases for API Configuration."""

    @patch.dict('os.environ', {'MOBILE_APP_KEY': 'test-key', 'MAX_PAGE_SIZE': '500'})
    def test_config_initialization(self):
        """Test configuration initialization from env vars."""
        config = APIConfig()

        assert config.mobile_app_key == 'test-key'
        assert config.max_page_size == 500
        assert config.cors_enabled is True

    @patch.dict('os.environ', {'MOBILE_APP_KEY': 'test-key'})
    def test_validate_api_key(self):
        """Test API key validation."""
        config = APIConfig()

        assert config.validate_api_key('test-key') is True
        assert config.validate_api_key('wrong-key') is False

    def test_get_cors_headers(self):
        """Test CORS headers generation."""
        config = APIConfig()
        headers = config.get_cors_headers()

        assert 'Access-Control-Allow-Origin' in headers
        assert headers['Access-Control-Allow-Origin'] == '*'


class TestLambdaHandler:
    """Integration tests for Lambda handler."""

    @patch('boto3.resource')
    @patch.dict('os.environ', {
        'MOBILE_APP_KEY': 'test-key',
        'GAME_FIXTURES_TABLE': 'test-table'
    })
    def test_lambda_handler_integration(self, mock_dynamodb):
        """Test complete Lambda handler integration."""
        # Mock DynamoDB response
        mock_table = Mock()
        mock_dynamodb.return_value.Table.return_value = mock_table
        mock_table.query.return_value = {
            'Items': [{
                'fixture_id': 123456,
                'timestamp': Decimal('1704117600'),
                'date': '2024-01-01T15:00:00+00:00',
                'home': {'team_id': 1, 'team_name': 'Team A'},
                'away': {'team_id': 2, 'team_name': 'Team B'}
            }]
        }

        event = {
            'headers': {'x-api-key': 'test-key'},
            'queryStringParameters': {'fixture_id': '123456'}
        }
        context = Mock()

        response = lambda_handler(event, context)

        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        body = json.loads(response['body'])
        assert 'items' in body
        assert len(body['items']) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
