import boto3
import json
import os
from decimal import Decimal
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('game_fixtures')

MOBILE_API_KEY = os.getenv('MOBILE_APP_KEY')


def lambda_handler(event, context):
    print("Events:", json.dumps(event))

    # Get the API key from the identity in requestContext
    request_context = event.get('requestContext', {})
    identity = request_context.get('identity', {})
    api_key = identity.get('apiKey', '')

    if api_key != MOBILE_API_KEY:
        return {
            'statusCode': 401,
            'body': json.dumps('Authentication failed')
        }

    # Authentication successful - Mobile App is authorized
    print("Mobile App Authenticated!")

    # Extract parameters from queryStringParameters
    query_params = event.get('queryStringParameters', {}) or {}
    country = query_params.get('country')
    league = query_params.get('league')
    fixture_id = query_params.get('fixture_id')
    
    # Extract start_time and end_time if available
    start_time_param = query_params.get('startDate')
    end_time_param = query_params.get('endDate')

    # Process date parameters if provided
    if start_time_param and end_time_param:
        try:
            start_time = int(datetime.strptime(start_time_param, '%Y-%m-%d').timestamp())
            end_time = int(datetime.strptime(end_time_param, '%Y-%m-%d').timestamp())
        except ValueError as e:
            print(f"Error parsing date parameters: {e}")
            return {
                'statusCode': 400,
                'body': json.dumps('Invalid date format. Please use yyyy-MM-dd.')
            }
    else:
        # Calculate default date range (current day to 4 days in the future)
        current_time = datetime.utcnow()
        start_time = int((current_time - timedelta(days=0)).timestamp())
        end_time = int((current_time + timedelta(days=4)).timestamp())

    # Log date range for debugging
    s_time = datetime.fromtimestamp(start_time)
    e_time = datetime.fromtimestamp(end_time)
    print(f"Start Date: {s_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"End Date: {e_time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Check if fixture_id is provided
        if fixture_id:
            # Get specific fixture details
            fixture_data = get_fixture(table, int(fixture_id))
            response_body = {
                'items': fixture_data,
                'last_evaluated_key': None
            }
        else:
            # Validate that both country and league are provided for league-based query
            if not country or not league:
                return {
                    'statusCode': 400,
                    'body': json.dumps('Error: Please provide both country and league, or a specific fixture_id.')
                }

            # Query fixtures by country and league within date range
            params = {
                'IndexName': 'country-league-index',
                'KeyConditionExpression': '#ct = :country AND #lg = :league',
                'ExpressionAttributeNames': {
                    '#ct': 'country',
                    '#lg': 'league',
                    '#ts': 'timestamp'
                },
                'ExpressionAttributeValues': {
                    ':country': country,
                    ':league': league,
                    ':start_ts': Decimal(start_time),
                    ':end_ts': Decimal(end_time)
                },
                'FilterExpression': '#ts BETWEEN :start_ts AND :end_ts'
            }

            # Loop to fetch all pages
            filtered_items = []
            last_evaluated_key = None

            while True:
                if last_evaluated_key:
                    params['ExclusiveStartKey'] = last_evaluated_key
                else:
                    params.pop('ExclusiveStartKey', None)

                response = table.query(**params)
                items = response.get('Items', [])

                for item in items:
                    has_best_bet = 'best_bet' in item and item['best_bet'] and len(item['best_bet']) > 0

                    filtered_item = {
                        'fixture_id': item.get('fixture_id'),
                        'timestamp': item.get('timestamp'),
                        'date': item.get('date'),
                        'has_best_bet': has_best_bet,
                        'home': {
                            'team_id': item.get('home', {}).get('team_id'),
                            'team_name': item.get('home', {}).get('team_name'),
                            'team_logo': item.get('home', {}).get('team_logo'),
                            'predicted_goals': item.get('home', {}).get('predicted_goals'),
                            'predicted_goals_alt': item.get('home', {}).get('predicted_goals_alt'),
                            'home_performance': item.get('home', {}).get('home_performance')
                        },
                        'away': {
                            'team_id': item.get('away', {}).get('team_id'),
                            'team_name': item.get('away', {}).get('team_name'),
                            'team_logo': item.get('away', {}).get('team_logo'),
                            'predicted_goals': item.get('away', {}).get('predicted_goals'),
                            'predicted_goals_alt': item.get('away', {}).get('predicted_goals_alt'),
                            'away_performance': item.get('away', {}).get('away_performance')
                        }
                    }
                    filtered_items.append(filtered_item)

                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break

            response_body = {
                'items': filtered_items,
                'last_evaluated_key': None  # You can return this if frontend wants to paginate
            }

        print(f'Response: {json.dumps(response_body, default=decimal_default)}')

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps(response_body, default=decimal_default)
        }

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Server error: {str(e)}')
        }


def get_fixture(table, fixture_id):
    try:
        response = table.query(
            KeyConditionExpression=Key('fixture_id').eq(fixture_id),
            Limit=1,
            ScanIndexForward=False  # get the latest fixture first
        )
        return response.get('Items', [])
    except Exception as e:
        print(f"Error getting fixture {fixture_id}: {str(e)}")
        return []

def decimal_default(obj):
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    raise TypeError
