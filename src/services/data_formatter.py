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

    def _resolve_score_components(self, item: Dict) -> Dict[str, Optional[int]]:
        """Pick predicted_goals (V2/xG) and predicted_goals_alt (V1) from
        the most-likely joint score in each engine's summary.

        Falls back to the per-team attributes (xg_predicted_goals,
        predicted_goals) if the summary structure is missing — that keeps
        the response usable on records produced before V2 was deployed.

        Returns a dict with home_primary, away_primary, home_alt, away_alt.
        """
        def _parse_score_str(s: Any) -> tuple[Optional[int], Optional[int]]:
            if not isinstance(s, str) or '-' not in s:
                return None, None
            parts = s.split('-', 1)
            try:
                return int(parts[0].strip()), int(parts[1].strip())
            except (ValueError, AttributeError):
                return None, None

        def _from_summary(summary: Any) -> tuple[Optional[int], Optional[int]]:
            """Try most_likely_score.score, then top_scores[0].score."""
            if not isinstance(summary, dict):
                return None, None
            mls = summary.get('most_likely_score')
            if isinstance(mls, dict):
                h, a = _parse_score_str(mls.get('score'))
                if h is not None:
                    return h, a
            top = summary.get('top_scores')
            if isinstance(top, list) and top:
                first = top[0]
                if isinstance(first, dict):
                    return _parse_score_str(first.get('score'))
            return None, None

        # Primary = V2 TEAM-PARAMS variant (xg_alternate_predictions / V2b).
        # We deliberately do NOT use xg_predictions (V2a) here: V2a is the
        # league-baseline variant — its lambdas resolve to ~league_avg for
        # both sides, so the joint mode collapses to 1-1 on almost every
        # fixture. The team-aware V2 prediction lives in V2b.
        h_pri, a_pri = _from_summary(item.get('xg_alternate_predictions'))
        if h_pri is None:
            # Fall back to per-team xg_predicted_goals_alt (V2b marginal mode)
            home_data = item.get('home', {}) or {}
            away_data = item.get('away', {}) or {}
            h_pri = home_data.get('xg_predicted_goals_alt')
            a_pri = away_data.get('xg_predicted_goals_alt')

        # Alt = V1 LEAGUE-PARAMS variant (predictions / V1a) — preserves the
        # field that downstream consumers were already comparing against.
        h_alt, a_alt = _from_summary(item.get('predictions'))
        if h_alt is None:
            home_data = item.get('home', {}) or {}
            away_data = item.get('away', {}) or {}
            h_alt = home_data.get('predicted_goals')
            a_alt = away_data.get('predicted_goals')

        return {
            'home_primary': h_pri,
            'away_primary': a_pri,
            'home_alt': h_alt,
            'away_alt': a_alt,
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

        # Resolve which engine drives predicted_goals vs predicted_goals_alt:
        #   predicted_goals      <- xg_predictions most-likely score (V2)
        #   predicted_goals_alt  <- predictions     most-likely score (V1)
        # See _resolve_score_components for fallback logic when one
        # engine's summary is absent.
        scores = self._resolve_score_components(item)

        # Extract home team data
        home_data = item.get('home', {})
        home_team = {
            'team_id': self._safe_decimal_convert(home_data.get('team_id')),
            'team_name': home_data.get('team_name'),
            'team_logo': home_data.get('team_logo'),
            'predicted_goals': self._safe_decimal_convert(scores['home_primary']),
            'predicted_goals_alt': self._safe_decimal_convert(scores['home_alt']),
            'home_performance': self._safe_decimal_convert(home_data.get('home_performance'))
        }

        # Extract away team data
        away_data = item.get('away', {})
        away_team = {
            'team_id': self._safe_decimal_convert(away_data.get('team_id')),
            'team_name': away_data.get('team_name'),
            'team_logo': away_data.get('team_logo'),
            'predicted_goals': self._safe_decimal_convert(scores['away_primary']),
            'predicted_goals_alt': self._safe_decimal_convert(scores['away_alt']),
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
