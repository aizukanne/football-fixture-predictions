"""
GenAI Pundit v2.0 Lambda Handler
Generates AI-powered match analysis using Phase 0-6 parameters.

Supports:
- API Gateway requests with CORS and authentication
- Direct Lambda invocations for async processing
- Claim-based work management to prevent duplicates
"""

import json
import time
import os
import boto3
import requests
from boto3.dynamodb.conditions import Key
from typing import Dict, Any, Optional

from ..services.genai_analysis_service import GenAIAnalysisService
from ..utils.converters_lite import convert_for_dynamodb, decimal_to_float

# Initialize DynamoDB tables
dynamodb = boto3.resource('dynamodb')
games_table = dynamodb.Table(os.getenv('GAME_FIXTURES_TABLE', 'game_fixtures'))
teams_table = dynamodb.Table(os.getenv('TEAM_PARAMETERS_TABLE', 'team_parameters'))
league_table = dynamodb.Table(os.getenv('LEAGUE_PARAMETERS_TABLE', 'league_parameters'))
analysis_table = dynamodb.Table(os.getenv('GAME_ANALYSIS_TABLE', 'game_analysis'))

# Initialize AI service (at module level for Lambda container reuse)
ai_service = None

# CORS Configuration
ALLOWED_ORIGINS = [
    "https://footystats.abv.ng",
    "https://chacha-online.abv.ng",
    "http://10.197.182.36:3000",
    "http://localhost:3000"  # For local testing
]
MOBILE_API_KEY = os.getenv('VALID_MOBILE_API_KEY')

# API Keys for external services
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_KEY')
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')


def get_coordinates(location_name: str) -> Optional[tuple]:
    """
    Get latitude and longitude coordinates for a location using OpenWeather Geocoding API.
    
    Args:
        location_name: City name (e.g., "Manchester", "London")
        
    Returns:
        Tuple of (lat, lon) or None if not found
    """
    if not OPENWEATHER_API_KEY:
        print("Warning: OPENWEATHER_KEY not configured")
        return None
    
    base_url = 'http://api.openweathermap.org/geo/1.0/direct'
    params = {
        'q': location_name,
        'limit': 1,
        'appid': OPENWEATHER_API_KEY
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = data[0]['lat']
                lon = data[0]['lon']
                return lat, lon
        else:
            print(f"Geocoding API error: {response.status_code}")
    except Exception as e:
        print(f"Error getting coordinates for {location_name}: {e}")
    
    return None


def get_weather_data(location_name: str) -> Optional[dict]:
    """
    Get weather forecast data for a location using OpenWeather OneCall API 3.0.
    
    Args:
        location_name: City name (e.g., "Manchester, England")
        
    Returns:
        Weather data dict with hourly forecasts or None if failed
    """
    # Extract city name (remove country/region)
    location_name = location_name.split(',')[0].strip()
    
    # Validate location_name
    if not location_name:
        print('Location name is empty')
        return None
    
    coordinates = get_coordinates(location_name)
    if not coordinates:
        print(f'Could not find coordinates for location: {location_name}')
        return None
    
    lat, lon = coordinates
    url = 'https://api.openweathermap.org/data/3.0/onecall'
    params = {
        'appid': OPENWEATHER_API_KEY,
        'lat': lat,
        'lon': lon,
        'exclude': 'current,minutely,daily,alerts',
        'units': 'metric'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            print(f'Weather API error: {response.status_code} - {response.reason}')
            return None
        
        return response.json()
    except Exception as e:
        print(f"Error getting weather data: {e}")
        return None


def get_weather_forecast(timestamp: int, match_venue: str) -> dict:
    """
    Get weather forecast for a specific match time (±2 hours window).
    
    Args:
        timestamp: Match timestamp (Unix epoch)
        match_venue: Venue city name
        
    Returns:
        Dict with relevant weather forecasts within the time window
    """
    weather_data = get_weather_data(match_venue)
    
    if not weather_data:
        return {'weather': {}}
    
    # Define the range (2 hours before and after the given timestamp)
    two_hours = 2 * 3600
    start_range = timestamp - two_hours
    end_range = timestamp + two_hours
    
    # Initialize a dictionary to store the relevant forecasts
    relevant_forecasts = {}
    
    # Loop through the hourly forecasts
    for forecast in weather_data.get('hourly', []):
        forecast_timestamp = forecast.get('dt')
        # Check if the forecast's timestamp falls within the desired range
        if start_range <= forecast_timestamp <= end_range:
            str_forecast_timestamp = str(forecast_timestamp)
            relevant_forecasts[str_forecast_timestamp] = forecast.get('weather', [])
    
    return {'weather': relevant_forecasts}


def get_team_standing(home_team_id: int, away_team_id: int, league_id: int, season: int) -> tuple:
    """
    Get team standings from RapidAPI for both home and away teams.
    
    Args:
        home_team_id: Home team ID
        away_team_id: Away team ID
        league_id: League ID
        season: Season year
        
    Returns:
        Tuple of (home_data, away_data) dicts with standings info
    """
    if not RAPIDAPI_KEY:
        print("Warning: RAPIDAPI_KEY not configured")
        return {}, {}
    
    url = "https://api-football-v1.p.rapidapi.com/v3/standings"
    querystring = {
        "league": str(league_id),
        "season": str(season)
    }
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        if response.status_code != 200:
            print(f"Standings API error: {response.status_code}")
            return {}, {}
        
        data = response.json()
        print(f"Standings API response structure: {list(data.keys())}")
        
        if "response" not in data or not data["response"]:
            print("No standings data found")
            return {}, {}
        
        print(f"Response data contains {len(data['response'])} items")
        print(f"First response structure: {list(data['response'][0].keys())}")
        
        standings_list = data["response"][0]["league"]["standings"][0]
        league_name = data["response"][0]["league"]["name"]
        
        print(f"League: {league_name}, Total teams in standings: {len(standings_list)}")
        print(f"Looking for home_team_id={home_team_id}, away_team_id={away_team_id}")
        
        # Log all team IDs in standings for debugging
        all_team_ids = [standing.get("team", {}).get("id") for standing in standings_list]
        print(f"All team IDs in standings: {all_team_ids[:10]}...")  # First 10 for brevity
        
        total_teams = len(standings_list)
        home_data = None
        away_data = None
        
        for standing in standings_list:
            team = standing.get("team", {})
            team_id = team.get("id")
            if team_id == home_team_id:
                home_data = {
                    "team_name": team.get("name"),
                    "league_position": standing.get("rank"),
                    "league_points": standing.get("points"),
                    "total_teams": total_teams,
                    "league_name": league_name
                }
            if team_id == away_team_id:
                away_data = {
                    "team_name": team.get("name"),
                    "league_position": standing.get("rank"),
                    "league_points": standing.get("points"),
                    "total_teams": total_teams,
                    "league_name": league_name
                }
        
        if not home_data:
            print(f"Home team with id {home_team_id} not found in standings")
            home_data = {}
        if not away_data:
            print(f"Away team with id {away_team_id} not found in standings")
            away_data = {}
        
        return home_data, away_data
    
    except Exception as e:
        print(f"Error getting team standings: {e}")
        return {}, {}


def lambda_handler(event, context):
    """
    Main Lambda handler for GenAI Pundit v2.0.
    
    Handles both:
    1. API Gateway requests (with CORS and authentication)
    2. Direct Lambda invocations (for async processing)
    """
    print(f"Event: {json.dumps(event)}")
    
    # Initialize AI service on first invocation (cold start)
    global ai_service
    if ai_service is None:
        try:
            ai_service = GenAIAnalysisService()
            print(f"AI Service initialized: {ai_service.get_provider_info()}")
        except Exception as e:
            print(f"Error initializing AI service: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'AI service initialization failed: {str(e)}'})
            }
    
    # Check if this is a direct Lambda invocation (background processing)
    if 'httpMethod' not in event:
        return handle_direct_invocation(event, context)
    
    # Handle API Gateway request
    return handle_api_gateway_request(event, context)


def handle_direct_invocation(event: dict, context: Any) -> dict:
    """
    Handle direct Lambda invocation for background processing.
    
    Args:
        event: Event containing fixture_id
        context: Lambda context
        
    Returns:
        Success/error response
    """
    fixture_id = event.get('fixture_id')
    if not fixture_id:
        print("Error: Missing fixture_id in direct invocation")
        return {'error': 'Missing fixture_id'}
    
    print(f"Direct invocation for fixture_id: {fixture_id}")
    
    # Generate and store analysis
    try:
        analysis = generate_fixture_analysis(fixture_id)
        if analysis:
            return {
                'success': True,
                'fixture_id': fixture_id,
                'provider': analysis.get('provider'),
                'generation_time_ms': analysis.get('generation_time_ms')
            }
        else:
            return {'error': 'Failed to generate analysis'}
    except Exception as e:
        print(f"Error in direct invocation: {e}")
        return {'error': str(e)}


def handle_api_gateway_request(event: dict, context: Any) -> dict:
    """
    Handle API Gateway HTTP request with CORS and authentication.
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response with CORS headers
    """
    # Get origin and API key
    origin = event['headers'].get('origin', '')
    request_context = event.get('requestContext', {})
    identity = request_context.get('identity', {})
    api_key = identity.get('apiKey', '')
    
    # Determine allowed origin
    # Always allow requests with valid API key by echoing back the origin
    if api_key == MOBILE_API_KEY:
        # Echo back the exact origin (including 'null' for local files)
        allowed_origin = origin if origin else "*"
    elif origin in ALLOWED_ORIGINS:
        allowed_origin = origin
    else:
        allowed_origin = None
    
    # CORS headers
    cors_headers = {
        'Access-Control-Allow-Origin': allowed_origin if allowed_origin else "*",
        'Access-Control-Allow-Headers': 'content-type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,x-api-key',
        'Access-Control-Allow-Methods': 'OPTIONS,POST',
        'Content-Type': 'application/json; charset=utf-8'
    }
    
    # Handle OPTIONS (preflight)
    if event['httpMethod'] == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps('CORS preflight successful')
        }
    
    # Handle POST
    if event['httpMethod'] == 'POST':
        if not allowed_origin:
            return {
                'statusCode': 403,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Forbidden: Origin not allowed'})
            }
        
        return handle_post_request(event, cors_headers, context)
    
    # Method not allowed
    return {
        'statusCode': 405,
        'headers': cors_headers,
        'body': json.dumps({'error': 'Method not allowed'})
    }


def handle_post_request(event: dict, cors_headers: dict, context: Any) -> dict:
    """
    Handle POST request to generate analysis.
    
    Args:
        event: API Gateway event
        cors_headers: CORS headers
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    # Validate body
    if not event.get('body'):
        return {
            'statusCode': 400,
            'headers': cors_headers,
            'body': json.dumps({'error': 'Request body is missing'})
        }
    
    try:
        body = json.loads(event['body'])
        fixture_id = body.get('fixture_id')
        
        if not fixture_id:
            raise ValueError("Missing required field: 'fixture_id'")
        
        # Convert to integer
        try:
            fixture_id = int(fixture_id)
        except ValueError:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'fixture_id must be an integer'})
            }
        
        print(f"Fixture ID: {fixture_id}")
        
        # Check if analysis already exists or claim work
        existing_analysis = get_analysis(fixture_id)
        
        if existing_analysis:
            status = existing_analysis.get('status', 'COMPLETED')
            
            if status == 'COMPLETED':
                print(f"Completed analysis found for fixture ID: {fixture_id}")
                # Convert Decimal objects to float for JSON serialization
                generation_time = existing_analysis.get('generation_time_ms')
                if generation_time is not None:
                    generation_time = decimal_to_float(generation_time)
                
                return {
                    'statusCode': 200,
                    'headers': cors_headers,
                    'body': json.dumps({
                        'analysis': existing_analysis['text'],
                        'provider': existing_analysis.get('ai_provider', 'unknown'),
                        'generation_time_ms': generation_time
                    }, ensure_ascii=False)
                }
            elif status == 'IN_PROGRESS':
                print(f"Analysis already in progress for fixture ID: {fixture_id}")
                return {
                    'statusCode': 202,
                    'headers': cors_headers,
                    'body': json.dumps({
                        'message': 'Analysis generation already in progress. Please retry in a few moments.',
                        'fixture_id': fixture_id
                    })
                }
        
        # Claim work
        if claim_analysis_work(fixture_id):
            print(f"Successfully claimed analysis work for fixture ID: {fixture_id}")
            
            # Invoke Lambda asynchronously
            lambda_client = boto3.client('lambda')
            lambda_client.invoke(
                FunctionName=context.function_name,
                InvocationType='Event',  # Asynchronous
                Payload=json.dumps({'fixture_id': fixture_id})
            )
            
            return {
                'statusCode': 202,
                'headers': cors_headers,
                'body': json.dumps({
                    'message': 'Analysis generation started. Please retry in a few moments.',
                    'fixture_id': fixture_id
                })
            }
        else:
            print(f"Another process already claimed work for fixture ID: {fixture_id}")
            return {
                'statusCode': 202,
                'headers': cors_headers,
                'body': json.dumps({
                    'message': 'Analysis generation already in progress. Please retry in a few moments.',
                    'fixture_id': fixture_id
                })
            }
    
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': cors_headers,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except ValueError as e:
        return {
            'statusCode': 400,
            'headers': cors_headers,
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': 'Internal server error'})
        }


def generate_fixture_analysis(fixture_id: int) -> Optional[dict]:
    """
    Generate AI-powered analysis for a fixture.
    
    Args:
        fixture_id: Fixture identifier
        
    Returns:
        Analysis result or None if failed
    """
    try:
        print(f"Generating analysis for fixture_id: {fixture_id}")
        
        # 1. Load fixture data
        fixture_data = get_fixture(fixture_id)
        if not fixture_data:
            print(f"No fixture data found for fixture_id: {fixture_id}")
            return None
        
        print("Fixture data loaded successfully")
        
        # 2. Extract team and league IDs
        home_team_id = fixture_data['home']['team_id']
        away_team_id = fixture_data['away']['team_id']
        league_id = fixture_data['league_id']
        season = fixture_data['season']
        
        print(f"Home team: {home_team_id}, Away team: {away_team_id}, League: {league_id}")
        
        # 3. Fetch weather data - check multiple possible venue paths
        venue_info = fixture_data.get('venue', {})

        # Handle venue being either a dict or a numeric ID (for backward compatibility with old records)
        if isinstance(venue_info, dict):
            venue_city = venue_info.get('venue_city') or venue_info.get('venue_name', '').split(',')[0].strip()
        else:
            # Old record with venue stored as ID only - cannot extract city
            print(f"Warning: venue stored as ID ({venue_info}) in old record format, cannot extract city for weather")
            venue_city = None

        timestamp = fixture_data.get('timestamp') or fixture_data.get('fixture', {}).get('timestamp', 0)

        print(f"Venue info: {venue_info}")
        print(f"Extracted venue_city: {venue_city}, timestamp: {timestamp}")
        
        weather_data = {}
        if venue_city and timestamp:
            print(f"Fetching weather for {venue_city} at timestamp {timestamp}")
            weather_data = get_weather_forecast(timestamp, venue_city)
        else:
            print(f"Warning: No venue city or timestamp found. Venue data: {venue_info}, Timestamp: {timestamp}")
        
        # 4. Fetch team standings
        home_standings, away_standings = get_team_standing(
            home_team_id,
            away_team_id,
            league_id,
            season
        )
        print(f"Home standings: {home_standings}")
        print(f"Away standings: {away_standings}")
        
        # 5. Load team parameters (send complete data - no extraction)
        home_params_raw = get_team_parameters(league_id, home_team_id)
        away_params_raw = get_team_parameters(league_id, away_team_id)
        
        if not home_params_raw or not away_params_raw:
            print("Warning: Team parameters not found")
            return None
        
        # Convert Decimal to float for JSON serialization
        from ..utils.converters_lite import decimal_to_float
        home_params = decimal_to_float(home_params_raw)
        away_params = decimal_to_float(away_params_raw)
        
        print(f"Sending complete team parameters to AI")
        print(f"Home params fields: {len(home_params)} | Away params fields: {len(away_params)}")
        
        # 7. Load league parameters
        league_params = get_league_parameters(league_id, season)
        if not league_params:
            league_params = {}
            print("Warning: League parameters not found, using empty dict")
        else:
            # Convert Decimal to float for JSON serialization
            league_params = decimal_to_float(league_params)
        
        # 8. Build complete AI context with raw data
        context = {
            'fixture_info': {
                'fixture_id': fixture_data.get('fixture_id'),
                'date': fixture_data.get('date'),
                'league': fixture_data.get('league'),
                'venue': fixture_data.get('venue'),
                'timestamp': fixture_data.get('timestamp')
            },
            'home_team': {
                'team_name': fixture_data.get('home', {}).get('team_name'),
                'team_id': fixture_data.get('home', {}).get('team_id'),
                'predictions': fixture_data.get('home'),
                'parameters': home_params,  # Complete raw parameters
                'standings': home_standings if home_standings else {}
            },
            'away_team': {
                'team_name': fixture_data.get('away', {}).get('team_name'),
                'team_id': fixture_data.get('away', {}).get('team_id'),
                'predictions': fixture_data.get('away'),
                'parameters': away_params,  # Complete raw parameters
                'standings': away_standings if away_standings else {}
            },
            'match_predictions': fixture_data.get('predictions', {}),
            'league_parameters': league_params,  # Complete league parameters
            'weather': weather_data if weather_data else fixture_data.get('weather', {})
        }
        
        print("AI context built with complete raw parameters")
        
        # 9. Generate analysis with AI
        analysis_text, provider, generation_time_ms = ai_service.generate_analysis(context)
        
        print(f"Analysis generated with {provider} in {generation_time_ms}ms")
        
        # 10. Save to database
        current_time = int(time.time())
        analysis_output = {
            'fixture_id': fixture_id,
            'timestamp': fixture_data['timestamp'],
            'text': analysis_text,
            'status': 'COMPLETED',
            'completed_at': current_time,
            'ai_provider': provider,
            'generation_time_ms': generation_time_ms,
            'fixture_data': convert_for_dynamodb(context)
        }
        
        analysis_table.put_item(Item=analysis_output)
        print(f"Successfully saved analysis for fixture ID: {fixture_id}")
        
        return {
            'text': analysis_text,
            'provider': provider,
            'generation_time_ms': generation_time_ms
        }
    
    except Exception as e:
        print(f"Error generating analysis: {e}")
        # Clean up IN_PROGRESS status on failure
        try:
            if fixture_data:
                analysis_table.delete_item(
                    Key={
                        'fixture_id': fixture_id,
                        'timestamp': fixture_data.get('timestamp', 0)
                    }
                )
        except:
            pass
        return None


def get_fixture(fixture_id: int) -> Optional[dict]:
    """Get fixture data from database."""
    try:
        response = games_table.query(
            KeyConditionExpression=Key('fixture_id').eq(fixture_id),
            Limit=1,
            ScanIndexForward=False
        )
        items = response.get('Items', [])
        return items[0] if items else None
    except Exception as e:
        print(f"Error fetching fixture {fixture_id}: {e}")
        return None


def get_team_parameters(league_id: int, team_id: int) -> Optional[dict]:
    """
    Get team parameters from database using modern composite key structure.
    
    Modern football_team_parameters_prod table uses:
    - Partition key: league_id (Number)
    - Sort key: team_id (Number)
    """
    try:
        print(f"Querying team parameters: league_id={league_id}, team_id={team_id}")
        response = teams_table.query(
            KeyConditionExpression=Key('league_id').eq(league_id) & Key('team_id').eq(team_id),
            Limit=1
        )
        items = response.get('Items', [])
        if items:
            print(f"Found team parameters for team {team_id}")
            return items[0]
        else:
            print(f"No team parameters found for league {league_id}, team {team_id}")
            return None
    except Exception as e:
        print(f"Error fetching team parameters for league {league_id}, team {team_id}: {e}")
        return None


def get_league_parameters(league_id: int, season: int) -> Optional[dict]:
    """Get league parameters from database."""
    try:
        response = league_table.get_item(
            Key={
                'league_id': league_id,
                'season': season
            }
        )
        return response.get('Item')
    except Exception as e:
        print(f"Error fetching league parameters for {league_id}: {e}")
        return None


def get_analysis(fixture_id: int) -> Optional[dict]:
    """Get existing analysis from database."""
    try:
        response = analysis_table.query(
            KeyConditionExpression=Key('fixture_id').eq(fixture_id),
            Limit=1,
            ScanIndexForward=False
        )
        items = response.get('Items', [])
        return items[0] if items else None
    except Exception as e:
        print(f"Error fetching analysis for {fixture_id}: {e}")
        return None


def claim_analysis_work(fixture_id: int) -> bool:
    """
    Atomically claim analysis work for a fixture.
    
    Args:
        fixture_id: Fixture identifier
        
    Returns:
        True if successfully claimed, False if already claimed
    """
    try:
        # Get fixture timestamp
        fixture = get_fixture(fixture_id)
        if not fixture:
            return False
        
        timestamp = fixture['timestamp']
        
        # Attempt to claim with conditional put
        analysis_table.put_item(
            Item={
                'fixture_id': fixture_id,
                'timestamp': timestamp,
                'status': 'IN_PROGRESS',
                'claimed_at': int(time.time())
            },
            ConditionExpression='attribute_not_exists(fixture_id)'
        )
        return True
    except analysis_table.meta.client.exceptions.ConditionalCheckFailedException:
        # Already exists (claimed by another process)
        return False
    except Exception as e:
        print(f"Error claiming work for fixture {fixture_id}: {e}")
        return False