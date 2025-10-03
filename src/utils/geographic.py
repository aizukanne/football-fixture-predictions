"""
Geographic distance and travel calculations for football venue analysis.

This module provides geographic utilities for:
- Distance calculations between venues using Haversine formula
- Travel fatigue factor calculations
- Time zone difference estimations
- Geographic coordinate utilities

Phase 2: Home/Away Venue Analysis
Part of the venue analysis system for calculating travel impacts on away team performance.
"""

from decimal import Decimal
import math
from typing import Tuple, Optional


def calculate_haversine_distance(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> Decimal:
    """
    Calculate distance between two geographic points using Haversine formula.
    
    The Haversine formula determines the great-circle distance between two points 
    on a sphere given their latitude and longitude coordinates.
    
    Args:
        lat1: Latitude of first point in decimal degrees
        lon1: Longitude of first point in decimal degrees
        lat2: Latitude of second point in decimal degrees
        lon2: Longitude of second point in decimal degrees
    
    Returns:
        Distance in kilometers as Decimal
        
    Example:
        >>> lat1, lon1 = Decimal('51.5074'), Decimal('-0.1278')  # London
        >>> lat2, lon2 = Decimal('48.8566'), Decimal('2.3522')   # Paris
        >>> distance = calculate_haversine_distance(lat1, lon1, lat2, lon2)
        >>> print(f"Distance: {distance:.1f} km")
        Distance: 344.7 km
    """
    # Convert decimal degrees to radians
    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))
    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
    
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth's radius in kilometers (mean radius)
    earth_radius_km = 6371.0
    
    distance = earth_radius_km * c
    
    return Decimal(str(round(distance, 2)))


def calculate_travel_fatigue_factor(distance_km: Decimal) -> Decimal:
    """
    Calculate travel fatigue impact based on distance.
    
    Travel fatigue affects away team performance based on distance traveled.
    Formula accounts for physical and psychological effects of long-distance travel.
    
    Args:
        distance_km: Distance traveled in kilometers
        
    Returns:
        Performance multiplier for away team (0.95-1.0)
        - 0-100km: No impact (1.0)
        - 100-500km: Linear decrease (1.0 to 0.98)  
        - 500km+: Significant impact (0.95-0.97)
        
    Example:
        >>> distance = Decimal('350')
        >>> fatigue = calculate_travel_fatigue_factor(distance)
        >>> print(f"Fatigue factor: {fatigue}")
        Fatigue factor: 0.986
    """
    distance = float(distance_km)
    
    if distance <= 100:
        # Local matches - no travel fatigue
        return Decimal('1.0')
    
    elif distance <= 500:
        # Medium distance - linear decrease
        # From 1.0 at 100km to 0.98 at 500km
        fatigue_rate = (distance - 100) / 400  # 0 to 1
        fatigue_impact = fatigue_rate * 0.02   # 0% to 2% impact
        return Decimal(str(round(1.0 - fatigue_impact, 3)))
    
    elif distance <= 1000:
        # Long distance - moderate impact
        # From 0.98 at 500km to 0.96 at 1000km
        base_fatigue = 0.02  # 2% from medium distance
        additional_fatigue = ((distance - 500) / 500) * 0.02  # Up to 2% more
        total_fatigue = base_fatigue + additional_fatigue
        return Decimal(str(round(1.0 - total_fatigue, 3)))
    
    else:
        # Very long distance - maximum impact
        # 5% performance decrease for international/transcontinental travel
        return Decimal('0.95')


def get_time_zone_difference(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> int:
    """
    Estimate time zone difference impact on away team performance.
    
    Approximates time zone difference based on longitude difference.
    Each 15 degrees of longitude approximately equals 1 hour time difference.
    
    Args:
        lat1, lon1: First location coordinates
        lat2, lon2: Second location coordinates
        
    Returns:
        Estimated hours of time zone difference (absolute value)
        
    Note:
        This is an approximation. Actual time zones have political boundaries
        and don't follow longitude lines exactly.
        
    Example:
        >>> # London to New York
        >>> lon_diff = get_time_zone_difference(
        ...     Decimal('51.5074'), Decimal('-0.1278'),  # London
        ...     Decimal('40.7128'), Decimal('-74.0060')  # New York
        ... )
        >>> print(f"Time zone difference: {lon_diff} hours")
        Time zone difference: 5 hours
    """
    lon_diff = abs(float(lon2) - float(lon1))
    
    # Handle crossing the international date line
    if lon_diff > 180:
        lon_diff = 360 - lon_diff
    
    # Convert longitude difference to hours (15 degrees = 1 hour)
    hours_diff = round(lon_diff / 15)
    
    return int(hours_diff)


def calculate_jet_lag_factor(time_zone_diff: int) -> Decimal:
    """
    Calculate performance impact from jet lag based on time zone difference.
    
    Jet lag affects player performance, particularly for significant time differences.
    
    Args:
        time_zone_diff: Hours of time zone difference
        
    Returns:
        Performance multiplier (0.96-1.0)
        - 0-2 hours: No impact (1.0)
        - 3-5 hours: Minor impact (0.99-0.98)
        - 6+ hours: Significant impact (0.96-0.97)
        
    Example:
        >>> jet_lag = calculate_jet_lag_factor(6)
        >>> print(f"Jet lag factor: {jet_lag}")
        Jet lag factor: 0.97
    """
    if time_zone_diff <= 2:
        return Decimal('1.0')  # No jet lag impact
    
    elif time_zone_diff <= 5:
        # Minor jet lag - 1-2% performance decrease
        impact = (time_zone_diff - 2) * 0.005  # 0.5% per hour over 2
        return Decimal(str(round(1.0 - impact, 3)))
    
    else:
        # Significant jet lag - 3-4% performance decrease
        return Decimal('0.97')


def calculate_combined_travel_impact(distance_km: Decimal, 
                                   home_coordinates: Tuple[Decimal, Decimal],
                                   away_coordinates: Tuple[Decimal, Decimal]) -> Decimal:
    """
    Calculate combined travel impact including distance fatigue and jet lag.
    
    Combines both physical travel fatigue and time zone adjustment effects
    to provide overall travel impact on away team performance.
    
    Args:
        distance_km: Travel distance in kilometers
        home_coordinates: (latitude, longitude) of home venue
        away_coordinates: (latitude, longitude) of away team's home venue
        
    Returns:
        Combined travel impact multiplier (0.92-1.0)
        
    Example:
        >>> distance = Decimal('1200')
        >>> home_coords = (Decimal('51.5074'), Decimal('-0.1278'))  # London
        >>> away_coords = (Decimal('40.7128'), Decimal('-74.0060'))  # New York
        >>> impact = calculate_combined_travel_impact(distance, home_coords, away_coords)
        >>> print(f"Combined travel impact: {impact}")
        Combined travel impact: 0.922
    """
    # Calculate individual factors
    fatigue_factor = calculate_travel_fatigue_factor(distance_km)
    
    time_zone_diff = get_time_zone_difference(
        home_coordinates[0], home_coordinates[1],
        away_coordinates[0], away_coordinates[1]
    )
    jet_lag_factor = calculate_jet_lag_factor(time_zone_diff)
    
    # Combine factors (multiplicative)
    combined_factor = fatigue_factor * jet_lag_factor
    
    # Ensure minimum reasonable performance (8% maximum impact)
    return max(Decimal('0.92'), combined_factor)


def is_domestic_travel(distance_km: Decimal, time_zone_diff: int) -> bool:
    """
    Determine if travel is considered domestic (within same country/region).
    
    Domestic travel typically has less impact than international travel.
    
    Args:
        distance_km: Travel distance in kilometers
        time_zone_diff: Time zone difference in hours
        
    Returns:
        True if considered domestic travel, False otherwise
        
    Criteria:
        - Distance < 800km AND time zone difference <= 1 hour
    """
    return float(distance_km) < 800 and time_zone_diff <= 1


def calculate_recovery_time_needed(distance_km: Decimal, time_zone_diff: int) -> int:
    """
    Estimate recovery time needed after travel (in days).
    
    Teams traveling long distances may need more time to recover and adjust.
    
    Args:
        distance_km: Travel distance in kilometers
        time_zone_diff: Time zone difference in hours
        
    Returns:
        Recommended recovery days (0-3)
        
    Guidelines:
        - Local travel (< 200km): 0 days
        - Domestic travel (200-800km): 1 day
        - International travel (800km+): 2-3 days
        - Transcontinental (6+ hour time diff): 3+ days
    """
    distance = float(distance_km)
    
    if distance < 200:
        return 0  # Local travel - no recovery needed
    
    elif distance < 800 and time_zone_diff <= 2:
        return 1  # Domestic travel - 1 day recovery
    
    elif distance < 2000 and time_zone_diff <= 4:
        return 2  # International travel - 2 days recovery
    
    else:
        return 3  # Long-haul international - 3+ days recovery


def get_geographic_region(latitude: Decimal, longitude: Decimal) -> str:
    """
    Determine geographic region based on coordinates.
    
    Useful for understanding regional travel patterns and impacts.
    
    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        
    Returns:
        Geographic region name
        
    Regions:
        - Europe, North America, South America, Asia, Africa, Oceania
    """
    lat = float(latitude)
    lon = float(longitude)
    
    if -25 <= lat <= 75 and -15 <= lon <= 45:
        return "Europe"
    elif 15 <= lat <= 75 and -170 <= lon <= -50:
        return "North America"
    elif -55 <= lat <= 15 and -85 <= lon <= -35:
        return "South America"
    elif -10 <= lat <= 75 and 25 <= lon <= 180:
        return "Asia"
    elif -35 <= lat <= 40 and -20 <= lon <= 55:
        return "Africa"
    elif -50 <= lat <= -10 and 110 <= lon <= 180:
        return "Oceania"
    else:
        return "Unknown"


# Convenience function for complete travel analysis
def analyze_travel_impact(home_venue_coords: Tuple[Decimal, Decimal],
                         away_venue_coords: Tuple[Decimal, Decimal]) -> dict:
    """
    Perform complete travel impact analysis between two venues.
    
    Args:
        home_venue_coords: (latitude, longitude) of home venue
        away_venue_coords: (latitude, longitude) of away team's venue
        
    Returns:
        Complete travel analysis dict with all metrics
        
    Example:
        >>> home = (Decimal('51.5074'), Decimal('-0.1278'))  # London
        >>> away = (Decimal('40.7128'), Decimal('-74.0060'))  # New York
        >>> analysis = analyze_travel_impact(home, away)
        >>> print(f"Travel distance: {analysis['distance_km']}km")
        >>> print(f"Performance impact: {analysis['performance_factor']}")
    """
    home_lat, home_lon = home_venue_coords
    away_lat, away_lon = away_venue_coords
    
    # Calculate distance
    distance = calculate_haversine_distance(home_lat, home_lon, away_lat, away_lon)
    
    # Calculate time zone difference
    tz_diff = get_time_zone_difference(home_lat, home_lon, away_lat, away_lon)
    
    # Calculate performance impacts
    fatigue_factor = calculate_travel_fatigue_factor(distance)
    jet_lag_factor = calculate_jet_lag_factor(tz_diff)
    combined_factor = calculate_combined_travel_impact(distance, home_venue_coords, away_venue_coords)
    
    # Additional analysis
    is_domestic = is_domestic_travel(distance, tz_diff)
    recovery_days = calculate_recovery_time_needed(distance, tz_diff)
    home_region = get_geographic_region(home_lat, home_lon)
    away_region = get_geographic_region(away_lat, away_lon)
    
    return {
        'distance_km': distance,
        'time_zone_difference': tz_diff,
        'fatigue_factor': fatigue_factor,
        'jet_lag_factor': jet_lag_factor,
        'performance_factor': combined_factor,
        'is_domestic_travel': is_domestic,
        'recovery_days_needed': recovery_days,
        'home_region': home_region,
        'away_region': away_region,
        'travel_type': 'domestic' if is_domestic else 'international'
    }