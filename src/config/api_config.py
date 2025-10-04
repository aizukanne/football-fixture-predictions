"""
API Configuration - Configuration settings for API service.
Centralizes API-related configuration and settings.
"""

import os
from typing import Dict, Any


class APIConfig:
    """Configuration for API service."""

    def __init__(self):
        """Initialize API configuration from environment variables."""
        self.mobile_app_key = os.getenv('MOBILE_APP_KEY', '')
        self.api_key_header = 'X-API-Key'
        self.cors_enabled = True
        self.cors_origins = os.getenv('CORS_ORIGINS', '*')
        self.max_page_size = int(os.getenv('MAX_PAGE_SIZE', '1000'))
        self.default_page_size = int(os.getenv('DEFAULT_PAGE_SIZE', '100'))
        self.default_date_range_days = int(os.getenv('DEFAULT_DATE_RANGE_DAYS', '4'))

    def get_cors_headers(self) -> Dict[str, str]:
        """Get CORS headers for response."""
        if not self.cors_enabled:
            return {}

        return {
            'Access-Control-Allow-Origin': self.cors_origins,
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'OPTIONS,GET,POST'
        }

    def validate_api_key(self, provided_key: str) -> bool:
        """
        Validate API key.

        Args:
            provided_key: API key from request

        Returns:
            bool: True if valid, False otherwise
        """
        if not self.mobile_app_key:
            print("Warning: MOBILE_APP_KEY not configured")
            return False

        return provided_key == self.mobile_app_key

    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary (without sensitive data)."""
        return {
            'cors_enabled': self.cors_enabled,
            'cors_origins': self.cors_origins,
            'max_page_size': self.max_page_size,
            'default_page_size': self.default_page_size,
            'default_date_range_days': self.default_date_range_days,
            'api_key_configured': bool(self.mobile_app_key)
        }
