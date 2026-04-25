"""
Data Formatter - Format database records for API responses.
Ensures consistent data structure and removes sensitive information.
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal


class DataFormatter:
    """Service for formatting API response data."""

    def format_fixture_response(self, fixtures: List[Dict], full_details: bool = True) -> List[Dict]:
        """
        Format fixture data for single fixture response.

        Args:
            fixtures: Raw fixture data from database
            full_details: If True, return complete record. If False, return filtered subset.

        Returns:
            List of formatted fixture dictionaries
        """
        if full_details:
            # Return complete records with Decimal conversion
            return [self._convert_decimals_recursive(fixture) for fixture in fixtures]
        else:
            # Return filtered subset for league queries
            return [self._format_single_fixture(fixture) for fixture in fixtures]

    def format_league_response(self, query_result: Dict) -> Dict:
        """
        Format league fixtures query result.

        Args:
            query_result: Result from query service

        Returns:
            Dict with formatted items and pagination info
        """
        formatted_items = []

        for item in query_result.get('items', []):
            formatted_item = self._format_single_fixture(item)
            formatted_items.append(formatted_item)

        return {
            'items': formatted_items,
            'last_evaluated_key': query_result.get('last_evaluated_key')
        }

    def _format_single_fixture(self, item: Dict) -> Dict:
        """
        Format a single fixture record.
        Based on the filtering logic from analysis_backend_mobile.py.

        Args:
            item: Raw fixture record from database

        Returns:
            Dict: Formatted fixture data
        """
        # Check if fixture has best bet information
        has_best_bet = (
            'best_bet' in item and
            item['best_bet'] and
            len(item.get('best_bet', [])) > 0
        )

        # V1 (the per-match goal-arrays engine) is primary; V3 (the SoT
        # engine) is the alternate. Sourcing:
        #   predicted_goals       <- home.predicted_goals       (V1)
        #   predicted_goals_alt   <- home.sot_predicted_goals   (V3)
        #
        # If V3 hasn't run yet (cold-start league with no fitted SoT params,
        # or the V3 block raised), predicted_goals_alt is omitted.
        home_data = item.get('home', {})
        away_data = item.get('away', {})

        home_team = {
            'team_id': self._safe_decimal_convert(home_data.get('team_id')),
            'team_name': home_data.get('team_name'),
            'team_logo': home_data.get('team_logo'),
            'predicted_goals': self._safe_decimal_convert(home_data.get('predicted_goals')),
            'predicted_goals_alt': self._safe_decimal_convert(home_data.get('sot_predicted_goals')),
            'home_performance': self._safe_decimal_convert(home_data.get('home_performance'))
        }

        away_team = {
            'team_id': self._safe_decimal_convert(away_data.get('team_id')),
            'team_name': away_data.get('team_name'),
            'team_logo': away_data.get('team_logo'),
            'predicted_goals': self._safe_decimal_convert(away_data.get('predicted_goals')),
            'predicted_goals_alt': self._safe_decimal_convert(away_data.get('sot_predicted_goals')),
            'away_performance': self._safe_decimal_convert(away_data.get('away_performance'))
        }

        # Build formatted response
        formatted_fixture = {
            'fixture_id': self._safe_decimal_convert(item.get('fixture_id')),
            'timestamp': self._safe_decimal_convert(item.get('timestamp')),
            'date': item.get('date'),
            'has_best_bet': has_best_bet,
            'home': home_team,
            'away': away_team
        }

        # Add additional fields if available
        if 'league' in item:
            formatted_fixture['league'] = item['league']

        if 'country' in item:
            formatted_fixture['country'] = item['country']

        # Add best bet information if available
        if has_best_bet:
            formatted_fixture['best_bet'] = item.get('best_bet')

        # Add prediction confidence if available
        if 'prediction_confidence' in item:
            formatted_fixture['prediction_confidence'] = self._safe_decimal_convert(
                item['prediction_confidence']
            )

        # Add actual scores if available (for finished matches)
        if 'goals' in item and item['goals']:
            formatted_fixture['goals'] = {
                'home': self._safe_decimal_convert(item['goals'].get('home')),
                'away': self._safe_decimal_convert(item['goals'].get('away'))
            }

        return formatted_fixture

    def _safe_decimal_convert(self, value: Any) -> Any:
        """
        Safely convert Decimal values to appropriate types.

        Args:
            value: Value to convert

        Returns:
            Converted value (int, float, or original)
        """
        if isinstance(value, Decimal):
            if value % 1 == 0:
                return int(value)
            else:
                return float(value)
        return value

    def _convert_decimals_recursive(self, obj: Any) -> Any:
        """
        Recursively convert all Decimal values in nested dictionaries/lists.

        Args:
            obj: Object to convert (can be dict, list, or primitive)

        Returns:
            Object with all Decimals converted to int/float
        """
        if isinstance(obj, dict):
            return {key: self._convert_decimals_recursive(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimals_recursive(item) for item in obj]
        elif isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            else:
                return float(obj)
        else:
            return obj
