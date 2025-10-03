"""
Opponent Strength Classification Module

This module implements Phase 1 opponent strength stratification to enhance
prediction accuracy by segmenting team performance against different opponent tiers.

Key Features:
- League standings integration via API-Football  
- Three-tier classification: top (25%), middle (50%), bottom (25%)
- DynamoDB caching for performance optimization (24-hour TTL)
- Version tracking integration with Phase 0 infrastructure

Opponent Classification Tiers:
- "top": Top 25% of teams (strongest opponents, positions 1-5 in 20-team league)
- "middle": Middle 50% of teams (positions 6-15 in 20-team league)  
- "bottom": Bottom 25% of teams (weakest opponents, positions 16-20 in 20-team league)
"""

import boto3
import requests
import time
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union
import json
import logging

from ..infrastructure.version_manager import VersionManager
from ..utils.constants import RAPIDAPI_KEY

class OpponentClassifier:
    """
    Handles opponent strength classification based on league standings.
    
    This is the core Phase 1 enhancement that enables segmented team parameters
    for more accurate predictions against different strength opponents.
    """
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.version_manager = VersionManager()
        self.logger = logging.getLogger(__name__)
        
        # Initialize standings cache table
        try:
            self.cache_table = self.dynamodb.Table('league_standings_cache')
        except Exception as e:
            self.logger.warning(f"Could not connect to league_standings_cache table: {e}")
            self.cache_table = None
        
        # Opponent strength tier thresholds
        self.TIER_THRESHOLDS = {
            'small_league': {  # 12-14 teams
                'top': 0.25,       # Top 25%
                'bottom': 0.75     # Bottom 25%
            },
            'medium_league': {  # 16-18 teams
                'top': 0.25,
                'bottom': 0.75
            },
            'large_league': {  # 20+ teams
                'top': 0.25,
                'bottom': 0.75
            }
        }
    
    def get_league_size_category(self, total_teams: int) -> str:
        """
        Determine league size category for threshold application.
        
        Args:
            total_teams: Number of teams in the league
            
        Returns:
            str: League size category ('small_league', 'medium_league', 'large_league')
        """
        if total_teams <= 14:
            return 'small_league'
        elif total_teams <= 18:
            return 'medium_league'
        else:
            return 'large_league'
    
    def classify_team_by_position(self, league_position: int, total_teams: int) -> str:
        """
        Classify a team into strength tier based on league position.
        
        This is the core classification logic that determines opponent strength
        for segmented parameter calculation.
        
        Args:
            league_position: Current position in league (1 = first place)
            total_teams: Total number of teams in league
            
        Returns:
            str: 'top', 'middle', or 'bottom'
        """
        if not league_position or not total_teams or league_position > total_teams:
            return 'middle'  # Default fallback for invalid data
        
        league_category = self.get_league_size_category(total_teams)
        thresholds = self.TIER_THRESHOLDS[league_category]
        
        # Calculate position percentile (lower is better)
        position_percentile = league_position / total_teams
        
        if position_percentile <= thresholds['top']:
            return 'top'
        elif position_percentile >= thresholds['bottom']:
            return 'bottom'
        else:
            return 'middle'
    
    def get_league_standings(self, league_id: int, season: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Fetch current league standings with 24-hour caching.
        
        This function integrates with API-Football for real-time standings data
        while using DynamoDB caching for performance optimization.
        
        Args:
            league_id: League ID for API-Football
            season: Season year (e.g., "2024")
            use_cache: Whether to use cached data (default: True)
            
        Returns:
            dict: Standings data with team positions and metadata, or None if failed
        """
        cache_key = f"{league_id}-{season}"
        current_timestamp = datetime.now().timestamp()
        
        # Try cache first if enabled
        if use_cache and self.cache_table:
            try:
                response = self.cache_table.get_item(Key={'cache_key': cache_key})
                if 'Item' in response:
                    cached_data = response['Item']
                    cached_timestamp = float(cached_data['timestamp'])
                    cache_age_hours = (current_timestamp - cached_timestamp) / 3600
                    
                    # Cache valid for 24 hours
                    if cache_age_hours < 24:
                        self.logger.info(f"Using cached standings for league {league_id} (age: {cache_age_hours:.1f}h)")
                        return {
                            'standings_data': cached_data['standings_data'],
                            'team_positions': cached_data['team_positions'],
                            'total_teams': cached_data['total_teams'],
                            'last_updated': cached_data['last_updated'],
                            'source': 'cache'
                        }
                    else:
                        self.logger.info(f"Cache expired for league {league_id} (age: {cache_age_hours:.1f}h)")
            except Exception as e:
                self.logger.warning(f"Cache read failed for league {league_id}: {e}")
        
        # Fetch from API-Football
        self.logger.info(f"Fetching fresh standings data for league {league_id}, season {season}")
        
        try:
            standings_data = self._fetch_standings_from_api(league_id, season)
            if not standings_data:
                return None
            
            # Process and cache the standings
            processed_data = self._process_standings_data(standings_data)
            if processed_data and self.cache_table:
                self._cache_standings_data(cache_key, processed_data, current_timestamp)
            
            return processed_data
            
        except Exception as e:
            self.logger.error(f"Failed to fetch standings for league {league_id}: {e}")
            return None
    
    def _fetch_standings_from_api(self, league_id: int, season: str) -> Optional[Dict]:
        """
        Fetch standings data from API-Football.
        
        Args:
            league_id: League ID
            season: Season year
            
        Returns:
            dict: Raw API response data
        """
        if not RAPIDAPI_KEY:
            self.logger.error("RAPIDAPI_KEY not configured")
            return None
        
        url = "https://api-football-v1.p.rapidapi.com/v3/standings"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
        params = {
            "league": league_id,
            "season": season
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('response') and len(data['response']) > 0:
                return data['response'][0]  # Get first standings group
            else:
                self.logger.warning(f"No standings data returned for league {league_id}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed for league {league_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response for league {league_id}: {e}")
            return None
    
    def _process_standings_data(self, api_data: Dict) -> Dict:
        """
        Process raw API standings data into usable format.
        
        Args:
            api_data: Raw API response data
            
        Returns:
            dict: Processed standings with team positions
        """
        if not api_data or 'league' not in api_data:
            return {}
        
        league_info = api_data['league']
        standings = league_info.get('standings', [])
        
        if not standings or len(standings) == 0:
            return {}
        
        # Process the main standings table (first group)
        main_table = standings[0]
        team_positions = {}
        standings_list = []
        
        for team_data in main_table:
            team_id = team_data['team']['id']
            team_name = team_data['team']['name']
            position = team_data['rank']
            points = team_data['points']
            played = team_data['all']['played']
            
            team_positions[str(team_id)] = {
                'position': position,
                'name': team_name,
                'points': points,
                'played': played,
                'tier': self.classify_team_by_position(position, len(main_table))
            }
            
            standings_list.append({
                'team_id': team_id,
                'team_name': team_name,
                'position': position,
                'points': points,
                'played': played
            })
        
        return {
            'standings_data': standings_list,
            'team_positions': team_positions,
            'total_teams': len(main_table),
            'last_updated': league_info.get('season'),
            'source': 'api'
        }
    
    def _convert_to_dynamodb_format(self, data: Union[Dict, List, int, float, str]) -> Union[Dict, List, Decimal, str, int]:
        """
        Recursively convert data to DynamoDB-compatible format.
        Converts floats to Decimals and handles nested structures.
        
        Args:
            data: Data to convert
            
        Returns:
            DynamoDB-compatible data
        """
        if isinstance(data, dict):
            return {key: self._convert_to_dynamodb_format(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._convert_to_dynamodb_format(item) for item in data]
        elif isinstance(data, float):
            return Decimal(str(data))
        elif isinstance(data, int):
            return data
        elif isinstance(data, str):
            return data
        else:
            return str(data)  # Convert other types to string for safety

    def _cache_standings_data(self, cache_key: str, processed_data: Dict, timestamp: float):
        """
        Cache processed standings data in DynamoDB.
        
        Args:
            cache_key: Cache identifier (league_id-season)
            processed_data: Processed standings data
            timestamp: Current timestamp
        """
        if not self.cache_table:
            return
        
        try:
            # Calculate TTL (24 hours from now)
            ttl_timestamp = int(timestamp + (24 * 3600))
            
            # Convert all data to DynamoDB-compatible format
            cache_item = {
                'cache_key': cache_key,
                'timestamp': int(timestamp),  # Convert to int for DynamoDB
                'ttl': ttl_timestamp,
                'standings_data': self._convert_to_dynamodb_format(processed_data['standings_data']),
                'team_positions': self._convert_to_dynamodb_format(processed_data['team_positions']),
                'total_teams': processed_data['total_teams'],  # Already int
                'last_updated': str(processed_data['last_updated'])  # Ensure string
            }
            
            self.cache_table.put_item(Item=cache_item)
            self.logger.info(f"Cached standings data for {cache_key} (TTL: {ttl_timestamp})")
            
        except Exception as e:
            self.logger.error(f"Failed to cache standings data for {cache_key}: {e}")
    
    def get_opponent_tier_from_match(self, home_team_id: int, away_team_id: int, 
                                   league_id: int, season: str, 
                                   perspective_team_id: int) -> str:
        """
        Determine opponent strength tier from perspective of a specific team.
        
        This is the key function used during parameter calculation to segment
        matches by opponent strength for more accurate team parameters.
        
        Args:
            home_team_id: Home team ID
            away_team_id: Away team ID
            league_id: League ID
            season: Season year
            perspective_team_id: The team whose perspective we're analyzing from
            
        Returns:
            str: Opponent tier ('top', 'middle', 'bottom')
        """
        # Determine who the opponent is
        if perspective_team_id == home_team_id:
            opponent_id = away_team_id
        elif perspective_team_id == away_team_id:
            opponent_id = home_team_id
        else:
            self.logger.warning(f"Team {perspective_team_id} not found in match {home_team_id} vs {away_team_id}")
            return 'middle'  # Default fallback
        
        # Get league standings
        standings = self.get_league_standings(league_id, season)
        if not standings or 'team_positions' not in standings:
            self.logger.warning(f"No standings available for league {league_id}, season {season}")
            return 'middle'  # Default fallback when standings unavailable
        
        # Look up opponent tier
        opponent_key = str(opponent_id)
        if opponent_key in standings['team_positions']:
            tier = standings['team_positions'][opponent_key]['tier']
            self.logger.debug(f"Opponent {opponent_id} classified as '{tier}' tier")
            return tier
        else:
            self.logger.warning(f"Team {opponent_id} not found in standings for league {league_id}")
            return 'middle'  # Default fallback when team not found
    
    def get_team_tier(self, team_id: int, league_id: int, season: str) -> str:
        """
        Get a team's own strength tier classification.
        
        Args:
            team_id: Team ID to classify
            league_id: League ID
            season: Season year
            
        Returns:
            str: Team's tier ('top', 'middle', 'bottom')
        """
        standings = self.get_league_standings(league_id, season)
        if not standings or 'team_positions' not in standings:
            return 'middle'
        
        team_key = str(team_id)
        if team_key in standings['team_positions']:
            return standings['team_positions'][team_key]['tier']
        else:
            return 'middle'


# Convenience functions for backward compatibility and ease of use

def get_league_standings(league_id: int, season: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Convenience function to get league standings.
    
    Args:
        league_id: League ID for API-Football
        season: Season year (e.g., "2024")
        use_cache: Whether to use cached data
        
    Returns:
        dict: Standings data with team positions and metadata
    """
    classifier = OpponentClassifier()
    return classifier.get_league_standings(league_id, season, use_cache)


def classify_team_by_position(league_position: int, total_teams: int) -> str:
    """
    Convenience function to classify team strength by league position.
    
    Args:
        league_position: Current position in league (1 = first place)
        total_teams: Total number of teams in league
        
    Returns:
        str: Strength tier ('top', 'middle', 'bottom')
    """
    classifier = OpponentClassifier()
    return classifier.classify_team_by_position(league_position, total_teams)


def get_opponent_tier_from_match(home_team_id: int, away_team_id: int, 
                               league_id: int, season: str, 
                               perspective_team_id: int) -> str:
    """
    Convenience function to determine opponent tier from match perspective.
    
    Args:
        home_team_id: Home team ID
        away_team_id: Away team ID
        league_id: League ID
        season: Season year
        perspective_team_id: The team whose perspective we're analyzing from
        
    Returns:
        str: Opponent tier ('top', 'middle', 'bottom')
    """
    classifier = OpponentClassifier()
    return classifier.get_opponent_tier_from_match(
        home_team_id, away_team_id, league_id, season, perspective_team_id
    )


def cache_league_standings(league_id: int, season: str, standings_data: Dict):
    """
    Convenience function to manually cache league standings data.
    
    Args:
        league_id: League ID
        season: Season year
        standings_data: Processed standings data to cache
    """
    classifier = OpponentClassifier()
    cache_key = f"{league_id}-{season}"
    current_timestamp = datetime.now().timestamp()
    classifier._cache_standings_data(cache_key, standings_data, current_timestamp)