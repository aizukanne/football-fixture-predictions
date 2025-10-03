import boto3
import json
import logging
import os
import requests
import time

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from leagues import allLeagues, someLeagues

#someLeagues = allLeagues

#allLeagues = someLeagues

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


rapidapi_key = os.getenv('RAPIDAPI_KEY')


dynamodb = boto3.resource('dynamodb')
games_table = dynamodb.Table('game_fixtures')  # Replace with your DynamoDB Table Name


def lambda_handler(event, context):

    isUpdate = False
    if isUpdate:
        end_date = datetime(2025, 9, 16)
        get_historical_scores(end_date)
    else:
        try:
            # Set the time range for the last 24 hours
            end_time = datetime.now() # Current time
            start_time = end_time - timedelta(days=4)  # Exactly 24 hours ago

            # Convert to UNIX timestamps
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())

            for country, leagues in allLeagues.items():
                for league_info in leagues:
                    league_id = league_info['id']
                    league_name = league_info['name']
                    
                    logging.info(f"Updating league: {league_name} ({country}) for games in the last 24 hours")

                    try:
                        # Query DynamoDB for fixtures within the last 24 hours
                        fixtures_data = query_dynamodb_records(country, league_name, start_timestamp, end_timestamp)
                        fixture_ids = [fixture["fixture_id"] for fixture in fixtures_data.get("items", [])]
                        
                        # Get goals for fixtures
                        goals_dict = get_fixtures_goals(fixture_ids)
                        
                        # Update each fixture with goals
                        for fixture_id in fixture_ids:
                            if fixture_id in goals_dict:
                                add_attribute_to_dynamodb_item(fixture_id, "goals", goals_dict[fixture_id])
                        
                    except Exception as e:
                        logging.error(f"Error processing league {league_name} ({league_id}): {e}")
        
        except Exception as e:
            logging.critical(f"Critical error in lambda handler: {e}")


def add_attribute_to_dynamodb_item(partition_key_value, new_attribute_name, new_value):
    try:
        # Query the item to get the timestamp
        response = games_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('fixture_id').eq(int(partition_key_value)),
            Limit=1
        )
        
        # Check if the item exists
        if not response['Items']:
            print(f"No item found with fixture_id: {partition_key_value}")
            return
        
        # Get the timestamp from the queried item
        timestamp = response['Items'][0]['timestamp']
        
        # Update the item with both partition key and sort key
        update_response = games_table.update_item(
            Key={
                'fixture_id': int(partition_key_value),
                'timestamp': timestamp
            },
            UpdateExpression=f"SET {new_attribute_name} = :new_value",
            ExpressionAttributeValues={
                ':new_value': new_value
            },
            ReturnValues="UPDATED_NEW"
        )
        
        print(f"Update successful: Fixture ID: {partition_key_value}: {update_response['Attributes']}")
    
    except ClientError as e:
        print("DynamoDB ClientError:", e.response['Error']['Message'])
    except Exception as e:
        print("An error occurred:", str(e))


def query_dynamodb_records(country, league, start_time, end_time, event=None):
    """
    Query all matching records from DynamoDB based on country and league within a timestamp range.
    Supports pagination and returns all matching results across all pages.

    :param country: The country to filter records.
    :param league: The league to filter records.
    :param start_time: Start time of the range as a UNIX timestamp.
    :param end_time: End time of the range as a UNIX timestamp.
    :param event: Optional parameter to accept an 'ExclusiveStartKey' for partial paging use cases.
    :return: A dictionary with the full list of matching items.
    """

    if not country or not league:
        return {
            'statusCode': 400,
            'body': json.dumps('Error: Please provide both country and league.')
        }

    # Prepare query
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

    all_items = []
    last_evaluated_key = None

    # Allow external pagination override
    if event and 'ExclusiveStartKey' in event:
        last_evaluated_key = event['ExclusiveStartKey']

    while True:
        if last_evaluated_key:
            params['ExclusiveStartKey'] = last_evaluated_key
        else:
            params.pop('ExclusiveStartKey', None)

        try:
            response = games_table.query(**params)
        except Exception as e:
            print(f"Error querying DynamoDB: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps(f"Query failed: {str(e)}")
            }

        all_items.extend(response.get('Items', []))
        last_evaluated_key = response.get('LastEvaluatedKey')

        if not last_evaluated_key:
            break

    return {
        'items': all_items
    }


def get_league_start_date(league_id):
    """
    Fetch the start date of the current season for a given league.

    Parameters:
    - league_id: The league ID.

    Returns:
    - The start date of the league season (format: YYYY-MM-DD) or None if not found.
    """
    url = "https://api-football-v1.p.rapidapi.com/v3/leagues"
    querystring = {"id": league_id, "current": "true"}

    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)

    if response.status_code != 200:
        print(f"Error: API request failed with status code {response.status_code}")
        return None

    data = response.json()

    if "response" not in data or not data["response"]:
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


def get_fixtures_goals(fixture_ids):
    """
    Fetch goals for a list of fixture IDs from the API and return a dictionary
    with fixture IDs as keys and goals as values.
    
    :param fixture_ids: List of fixture IDs.
    :return: Dictionary with fixture IDs as keys and their corresponding goals as values.
    """
    
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }
    goals_dict = {}

    # Process fixture_ids in batches of 20
    batch_size = 20
    for i in range(0, len(fixture_ids), batch_size):
        batch = fixture_ids[i:i + batch_size]
        ids_str = '-'.join(map(str, batch))  # Combine fixture IDs into a string separated by '-'
        querystring = {"ids": ids_str}
        
        try:
            response = requests.get(url, headers=headers, params=querystring)
            response_data = response.json()
            
            # Update goals_dict with results from the current batch
            goals_dict.update({
                fixture['fixture']['id']: fixture['goals']
                for fixture in response_data.get('response', [])
            })
            
        except requests.exceptions.RequestException as e:
            print("Request failed:", e)
        except ValueError as e:
            print("Failed to parse response:", e)

    return goals_dict


def get_historical_scores(end_date):
    try:
        for country, leagues in someLeagues.items():
            for league_info in leagues:
                league_id = league_info['id']
                league_name = league_info['name']

                try:
                    start_date_str = get_league_start_date(league_id)
                    current_date = datetime.strptime(start_date_str, "%Y-%m-%d")

                except Exception as e:
                    logging.error(f"Error getting start date for league {league_name} ({league_id}): {e}")
                    continue

                if not current_date:
                    logging.warning(f"No start date found for league {league_name} ({league_id})")
                    continue

                while current_date <= end_date:
                    try:
                        # Calculate time range for the week
                        start_time = int(current_date.timestamp())
                        end_time = int((current_date + timedelta(weeks=1)).timestamp())

                        # Log the update attempt
                        logging.info(f"Updating league: {league_name} ({country}) for week starting {current_date}")

                        # Query DynamoDB for fixtures
                        fixtures_data = query_dynamodb_records(country, league_name, start_time, end_time)
                        fixture_ids = [fixture["fixture_id"] for fixture in fixtures_data.get("items", [])]
                        print(fixture_ids)

                        # Get goals for fixtures
                        goals_dict = get_fixtures_goals(fixture_ids)

                        # Update each fixture with goals
                        for fixture_id in fixture_ids:
                            if fixture_id in goals_dict:
                                add_attribute_to_dynamodb_item(fixture_id, "goals", goals_dict[fixture_id])

                    except Exception as e:
                        logging.error(f"Error processing league {league_name} ({league_id}) for week {current_date}: {e}")
                    
                    current_date = current_date + timedelta(weeks=1)

    except Exception as e:
        logging.critical(f"Critical error in lambda handler: {e}")


def decimal_default(obj):
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError
