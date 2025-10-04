"""
API client for interacting with API-Football external service.
Consolidates all external API calls with consistent retry logic and error handling.
"""

import os
import random
import requests
import time
from datetime import datetime, timedelta

from ..utils.constants import (
    API_FOOTBALL_BASE_URL,
    API_FOOTBALL_HOST,
    DEFAULT_MAX_RETRIES,
    MIN_WAIT_TIME,
    MAX_WAIT_TIME
)


# Get API Keys
rapidapi_key = os.getenv('RAPIDAPI_KEY')


def _make_api_request(url, params=None, headers=None, max_retries=DEFAULT_MAX_RETRIES):
    """
    Base method for making API requests with retry logic for 429 errors.
    
    Args:
        url: API endpoint URL
        params: Query parameters
        headers: Request headers
        max_retries: Maximum retry attempts
        
    Returns:
        JSON response data or None if failed
    """
    if headers is None:
        headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": API_FOOTBALL_HOST
        }
    
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'response' not in data:
                        print(f"Warning: 'response' key missing in API response. Full response: {data}")
                        return {"response": {}}
                    return data
                except Exception as e:
                    print(f"Error parsing API response: {e}")
                    print(f"Response content: {response.text[:200]}...")
                    return {"response": {}}
            elif response.status_code == 429:
                wait_time = random.randint(MIN_WAIT_TIME, MAX_WAIT_TIME)
                print(f"Received 429. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                retries += 1
            else:
                print(f"Error in API call: Status code {response.status_code}")
                print(f"Response content: {response.text}")
                return {"response": {}}
        except requests.exceptions.RequestException as e:
            print(f"Request exception: {e}")
            return {"response": {}}
    
    print("Max retries reached. Request failed.")
    return {"response": {}}


def get_league_start_date(league_id, max_retries=DEFAULT_MAX_RETRIES):
    """
    Fetch the start date of the current season for a given league.
    
    Args:
        league_id: The league ID
        max_retries: Maximum number of retries for 429 errors
        
    Returns:
        The start date of the league season (format: YYYY-MM-DD) or None if not found
    """
    url = f"{API_FOOTBALL_BASE_URL}/leagues"
    params = {"id": league_id, "current": "true"}
    
    data = _make_api_request(url, params, max_retries=max_retries)
    
    if not data or "response" not in data or not data["response"]:
        print("Error: Unexpected API response format or no data found")
        return None
    
    try:
        # Extract the start date of the current season
        seasons = data["response"][0].get("seasons", [])
        for season in seasons:
            if season.get("current"):
                return season.get("start")
    except (IndexError, KeyError, TypeError):
        print("Error: Failed to extract league start date")
        return None
    
    return None


def get_team_statistics(league_id, season, team_id, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get team statistics for a specific league, season, and team.
    
    Args:
        league_id: League identifier
        season: Season year
        team_id: Team identifier
        max_retries: Maximum retry attempts
        
    Returns:
        API response with team statistics
    """
    url = f"{API_FOOTBALL_BASE_URL}/teams/statistics"
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    params = {
        "league": str(league_id),
        "season": str(season),
        "team": str(team_id),
        "date": yesterday
    }
    
    data = _make_api_request(url, params, max_retries=max_retries)
    
    # Handle list response format
    if data and isinstance(data.get('response'), list):
        if len(data['response']) > 0:
            print("Converting response from list to dict (taking first item)")
            data = {"response": data['response'][0]}
        else:
            print("Empty response list received")
            data = {"response": {}}
    
    return data


def get_venue_id(team_id, league_id, season, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get the venue ID for a given team in a league and season.
    
    Args:
        team_id: API-Football team ID
        league_id: API-Football league ID
        season: Season year
        max_retries: Maximum times to retry for HTTP 429
        
    Returns:
        Venue ID or None if not found
        
    Raises:
        Exception: Descriptive message if unable to fetch or parse the venue ID
    """
    url = f"{API_FOOTBALL_BASE_URL}/teams"
    params = {
        "id": str(team_id),
        "league": str(league_id),
        "season": str(season)
    }
    
    data = _make_api_request(url, params, max_retries=max_retries)
    
    if not data or "response" not in data or not data["response"]:
        raise Exception(f"No response data for team {team_id} in league {league_id}, season {season}")
    
    try:
        venue_info = data["response"][0]["venue"]
        venue_id = venue_info["id"]
        venue_name = venue_info["name"]
        venue_city = venue_info["city"]
        
        return {
            "venue_id": venue_id,
            "venue_name": venue_name,
            "venue_city": venue_city
        }
    except (KeyError, IndexError, TypeError) as e:
        raise Exception(f"Failed to parse venue data for team {team_id}: {e}")


def get_league_teams(league_id, season, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get all teams in a specific league and season.
    
    Args:
        league_id: League identifier
        season: Season year
        max_retries: Maximum retry attempts
        
    Returns:
        List of teams in the league
    """
    url = f"{API_FOOTBALL_BASE_URL}/teams"
    params = {
        "league": str(league_id),
        "season": str(season)
    }
    
    data = _make_api_request(url, params, max_retries=max_retries)
    
    if not data or "response" not in data:
        print(f"No teams data found for league {league_id}")
        return []
    
    teams = []
    for team_data in data["response"]:
        teams.append({
            "team_id": team_data["team"]["id"],
            "team_name": team_data["team"]["name"]
        })
    
    return teams


def get_last_five_games(team_id, league_id, season, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get the last five games for a team in a specific league and season.
    
    Args:
        team_id: Team identifier
        league_id: League identifier  
        season: Season year
        max_retries: Maximum retry attempts
        
    Returns:
        List of last five games or empty list if not found
    """
    url = f"{API_FOOTBALL_BASE_URL}/fixtures"
    params = {
        "team": str(team_id),
        "league": str(league_id),
        "season": str(season),
        "last": "5"
    }
    
    data = _make_api_request(url, params, max_retries=max_retries)
    
    if not data or "response" not in data:
        return []
    
    games = []
    for fixture in data["response"]:
        games.append({
            "fixture_id": fixture["fixture"]["id"],
            "date": fixture["fixture"]["date"],
            "home_team": fixture["teams"]["home"]["name"],
            "away_team": fixture["teams"]["away"]["name"],
            "home_goals": fixture["goals"]["home"],
            "away_goals": fixture["goals"]["away"]
        })
    
    return games


def get_head_to_head(home_team_id, away_team_id, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get head-to-head record between two teams.
    
    Args:
        home_team_id: Home team identifier
        away_team_id: Away team identifier
        max_retries: Maximum retry attempts
        
    Returns:
        Head-to-head fixture data
    """
    url = f"{API_FOOTBALL_BASE_URL}/fixtures/headtohead"
    params = {
        "h2h": f"{home_team_id}-{away_team_id}"
    }
    
    data = _make_api_request(url, params, max_retries=max_retries)
    
    if not data or "response" not in data:
        return []
    
    return data["response"]


def get_injured_players(fixture_id, date, max_retries=DEFAULT_MAX_RETRIES):
    """
    Fetch a list of injured players for a given fixture on a specific date.
    
    Args:
        fixture_id: The ID of the fixture
        date: The date of the fixture in 'YYYY-MM-DD' format
        max_retries: Maximum retry attempts on HTTP 429
        
    Returns:
        A list of dictionaries containing details of injured players or an error message
    """
    url = f"{API_FOOTBALL_BASE_URL}/injuries"
    params = {
        "fixture": str(fixture_id),
        "date": date
    }
    
    data = _make_api_request(url, params, max_retries=max_retries)
    
    if not data or "response" not in data:
        return []
    
    return data["response"]


def fetch_team_match_data(league_id, season, team_id, from_date, max_retries=DEFAULT_MAX_RETRIES):
    """
    Fetch match data for a specific team in a league from a given date.
    
    Args:
        league_id: League identifier
        season: Season year
        team_id: Team identifier
        from_date: Start date for fetching matches
        max_retries: Maximum retry attempts
        
    Returns:
        Tuple of (team_parameters, match_details) or (None, None) if failed
    """
    url = f"{API_FOOTBALL_BASE_URL}/fixtures"
    params = {
        "league": str(league_id),
        "season": str(season),
        "team": str(team_id),
        "from": from_date
    }
    
    data = _make_api_request(url, params, max_retries=max_retries)
    
    if not data or "response" not in data or not data["response"]:
        print(f"No fixtures found for team {team_id}")
        return None, None
    
    goals_scored_raw = []
    goals_conceded_raw = []
    games_scored_raw = []
    games_cleanSheet_raw = []
    match_details = []

    for match in data["response"]:
        if (
            "goals" in match and
            match["goals"]["home"] is not None and
            match["goals"]["away"] is not None
        ):
            home_team = match["teams"]["home"]["id"]
            away_team = match["teams"]["away"]["id"]
            is_home = team_id == home_team

            if is_home:
                goals_scored = match["goals"]["home"]
                goals_conceded = match["goals"]["away"]
            else:
                goals_scored = match["goals"]["away"]
                goals_conceded = match["goals"]["home"]

            goals_scored_raw.append(goals_scored)
            goals_conceded_raw.append(goals_conceded)
            games_scored_raw.append(1 if goals_scored > 0 else 0)
            games_cleanSheet_raw.append(1 if goals_conceded == 0 else 0)
            match_details.append([goals_scored, goals_conceded, is_home])

    total_games_played = len(goals_scored_raw)
    if total_games_played == 0:
        print(f"No valid matches found for team {team_id}")
        return None, None

    team_parameters = [
        goals_scored_raw,
        goals_conceded_raw,
        games_scored_raw,
        games_cleanSheet_raw,
        total_games_played
    ]

    return team_parameters, match_details


def get_fixtures_goals(league_id, start_timestamp, end_timestamp, max_retries=DEFAULT_MAX_RETRIES):
    """
    Fetch fixture goals for a specific league within a time range.
    Enhanced version from checkScores.py functionality.
    
    Args:
        league_id: League identifier
        start_timestamp: Start timestamp
        end_timestamp: End timestamp
        max_retries: Maximum retry attempts
        
    Returns:
        List of fixture data with goals
    """
    url = f"{API_FOOTBALL_BASE_URL}/fixtures"
    params = {
        "league": str(league_id),
        "from": datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d'),
        "to": datetime.fromtimestamp(end_timestamp).strftime('%Y-%m-%d')
    }
    
    data = _make_api_request(url, params, max_retries=max_retries)
    
    if not data or "response" not in data:
        return []
    
    fixtures = []
    for fixture in data["response"]:
        if fixture["goals"]["home"] is not None and fixture["goals"]["away"] is not None:
            fixtures.append({
                "fixture_id": fixture["fixture"]["id"],
                "home_goals": fixture["goals"]["home"],
                "away_goals": fixture["goals"]["away"],
                "status": fixture["fixture"]["status"]["short"]
            })
    
    return fixtures


def get_next_fixture(team_id, current_fixture_id, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get the next fixture for a team after the current fixture.
    
    Args:
        team_id: Team identifier
        current_fixture_id: Current fixture ID to find next after
        max_retries: Maximum retry attempts
        
    Returns:
        Next fixture information or None if not found
    """
    url = f"{API_FOOTBALL_BASE_URL}/fixtures"
    params = {
        "team": str(team_id),
        "next": "5"  # Get next 5 fixtures to find the one after current
    }
    
    data = _make_api_request(url, params, max_retries=max_retries)
    
    if not data or "response" not in data or not data["response"]:
        return None
    
    # Find the fixture that comes after the current one
    for fixture in data["response"]:
        if fixture["fixture"]["id"] != current_fixture_id:
            return {
                "fixture_type": "home" if fixture["teams"]["home"]["id"] == team_id else "away",
                "opponent": fixture["teams"]["away"]["name"] if fixture["teams"]["home"]["id"] == team_id else fixture["teams"]["home"]["name"],
                "date": fixture["fixture"]["date"],
                "league": fixture["league"]["name"]
            }
    
    return None


def get_coach_by_team(team_id, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get current coach/manager information for a team.

    Args:
        team_id: Team identifier
        max_retries: Maximum retry attempts

    Returns:
        Coach information dict or None

    Example response:
        {
            'id': 1993,
            'name': 'E. ten Hag',
            'firstname': 'Erik',
            'lastname': 'ten Hag',
            'age': 55,
            'birth': {'date': '1970-02-02', 'place': 'Haaksbergen', 'country': 'Netherlands'},
            'nationality': 'Netherlands',
            'photo': 'https://...',
            'team': {'id': 33, 'name': 'Manchester United', 'logo': '...'},
            'career': [...]  # Career history with teams
        }
    """
    url = f"{API_FOOTBALL_BASE_URL}/coachs"
    params = {"team": str(team_id)}

    data = _make_api_request(url, params, max_retries=max_retries)

    if not data or "response" not in data or not data["response"]:
        return None

    # Return current coach (should be first in response)
    coaches = data["response"]
    if coaches:
        return coaches[0]  # Most recent/current coach

    return None


def get_coach_by_id(coach_id, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get coach/manager information by coach ID.

    Args:
        coach_id: Coach identifier
        max_retries: Maximum retry attempts

    Returns:
        Coach information dict or None
    """
    url = f"{API_FOOTBALL_BASE_URL}/coachs"
    params = {"id": str(coach_id)}

    data = _make_api_request(url, params, max_retries=max_retries)

    if not data or "response" not in data or not data["response"]:
        return None

    if data["response"]:
        return data["response"][0]

    return None


def get_fixture_lineups(fixture_id, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get lineups for a specific fixture, including coach information.

    Args:
        fixture_id: Fixture identifier
        max_retries: Maximum retry attempts

    Returns:
        Dict with home and away lineups including coach info

    Example response:
        {
            'home': {
                'team': {...},
                'coach': {'id': 1993, 'name': 'E. ten Hag', 'photo': '...'},
                'formation': '4-2-3-1',
                'startXI': [...],
                'substitutes': [...]
            },
            'away': {...}
        }
    """
    url = f"{API_FOOTBALL_BASE_URL}/fixtures/lineups"
    params = {"fixture": str(fixture_id)}

    data = _make_api_request(url, params, max_retries=max_retries)

    if not data or "response" not in data or not data["response"]:
        return None

    response = data["response"]
    if len(response) >= 2:
        return {
            'home': response[0],
            'away': response[1]
        }

    return None


class APIClient:
    """
    Wrapper class for API client functions to maintain compatibility
    with feature modules that expect a class interface.
    """
    
    def __init__(self):
        pass
    
    def get_league_start_date(self, league_id, max_retries=DEFAULT_MAX_RETRIES):
        return get_league_start_date(league_id, max_retries)
    
    def get_team_statistics(self, league_id, season, team_id, max_retries=DEFAULT_MAX_RETRIES):
        return get_team_statistics(league_id, season, team_id, max_retries)
    
    def get_venue_id(self, team_id, league_id, season, max_retries=DEFAULT_MAX_RETRIES):
        return get_venue_id(team_id, league_id, season, max_retries)
    
    def get_league_teams(self, league_id, season, max_retries=DEFAULT_MAX_RETRIES):
        return get_league_teams(league_id, season, max_retries)
    
    def get_last_five_games(self, team_id, league_id, season, max_retries=DEFAULT_MAX_RETRIES):
        return get_last_five_games(team_id, league_id, season, max_retries)
    
    def get_head_to_head(self, home_team_id, away_team_id, max_retries=DEFAULT_MAX_RETRIES):
        return get_head_to_head(home_team_id, away_team_id, max_retries)
    
    def get_injured_players(self, fixture_id, date, max_retries=DEFAULT_MAX_RETRIES):
        return get_injured_players(fixture_id, date, max_retries)
    
    def fetch_team_match_data(self, league_id, season, team_id, from_date, max_retries=DEFAULT_MAX_RETRIES):
        return fetch_team_match_data(league_id, season, team_id, from_date, max_retries)
    
    def get_fixtures_goals(self, league_id, start_timestamp, end_timestamp, max_retries=DEFAULT_MAX_RETRIES):
        return get_fixtures_goals(league_id, start_timestamp, end_timestamp, max_retries)
    
    def get_next_fixture(self, team_id, current_fixture_id, max_retries=DEFAULT_MAX_RETRIES):
        return get_next_fixture(team_id, current_fixture_id, max_retries)

    def get_coach_by_team(self, team_id, max_retries=DEFAULT_MAX_RETRIES):
        return get_coach_by_team(team_id, max_retries)

    def get_coach_by_id(self, coach_id, max_retries=DEFAULT_MAX_RETRIES):
        return get_coach_by_id(coach_id, max_retries)

    def get_fixture_lineups(self, fixture_id, max_retries=DEFAULT_MAX_RETRIES):
        return get_fixture_lineups(fixture_id, max_retries)