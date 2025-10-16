"""
Fixture Ingestion Handler - Daily fixture retrieval for prediction system.

Based on code-samples/get_fixtures.py but integrated with modular architecture.
This handler serves as the entry point for the entire prediction pipeline,
automatically retrieving upcoming fixtures and populating the SQS queue for processing.

Author: Football Fixture Prediction System
Phase: Fixture Ingestion Implementation
Version: 1.0
"""

import json
import boto3
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from ..data.fixture_retrieval import FixtureRetriever
from ..utils.fixture_formatter import FixtureFormatter
from ..config.leagues_config import get_all_leagues
from ..utils.constants import FIXTURES_QUEUE_URL
from ..utils.converters import convert_for_json
from ..infrastructure.version_manager import VersionManager


def lambda_handler(event, context) -> Dict:
    """
    Main Lambda handler for daily fixture ingestion.

    Triggered by EventBridge rule daily at 06:00 UTC.
    Retrieves upcoming fixtures and populates SQS queue for prediction processing.

    Args:
        event: EventBridge event data
        context: Lambda context

    Returns:
        Dict: Processing summary with success/failure counts
    """

    print(f"Fixture ingestion started at {datetime.now().isoformat()}")
    print(f"Event: {json.dumps(event)}")

    # Initialize components
    retriever = FixtureRetriever()
    formatter = FixtureFormatter()
    sqs = boto3.client('sqs')
    version_manager = VersionManager()
    
    # Get current architecture version
    current_version = version_manager.get_current_version()
    print(f"Using architecture version: {current_version}")

    # Processing summary
    summary = {
        'processed_leagues': 0,
        'total_fixtures': 0,
        'successful_leagues': 0,
        'failed_leagues': 0,
        'errors': []
    }

    # Get all configured leagues
    try:
        all_leagues = get_all_leagues()
        print(f"Processing {len(all_leagues)} leagues")
    except Exception as e:
        error_msg = f"Failed to load leagues configuration: {e}"
        print(error_msg)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': error_msg})
        }

    # Calculate date range (based on original logic)
    current_day = datetime.today().weekday()
    to_start = 12  # Hours ahead to start looking

    # Determine end range based on day of week
    if current_day == 0:  # Monday
        to_end = 2
    elif current_day == 3:  # Thursday
        to_end = 3
    else:
        to_end = 2

    start_date = (datetime.now() + timedelta(hours=to_start)).strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=to_end, hours=to_start)).strftime('%Y-%m-%d')

    print(f"Retrieving fixtures from {start_date} to {end_date}")
    print(f"Current day: {current_day} (0=Monday), Range: {to_end} days")

    # Process each league
    for league in all_leagues:
        summary['processed_leagues'] += 1
        league_id = league['id']
        league_name = league['name']
        country = league.get('country', 'Unknown')

        try:
            print(f"Processing {league_name} (ID: {league_id}, Country: {country})")

            # Retrieve fixtures for this league
            fixtures = retriever.get_league_fixtures(
                league_id=league_id,
                start_date=start_date,
                end_date=end_date
            )

            if not fixtures:
                print(f"No fixtures found for {league_name}")
                continue

            # Format fixtures for processing
            formatted_fixtures = formatter.format_fixtures_for_queue(
                fixtures=fixtures,
                league_info={
                    'id': league_id,
                    'name': league_name,
                    'country': country
                }
            )

            if not formatted_fixtures:
                print(f"No valid fixtures after formatting for {league_name}")
                continue
            
            # Add version metadata to each fixture
            current_timestamp = int(datetime.now().timestamp())
            for fixture in formatted_fixtures:
                fixture['prediction_metadata'] = {
                    'architecture_version': current_version,
                    'ingestion_date': current_timestamp
                }

            # Send to SQS queue
            queue_response = send_fixtures_to_queue(
                sqs_client=sqs,
                fixtures=formatted_fixtures,
                league_info={
                    'id': league_id,
                    'name': league_name,
                    'country': country
                }
            )

            if queue_response['success']:
                summary['successful_leagues'] += 1
                summary['total_fixtures'] += len(formatted_fixtures)
                print(f"✅ Successfully queued {len(formatted_fixtures)} fixtures for {league_name}")
            else:
                summary['failed_leagues'] += 1
                summary['errors'].append(f"{league_name}: {queue_response['error']}")
                print(f"❌ Failed to queue fixtures for {league_name}: {queue_response['error']}")

        except Exception as e:
            error_msg = f"Failed to process {league_name}: {e}"
            print(error_msg)
            summary['failed_leagues'] += 1
            summary['errors'].append(error_msg)
            continue

    # Final summary
    print("=" * 70)
    print(f"Fixture ingestion completed at {datetime.now().isoformat()}")
    print(f"Total fixtures processed: {summary['total_fixtures']}")
    print(f"Successful leagues: {summary['successful_leagues']}/{summary['processed_leagues']}")
    print(f"Failed leagues: {summary['failed_leagues']}")

    if summary['errors']:
        print(f"\nErrors encountered ({len(summary['errors'])}):")
        for error in summary['errors']:
            print(f"  - {error}")

    print("=" * 70)

    # Determine success/failure
    is_success = summary['successful_leagues'] > 0
    status_code = 200 if is_success else 500

    return {
        'statusCode': status_code,
        'body': json.dumps(convert_for_json(summary)),
        'headers': {
            'Content-Type': 'application/json'
        }
    }


def send_fixtures_to_queue(sqs_client: boto3.client, fixtures: List[Dict],
                          league_info: Dict) -> Dict:
    """
    Send formatted fixtures to SQS queue for processing.

    Args:
        sqs_client: Boto3 SQS client
        fixtures: List of formatted fixture data
        league_info: League metadata

    Returns:
        Dict: Success status and error message if applicable
    """
    try:
        message_body = {
            'payload': fixtures,
            'league_info': league_info,
            'timestamp': int(datetime.now().timestamp()),
            'source': 'fixture_ingestion_handler',
            'fixture_count': len(fixtures)
        }

        response = sqs_client.send_message(
            QueueUrl=FIXTURES_QUEUE_URL,
            MessageBody=json.dumps(message_body, default=str),
            MessageAttributes={
                'league_id': {
                    'StringValue': str(league_info['id']),
                    'DataType': 'String'
                },
                'league_name': {
                    'StringValue': league_info['name'],
                    'DataType': 'String'
                },
                'country': {
                    'StringValue': league_info.get('country', 'Unknown'),
                    'DataType': 'String'
                },
                'fixture_count': {
                    'StringValue': str(len(fixtures)),
                    'DataType': 'Number'
                },
                'source': {
                    'StringValue': 'fixture_ingestion',
                    'DataType': 'String'
                }
            }
        )

        return {
            'success': True,
            'message_id': response['MessageId']
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
