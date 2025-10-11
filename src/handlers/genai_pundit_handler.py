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
from boto3.dynamodb.conditions import Key
from typing import Dict, Any, Optional

from ..services.parameter_extraction_service import (
    extract_ai_relevant_parameters,
    build_ai_context,
    get_parameter_summary
)
from ..services.genai_analysis_service import GenAIAnalysisService
from ..utils.converters import convert_for_dynamodb

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
    if origin in ALLOWED_ORIGINS:
        allowed_origin = origin
    elif api_key == MOBILE_API_KEY:
        allowed_origin = "Mobile App"
    else:
        allowed_origin = None
    
    # CORS headers
    cors_headers = {
        'Access-Control-Allow-Origin': allowed_origin if allowed_origin else "null",
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
                return {
                    'statusCode': 200,
                    'headers': cors_headers,
                    'body': json.dumps({
                        'analysis': existing_analysis['text'],
                        'provider': existing_analysis.get('ai_provider', 'unknown'),
                        'generation_time_ms': existing_analysis.get('generation_time_ms')
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
        
        # 3. Load team parameters
        home_params_raw = get_team_parameters(league_id, home_team_id)
        away_params_raw = get_team_parameters(league_id, away_team_id)
        
        if not home_params_raw or not away_params_raw:
            print("Warning: Team parameters not found")
            return None
        
        # 4. Extract AI-relevant parameters
        home_params = extract_ai_relevant_parameters(home_params_raw)
        away_params = extract_ai_relevant_parameters(away_params_raw)
        
        print(f"Home params: {get_parameter_summary(home_params)}")
        print(f"Away params: {get_parameter_summary(away_params)}")
        
        # 5. Load league parameters
        league_params = get_league_parameters(league_id, season)
        if not league_params:
            league_params = {}
            print("Warning: League parameters not found, using empty dict")
        
        # 6. Build AI context
        context = build_ai_context(
            fixture_data, 
            home_params, 
            away_params, 
            league_params
        )
        
        print("AI context built successfully")
        
        # 7. Generate analysis with AI
        analysis_text, provider, generation_time_ms = ai_service.generate_analysis(context)
        
        print(f"Analysis generated with {provider} in {generation_time_ms}ms")
        
        # 8. Save to database
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
    """Get team parameters from database."""
    try:
        unique_id = f"{league_id}-{team_id}"
        response = teams_table.query(
            KeyConditionExpression=Key('id').eq(unique_id),
            Limit=1
        )
        items = response.get('Items', [])
        return items[0] if items else None
    except Exception as e:
        print(f"Error fetching team parameters for {league_id}-{team_id}: {e}")
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