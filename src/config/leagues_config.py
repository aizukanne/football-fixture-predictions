"""
League configuration for fixture ingestion.

Centralizes league data from the original allLeagues configuration.
Provides utilities for accessing league information by country or league ID.

Author: Football Fixture Prediction System
Phase: Fixture Ingestion Implementation
Version: 1.0
"""

import sys
import os
from typing import List, Dict, Optional

# Add project root to path to import leagues.py
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the original leagues configuration
# No fallback - leagues.py must be available in deployment package
from leagues import allLeagues


def get_all_leagues() -> List[Dict]:
    """
    Get all configured leagues in flattened format.
    Maintains compatibility with original code structure.

    Returns:
        List of league dictionaries with country information
    """
    leagues_flat = []

    for country, leagues in allLeagues.items():
        for league in leagues:
            league_with_country = {
                **league,
                'country': country
            }
            leagues_flat.append(league_with_country)

    return leagues_flat


def get_leagues_by_country(country: str) -> List[Dict]:
    """
    Get leagues for a specific country.

    Args:
        country: Country name

    Returns:
        List of league dictionaries for the country
    """
    return allLeagues.get(country, [])


def get_league_info(league_id: int) -> Optional[Dict]:
    """
    Get information for a specific league.

    Args:
        league_id: League identifier

    Returns:
        League dictionary with country info, or None if not found
    """
    for country, leagues in allLeagues.items():
        for league in leagues:
            if league['id'] == league_id:
                return {
                    **league,
                    'country': country
                }
    return None


def get_countries() -> List[str]:
    """
    Get list of all configured countries.

    Returns:
        List of country names
    """
    return list(allLeagues.keys())


def get_league_count() -> int:
    """
    Get total number of configured leagues.

    Returns:
        Total league count
    """
    return sum(len(leagues) for leagues in allLeagues.values())


def get_leagues_by_type(league_type: str) -> List[Dict]:
    """
    Get all leagues of a specific type (League or Cup).

    Args:
        league_type: Type filter ('League', 'Cup', etc.)

    Returns:
        List of leagues matching the type
    """
    filtered_leagues = []

    for country, leagues in allLeagues.items():
        for league in leagues:
            if league.get('type') == league_type:
                league_with_country = {
                    **league,
                    'country': country
                }
                filtered_leagues.append(league_with_country)

    return filtered_leagues


# Print configuration summary when module is imported
def print_config_summary():
    """Print a summary of the leagues configuration."""
    total_leagues = get_league_count()
    total_countries = len(get_countries())
    leagues_only = len(get_leagues_by_type('League'))
    cups_only = len(get_leagues_by_type('Cup'))

    print(f"Leagues Configuration Loaded:")
    print(f"  Total Countries: {total_countries}")
    print(f"  Total Competitions: {total_leagues}")
    print(f"  - Leagues: {leagues_only}")
    print(f"  - Cups: {cups_only}")


# Only print summary if this is being run directly (not during import)
if __name__ == '__main__':
    print_config_summary()
    print("\nSample leagues:")
    for country in list(get_countries())[:5]:  # Show first 5 countries
        leagues = get_leagues_by_country(country)
        print(f"\n{country}:")
        for league in leagues:
            print(f"  - {league['name']} (ID: {league['id']}, Type: {league.get('type', 'Unknown')})")
