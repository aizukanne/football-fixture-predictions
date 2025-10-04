"""
Query Service - Database query operations for API service.
Handles DynamoDB queries with proper error handling and optimization.
"""

import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal
from typing import List, Dict, Optional, Any

from ..utils.constants import GAME_FIXTURES_TABLE
from ..utils.converters import convert_for_json


class QueryService:
    """Service for database query operations."""

    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(GAME_FIXTURES_TABLE)

    def get_fixture_by_id(self, fixture_id: int) -> List[Dict]:
        """
        Get a specific fixture by ID.

        Args:
            fixture_id: Fixture identifier

        Returns:
            List of fixture records (usually 1 item)
        """
        try:
            response = self.table.query(
                KeyConditionExpression=Key('fixture_id').eq(fixture_id),
                Limit=1,
                ScanIndexForward=False  # Get latest version first
            )

            return response.get('Items', [])

        except Exception as e:
            print(f"Error querying fixture {fixture_id}: {e}")
            return []

    def get_league_fixtures(self, country: str, league: str,
                           start_time: int, end_time: int,
                           limit: Optional[str] = None,
                           last_key: Optional[str] = None) -> Dict:
        """
        Get fixtures for a league within date range.

        Args:
            country: Country name
            league: League name
            start_time: Start timestamp
            end_time: End timestamp
            limit: Maximum items to return
            last_key: Last evaluated key for pagination

        Returns:
            Dict with items and pagination info
        """
        try:
            # Build query parameters
            params = {
                'IndexName': 'country-league-index',
                'KeyConditionExpression': Key('country').eq(country) & Key('league').eq(league),
                'FilterExpression': Key('timestamp').between(Decimal(start_time), Decimal(end_time))
            }

            # Add limit if specified
            if limit:
                try:
                    params['Limit'] = int(limit)
                except ValueError:
                    pass  # Ignore invalid limit

            # Add pagination key if specified
            if last_key:
                try:
                    # Decode last_key (would need proper implementation)
                    # For now, assuming it's a JSON string
                    import json
                    params['ExclusiveStartKey'] = json.loads(last_key)
                except:
                    pass  # Ignore invalid last_key

            # Execute query with pagination
            all_items = []
            last_evaluated_key = None

            while True:
                if last_evaluated_key:
                    params['ExclusiveStartKey'] = last_evaluated_key
                else:
                    params.pop('ExclusiveStartKey', None)

                response = self.table.query(**params)
                items = response.get('Items', [])
                all_items.extend(items)

                last_evaluated_key = response.get('LastEvaluatedKey')

                # Break if no more pages or if we have a limit
                if not last_evaluated_key or (limit and len(all_items) >= int(limit)):
                    break

            return {
                'items': all_items,
                'last_evaluated_key': last_evaluated_key
            }

        except Exception as e:
            print(f"Error querying league fixtures: {e}")
            return {'items': [], 'last_evaluated_key': None}
