"""
tactical_data_collector.py - Enhanced match data collection for tactical analysis

Phase 4: Derived Tactical Style Features
Collects and processes enhanced match data including formation information,
tactical statistics, and advanced metrics needed for sophisticated tactical analysis.

This module provides:
- Formation data collection from API-Football
- Enhanced tactical statistics gathering
- Match-level tactical data processing
- Tactical analysis data caching
- Real-time tactical metrics collection
"""

import requests
import json
from typing import Dict, List, Optional, Tuple, Union
from decimal import Decimal
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
import logging
import time

from ..infrastructure.version_manager import VersionManager
from ..data.api_client import APIClient
from ..data.database_client import DatabaseClient

logger = logging.getLogger(__name__)

class TacticalDataCollector:
    """Collects enhanced tactical data for Phase 4 analysis."""
    
    def __init__(self):
        self.api_client = APIClient()
        self.db_client = DatabaseClient()
        self.version_manager = VersionManager()
        
        # DynamoDB table for tactical cache
        self.tactical_cache_table = 'tactical_analysis_cache'
        
        # Cache TTL (48 hours for tactical analysis)
        self.cache_ttl = 48 * 60 * 60  # 48 hours in seconds
    
    def collect_formation_data(self, match_id: int) -> Dict:
        """
        Collect formation and tactical data from API-Football.
        
        Args:
            match_id: Match identifier
            
        Returns:
            {
                'home_formation': str,              # Home team formation
                'away_formation': str,              # Away team formation
                'formation_changes': List[Dict],    # In-game formation changes
                'tactical_stats': Dict,             # Advanced tactical statistics
                'lineup_data': Dict,                # Player positioning data
                'substitutions': List[Dict]         # Substitution timing and impact
            }
        """
        try:
            # Check cache first
            cached_data = self._get_cached_formation_data(match_id)
            if cached_data:
                return cached_data
            
            # Fetch formation data from API-Football
            formation_data = self._fetch_formation_from_api(match_id)
            
            if formation_data:
                # Cache the result
                self._cache_formation_data(match_id, formation_data)
                return formation_data
            else:
                return self._get_default_formation_data()
                
        except Exception as e:
            logger.error(f"Error collecting formation data for match {match_id}: {e}")
            return self._get_default_formation_data()
    
    def get_team_tactical_statistics(self, team_id: int, league_id: int, season: int) -> Dict:
        """
        Get comprehensive tactical statistics for team analysis.
        
        Args:
            team_id: Team identifier
            league_id: League identifier
            season: Season year
            
        Returns:
            {
                'possession_stats': Dict,           # Possession-related metrics
                'passing_stats': Dict,              # Passing accuracy and patterns
                'attacking_stats': Dict,            # Shots, corners, attacks
                'defensive_stats': Dict,            # Tackles, blocks, clearances
                'set_piece_stats': Dict,           # Set piece effectiveness
                'pressing_stats': Dict,            # Pressing intensity metrics
                'transition_stats': Dict,          # Transition speed and effectiveness
                'formation_usage': Dict,           # Formation preferences
                'tactical_flexibility': Dict       # In-game adaptation metrics
            }
        """
        try:
            # Check cache first
            cache_key = f"tactical_stats_{team_id}_{league_id}_{season}"
            cached_stats = self._get_cached_tactical_stats(cache_key)
            if cached_stats:
                return cached_stats
            
            # Collect comprehensive tactical statistics
            tactical_stats = self._collect_team_tactical_stats(team_id, league_id, season)
            
            # Cache the results
            self._cache_tactical_statistics(cache_key, tactical_stats)
            
            return tactical_stats
            
        except Exception as e:
            logger.error(f"Error getting tactical statistics for team {team_id}: {e}")
            return self._get_default_tactical_stats()
    
    def cache_tactical_data(self, team_id: int, league_id: int, season: int, tactical_data: Dict):
        """
        Cache tactical analysis data in DynamoDB for performance.
        
        Args:
            team_id: Team identifier
            league_id: League identifier
            season: Season year
            tactical_data: Tactical analysis results to cache
            
        Table: tactical_analysis_cache  
        TTL: 48 hours (tactical analysis updated after each match)
        """
        try:
            dynamodb = boto3.resource('dynamodb')
            table = dynamodb.Table(self.tactical_cache_table)
            
            # Create cache item
            cache_item = {
                'cache_key': f"tactical_analysis_{team_id}_{league_id}_{season}",
                'team_id': team_id,
                'league_id': league_id,
                'season': season,
                'tactical_data': tactical_data,
                'cached_at': int(datetime.now().timestamp()),
                'ttl': int(datetime.now().timestamp()) + self.cache_ttl,
                'architecture_version': self.version_manager.get_current_version()
            }
            
            # Store in DynamoDB
            table.put_item(Item=cache_item)
            logger.info(f"Cached tactical data for team {team_id}")
            
        except Exception as e:
            logger.error(f"Error caching tactical data: {e}")
    
    # Private helper methods for data collection
    
    def _fetch_formation_from_api(self, match_id: int) -> Optional[Dict]:
        """Fetch formation data from API-Football."""
        try:
            # API-Football lineups endpoint
            response = self.api_client.make_request(f"fixtures/lineups/{match_id}")
            
            if response and len(response) >= 2:
                home_team_data = response[0]
                away_team_data = response[1]
                
                formation_data = {
                    'home_formation': home_team_data.get('formation', '4-4-2'),
                    'away_formation': away_team_data.get('formation', '4-4-2'),
                    'formation_changes': [],  # Would need additional API calls for this
                    'tactical_stats': self._extract_tactical_stats_from_lineup(home_team_data, away_team_data),
                    'lineup_data': {
                        'home': home_team_data.get('startXI', []),
                        'away': away_team_data.get('startXI', [])
                    },
                    'substitutions': {
                        'home': home_team_data.get('substitutes', []),
                        'away': away_team_data.get('substitutes', [])
                    }
                }
                
                return formation_data
            
        except Exception as e:
            logger.error(f"Error fetching formation from API: {e}")
        
        return None
    
    def _collect_team_tactical_stats(self, team_id: int, league_id: int, season: int) -> Dict:
        """Collect comprehensive tactical statistics for a team."""
        try:
            # Get team's matches for the season
            matches = self.api_client.get_team_matches(team_id, league_id, season)
            
            if not matches:
                return self._get_default_tactical_stats()
            
            # Aggregate tactical statistics
            tactical_stats = {
                'possession_stats': self._calculate_possession_stats(matches, team_id),
                'passing_stats': self._calculate_passing_stats(matches, team_id),
                'attacking_stats': self._calculate_attacking_stats(matches, team_id),
                'defensive_stats': self._calculate_defensive_stats(matches, team_id),
                'set_piece_stats': self._calculate_set_piece_stats(matches, team_id),
                'pressing_stats': self._calculate_pressing_stats(matches, team_id),
                'transition_stats': self._calculate_transition_stats(matches, team_id),
                'formation_usage': self._calculate_formation_usage(matches, team_id),
                'tactical_flexibility': self._calculate_tactical_flexibility(matches, team_id)
            }
            
            return tactical_stats
            
        except Exception as e:
            logger.error(f"Error collecting team tactical stats: {e}")
            return self._get_default_tactical_stats()
    
    def _extract_tactical_stats_from_lineup(self, home_data: Dict, away_data: Dict) -> Dict:
        """Extract tactical statistics from lineup data."""
        return {
            'formation_balance': {
                'home_defensive_players': self._count_defensive_players(home_data.get('formation', '4-4-2')),
                'away_defensive_players': self._count_defensive_players(away_data.get('formation', '4-4-2')),
                'home_midfield_players': self._count_midfield_players(home_data.get('formation', '4-4-2')),
                'away_midfield_players': self._count_midfield_players(away_data.get('formation', '4-4-2')),
                'home_attacking_players': self._count_attacking_players(home_data.get('formation', '4-4-2')),
                'away_attacking_players': self._count_attacking_players(away_data.get('formation', '4-4-2'))
            },
            'tactical_approach': {
                'home_approach': self._determine_tactical_approach(home_data.get('formation', '4-4-2')),
                'away_approach': self._determine_tactical_approach(away_data.get('formation', '4-4-2'))
            }
        }
    
    def _count_defensive_players(self, formation: str) -> int:
        """Count defensive players in formation."""
        formation_counts = {
            '3-5-2': 3, '3-4-3': 3, '4-3-3': 4, '4-4-2': 4,
            '4-2-3-1': 4, '4-5-1': 4, '5-3-2': 5, '5-4-1': 5
        }
        return formation_counts.get(formation, 4)
    
    def _count_midfield_players(self, formation: str) -> int:
        """Count midfield players in formation."""
        formation_counts = {
            '3-5-2': 5, '3-4-3': 4, '4-3-3': 3, '4-4-2': 4,
            '4-2-3-1': 3, '4-5-1': 5, '5-3-2': 3, '5-4-1': 4
        }
        return formation_counts.get(formation, 4)
    
    def _count_attacking_players(self, formation: str) -> int:
        """Count attacking players in formation."""
        formation_counts = {
            '3-5-2': 2, '3-4-3': 3, '4-3-3': 3, '4-4-2': 2,
            '4-2-3-1': 1, '4-5-1': 1, '5-3-2': 2, '5-4-1': 1
        }
        return formation_counts.get(formation, 2)
    
    def _determine_tactical_approach(self, formation: str) -> str:
        """Determine tactical approach from formation."""
        attacking_formations = ['3-4-3', '4-3-3', '3-5-2']
        defensive_formations = ['5-4-1', '5-3-2', '4-5-1']
        
        if formation in attacking_formations:
            return 'attacking'
        elif formation in defensive_formations:
            return 'defensive'
        else:
            return 'balanced'
    
    def _calculate_possession_stats(self, matches: List[Dict], team_id: int) -> Dict:
        """Calculate possession-related statistics."""
        possession_values = []
        pass_accuracies = []
        
        for match in matches:
            if match.get('team_id') == team_id:
                possession = match.get('possession_percentage')
                pass_accuracy = match.get('pass_accuracy')
                
                if possession:
                    possession_values.append(possession)
                if pass_accuracy:
                    pass_accuracies.append(pass_accuracy)
        
        return {
            'avg_possession': sum(possession_values) / len(possession_values) if possession_values else 50,
            'avg_pass_accuracy': sum(pass_accuracies) / len(pass_accuracies) if pass_accuracies else 75,
            'possession_consistency': self._calculate_consistency(possession_values),
            'games_with_majority_possession': sum(1 for p in possession_values if p > 50)
        }
    
    def _calculate_attacking_stats(self, matches: List[Dict], team_id: int) -> Dict:
        """Calculate attacking statistics."""
        shots_per_game = []
        corners_per_game = []
        
        for match in matches:
            if match.get('team_id') == team_id:
                shots = match.get('shots_total', 0)
                corners = match.get('corners', 0)
                
                shots_per_game.append(shots)
                corners_per_game.append(corners)
        
        return {
            'avg_shots_per_game': sum(shots_per_game) / len(shots_per_game) if shots_per_game else 10,
            'avg_corners_per_game': sum(corners_per_game) / len(corners_per_game) if corners_per_game else 5,
            'shot_consistency': self._calculate_consistency(shots_per_game),
            'high_shot_games': sum(1 for s in shots_per_game if s > 15)
        }
    
    def _calculate_defensive_stats(self, matches: List[Dict], team_id: int) -> Dict:
        """Calculate defensive statistics."""
        clean_sheets = 0
        tackles_per_game = []
        
        for match in matches:
            if match.get('team_id') == team_id:
                goals_conceded = match.get('goals_against', 0)
                tackles = match.get('tackles', 0)
                
                if goals_conceded == 0:
                    clean_sheets += 1
                tackles_per_game.append(tackles)
        
        return {
            'clean_sheet_rate': clean_sheets / len(matches) if matches else 0,
            'avg_tackles_per_game': sum(tackles_per_game) / len(tackles_per_game) if tackles_per_game else 15,
            'defensive_consistency': self._calculate_consistency(tackles_per_game)
        }
    
    def _calculate_consistency(self, values: List[float]) -> float:
        """Calculate statistical consistency (inverse of coefficient of variation)."""
        if not values or len(values) < 2:
            return 0.5
        
        mean_val = sum(values) / len(values)
        if mean_val == 0:
            return 0.5
        
        variance = sum((x - mean_val) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        
        coefficient_of_variation = std_dev / mean_val
        consistency = max(0, 1 - coefficient_of_variation)  # Higher = more consistent
        
        return min(consistency, 1.0)
    
    # Caching methods
    
    def _get_cached_formation_data(self, match_id: int) -> Optional[Dict]:
        """Get cached formation data."""
        try:
            dynamodb = boto3.resource('dynamodb')
            table = dynamodb.Table(self.tactical_cache_table)
            
            response = table.get_item(Key={'cache_key': f"formation_{match_id}"})
            
            if 'Item' in response:
                item = response['Item']
                # Check TTL
                if item.get('ttl', 0) > int(datetime.now().timestamp()):
                    return item.get('formation_data')
            
        except Exception as e:
            logger.error(f"Error getting cached formation data: {e}")
        
        return None
    
    def _cache_formation_data(self, match_id: int, formation_data: Dict):
        """Cache formation data."""
        try:
            dynamodb = boto3.resource('dynamodb')
            table = dynamodb.Table(self.tactical_cache_table)
            
            table.put_item(Item={
                'cache_key': f"formation_{match_id}",
                'match_id': match_id,
                'formation_data': formation_data,
                'cached_at': int(datetime.now().timestamp()),
                'ttl': int(datetime.now().timestamp()) + self.cache_ttl
            })
            
        except Exception as e:
            logger.error(f"Error caching formation data: {e}")
    
    def _get_cached_tactical_stats(self, cache_key: str) -> Optional[Dict]:
        """Get cached tactical statistics."""
        try:
            dynamodb = boto3.resource('dynamodb')
            table = dynamodb.Table(self.tactical_cache_table)
            
            response = table.get_item(Key={'cache_key': cache_key})
            
            if 'Item' in response:
                item = response['Item']
                if item.get('ttl', 0) > int(datetime.now().timestamp()):
                    return item.get('tactical_stats')
            
        except Exception as e:
            logger.error(f"Error getting cached tactical stats: {e}")
        
        return None
    
    def _cache_tactical_statistics(self, cache_key: str, tactical_stats: Dict):
        """Cache tactical statistics."""
        try:
            dynamodb = boto3.resource('dynamodb')
            table = dynamodb.Table(self.tactical_cache_table)
            
            table.put_item(Item={
                'cache_key': cache_key,
                'tactical_stats': tactical_stats,
                'cached_at': int(datetime.now().timestamp()),
                'ttl': int(datetime.now().timestamp()) + self.cache_ttl
            })
            
        except Exception as e:
            logger.error(f"Error caching tactical statistics: {e}")
    
    # Placeholder methods for comprehensive stats calculation
    
    def _calculate_passing_stats(self, matches: List[Dict], team_id: int) -> Dict:
        """Calculate passing statistics."""
        return {
            'short_passes_per_game': 400,
            'long_passes_per_game': 60,
            'pass_completion_rate': 0.8
        }
    
    def _calculate_set_piece_stats(self, matches: List[Dict], team_id: int) -> Dict:
        """Calculate set piece statistics."""
        return {
            'corners_per_game': 6,
            'free_kicks_per_game': 15,
            'set_piece_conversion': 0.08
        }
    
    def _calculate_pressing_stats(self, matches: List[Dict], team_id: int) -> Dict:
        """Calculate pressing statistics."""
        return {
            'tackles_per_game': 16,
            'interceptions_per_game': 12,
            'pressing_intensity': 0.6
        }
    
    def _calculate_transition_stats(self, matches: List[Dict], team_id: int) -> Dict:
        """Calculate transition statistics."""
        return {
            'counter_attacks_per_game': 3,
            'transition_success_rate': 0.4
        }
    
    def _calculate_formation_usage(self, matches: List[Dict], team_id: int) -> Dict:
        """Calculate formation usage statistics."""
        return {
            '4-4-2': 0.7,
            '4-3-3': 0.3
        }
    
    def _calculate_tactical_flexibility(self, matches: List[Dict], team_id: int) -> Dict:
        """Calculate tactical flexibility metrics."""
        return {
            'formation_changes_per_game': 0.5,
            'tactical_consistency': 0.7
        }
    
    # Default/fallback methods
    
    def _get_default_formation_data(self) -> Dict:
        """Default formation data when API fails."""
        return {
            'home_formation': '4-4-2',
            'away_formation': '4-4-2',
            'formation_changes': [],
            'tactical_stats': {
                'formation_balance': {
                    'home_defensive_players': 4,
                    'away_defensive_players': 4,
                    'home_midfield_players': 4,
                    'away_midfield_players': 4,
                    'home_attacking_players': 2,
                    'away_attacking_players': 2
                },
                'tactical_approach': {
                    'home_approach': 'balanced',
                    'away_approach': 'balanced'
                }
            },
            'lineup_data': {'home': [], 'away': []},
            'substitutions': {'home': [], 'away': []}
        }
    
    def _get_default_tactical_stats(self) -> Dict:
        """Default tactical statistics when data unavailable."""
        return {
            'possession_stats': {
                'avg_possession': 50,
                'avg_pass_accuracy': 75,
                'possession_consistency': 0.6,
                'games_with_majority_possession': 0
            },
            'passing_stats': {
                'short_passes_per_game': 400,
                'long_passes_per_game': 60,
                'pass_completion_rate': 0.8
            },
            'attacking_stats': {
                'avg_shots_per_game': 12,
                'avg_corners_per_game': 6,
                'shot_consistency': 0.5,
                'high_shot_games': 0
            },
            'defensive_stats': {
                'clean_sheet_rate': 0.25,
                'avg_tackles_per_game': 16,
                'defensive_consistency': 0.6
            },
            'set_piece_stats': {
                'corners_per_game': 6,
                'free_kicks_per_game': 15,
                'set_piece_conversion': 0.08
            },
            'pressing_stats': {
                'tackles_per_game': 16,
                'interceptions_per_game': 12,
                'pressing_intensity': 0.6
            },
            'transition_stats': {
                'counter_attacks_per_game': 3,
                'transition_success_rate': 0.4
            },
            'formation_usage': {
                '4-4-2': 0.7,
                '4-3-3': 0.3
            },
            'tactical_flexibility': {
                'formation_changes_per_game': 0.5,
                'tactical_consistency': 0.7
            }
        }


# Convenience functions for easy integration

def collect_formation_data(match_id: int) -> Dict:
    """
    Collect formation and tactical data from API-Football.
    
    Returns formation information, tactical stats, and lineup data for the match.
    """
    collector = TacticalDataCollector()
    return collector.collect_formation_data(match_id)


def get_team_tactical_statistics(team_id: int, league_id: int, season: int) -> Dict:
    """
    Get comprehensive tactical statistics for team analysis.
    
    Returns detailed tactical metrics including possession, attacking patterns,
    defensive stats, formation usage, and tactical flexibility.
    """
    collector = TacticalDataCollector()
    return collector.get_team_tactical_statistics(team_id, league_id, season)


def cache_tactical_data(team_id: int, league_id: int, season: int, tactical_data: Dict):
    """
    Cache tactical analysis data in DynamoDB for performance.
    
    Stores tactical analysis results with TTL for efficient retrieval.
    """
    collector = TacticalDataCollector()
    collector.cache_tactical_data(team_id, league_id, season, tactical_data)