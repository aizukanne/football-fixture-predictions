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
    Base method for making API requests with robust retry logic for 429 and other errors.

    Implements exponential backoff with jitter for 429 (rate limit) errors.

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
    base_wait = MIN_WAIT_TIME

    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)

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
                # Rate limit hit - use exponential backoff with jitter
                retries += 1

                # Check if we have Retry-After header
                retry_after = response.headers.get('Retry-After')
                if retry_after:
                    try:
                        wait_time = int(retry_after)
                        print(f"Received 429 with Retry-After: {wait_time}s")
                    except ValueError:
                        wait_time = base_wait * (2 ** (retries - 1))
                else:
                    # Exponential backoff: MIN_WAIT_TIME * 2^retry
                    wait_time = min(base_wait * (2 ** (retries - 1)), MAX_WAIT_TIME)

                # Add jitter (randomness) to prevent thundering herd
                jitter = random.uniform(0, wait_time * 0.3)
                final_wait = wait_time + jitter

                print(f"Rate limit (429) hit. Retry {retries}/{max_retries}. Waiting {final_wait:.1f}s...")
                time.sleep(final_wait)

            elif response.status_code in [500, 502, 503, 504]:
                # Server errors - retry with backoff
                retries += 1
                wait_time = min(base_wait * (2 ** (retries - 1)), MAX_WAIT_TIME)
                print(f"Server error {response.status_code}. Retry {retries}/{max_retries}. Waiting {wait_time}s...")
                time.sleep(wait_time)

            elif response.status_code == 401:
                # Authentication error - don't retry
                print(f"Authentication error (401): Invalid API key")
                print(f"Response: {response.text}")
                return {"response": {}}

            else:
                # Other errors - don't retry
                print(f"Error in API call: Status code {response.status_code}")
                print(f"Response content: {response.text}")
                return {"response": {}}

        except requests.exceptions.Timeout:
            retries += 1
            wait_time = min(base_wait * (2 ** (retries - 1)), MAX_WAIT_TIME)
            print(f"Request timeout. Retry {retries}/{max_retries}. Waiting {wait_time}s...")
            time.sleep(wait_time)

        except requests.exceptions.RequestException as e:
            print(f"Request exception: {e}")
            return {"response": {}}

    print(f"Max retries ({max_retries}) reached. Request failed.")
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


def get_fixture_events(fixture_id, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get all events (goals, cards, substitutions) for a specific fixture.

    Args:
        fixture_id: Fixture identifier
        max_retries: Maximum retry attempts

    Returns:
        API response with fixture events including:
        - Goal events with detail (Normal Goal, Penalty, Own Goal)
        - Card events (Yellow, Red)
        - Substitution events
        - Time information for each event
        - Player and team information
    """
    url = f"{API_FOOTBALL_BASE_URL}/fixtures/events"
    params = {"fixture": str(fixture_id)}

    data = _make_api_request(url, params, max_retries=max_retries)
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
    Returns legacy-compatible nested structure with teams and scores objects.
    
    Args:
        team_id: Team identifier
        league_id: League identifier
        season: Season year
        max_retries: Maximum retry attempts
        
    Returns:
        List of last five games in legacy format or empty list if not found
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
        # Use legacy-compatible nested structure for backwards compatibility
        games.append({
            'date': fixture["fixture"]["date"],
            'teams': {
                'home': fixture["teams"]["home"]["name"],
                'away': fixture["teams"]["away"]["name"]
            },
            'scores': {
                'home': fixture["goals"]["home"],
                'away': fixture["goals"]["away"]
            }
        })
    
    return games


def get_head_to_head(home_team_id, away_team_id, league_id=None, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get head-to-head record between two teams.
    Returns legacy-compatible simplified structure matching past_fixtures format.
    
    Args:
        home_team_id: Home team identifier
        away_team_id: Away team identifier
        league_id: League identifier to filter by (optional)
        max_retries: Maximum retry attempts
        
    Returns:
        List of head-to-head games in legacy format with nested teams/scores structure
    """
    url = f"{API_FOOTBALL_BASE_URL}/fixtures/headtohead"
    params = {
        "h2h": f"{home_team_id}-{away_team_id}",
        "last": 5  # Limit to last 5 matches
    }
    
    data = _make_api_request(url, params, max_retries=max_retries)
    
    if not data or "response" not in data:
        return []
    
    fixtures = data["response"]
    
    # Filter by league if specified
    if league_id:
        fixtures = [f for f in fixtures if f.get('league', {}).get('id') == league_id]
    
    # Transform to legacy-compatible format (same as past_fixtures)
    games = []
    for fixture in fixtures[:5]:  # Ensure max 5 matches
        games.append({
            'date': fixture['fixture']['date'],
            'teams': {
                'home': fixture['teams']['home']['name'],
                'away': fixture['teams']['away']['name']
            },
            'scores': {
                'home': fixture['goals']['home'],
                'away': fixture['goals']['away']
            }
        })
    
    return games


def get_player_statistics(player_id, team_id, league_id, season, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get statistics for a specific player in a team, league, and season.
    
    Args:
        player_id: Player identifier
        team_id: Team identifier
        league_id: League identifier
        season: Season year
        max_retries: Maximum retry attempts
        
    Returns:
        Player statistics dict or empty dict if not found
    """
    url = f"{API_FOOTBALL_BASE_URL}/players"
    params = {
        "id": str(player_id),
        "team": str(team_id),
        "league": str(league_id),
        "season": str(season)
    }
    
    data = _make_api_request(url, params, max_retries=max_retries)
    
    if not data or "response" not in data or not data.get("results", 0):
        return {}
    
    return data["response"][0] if data["response"] else {}


def extract_player_info(player_data):
    """
    Extract relevant player information from API response.
    
    Args:
        player_data: Player data from API
        
    Returns:
        Dict with player info or empty dict if no statistics
    """
    player_info = player_data.get('player', {})
    player_name = player_info.get('name')
    player_id = player_info.get('id')
    player_photo = player_info.get('photo')

    if 'statistics' in player_data and player_data['statistics']:
        stat = player_data['statistics'][0]
        games = stat.get('games', {})
        position = games.get('position', 'Unknown')
        minutes_played = games.get('minutes', 0) or 0
        player_rating = games.get('rating', 0) or 0

        goals_data = stat.get('goals', {})
        total_goals = goals_data.get('total', 0) or 0
        assists = goals_data.get('assists', 0) or 0
        goal_involvement = total_goals + assists

        shots_data = stat.get('shots', {})
        total_shots = shots_data.get('total', 0) or 0
        shots_on_target = shots_data.get('on', 0) or 0

        dribbles_data = stat.get('dribbles', {})
        dribbles_attempted = dribbles_data.get('attempts', 0) or 0
        dribbles_successful = dribbles_data.get('success', 0) or 0

        duels_data = stat.get('duels', {})
        duels_total = duels_data.get('total', 0) or 0
        duels_won = duels_data.get('won', 0) or 0

        passes_data = stat.get('passes', {})
        key_passes = passes_data.get('key', 0) or 0

        return {
            'id': player_id,
            'name': player_name,
            'position': position,
            'photo': player_photo,
            'minutes': minutes_played,
            'rating': player_rating,
            'goal_involvement': goal_involvement,
            'total_goals': total_goals,
            'assists': assists,
            'total_shots': total_shots,
            'shots_on_target': shots_on_target,
            'dribbles_attempted': dribbles_attempted,
            'dribbles_successful': dribbles_successful,
            'duels_total': duels_total,
            'duels_won': duels_won,
            'key_passes': key_passes
        }

    return {}


def process_injuries(injury_list, home_team_id, away_team_id, season):
    """
    Process injury list and separate by home/away teams with enriched player data.
    
    Args:
        injury_list: List of injuries from API
        home_team_id: Home team identifier
        away_team_id: Away team identifier
        season: Season year
        
    Returns:
        Tuple of (home_injured, away_injured) lists with enriched player info
    """
    home_injured = []
    away_injured = []

    for entry in injury_list:
        player_id = entry['player']['id']
        team_id = entry['team']['id']
        league_id = entry['league']['id']

        player_stats = get_player_statistics(player_id, team_id, league_id, season)

        # Ensure player_stats contains statistics before extracting player info
        if player_stats and 'statistics' in player_stats and player_stats['statistics']:
            player_info = extract_player_info(player_stats)

            if team_id == home_team_id:
                home_injured.append(player_info)
            elif team_id == away_team_id:
                away_injured.append(player_info)

    return home_injured, away_injured


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
        from_date: Start date for fetching matches (format: YYYY-MM-DD)
        max_retries: Maximum retry attempts

    Returns:
        Tuple of (team_parameters, match_details) or (None, None) if failed
    """
    from datetime import datetime

    url = f"{API_FOOTBALL_BASE_URL}/fixtures"
    to_date = datetime.now().strftime("%Y-%m-%d")  # Fetch up to today
    params = {
        "league": str(league_id),
        "season": str(season),
        "team": str(team_id),
        "from": from_date,
        "to": to_date  # Added missing parameter to match legacy version
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


def get_fixtures_goals(league_id, start_timestamp, end_timestamp, season, max_retries=DEFAULT_MAX_RETRIES):
    """
    Fetch fixture goals for a specific league within a time range.
    Used by tactical_analyzer and team_classifier for analytics on historical matches.

    Returns ALL finished matches from the API for the league/timerange, regardless of
    whether they exist in our database. This is for parameter calculation and analytics.

    Args:
        league_id: League identifier
        start_timestamp: Start timestamp
        end_timestamp: End timestamp
        season: Season year (REQUIRED) - e.g. "2024" or 2024
        max_retries: Maximum retry attempts

    Returns:
        List of fixture dictionaries with full details (teams, goals, fixture metadata)
    """
    url = f"{API_FOOTBALL_BASE_URL}/fixtures"
    params = {
        "league": str(league_id),
        "season": str(season),
        "from": datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d'),
        "to": datetime.fromtimestamp(end_timestamp).strftime('%Y-%m-%d')
    }

    data = _make_api_request(url, params, max_retries=max_retries)

    if not data or "response" not in data:
        return []

    fixtures = []
    for fixture in data["response"]:
        # Only include finished matches with valid goals
        status = fixture["fixture"]["status"]["short"]
        if status in ["FT", "AET", "PEN", "FT_PEN"]:
            if fixture["goals"]["home"] is not None and fixture["goals"]["away"] is not None:
                fixtures.append({
                    "fixture_id": fixture["fixture"]["id"],
                    "home_goals": fixture["goals"]["home"],
                    "away_goals": fixture["goals"]["away"],
                    "status": status,
                    "teams": fixture.get("teams", {}),
                    "league": fixture.get("league", {}),
                    "fixture": fixture.get("fixture", {}),
                    "goals": fixture.get("goals", {}),
                    "score": fixture.get("score", {})
                })

    return fixtures


def get_fixtures_goals_by_ids(fixture_ids, max_retries=DEFAULT_MAX_RETRIES):
    """
    Fetch goals for a list of specific fixture IDs from the API.
    Used by match_data_handler for score checking on fixtures we've already predicted.

    This is the database-first approach: query DB for fixture IDs first, then fetch
    only those specific fixtures from the API. More efficient than querying by date range.

    Args:
        fixture_ids: List of fixture IDs to fetch goals for
        max_retries: Maximum retry attempts

    Returns:
        Dictionary mapping fixture_id -> {home: int, away: int, halftime_home: int, halftime_away: int, status: str}
    """
    if not fixture_ids:
        return {}

    url = f"{API_FOOTBALL_BASE_URL}/fixtures"
    goals_dict = {}

    # Process fixture_ids in batches of 20 (API limit)
    batch_size = 20
    for i in range(0, len(fixture_ids), batch_size):
        batch = fixture_ids[i:i + batch_size]
        ids_str = '-'.join(map(str, batch))
        params = {"ids": ids_str}

        data = _make_api_request(url, params, max_retries=max_retries)

        if not data or "response" not in data:
            continue

        # Extract goal data for each fixture
        for fixture in data["response"]:
            fixture_id = fixture["fixture"]["id"]
            status = fixture["fixture"]["status"]["short"]

            # Only include finished matches
            if status in ["FT", "AET", "PEN", "FT_PEN"]:
                goals_dict[fixture_id] = {
                    "home": fixture["goals"]["home"],
                    "away": fixture["goals"]["away"],
                    "halftime_home": fixture.get("score", {}).get("halftime", {}).get("home"),
                    "halftime_away": fixture.get("score", {}).get("halftime", {}).get("away"),
                    "status": status
                }

    return goals_dict


def get_next_fixture(team_id, current_fixture_id, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get the next fixture for a team after the current fixture.
    Returns dictionary with keys matching legacy system for backwards compatibility.
    
    Args:
        team_id: Team identifier
        current_fixture_id: Current fixture ID to find next after
        max_retries: Maximum retry attempts
        
    Returns:
        Dict with keys: Next_Fix_Type, Next_Opp, Next_Fix_Date, Next_League
        or None if not found
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
            # Determine fixture type and opponent
            fixture_type = "home" if fixture["teams"]["home"]["id"] == team_id else "away"
            opponent = fixture["teams"]["away"]["name"] if fixture_type == "home" else fixture["teams"]["home"]["name"]
            
            # Format date to match legacy system: "YYYY-MM-DD HH:MM"
            try:
                fixture_date = datetime.strptime(
                    fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z"
                ).strftime("%Y-%m-%d %H:%M")
            except (ValueError, KeyError):
                # Fallback to raw date if parsing fails
                fixture_date = fixture["fixture"]["date"]
            
            # Return with legacy-compatible keys for backwards compatibility
            return {
                "Next_Fix_Type": fixture_type,
                "Next_Opp": opponent,
                "Next_Fix_Date": fixture_date,
                "Next_League": fixture["league"]["name"]
            }

    return None


def get_coach_by_team(team_id, max_retries=DEFAULT_MAX_RETRIES):
    """
    Get current coach/manager information for a team.

    Uses recent fixture lineups to get the ACTUAL current manager, as the /coachs
    endpoint is often outdated. Falls back to /coachs endpoint if lineups unavailable.

    Args:
        team_id: Team identifier
        max_retries: Maximum retry attempts

    Returns:
        Coach information dict or None

    Example response:
        {
            'id': 4720,
            'name': 'Ruben Amorim',
            'firstname': 'Ruben',
            'lastname': 'Amorim',
            'age': 40,
            'birth': {...},
            'nationality': 'Portugal',
            'photo': 'https://...',
            'team': {'id': 33, 'name': 'Manchester United', ...},
            'career': [...]
        }
    """
    # STRATEGY 1: Get manager from recent fixture lineup (most accurate)
    try:
        # Get the most recent fixture for this team
        fixtures_url = f"{API_FOOTBALL_BASE_URL}/fixtures"
        fixtures_params = {"team": str(team_id), "last": "1"}

        fixtures_data = _make_api_request(fixtures_url, fixtures_params, max_retries=max_retries)

        if fixtures_data and "response" in fixtures_data and fixtures_data["response"]:
            recent_fixture = fixtures_data["response"][0]
            fixture_id = recent_fixture.get('fixture', {}).get('id')

            if fixture_id:
                # Get lineup for this fixture
                lineup_url = f"{API_FOOTBALL_BASE_URL}/fixtures/lineups"
                lineup_params = {"fixture": str(fixture_id)}

                lineup_data = _make_api_request(lineup_url, lineup_params, max_retries=max_retries)

                if lineup_data and "response" in lineup_data:
                    lineups = lineup_data["response"]

                    # Find the team's lineup
                    for lineup in lineups:
                        if lineup.get('team', {}).get('id') == team_id:
                            coach_info = lineup.get('coach', {})

                            if coach_info and coach_info.get('id'):
                                print(f"Found current manager from fixture lineup: {coach_info.get('name')}")

                                # Get full coach details by ID
                                full_coach_data = get_coach_by_id(coach_info.get('id'), max_retries=max_retries)
                                if full_coach_data:
                                    return full_coach_data

                                # If can't get full details, return what we have
                                return coach_info
    except Exception as e:
        print(f"Could not get manager from fixture lineup: {e}")

    # STRATEGY 2: Fallback to /coachs endpoint (may be outdated)
    print(f"Falling back to /coachs endpoint for team {team_id}")
    url = f"{API_FOOTBALL_BASE_URL}/coachs"
    params = {"team": str(team_id)}

    data = _make_api_request(url, params, max_retries=max_retries)

    if not data or "response" not in data or not data["response"]:
        return None

    # Return current coach (should be first in response)
    coaches = data["response"]
    if coaches:
        return coaches[0]

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

    def get_fixture_events(self, fixture_id, max_retries=DEFAULT_MAX_RETRIES):
        return get_fixture_events(fixture_id, max_retries)

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
    
    def get_fixtures_goals(self, league_id, start_timestamp, end_timestamp, season, max_retries=DEFAULT_MAX_RETRIES):
        return get_fixtures_goals(league_id, start_timestamp, end_timestamp, season, max_retries)

    def get_fixtures_goals_by_ids(self, fixture_ids, max_retries=DEFAULT_MAX_RETRIES):
        return get_fixtures_goals_by_ids(fixture_ids, max_retries)
    
    def get_next_fixture(self, team_id, current_fixture_id, max_retries=DEFAULT_MAX_RETRIES):
        return get_next_fixture(team_id, current_fixture_id, max_retries)

    def get_coach_by_team(self, team_id, max_retries=DEFAULT_MAX_RETRIES):
        return get_coach_by_team(team_id, max_retries)

    def get_coach_by_id(self, coach_id, max_retries=DEFAULT_MAX_RETRIES):
        return get_coach_by_id(coach_id, max_retries)

    def get_fixture_lineups(self, fixture_id, max_retries=DEFAULT_MAX_RETRIES):
        return get_fixture_lineups(fixture_id, max_retries)
    
    def get_team_recent_matches(self, team_id, league_id, season, limit=10, max_retries=DEFAULT_MAX_RETRIES):
        """
        Get recent matches for a team from the API.
        
        Args:
            team_id: Team identifier
            league_id: League identifier
            season: Season year
            limit: Maximum number of matches to return
            max_retries: Maximum retry attempts
            
        Returns:
            List of match dictionaries with match data
        """
        url = f"{API_FOOTBALL_BASE_URL}/fixtures"
        params = {
            "team": str(team_id),
            "league": str(league_id),
            "season": str(season),
            "last": str(limit)
        }
        
        data = _make_api_request(url, params, max_retries=max_retries)
        
        if not data or "response" not in data or not data["response"]:
            return []
        
        matches = []
        for fixture in data["response"]:
            if fixture["fixture"]["status"]["short"] in ["FT", "AET", "PEN"]:  # Finished matches only
                match_data = {
                    "fixture_id": fixture["fixture"]["id"],
                    "match_date": fixture["fixture"]["date"],
                    "home_team_id": fixture["teams"]["home"]["id"],
                    "away_team_id": fixture["teams"]["away"]["id"],
                    "home_team": fixture["teams"]["home"]["name"],
                    "away_team": fixture["teams"]["away"]["name"],
                    "home_goals": fixture["goals"]["home"],
                    "away_goals": fixture["goals"]["away"],
                    "venue_id": fixture["fixture"].get("venue", {}).get("id"),
                    "league_id": league_id,
                    "season": season
                }
                matches.append(match_data)
        
        return matches
    
    def get_team_season_matches(self, team_id, league_id, season, max_retries=DEFAULT_MAX_RETRIES):
        """
        Get all matches for a team in a specific league and season.
        
        Args:
            team_id: Team identifier
            league_id: League identifier
            season: Season year
            max_retries: Maximum retry attempts
            
        Returns:
            List of all match dictionaries for the season
        """
        url = f"{API_FOOTBALL_BASE_URL}/fixtures"
        params = {
            "team": str(team_id),
            "league": str(league_id),
            "season": str(season)
        }
        
        data = _make_api_request(url, params, max_retries=max_retries)
        
        if not data or "response" not in data or not data["response"]:
            return []
        
        matches = []
        for fixture in data["response"]:
            if fixture["fixture"]["status"]["short"] in ["FT", "AET", "PEN"]:  # Finished matches only
                match_data = {
                    "fixture_id": fixture["fixture"]["id"],
                    "match_date": fixture["fixture"]["date"],
                    "home_team_id": fixture["teams"]["home"]["id"],
                    "away_team_id": fixture["teams"]["away"]["id"],
                    "home_team": fixture["teams"]["home"]["name"],
                    "away_team": fixture["teams"]["away"]["name"],
                    "home_goals": fixture["goals"]["home"],
                    "away_goals": fixture["goals"]["away"],
                    "venue_id": fixture["fixture"].get("venue", {}).get("id"),
                    "league_id": league_id,
                    "season": season
                }
                matches.append(match_data)
        
        return matches
    
    def get_team_injuries(self, team_id, season, max_retries=DEFAULT_MAX_RETRIES):
        """
        Get current injured players for a team.
        
        Args:
            team_id: Team identifier
            season: Season year
            max_retries: Maximum retry attempts
            
        Returns:
            List of injured player dictionaries
        """
        url = f"{API_FOOTBALL_BASE_URL}/injuries"
        params = {
            "team": str(team_id),
            "season": str(season)
        }
        
        data = _make_api_request(url, params, max_retries=max_retries)
        
        if not data or "response" not in data or not data["response"]:
            return []
        
        injuries = []
        for injury_data in data["response"]:
            injury = {
                "player_id": injury_data.get("player", {}).get("id"),
                "player_name": injury_data.get("player", {}).get("name"),
                "injury_type": injury_data.get("player", {}).get("type"),
                "injury_reason": injury_data.get("player", {}).get("reason"),
                "status": "injured"
            }
            injuries.append(injury)
        
        return injuries
    
    def get_team_suspensions(self, team_id, season, max_retries=DEFAULT_MAX_RETRIES):
        """
        Get current suspended players for a team.
        Note: API-Football may not have a dedicated suspensions endpoint,
        so this returns empty list as a placeholder.
        
        Args:
            team_id: Team identifier
            season: Season year
            max_retries: Maximum retry attempts
            
        Returns:
            List of suspended player dictionaries (currently empty)
        """
        # API-Football does not have a dedicated suspensions endpoint
        # Suspensions are typically included in the injuries endpoint or fixture data
        # Return empty list for now
        return []
    
    def get_team_fixtures_in_period(self, team_id, league_id, season, start_date, end_date, max_retries=DEFAULT_MAX_RETRIES):
        """
        Get team fixtures within a specific date range.
        
        Args:
            team_id: Team identifier
            league_id: League identifier
            season: Season year
            start_date: Start date (datetime object)
            end_date: End date (datetime object)
            max_retries: Maximum retry attempts
            
        Returns:
            List of fixture dictionaries within the date range
        """
        url = f"{API_FOOTBALL_BASE_URL}/fixtures"
        params = {
            "team": str(team_id),
            "league": str(league_id),
            "season": str(season),
            "from": start_date.strftime('%Y-%m-%d'),
            "to": end_date.strftime('%Y-%m-%d')
        }
        
        data = _make_api_request(url, params, max_retries=max_retries)
        
        if not data or "response" not in data or not data["response"]:
            return []
        
        fixtures = []
        for fixture in data["response"]:
            fixture_data = {
                "fixture_id": fixture["fixture"]["id"],
                "match_date": fixture["fixture"]["date"],
                "home_team_id": fixture["teams"]["home"]["id"],
                "away_team_id": fixture["teams"]["away"]["id"],
                "home_team": fixture["teams"]["home"]["name"],
                "away_team": fixture["teams"]["away"]["name"],
                "status": fixture["fixture"]["status"]["short"],
                "league_id": league_id,
                "season": season
            }
            
            # Add goals if match is finished
            if fixture["fixture"]["status"]["short"] in ["FT", "AET", "PEN"]:
                fixture_data["home_goals"] = fixture["goals"]["home"]
                fixture_data["away_goals"] = fixture["goals"]["away"]
            
            fixtures.append(fixture_data)
        
        return fixtures


def get_football_match_scores(league_id, season, max_retries=DEFAULT_MAX_RETRIES):
    """
    Retrieves football match scores from the API-Football API and returns them as a DataFrame.
    Enhanced to include team IDs for team-specific analysis.

    Args:
        league_id: The ID of the league to get scores for
        season: The season to get scores for (e.g., "2024")
        max_retries: Maximum retry attempts

    Returns:
        pd.DataFrame: DataFrame containing match details including team IDs and goals
    """
    import pandas as pd

    url = f"{API_FOOTBALL_BASE_URL}/fixtures"

    params = {
        "league": str(league_id),
        "season": str(season)
    }

    data = _make_api_request(url, params, max_retries=max_retries)

    if not data or "response" not in data or not data["response"]:
        print(f"No match data found for league {league_id}, season {season}")
        return pd.DataFrame()

    # Initialize empty lists to store our data
    match_data = []

    # Process each fixture in the response
    for fixture in data['response']:
        # Check if the match is finished and has fulltime scores
        if (fixture['fixture']['status']['long'] == 'Match Finished' and
            fixture['score']['fulltime']['home'] is not None and
            fixture['score']['fulltime']['away'] is not None):

            match_info = {
                'fixture_id': fixture['fixture']['id'],
                'date': fixture['fixture']['date'],
                'home_team': fixture['teams']['home']['name'],
                'away_team': fixture['teams']['away']['name'],
                'home_team_id': fixture['teams']['home']['id'],
                'away_team_id': fixture['teams']['away']['id'],
                'home_goals': fixture['score']['fulltime']['home'],
                'away_goals': fixture['score']['fulltime']['away'],
                'venue_id': fixture['fixture'].get('venue', {}).get('id'),
                'league_id': league_id,
                'season': season
            }
            match_data.append(match_info)

    # Create DataFrame from the collected data
    df = pd.DataFrame(match_data)

    if not df.empty:
        print(f"Retrieved {len(df)} completed matches for league {league_id}, season {season}")
    else:
        print(f"No completed matches found for league {league_id}, season {season}")

    return df