"""
Fixture data formatting utilities.

Ensures consistent data structure for prediction processing.
Validates and formats raw fixture data from API for queue consumption.

Author: Football Fixture Prediction System
Phase: Fixture Ingestion Implementation
Version: 1.0
"""

from typing import List, Dict
from datetime import datetime


class FixtureFormatter:
    """Formats fixture data for consistent processing across the system."""

    def format_fixtures_for_queue(self, fixtures: List[Dict],
                                 league_info: Dict) -> List[Dict]:
        """
        Format raw fixture data for SQS queue consumption.
        Ensures compatibility with existing prediction_handler.py.

        Args:
            fixtures: Raw fixture data from API
            league_info: League metadata

        Returns:
            List of formatted fixture dictionaries
        """
        formatted = []

        for fixture in fixtures:
            try:
                # Format according to prediction_handler expectations
                formatted_fixture = {
                    'fixture_id': fixture['fixture_id'],
                    'date': fixture['date'],
                    'timestamp': fixture['timestamp'],
                    'venue_id': fixture.get('venue_id'),
                    'venue_name': fixture.get('venue_name'),
                    'home_team': fixture['home_team'],
                    'home_id': fixture['home_id'],
                    'away_team': fixture['away_team'],
                    'away_id': fixture['away_id'],
                    'league_id': fixture['league_id'],
                    'league_name': fixture.get('league_name'),
                    'season': fixture['season'],
                    'round': fixture.get('round', 'Unknown'),
                    # Add metadata for enhanced processing
                    'ingestion_timestamp': int(datetime.now().timestamp()),
                    'source': 'fixture_ingestion_handler',
                    'country': league_info.get('country', 'Unknown')
                }

                # Validate required fields
                if self._validate_fixture(formatted_fixture):
                    formatted.append(formatted_fixture)
                else:
                    fixture_id = fixture.get('fixture_id', 'unknown')
                    print(f"Invalid fixture data, skipping fixture {fixture_id}")

            except Exception as e:
                fixture_id = fixture.get('fixture_id', 'unknown')
                print(f"Error formatting fixture {fixture_id}: {e}")
                continue

        return formatted

    def _validate_fixture(self, fixture: Dict) -> bool:
        """
        Validate that fixture has all required fields.

        Args:
            fixture: Fixture dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        # Required fields for prediction processing
        required_fields = [
            'fixture_id', 'date', 'timestamp', 'home_team', 'home_id',
            'away_team', 'away_id', 'league_id', 'season'
        ]

        # Check all required fields are present and not None
        for field in required_fields:
            if field not in fixture or fixture[field] is None:
                print(f"  Validation failed: Missing or null required field '{field}'")
                return False

        # Validate data types for critical numeric fields
        try:
            int(fixture['fixture_id'])
            int(fixture['home_id'])
            int(fixture['away_id'])
            int(fixture['league_id'])
            int(fixture['timestamp'])
        except (ValueError, TypeError) as e:
            print(f"  Validation failed: Invalid data type for numeric field - {e}")
            return False

        # Validate string fields are not empty
        string_fields = ['home_team', 'away_team', 'date']
        for field in string_fields:
            if not isinstance(fixture[field], str) or not fixture[field].strip():
                print(f"  Validation failed: Invalid or empty string field '{field}'")
                return False

        # Validate timestamp is reasonable (not in distant past or future)
        try:
            timestamp = int(fixture['timestamp'])
            current_timestamp = int(datetime.now().timestamp())

            # Check if timestamp is within reasonable range (not more than 5 years in past or 2 years in future)
            five_years_ago = current_timestamp - (5 * 365 * 24 * 60 * 60)
            two_years_ahead = current_timestamp + (2 * 365 * 24 * 60 * 60)

            if timestamp < five_years_ago or timestamp > two_years_ahead:
                print(f"  Validation failed: Timestamp {timestamp} is outside reasonable range")
                return False

        except Exception as e:
            print(f"  Validation failed: Error validating timestamp - {e}")
            return False

        return True

    def format_date_for_display(self, date_string: str) -> str:
        """
        Format ISO date string for human-readable display.

        Args:
            date_string: ISO format date string

        Returns:
            Formatted date string
        """
        try:
            dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M UTC')
        except Exception:
            return date_string

    def extract_match_summary(self, fixture: Dict) -> str:
        """
        Generate a human-readable match summary.

        Args:
            fixture: Formatted fixture dictionary

        Returns:
            Match summary string
        """
        try:
            date_str = self.format_date_for_display(fixture['date'])
            home = fixture['home_team']
            away = fixture['away_team']
            league = fixture.get('league_name', f"League {fixture['league_id']}")
            round_info = fixture.get('round', '')

            summary = f"{home} vs {away} - {league}"
            if round_info:
                summary += f" ({round_info})"
            summary += f" - {date_str}"

            return summary
        except Exception as e:
            return f"Match {fixture.get('fixture_id', 'Unknown')} - Error: {e}"
