"""
Integration tests for fixture ingestion system.

Tests the complete flow from fixture retrieval to SQS queue population
using mocked AWS services.

Author: Football Fixture Prediction System
Phase: Fixture Ingestion Implementation - Integration Testing
Version: 1.0
"""

import pytest
import boto3
import json
from moto import mock_sqs
from unittest.mock import patch, Mock
from datetime import datetime


@mock_sqs
class TestSQSIntegration:
    """Test suite for SQS integration."""

    def test_send_fixtures_to_queue(self):
        """Test sending fixtures to SQS queue."""
        from src.handlers.fixture_ingestion_handler import send_fixtures_to_queue

        # Create mock SQS queue
        sqs = boto3.client('sqs', region_name='us-east-1')
        queue_url = sqs.create_queue(QueueName='test-fixtures-queue')['QueueUrl']

        # Test data
        fixtures = [
            {
                'fixture_id': 123,
                'home_team': 'Team A',
                'away_team': 'Team B',
                'league_id': 39
            }
        ]
        league_info = {
            'id': 39,
            'name': 'Premier League',
            'country': 'England'
        }

        # Send message
        result = send_fixtures_to_queue(sqs, fixtures, league_info)

        assert result['success'] == True
        assert 'message_id' in result

        # Verify message was sent
        messages = sqs.receive_message(QueueUrl=queue_url)
        assert 'Messages' in messages

        message_body = json.loads(messages['Messages'][0]['Body'])
        assert len(message_body['payload']) == 1
        assert message_body['league_info']['name'] == 'Premier League'
        assert message_body['source'] == 'fixture_ingestion_handler'

    @mock_sqs
    def test_send_fixtures_to_queue_with_attributes(self):
        """Test that message attributes are correctly set."""
        from src.handlers.fixture_ingestion_handler import send_fixtures_to_queue

        # Create mock SQS queue
        sqs = boto3.client('sqs', region_name='us-east-1')
        queue_url = sqs.create_queue(QueueName='test-fixtures-queue')['QueueUrl']

        fixtures = [{'fixture_id': 1}, {'fixture_id': 2}]
        league_info = {'id': 39, 'name': 'Premier League', 'country': 'England'}

        result = send_fixtures_to_queue(sqs, fixtures, league_info)

        assert result['success'] == True

        # Retrieve message with attributes
        messages = sqs.receive_message(
            QueueUrl=queue_url,
            MessageAttributeNames=['All']
        )

        attributes = messages['Messages'][0]['MessageAttributes']
        assert attributes['league_id']['StringValue'] == '39'
        assert attributes['league_name']['StringValue'] == 'Premier League'
        assert attributes['country']['StringValue'] == 'England'
        assert attributes['fixture_count']['StringValue'] == '2'
        assert attributes['source']['StringValue'] == 'fixture_ingestion'


class TestEndToEndFlow:
    """Test complete end-to-end fixture ingestion flow."""

    @patch('src.data.fixture_retrieval.requests.get')
    @patch.dict('os.environ', {
        'RAPIDAPI_KEY': 'test_key_12345',
        'FIXTURES_QUEUE_URL': 'https://sqs.us-east-1.amazonaws.com/123456789/test-queue'
    })
    @mock_sqs
    def test_complete_ingestion_flow(self, mock_get):
        """Test the complete flow from API retrieval to queue population."""
        from src.data.fixture_retrieval import FixtureRetriever
        from src.utils.fixture_formatter import FixtureFormatter

        # Setup mock SQS
        sqs = boto3.client('sqs', region_name='us-east-1')
        queue_url = sqs.create_queue(QueueName='test-queue')['QueueUrl']

        # Mock API responses
        season_response = Mock()
        season_response.status_code = 200
        season_response.json.return_value = {
            'response': [{
                'seasons': [{'current': True, 'start': '2024-08-01'}]
            }]
        }

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
                        'home': {'id': 1, 'name': 'Manchester United'},
                        'away': {'id': 2, 'name': 'Liverpool'}
                    },
                    'league': {
                        'id': 39,
                        'name': 'Premier League',
                        'season': 2024,
                        'round': 'Round 20'
                    }
                },
                {
                    'fixture': {
                        'id': 124,
                        'date': '2024-01-01T17:30:00+00:00',
                        'timestamp': 1704126600,
                        'venue': {'id': 2, 'name': 'Stadium B'}
                    },
                    'teams': {
                        'home': {'id': 3, 'name': 'Chelsea'},
                        'away': {'id': 4, 'name': 'Arsenal'}
                    },
                    'league': {
                        'id': 39,
                        'name': 'Premier League',
                        'season': 2024,
                        'round': 'Round 20'
                    }
                }
            ]
        }

        mock_get.side_effect = [season_response, fixtures_response]

        # Execute the flow
        # Step 1: Retrieve fixtures
        retriever = FixtureRetriever()
        raw_fixtures = retriever.get_league_fixtures(39, '2024-01-01', '2024-01-02')

        assert len(raw_fixtures) == 2

        # Step 2: Format fixtures
        formatter = FixtureFormatter()
        league_info = {'id': 39, 'name': 'Premier League', 'country': 'England'}
        formatted_fixtures = formatter.format_fixtures_for_queue(raw_fixtures, league_info)

        assert len(formatted_fixtures) == 2

        # Step 3: Send to queue
        from src.handlers.fixture_ingestion_handler import send_fixtures_to_queue
        result = send_fixtures_to_queue(sqs, formatted_fixtures, league_info)

        assert result['success'] == True

        # Step 4: Verify queue contents
        messages = sqs.receive_message(QueueUrl=queue_url)
        assert 'Messages' in messages

        message_body = json.loads(messages['Messages'][0]['Body'])
        assert len(message_body['payload']) == 2
        assert message_body['payload'][0]['home_team'] == 'Manchester United'
        assert message_body['payload'][1]['home_team'] == 'Chelsea'


class TestErrorHandling:
    """Test error handling and edge cases."""

    @patch.dict('os.environ', {'RAPIDAPI_KEY': 'test_key_12345'})
    def test_retrieval_with_malformed_api_response(self):
        """Test handling of malformed API response."""
        from src.data.fixture_retrieval import FixtureRetriever

        with patch('src.data.fixture_retrieval.requests.get') as mock_get:
            # Mock malformed response
            response = Mock()
            response.status_code = 200
            response.json.return_value = {
                # Missing 'response' key
                'data': []
            }
            mock_get.return_value = response

            retriever = FixtureRetriever()
            season = retriever._get_league_season(39)

            assert season is None  # Should handle gracefully

    def test_formatter_with_incomplete_fixture_data(self):
        """Test formatter with incomplete fixture data."""
        from src.utils.fixture_formatter import FixtureFormatter

        formatter = FixtureFormatter()

        # Incomplete fixture data
        incomplete_fixtures = [
            {
                'fixture_id': 123,
                'date': '2024-01-01T15:00:00+00:00',
                # Missing many required fields
            },
            {
                'fixture_id': 124,
                'date': '2024-01-01T17:30:00+00:00',
                'timestamp': 1704126600,
                'home_team': 'Team A',
                'home_id': 1,
                'away_team': 'Team B',
                'away_id': 2,
                'league_id': 39,
                'season': 2024  # This one is complete
            }
        ]

        league_info = {'id': 39, 'name': 'Test League', 'country': 'Test'}
        formatted = formatter.format_fixtures_for_queue(incomplete_fixtures, league_info)

        # Should only include the valid fixture
        assert len(formatted) == 1
        assert formatted[0]['fixture_id'] == 124

    @mock_sqs
    def test_sqs_send_failure(self):
        """Test handling of SQS send failure."""
        from src.handlers.fixture_ingestion_handler import send_fixtures_to_queue

        # Create SQS client
        sqs = boto3.client('sqs', region_name='us-east-1')

        fixtures = [{'fixture_id': 123}]
        league_info = {'id': 39, 'name': 'Test League'}

        # Try to send to non-existent queue (will fail)
        with patch.object(sqs, 'send_message', side_effect=Exception("Queue error")):
            result = send_fixtures_to_queue(sqs, fixtures, league_info)

            assert result['success'] == False
            assert 'error' in result


class TestDateRangeCalculation:
    """Test date range calculation logic."""

    def test_monday_date_range(self):
        """Test that Monday uses 2-day range."""
        from src.handlers.fixture_ingestion_handler import lambda_handler

        # This would need to be tested with specific date mocking
        # The logic is in the handler itself
        pass  # Placeholder for date-specific testing

    def test_thursday_date_range(self):
        """Test that Thursday uses 3-day range."""
        from src.handlers.fixture_ingestion_handler import lambda_handler

        # This would need to be tested with specific date mocking
        pass  # Placeholder for date-specific testing


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
