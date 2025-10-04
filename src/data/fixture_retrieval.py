"""
Fixture retrieval from RapidAPI Football API.

Extracted from code-samples/get_fixtures.py for modular architecture.
Handles all API interactions for fixture data retrieval.

Author: Football Fixture Prediction System
Phase: Fixture Ingestion Implementation
Version: 1.0
"""

import os
import requests
import time
from typing import List, Dict, Optional
from datetime import datetime


class FixtureRetriever:
    """Handles fixture retrieval from RapidAPI Football API."""

    def __init__(self):
        """Initialize the fixture retriever with API credentials."""
        self.api_key = os.getenv('RAPIDAPI_KEY')
        if not self.api_key:
            raise ValueError("RAPIDAPI_KEY environment variable is required")

        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
        self.base_url = "https://api-football-v1.p.rapidapi.com/v3"

        # Rate limiting configuration
        self.rate_limit_wait_seconds = 60
        self.max_retries = 3

    def get_league_fixtures(self, league_id: int, start_date: str,
                           end_date: str) -> List[Dict]:
        """
        Retrieve fixtures for a specific league within date range.

        Args:
            league_id: League identifier
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            List of fixture dictionaries
        """
        try:
            # Get current season for the league
            season = self._get_league_season(league_id)
            if not season:
                print(f"Could not determine season for league {league_id}")
                return []

            print(f"  Season: {season}")

            # Retrieve fixtures
            url = f"{self.base_url}/fixtures"
            params = {
                "league": str(league_id),
                "season": str(season),
                "from": start_date,
                "to": end_date
            }

            response = self._make_api_request(url, params, f"fixtures for league {league_id}")

            if not response:
                return []

            fixtures = []
            for game in response:
                try:
                    fixture_data = {
                        'fixture_id': game['fixture']['id'],
                        'date': game['fixture']['date'],
                        'timestamp': game['fixture']['timestamp'],
                        'venue_id': game['fixture'].get('venue', {}).get('id'),
                        'venue_name': game['fixture'].get('venue', {}).get('name'),
                        'home_team': game['teams']['home']['name'],
                        'home_id': game['teams']['home']['id'],
                        'away_team': game['teams']['away']['name'],
                        'away_id': game['teams']['away']['id'],
                        'league_id': game['league']['id'],
                        'league_name': game['league']['name'],
                        'season': game['league']['season'],
                        'round': game['league'].get('round', 'Unknown')
                    }
                    fixtures.append(fixture_data)
                except (KeyError, TypeError) as e:
                    print(f"  Warning: Skipping malformed fixture data: {e}")
                    continue

            print(f"  Retrieved {len(fixtures)} fixtures for league {league_id}")
            return fixtures

        except Exception as e:
            print(f"Error retrieving fixtures for league {league_id}: {e}")
            return []

    def _get_league_season(self, league_id: int) -> Optional[str]:
        """
        Get the current season year for a league.
        Based on get_league_start_date function from original code.

        Args:
            league_id: League identifier

        Returns:
            Season year as string or None if not found
        """
        try:
            url = f"{self.base_url}/leagues"
            params = {"id": league_id, "current": "true"}

            response = self._make_api_request(url, params, f"season for league {league_id}")

            if not response:
                return None

            # Extract current season start date
            if response and len(response) > 0:
                seasons = response[0].get("seasons", [])
                for season in seasons:
                    if season.get("current"):
                        start_date = season.get("start")
                        if start_date:
                            season_year = start_date[:4]  # Return year only
                            print(f"  Current season for league {league_id}: {season_year}")
                            return season_year

            print(f"  No current season found for league {league_id}")
            return None

        except Exception as e:
            print(f"Error getting season for league {league_id}: {e}")
            return None

    def _make_api_request(self, url: str, params: Dict, description: str,
                         retry_count: int = 0) -> Optional[List[Dict]]:
        """
        Make API request with retry logic and rate limit handling.

        Args:
            url: API endpoint URL
            params: Query parameters
            description: Description for logging
            retry_count: Current retry attempt

        Returns:
            API response data or None if failed
        """
        try:
            response = requests.get(url, headers=self.headers, params=params)

            # Handle rate limiting
            if response.status_code == 429:
                if retry_count < self.max_retries:
                    print(f"  Rate limit hit for {description}, waiting {self.rate_limit_wait_seconds}s... (attempt {retry_count + 1}/{self.max_retries})")
                    time.sleep(self.rate_limit_wait_seconds)
                    return self._make_api_request(url, params, description, retry_count + 1)
                else:
                    print(f"  Max retries reached for {description}")
                    return None

            # Handle other HTTP errors
            if response.status_code != 200:
                print(f"  API error for {description}: HTTP {response.status_code}")
                if retry_count < self.max_retries:
                    print(f"  Retrying... (attempt {retry_count + 1}/{self.max_retries})")
                    time.sleep(5)  # Wait 5 seconds before retry
                    return self._make_api_request(url, params, description, retry_count + 1)
                return None

            # Parse response
            data = response.json()
            if 'response' not in data:
                print(f"  Unexpected API response format for {description}")
                return None

            return data['response']

        except requests.exceptions.RequestException as e:
            print(f"  Network error for {description}: {e}")
            if retry_count < self.max_retries:
                print(f"  Retrying... (attempt {retry_count + 1}/{self.max_retries})")
                time.sleep(5)
                return self._make_api_request(url, params, description, retry_count + 1)
            return None

        except Exception as e:
            print(f"  Unexpected error for {description}: {e}")
            return None
