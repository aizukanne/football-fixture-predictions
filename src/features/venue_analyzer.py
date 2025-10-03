"""
Stadium and venue-specific analysis module for football predictions.

This module provides venue analysis capabilities including:
- Stadium advantage calculation
- Travel distance impact analysis
- Venue-specific performance tracking
- Surface type advantages
- DynamoDB venue data caching

Phase 2: Home/Away Venue Analysis
Enhanced predictions through detailed venue-specific insights and travel distance impacts.
"""

import requests
import math
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import boto3
from datetime import datetime, timedelta

from ..data.api_client import _make_api_request
from ..data.database_client import dynamodb
from ..infrastructure.version_manager import VersionManager
from ..utils.constants import MINIMUM_GAMES_THRESHOLD, API_FOOTBALL_BASE_URL


class VenueAnalyzer:
    """Main venue analysis class for stadium and venue-specific analysis."""
    
    def __init__(self):
        try:
            self.venue_cache_table = dynamodb.Table('venue_cache')
        except Exception as e:
            print(f"Warning: Could not initialize venue_cache table: {e}")
            self.venue_cache_table = None
        self.version_manager = VersionManager()
        
    def get_venue_details(self, venue_id: int) -> Dict:
        """
        Get detailed venue information from API-Football with caching.
        
        Args:
            venue_id: API-Football venue ID
            
        Returns:
            Dict with venue capacity, surface type, location coordinates
            {
                'venue_id': int,
                'venue_name': str,
                'capacity': int,
                'surface': str,
                'coordinates': {'latitude': Decimal, 'longitude': Decimal},
                'climate_data': {'altitude': Decimal, 'typical_weather': str}
            }
        """
        # Check cache first
        try:
            response = self.venue_cache_table.get_item(Key={'venue_id': venue_id})
            if 'Item' in response:
                cached_item = response['Item']
                # Check if cache is still valid (7 days TTL)
                cached_at = datetime.fromisoformat(cached_item.get('cached_at', ''))
                if datetime.now() - cached_at < timedelta(days=7):
                    return cached_item
        except Exception as e:
            print(f"Cache lookup failed for venue {venue_id}: {e}")
        
        # Fetch from API if not in cache or expired
        venue_data = self._fetch_venue_from_api(venue_id)
        
        # Cache the result
        if venue_data:
            self.cache_venue_data(venue_id, venue_data)
            
        return venue_data
    
    def _fetch_venue_from_api(self, venue_id: int) -> Dict:
        """
        Fetch venue details from API-Football.
        
        Args:
            venue_id: API-Football venue ID
            
        Returns:
            Venue details dict or empty dict if failed
        """
        try:
            # Use API-Football venues endpoint
            url = f"{API_FOOTBALL_BASE_URL}/venues"
            params = {'id': venue_id}
            api_data = _make_api_request(url, params)
            
            if not api_data or 'response' not in api_data or not api_data['response']:
                return {}
                
            venue_info = api_data['response'][0]
            
            # Extract and format venue data
            venue_data = {
                'venue_id': venue_id,
                'venue_name': venue_info.get('name', ''),
                'capacity': int(venue_info.get('capacity', 0)),
                'surface': venue_info.get('surface', 'grass').lower(),
                'coordinates': {
                    'latitude': Decimal(str(venue_info.get('latitude', 0))),
                    'longitude': Decimal(str(venue_info.get('longitude', 0)))
                },
                'climate_data': {
                    'altitude': Decimal(str(venue_info.get('altitude', 0))),
                    'typical_weather': venue_info.get('weather', 'temperate')
                },
                'cached_at': datetime.now().isoformat(),
                'ttl': int((datetime.now() + timedelta(days=7)).timestamp())
            }
            
            return venue_data
            
        except Exception as e:
            print(f"Error fetching venue {venue_id} from API: {e}")
            return {}
    
    def calculate_stadium_advantage(self, team_id: int, venue_id: int, season: int) -> Decimal:
        """
        Calculate team's specific advantage at their home stadium.
        
        Factors considered:
        - Historical performance at venue
        - Crowd capacity and atmosphere impact
        - Surface type advantages (grass vs artificial)
        - Altitude and climate factors
        
        Args:
            team_id: Team ID
            venue_id: Venue ID
            season: Season year
            
        Returns:
            Stadium advantage multiplier (typically 0.8-1.2)
        """
        try:
            # Get venue details
            venue_details = self.get_venue_details(venue_id)
            if not venue_details:
                return Decimal('1.0')  # Neutral if no venue data
            
            # Get venue-specific performance
            venue_performance = self.get_venue_specific_performance(team_id, venue_id, season)
            
            # Base advantage from capacity (larger stadiums = more atmosphere)
            capacity = venue_details.get('capacity', 0)
            capacity_advantage = self._calculate_capacity_advantage(capacity)
            
            # Surface advantage
            surface_advantage = self._calculate_surface_advantage(team_id, venue_details.get('surface', 'grass'), season)
            
            # Altitude advantage (higher altitude affects visiting teams more)
            altitude = venue_details.get('climate_data', {}).get('altitude', 0)
            altitude_advantage = self._calculate_altitude_advantage(altitude)
            
            # Historical performance at venue
            historical_advantage = self._calculate_historical_venue_advantage(venue_performance)
            
            # Combine all factors
            total_advantage = (
                capacity_advantage * 
                surface_advantage * 
                altitude_advantage * 
                historical_advantage
            )
            
            # Clamp to reasonable bounds (0.8 to 1.3)
            return max(Decimal('0.8'), min(Decimal('1.3'), total_advantage))
            
        except Exception as e:
            print(f"Error calculating stadium advantage for team {team_id} at venue {venue_id}: {e}")
            return Decimal('1.0')
    
    def calculate_travel_distance(self, home_venue_id: int, away_team_id: int) -> Decimal:
        """
        Calculate travel distance impact for away team.
        
        Uses venue coordinates to calculate:
        - Distance traveled
        - Travel fatigue factor
        - Time zone changes impact
        
        Args:
            home_venue_id: Home team's venue ID
            away_team_id: Away team ID
            
        Returns:
            Travel distance in kilometers
        """
        try:
            # Get home venue coordinates
            home_venue = self.get_venue_details(home_venue_id)
            if not home_venue or 'coordinates' not in home_venue:
                return Decimal('0')
            
            # Get away team's home venue
            away_venue_id = self._get_team_primary_venue(away_team_id)
            if not away_venue_id:
                return Decimal('0')
            
            away_venue = self.get_venue_details(away_venue_id)
            if not away_venue or 'coordinates' not in away_venue:
                return Decimal('0')
            
            # Calculate haversine distance
            home_lat = home_venue['coordinates']['latitude']
            home_lon = home_venue['coordinates']['longitude']
            away_lat = away_venue['coordinates']['latitude']
            away_lon = away_venue['coordinates']['longitude']
            
            distance = self._haversine_distance(home_lat, home_lon, away_lat, away_lon)
            return distance
            
        except Exception as e:
            print(f"Error calculating travel distance for team {away_team_id} to venue {home_venue_id}: {e}")
            return Decimal('0')
    
    def get_venue_specific_performance(self, team_id: int, venue_id: int, season: int) -> Dict:
        """
        Analyze team's historical performance at specific venue.
        
        Returns venue-specific stats:
        - Goals scored/conceded at venue
        - Win/loss record at venue
        - Performance vs venue surface type
        
        Args:
            team_id: Team ID
            venue_id: Venue ID
            season: Season year
            
        Returns:
            Dict with venue performance metrics
        """
        try:
            # This would typically query match database for venue-specific performance
            # For now, return structure with defaults
            return {
                'matches_played': 0,
                'goals_scored': Decimal('0'),
                'goals_conceded': Decimal('0'),
                'wins': 0,
                'draws': 0,
                'losses': 0,
                'win_rate': Decimal('0'),
                'goals_per_game': Decimal('0'),
                'goals_conceded_per_game': Decimal('0'),
                'points_per_game': Decimal('0')
            }
            
        except Exception as e:
            print(f"Error getting venue performance for team {team_id} at venue {venue_id}: {e}")
            return {}
    
    def cache_venue_data(self, venue_id: int, venue_data: Dict):
        """
        Cache venue data in DynamoDB for performance.
        Table: venue_cache
        TTL: 7 days (venue details rarely change)
        
        Args:
            venue_id: Venue ID
            venue_data: Venue data dictionary to cache
        """
        try:
            if self.venue_cache_table:
                # Add TTL and caching timestamp
                venue_data['cached_at'] = datetime.now().isoformat()
                venue_data['ttl'] = int((datetime.now() + timedelta(days=7)).timestamp())
                
                self.venue_cache_table.put_item(Item=venue_data)
                print(f"Cached venue data for venue {venue_id}")
            else:
                print(f"Warning: Venue cache table not available, skipping cache for venue {venue_id}")
            
        except Exception as e:
            print(f"Error caching venue data for venue {venue_id}: {e}")
    
    def _calculate_capacity_advantage(self, capacity: int) -> Decimal:
        """
        Calculate home advantage based on stadium capacity.
        
        Args:
            capacity: Stadium capacity
            
        Returns:
            Capacity advantage multiplier (1.0-1.1)
        """
        if capacity == 0:
            return Decimal('1.0')
        
        # Normalize capacity (typical range 10k-80k)
        # Larger stadiums provide more atmosphere advantage
        normalized = min(capacity / 80000, 1.0)
        advantage = 1.0 + (normalized * 0.05)  # Up to 5% advantage for largest stadiums
        
        return Decimal(str(advantage))
    
    def _calculate_surface_advantage(self, team_id: int, surface: str, season: int) -> Decimal:
        """
        Calculate advantage based on playing surface preference.
        
        Args:
            team_id: Team ID
            surface: Surface type ('grass' or 'artificial')
            season: Season year
            
        Returns:
            Surface advantage multiplier
        """
        # This would analyze team's historical performance on different surfaces
        # For now, assume neutral
        return Decimal('1.0')
    
    def _calculate_altitude_advantage(self, altitude: Decimal) -> Decimal:
        """
        Calculate advantage from altitude (affects visiting teams more).
        
        Args:
            altitude: Altitude in meters
            
        Returns:
            Altitude advantage multiplier
        """
        if altitude < 500:  # Sea level to 500m - minimal impact
            return Decimal('1.0')
        elif altitude < 1000:  # 500-1000m - slight advantage
            return Decimal('1.02')
        elif altitude < 2000:  # 1000-2000m - moderate advantage
            return Decimal('1.05')
        else:  # 2000m+ - significant advantage
            return Decimal('1.08')
    
    def _calculate_historical_venue_advantage(self, venue_performance: Dict) -> Decimal:
        """
        Calculate advantage based on historical performance at venue.
        
        Args:
            venue_performance: Historical performance data
            
        Returns:
            Historical advantage multiplier
        """
        if not venue_performance or venue_performance.get('matches_played', 0) < 5:
            return Decimal('1.0')  # Insufficient data
        
        win_rate = venue_performance.get('win_rate', Decimal('0'))
        points_per_game = venue_performance.get('points_per_game', Decimal('0'))
        
        # Teams with good venue record get advantage
        # Average win rate ~0.5 for home teams
        advantage = 1.0 + ((float(win_rate) - 0.5) * 0.2)
        
        return Decimal(str(max(0.9, min(1.2, advantage))))
    
    def _get_team_primary_venue(self, team_id: int) -> Optional[int]:
        """
        Get team's primary home venue ID.
        
        Args:
            team_id: Team ID
            
        Returns:
            Primary venue ID or None if not found
        """
        # This would query database for team's home venue
        # For now, return None to handle gracefully
        return None
    
    def _haversine_distance(self, lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> Decimal:
        """
        Calculate distance between two points using Haversine formula.
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            Distance in kilometers
        """
        # Convert to radians
        lat1_rad = math.radians(float(lat1))
        lon1_rad = math.radians(float(lon1))
        lat2_rad = math.radians(float(lat2))
        lon2_rad = math.radians(float(lon2))
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in kilometers
        r = 6371
        
        return Decimal(str(r * c))


# Convenience functions for direct access
def get_venue_details(venue_id: int) -> Dict:
    """
    Get detailed venue information from API-Football.
    
    Returns:
        Dict with venue capacity, surface type, location coordinates
    """
    analyzer = VenueAnalyzer()
    return analyzer.get_venue_details(venue_id)


def calculate_stadium_advantage(team_id: int, venue_id: int, season: int) -> Decimal:
    """
    Calculate team's specific advantage at their home stadium.
    
    Factors:
    - Historical performance at venue
    - Crowd capacity and atmosphere impact
    - Surface type advantages (grass vs artificial)
    - Altitude and climate factors
    """
    analyzer = VenueAnalyzer()
    return analyzer.calculate_stadium_advantage(team_id, venue_id, season)


def calculate_travel_distance(home_venue_id: int, away_team_id: int) -> Decimal:
    """
    Calculate travel distance impact for away team.
    
    Uses venue coordinates to calculate:
    - Distance traveled
    - Travel fatigue factor
    - Time zone changes impact
    """
    analyzer = VenueAnalyzer()
    return analyzer.calculate_travel_distance(home_venue_id, away_team_id)


def get_venue_specific_performance(team_id: int, venue_id: int, season: int) -> Dict:
    """
    Analyze team's historical performance at specific venue.
    
    Returns venue-specific stats:
    - Goals scored/conceded at venue
    - Win/loss record at venue
    - Performance vs venue surface type
    """
    analyzer = VenueAnalyzer()
    return analyzer.get_venue_specific_performance(team_id, venue_id, season)


def cache_venue_data(venue_id: int, venue_data: Dict):
    """
    Cache venue data in DynamoDB for performance.
    Table: venue_cache
    TTL: 7 days (venue details rarely change)
    """
    analyzer = VenueAnalyzer()
    return analyzer.cache_venue_data(venue_id, venue_data)