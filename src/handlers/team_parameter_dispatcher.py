"""
Team Parameter Dispatcher Lambda Function

This Lambda function dispatches team parameter computation jobs to SQS,
one message per league, to avoid Lambda timeout issues when processing
all leagues sequentially.

Purpose:
- Read leagues from leagues.py
- Send one SQS message per league to team parameter queue
- Enable parallel processing of up to 10 leagues simultaneously
- Complete in <10 seconds

Author: Football Fixture Prediction System
Version: 1.0
Date: 2025-10-06
"""

import json
import os
import boto3
from datetime import datetime
from typing import Dict, List, Optional
from botocore.exceptions import ClientError

# Import leagues configuration
from leagues import allLeagues


def lambda_handler(event, context):
    """
    Main Lambda handler for dispatching team parameter computation jobs.
    
    Input Event Format:
    {
        "trigger_type": "manual|scheduled|api",
        "league_filter": {
            "countries": ["England", "Spain"],  # Optional
            "league_ids": [39, 140]  # Optional
        },
        "dry_run": false  # Optional, default false
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "messages_sent": 60,
            "leagues_processed": [...],
            "errors": [],
            "execution_time_ms": 2341
        }
    }
    """
    start_time = datetime.now()
    
    # Parse input parameters
    trigger_type = event.get('trigger_type', 'manual')
    league_filter = event.get('league_filter', {})
    dry_run = event.get('dry_run', False)
    
    print(f"Team Parameter Dispatcher started")
    print(f"Trigger Type: {trigger_type}")
    print(f"Dry Run: {dry_run}")
    print(f"League Filter: {league_filter}")
    
    # Initialize SQS client
    sqs = boto3.client('sqs')
    
    # Get queue URL from environment or config
    queue_url = get_team_parameter_queue_url()
    print(f"Target Queue URL: {queue_url}")
    
    # Get filtered list of leagues
    leagues = get_filtered_leagues(league_filter)
    print(f"Total leagues to process: {len(leagues)}")
    
    # Dispatch messages
    results = []
    errors = []
    messages_sent = 0
    
    for league in leagues:
        try:
            # Prepare SQS message
            message_body = {
                'league_id': league['id'],
                'league_name': league['name'],
                'country': league['country'],
                'trigger_type': trigger_type,
                'force_recompute': event.get('force_recompute', False),
                'timestamp': int(datetime.now().timestamp())
            }
            
            if dry_run:
                # Dry run mode - don't actually send messages
                print(f"[DRY RUN] Would send message for: {league['name']} (ID: {league['id']})")
                results.append({
                    'league_id': league['id'],
                    'league_name': league['name'],
                    'message_id': 'dry-run-' + str(league['id']),
                    'status': 'dry_run'
                })
            else:
                # Send message to SQS
                response = sqs.send_message(
                    QueueUrl=queue_url,
                    MessageBody=json.dumps(message_body),
                    MessageAttributes={
                        'league_id': {
                            'StringValue': str(league['id']),
                            'DataType': 'String'
                        },
                        'country': {
                            'StringValue': league['country'],
                            'DataType': 'String'
                        },
                        'trigger_type': {
                            'StringValue': trigger_type,
                            'DataType': 'String'
                        }
                    }
                )
                
                messages_sent += 1
                print(f"✓ Sent message for: {league['name']} (ID: {league['id']}) - Message ID: {response['MessageId']}")
                
                results.append({
                    'league_id': league['id'],
                    'league_name': league['name'],
                    'country': league['country'],
                    'message_id': response['MessageId'],
                    'status': 'sent'
                })
                
        except ClientError as e:
            error_msg = f"Failed to send message for {league['name']} (ID: {league['id']}): {str(e)}"
            print(f"✗ {error_msg}")
            errors.append({
                'league_id': league['id'],
                'league_name': league['name'],
                'error': str(e),
                'error_code': e.response.get('Error', {}).get('Code', 'Unknown')
            })
        except Exception as e:
            error_msg = f"Unexpected error for {league['name']} (ID: {league['id']}): {str(e)}"
            print(f"✗ {error_msg}")
            errors.append({
                'league_id': league['id'],
                'league_name': league['name'],
                'error': str(e)
            })
    
    # Calculate execution time
    end_time = datetime.now()
    execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
    
    # Prepare response
    response_body = {
        'messages_sent': messages_sent,
        'total_leagues': len(leagues),
        'successful': len(results),
        'failed': len(errors),
        'dry_run': dry_run,
        'trigger_type': trigger_type,
        'execution_time_ms': execution_time_ms,
        'queue_url': queue_url,
        'leagues_processed': results,
        'errors': errors
    }
    
    # Log summary
    print(f"\n{'='*70}")
    print(f"DISPATCHER SUMMARY")
    print(f"{'='*70}")
    print(f"Total Leagues: {len(leagues)}")
    print(f"Messages Sent: {messages_sent}")
    print(f"Successful: {len(results)}")
    print(f"Failed: {len(errors)}")
    print(f"Execution Time: {execution_time_ms}ms")
    print(f"{'='*70}\n")
    
    return {
        'statusCode': 200 if len(errors) == 0 else 207,  # 207 = Multi-Status (partial success)
        'body': json.dumps(response_body, default=str)
    }


def get_team_parameter_queue_url() -> str:
    """
    Get the team parameter SQS queue URL from environment variables or config.
    
    Priority:
    1. Environment variable TEAM_PARAMETER_QUEUE_URL
    2. Load from queue_config_prod.json
    3. Construct from environment and account ID
    
    Returns:
        SQS queue URL
    """
    # Try environment variable first
    queue_url = os.getenv('TEAM_PARAMETER_QUEUE_URL')
    if queue_url:
        return queue_url
    
    # Try loading from config file
    try:
        import json
        config_path = os.path.join(os.path.dirname(__file__), '../../queue_config_prod.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
            queue_url = config.get('queues', {}).get('football-team-parameter-updates', {}).get('queue_url')
            if queue_url:
                return queue_url
    except Exception as e:
        print(f"Warning: Could not load queue config: {e}")
    
    # Construct from environment variables
    environment = os.getenv('ENVIRONMENT', 'prod')
    region = os.getenv('AWS_REGION', 'eu-west-2')
    
    # Get account ID from context or STS
    try:
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
    except:
        # Fallback to hardcoded (from config analysis)
        account_id = '985019772236'
    
    queue_name = f'football_football-team-parameter-updates_{environment}'
    queue_url = f'https://sqs.{region}.amazonaws.com/{account_id}/{queue_name}'
    
    print(f"Constructed queue URL: {queue_url}")
    return queue_url


def get_filtered_leagues(league_filter: Optional[Dict] = None) -> List[Dict]:
    """
    Get list of leagues, optionally filtered by criteria.
    
    Args:
        league_filter: Optional dictionary with filtering criteria
            - countries: List of country names to include
            - league_ids: List of specific league IDs to include
            - exclude_countries: List of countries to exclude
            - exclude_league_ids: List of league IDs to exclude
    
    Returns:
        List of league dictionaries with id, name, and country
    """
    # Flatten all leagues with country information
    all_leagues_flat = [
        {**league, 'country': country}
        for country, leagues in allLeagues.items()
        for league in leagues
    ]
    
    # If no filter provided, return all leagues
    if not league_filter:
        return all_leagues_flat
    
    filtered_leagues = all_leagues_flat
    
    # Filter by included countries
    if 'countries' in league_filter and league_filter['countries']:
        filtered_leagues = [
            league for league in filtered_leagues
            if league['country'] in league_filter['countries']
        ]
        print(f"Filtered to countries {league_filter['countries']}: {len(filtered_leagues)} leagues")
    
    # Filter by included league IDs
    if 'league_ids' in league_filter and league_filter['league_ids']:
        filtered_leagues = [
            league for league in filtered_leagues
            if league['id'] in league_filter['league_ids']
        ]
        print(f"Filtered to league IDs {league_filter['league_ids']}: {len(filtered_leagues)} leagues")
    
    # Exclude specific countries
    if 'exclude_countries' in league_filter and league_filter['exclude_countries']:
        filtered_leagues = [
            league for league in filtered_leagues
            if league['country'] not in league_filter['exclude_countries']
        ]
        print(f"Excluded countries {league_filter['exclude_countries']}: {len(filtered_leagues)} leagues remaining")
    
    # Exclude specific league IDs
    if 'exclude_league_ids' in league_filter and league_filter['exclude_league_ids']:
        filtered_leagues = [
            league for league in filtered_leagues
            if league['id'] not in league_filter['exclude_league_ids']
        ]
        print(f"Excluded league IDs {league_filter['exclude_league_ids']}: {len(filtered_leagues)} leagues remaining")
    
    return filtered_leagues


def validate_event(event: Dict) -> tuple[bool, Optional[str]]:
    """
    Validate the input event structure.
    
    Args:
        event: Lambda event dictionary
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check trigger_type is valid
    valid_trigger_types = ['manual', 'scheduled', 'api']
    trigger_type = event.get('trigger_type', 'manual')
    
    if trigger_type not in valid_trigger_types:
        return False, f"Invalid trigger_type: {trigger_type}. Must be one of {valid_trigger_types}"
    
    # Check league_filter structure if present
    if 'league_filter' in event:
        league_filter = event['league_filter']
        if not isinstance(league_filter, dict):
            return False, "league_filter must be a dictionary"
        
        valid_keys = ['countries', 'league_ids', 'exclude_countries', 'exclude_league_ids']
        invalid_keys = [key for key in league_filter.keys() if key not in valid_keys]
        if invalid_keys:
            return False, f"Invalid league_filter keys: {invalid_keys}. Valid keys are {valid_keys}"
    
    return True, None