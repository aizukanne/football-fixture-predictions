"""
API Utilities - Helper classes and functions for API responses.
Standardizes API response format and error handling.
"""

import json
from typing import Dict, Any
from .converters import decimal_default


class APIResponse:
    """Standard API response builder."""

    @staticmethod
    def _build_response(status_code: int, body: Any,
                       additional_headers: Dict = None) -> Dict:
        """Build standardized API Gateway response."""
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'OPTIONS,GET,POST',
            'Content-Type': 'application/json'
        }

        if additional_headers:
            headers.update(additional_headers)

        return {
            'statusCode': status_code,
            'headers': headers,
            'body': json.dumps(body, default=decimal_default)
        }

    @staticmethod
    def success(data: Any, additional_headers: Dict = None) -> Dict:
        """Return successful response with data."""
        return APIResponse._build_response(200, data, additional_headers)

    @staticmethod
    def bad_request(message: str) -> Dict:
        """Return 400 Bad Request response."""
        return APIResponse._build_response(400, {'error': message})

    @staticmethod
    def unauthorized(message: str) -> Dict:
        """Return 401 Unauthorized response."""
        return APIResponse._build_response(401, {'error': message})

    @staticmethod
    def not_found(message: str) -> Dict:
        """Return 404 Not Found response."""
        return APIResponse._build_response(404, {'error': message})

    @staticmethod
    def server_error(message: str) -> Dict:
        """Return 500 Server Error response."""
        return APIResponse._build_response(500, {'error': message})


class APIError(Exception):
    """Custom API error class."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)
