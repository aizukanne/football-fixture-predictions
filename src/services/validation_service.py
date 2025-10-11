"""
Validation Service - Input validation for API requests.
Ensures data integrity and security.
"""

import re
from typing import Dict, NamedTuple
from datetime import datetime


class ValidationResult(NamedTuple):
    """Result of validation check."""
    is_valid: bool
    error_message: str = ""


class ValidationService:
    """Service for validating API request parameters."""

    def __init__(self):
        # Allowed parameter patterns
        self.country_pattern = re.compile(r'^[A-Za-z\s\-]{1,50}$')
        self.league_pattern = re.compile(r'^[\w\s\-\.]{1,100}$', re.UNICODE)
        self.date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

    def validate_query_params(self, params: Dict) -> ValidationResult:
        """
        Validate query parameters for API request.

        Args:
            params: Query parameters dictionary

        Returns:
            ValidationResult with validation status
        """
        # Check for fixture_id query
        if 'fixture_id' in params:
            return self._validate_fixture_id(params['fixture_id'])

        # Check for league query parameters
        if 'country' in params or 'league' in params:
            return self._validate_league_params(params)

        return ValidationResult(
            is_valid=False,
            error_message="Either 'fixture_id' or both 'country' and 'league' parameters are required"
        )

    def _validate_fixture_id(self, fixture_id: str) -> ValidationResult:
        """Validate fixture ID parameter."""
        try:
            fixture_id_int = int(fixture_id)
            if fixture_id_int <= 0:
                return ValidationResult(
                    is_valid=False,
                    error_message="fixture_id must be a positive integer"
                )
            return ValidationResult(is_valid=True)
        except ValueError:
            return ValidationResult(
                is_valid=False,
                error_message="fixture_id must be a valid integer"
            )

    def _validate_league_params(self, params: Dict) -> ValidationResult:
        """Validate league query parameters."""
        country = params.get('country', '').strip()
        league = params.get('league', '').strip()

        # Check required parameters
        if not country:
            return ValidationResult(
                is_valid=False,
                error_message="'country' parameter is required and cannot be empty"
            )

        if not league:
            return ValidationResult(
                is_valid=False,
                error_message="'league' parameter is required and cannot be empty"
            )

        # Validate country format
        if not self.country_pattern.match(country):
            return ValidationResult(
                is_valid=False,
                error_message="'country' parameter contains invalid characters or is too long"
            )

        # Validate league format
        if not self.league_pattern.match(league):
            return ValidationResult(
                is_valid=False,
                error_message="'league' parameter contains invalid characters or is too long"
            )

        # Validate date parameters if provided
        start_date = params.get('startDate')
        end_date = params.get('endDate')

        if start_date:
            date_validation = self._validate_date_format(start_date, 'startDate')
            if not date_validation.is_valid:
                return date_validation

        if end_date:
            date_validation = self._validate_date_format(end_date, 'endDate')
            if not date_validation.is_valid:
                return date_validation

        # Validate date range if both provided
        if start_date and end_date:
            range_validation = self._validate_date_range(start_date, end_date)
            if not range_validation.is_valid:
                return range_validation

        # Validate optional limit parameter
        limit = params.get('limit')
        if limit:
            try:
                limit_int = int(limit)
                if limit_int <= 0 or limit_int > 1000:
                    return ValidationResult(
                        is_valid=False,
                        error_message="'limit' must be between 1 and 1000"
                    )
            except ValueError:
                return ValidationResult(
                    is_valid=False,
                    error_message="'limit' must be a valid integer"
                )

        return ValidationResult(is_valid=True)

    def _validate_date_format(self, date_str: str, param_name: str) -> ValidationResult:
        """Validate date format (YYYY-MM-DD)."""
        if not self.date_pattern.match(date_str):
            return ValidationResult(
                is_valid=False,
                error_message=f"'{param_name}' must be in YYYY-MM-DD format"
            )

        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return ValidationResult(is_valid=True)
        except ValueError:
            return ValidationResult(
                is_valid=False,
                error_message=f"'{param_name}' is not a valid date"
            )

    def _validate_date_range(self, start_date: str, end_date: str) -> ValidationResult:
        """Validate date range logic."""
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')

            if start >= end:
                return ValidationResult(
                    is_valid=False,
                    error_message="'startDate' must be before 'endDate'"
                )

            # Check if date range is reasonable (e.g., not more than 1 year)
            if (end - start).days > 365:
                return ValidationResult(
                    is_valid=False,
                    error_message="Date range cannot exceed 365 days"
                )

            return ValidationResult(is_valid=True)

        except ValueError:
            return ValidationResult(
                is_valid=False,
                error_message="Invalid date format in date range"
            )
