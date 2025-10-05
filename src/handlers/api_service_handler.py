"""
API Service Handler - REST API for serving prediction data to frontend applications.
Based on code-samples/analysis_backend_mobile.py but architected for modular system.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from ..services.query_service import QueryService
from ..services.data_formatter import DataFormatter
from ..services.validation_service import ValidationService
from ..config.api_config import APIConfig
from ..utils.api_utils import APIResponse, APIError
from ..utils.converters import decimal_default


class APIServiceHandler:
    """Main handler for prediction API requests."""

    def __init__(self):
        self.query_service = QueryService()
        self.data_formatter = DataFormatter()
        self.validation_service = ValidationService()
        self.config = APIConfig()

    def handle_request(self, event: Dict, context: Any) -> Dict:
        """
        Main request handler for API Gateway events.

        Args:
            event: API Gateway event data
            context: Lambda context

        Returns:
            Dict: API Gateway response with statusCode, headers, and body
        """
        print(f"API Request: {json.dumps(event, default=str)}")

        try:
            # Authenticate request
            if not self._authenticate_request(event):
                return APIResponse.unauthorized("Authentication failed")

            print("API request authenticated successfully")

            # Extract and validate parameters
            query_params = event.get('queryStringParameters') or {}

            validation_result = self.validation_service.validate_query_params(query_params)
            if not validation_result.is_valid:
                return APIResponse.bad_request(validation_result.error_message)

            # Determine query type and execute
            if 'fixture_id' in query_params:
                return self._handle_fixture_query(query_params)
            else:
                return self._handle_league_query(query_params)

        except Exception as e:
            print(f"API Error: {str(e)}")
            return APIResponse.server_error(f"Server error: {str(e)}")

    def _authenticate_request(self, event: Dict) -> bool:
        """
        Authenticate API request using API key.

        Args:
            event: API Gateway event

        Returns:
            bool: True if authenticated, False otherwise
        """
        try:
            # Get API key from headers
            headers = event.get('headers', {})

            # API Gateway normalizes headers to lowercase
            api_key = (
                headers.get('x-api-key') or
                headers.get('X-API-Key') or
                headers.get('X-Api-Key') or
                ''
            )

            # Also check request context for API Gateway managed keys
            if not api_key:
                request_context = event.get('requestContext', {})
                identity = request_context.get('identity', {})
                api_key = identity.get('apiKey', '')

            # Validate against configured API key
            return self.config.validate_api_key(api_key)

        except Exception as e:
            print(f"Authentication error: {e}")
            return False

    def _handle_fixture_query(self, query_params: Dict) -> Dict:
        """
        Handle single fixture query.

        Args:
            query_params: Query parameters from request

        Returns:
            Dict: API response
        """
        try:
            fixture_id = int(query_params['fixture_id'])

            # Query single fixture
            fixture_data = self.query_service.get_fixture_by_id(fixture_id)

            if not fixture_data:
                return APIResponse.not_found(f"Fixture {fixture_id} not found")

            # Format response with full details for single fixture query
            formatted_data = self.data_formatter.format_fixture_response(fixture_data, full_details=True)

            response_body = {
                'items': formatted_data,
                'last_evaluated_key': None,
                'query_type': 'single_fixture',
                'total_items': len(formatted_data)
            }

            return APIResponse.success(response_body)

        except ValueError:
            return APIResponse.bad_request("Invalid fixture_id format")
        except Exception as e:
            print(f"Fixture query error: {e}")
            return APIResponse.server_error("Error retrieving fixture data")

    def _handle_league_query(self, query_params: Dict) -> Dict:
        """
        Handle league-based fixture query with date filtering.

        Args:
            query_params: Query parameters from request

        Returns:
            Dict: API response
        """
        try:
            # Extract required parameters
            country = query_params.get('country')
            league = query_params.get('league')

            if not country or not league:
                return APIResponse.bad_request(
                    "Both 'country' and 'league' parameters are required"
                )

            # Parse date parameters or use defaults
            date_range = self._parse_date_range(query_params)

            print(f"Querying league: {country} - {league} from {date_range['start']} to {date_range['end']}")

            # Execute query
            fixtures_data = self.query_service.get_league_fixtures(
                country=country,
                league=league,
                start_time=date_range['start_timestamp'],
                end_time=date_range['end_timestamp'],
                limit=query_params.get('limit'),
                last_key=query_params.get('last_key')
            )

            # Format response
            formatted_data = self.data_formatter.format_league_response(fixtures_data)

            response_body = {
                'items': formatted_data['items'],
                'last_evaluated_key': formatted_data['last_evaluated_key'],
                'query_type': 'league_fixtures',
                'total_items': len(formatted_data['items']),
                'date_range': {
                    'start': date_range['start'],
                    'end': date_range['end']
                },
                'filters': {
                    'country': country,
                    'league': league
                }
            }

            return APIResponse.success(response_body)

        except Exception as e:
            print(f"League query error: {e}")
            return APIResponse.server_error("Error retrieving league fixtures")

    def _parse_date_range(self, query_params: Dict) -> Dict:
        """
        Parse date range parameters or provide defaults.

        Args:
            query_params: Query parameters

        Returns:
            Dict: Date range with timestamps
        """
        start_date_str = query_params.get('startDate')
        end_date_str = query_params.get('endDate')

        if start_date_str and end_date_str:
            try:
                start_time = int(datetime.strptime(start_date_str, '%Y-%m-%d').timestamp())
                end_time = int(datetime.strptime(end_date_str, '%Y-%m-%d').timestamp())
                return {
                    'start': start_date_str,
                    'end': end_date_str,
                    'start_timestamp': start_time,
                    'end_timestamp': end_time
                }
            except ValueError as e:
                raise ValueError(f"Invalid date format: {e}")
        else:
            # Default range: current day to N days in future (from config)
            current_time = datetime.utcnow()
            start_time = int(current_time.timestamp())
            days_ahead = self.config.default_date_range_days
            end_time = int((current_time + timedelta(days=days_ahead)).timestamp())

            return {
                'start': current_time.strftime('%Y-%m-%d'),
                'end': (current_time + timedelta(days=days_ahead)).strftime('%Y-%m-%d'),
                'start_timestamp': start_time,
                'end_timestamp': end_time
            }


def lambda_handler(event, context):
    """
    Lambda handler entry point for API Gateway.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        Dict: API Gateway response
    """
    handler = APIServiceHandler()
    return handler.handle_request(event, context)
