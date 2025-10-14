"""
Database client for interacting with DynamoDB.
Consolidates all DynamoDB operations with consistent error handling.
"""

import boto3
import json
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta

from ..utils.constants import (
    GAME_FIXTURES_TABLE,
    LEAGUE_PARAMETERS_TABLE,
    TEAM_PARAMETERS_TABLE
)
from ..utils.converters import convert_for_dynamodb, decimal_default


def _get_dynamodb_resource():
    """Get DynamoDB resource with timeout and error handling for testing."""
    try:
        # Add timeout for testing environments
        import botocore.config
        config = botocore.config.Config(
            read_timeout=5,
            connect_timeout=5,
            retries={'max_attempts': 1}
        )
        return boto3.resource('dynamodb', config=config)
    except Exception as e:
        print(f"Warning: Could not connect to DynamoDB: {e}")
        return None


# Export dynamodb for backward compatibility
dynamodb = _get_dynamodb_resource()

# Initialize table references at module level
webFE_table = None
league_table = None
teams_table = None

if dynamodb:
    try:
        webFE_table = dynamodb.Table(GAME_FIXTURES_TABLE)
        league_table = dynamodb.Table(LEAGUE_PARAMETERS_TABLE)
        teams_table = dynamodb.Table(TEAM_PARAMETERS_TABLE)
    except Exception as e:
        print(f"Warning: Could not initialize DynamoDB tables: {e}")


def get_team_params_from_db(team_id, league_id):
    """
    Retrieve team parameters from DynamoDB.

    Args:
        team_id: Team identifier (numeric)
        league_id: League identifier (numeric)

    Returns:
        Team parameters dictionary or None if not found
    """
    try:
        dynamodb = _get_dynamodb_resource()
        if not dynamodb:
            return None

        teams_table = dynamodb.Table(TEAM_PARAMETERS_TABLE)
        response = teams_table.get_item(Key={
            'team_id': int(team_id),
            'league_id': int(league_id)
        })
        if 'Item' in response:
            return response['Item']
        return None
    except Exception as e:
        print(f"Error retrieving team parameters for team_id={team_id}, league_id={league_id}: {e}")
        return None


def get_league_params_from_db(league_id, season=None):
    """
    Retrieve league parameters from DynamoDB.

    Args:
        league_id: League identifier
        season: Season year (defaults to current year if not provided)

    Returns:
        League parameters dictionary or None if not found
    """
    try:
        dynamodb = _get_dynamodb_resource()
        if not dynamodb:
            return None

        # Default to current year if season not provided
        if season is None:
            from datetime import datetime
            season = datetime.now().year

        league_table = dynamodb.Table(LEAGUE_PARAMETERS_TABLE)
        response = league_table.get_item(Key={
            'league_id': int(league_id),
            'season': int(season)
        })
        if 'Item' in response:
            return response['Item']
        return None
    except Exception as e:
        print(f"Error retrieving league parameters for league_id={league_id}, season={season}: {e}")
        return None


def put_team_parameters(team_id, league_id, team_params):
    """
    Store team parameters in DynamoDB.

    Args:
        team_id: Team identifier (numeric)
        league_id: League identifier (numeric)
        team_params: Team parameters dictionary

    Returns:
        True if successful, False otherwise
    """
    try:
        # Prepare data for DynamoDB
        item = convert_for_dynamodb(team_params)
        item['team_id'] = int(team_id)
        item['league_id'] = int(league_id)
        item['timestamp'] = int(datetime.now().timestamp())

        teams_table.put_item(Item=item)
        print(f"Successfully stored team parameters for team_id={team_id}, league_id={league_id}")
        return True
    except Exception as e:
        print(f"Error storing team parameters for team_id={team_id}, league_id={league_id}: {e}")
        return False


def put_league_parameters(league_id, league_params):
    """
    Store league parameters in DynamoDB.
    
    Args:
        league_id: League identifier
        league_params: League parameters dictionary
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Prepare data for DynamoDB
        item = convert_for_dynamodb(league_params)
        item['league_id'] = league_id
        item['timestamp'] = int(datetime.now().timestamp())
        
        league_table.put_item(Item=item)
        print(f"Successfully stored league parameters for {league_id}")
        return True
    except Exception as e:
        print(f"Error storing league parameters for {league_id}: {e}")
        return False


def put_fixture_record(fixture_record):
    """
    Store fixture record in DynamoDB.
    
    Args:
        fixture_record: Complete fixture data dictionary
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert data for DynamoDB storage
        item = convert_for_dynamodb(fixture_record)
        
        webFE_table.put_item(Item=item)
        print(f"Successfully inserted fixture record with ID: {fixture_record['fixture_id']}")
        return True
    except Exception as e:
        print(f"Failed to insert fixture record into DynamoDB: {e}")
        return False


def query_dynamodb_records(country, league_name, start_time, end_time):
    """
    Query DynamoDB records for a specific league within a time range.
    Uses the country-league-index GSI for efficient querying.
    Originally from checkScores.py.
    
    Args:
        country: Country name
        league_name: League name
        start_time: Start timestamp
        end_time: End timestamp
        
    Returns:
        List of matching records
    """
    try:
        # Use GSI to query by country and league (much more efficient than scan)
        response = webFE_table.query(
            IndexName='country-league-index',
            KeyConditionExpression=Key('country').eq(country) & Key('league').eq(league_name),
            FilterExpression=Key('timestamp').between(start_time, end_time)
        )
        
        items = response.get('Items', [])
        
        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = webFE_table.query(
                IndexName='country-league-index',
                KeyConditionExpression=Key('country').eq(country) & Key('league').eq(league_name),
                FilterExpression=Key('timestamp').between(start_time, end_time),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))
        
        return items
        
    except Exception as e:
        print(f"Error querying DynamoDB records: {e}")
        return []


def add_attribute_to_dynamodb_item(fixture_id, attribute_name, attribute_value):
    """
    Add or update an attribute in an existing DynamoDB item.
    Originally from checkScores.py.
    
    Args:
        fixture_id: Fixture identifier
        attribute_name: Name of the attribute to add/update
        attribute_value: Value of the attribute
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert value for DynamoDB if needed
        converted_value = convert_for_dynamodb(attribute_value)
        
        webFE_table.update_item(
            Key={'fixture_id': fixture_id},
            UpdateExpression=f'SET #{attribute_name} = :val',
            ExpressionAttributeNames={f'#{attribute_name}': attribute_name},
            ExpressionAttributeValues={':val': converted_value}
        )
        print(f"Successfully updated {attribute_name} for fixture {fixture_id}")
        return True
    except Exception as e:
        print(f"Error updating attribute {attribute_name} for fixture {fixture_id}: {e}")
        return False


def fetch_league_parameters(league_id, season=None):
    """
    Fetch league parameters with error handling.

    Args:
        league_id: League identifier
        season: Season year (defaults to current year if not provided)

    Returns:
        League parameters dictionary or None if not found
    """
    try:
        # Default to current year if season not provided
        if season is None:
            from datetime import datetime
            season = datetime.now().year

        response = league_table.get_item(Key={
            'league_id': int(league_id),
            'season': int(season)
        })
        if 'Item' in response:
            return response['Item']
        else:
            print(f"No league parameters found for league {league_id}, season {season}")
            return None
    except Exception as e:
        print(f"Error fetching league parameters for {league_id}: {e}")
        return None


def fetch_league_fixtures(country, league_name, start_time, end_time):
    """
    Fetch historical fixtures for a league from DynamoDB.
    Uses the country-league-index GSI for efficient querying.
    Used for multiplier calculations.
    
    Args:
        country: Country name
        league_name: League name
        start_time: Start timestamp
        end_time: End timestamp
        
    Returns:
        List of fixture records
    """
    try:
        # Use GSI to query by country and league (much more efficient than scan)
        response = webFE_table.query(
            IndexName='country-league-index',
            KeyConditionExpression=Key('country').eq(country) & Key('league').eq(league_name),
            FilterExpression=Key('timestamp').between(start_time, end_time),
            ProjectionExpression='fixture_id, home, away, predictions, alternate_predictions, #date, #timestamp',
            ExpressionAttributeNames={'#date': 'date', '#timestamp': 'timestamp'}
        )
        
        items = response.get('Items', [])
        
        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = webFE_table.query(
                IndexName='country-league-index',
                KeyConditionExpression=Key('country').eq(country) & Key('league').eq(league_name),
                FilterExpression=Key('timestamp').between(start_time, end_time),
                ProjectionExpression='fixture_id, home, away, predictions, alternate_predictions, #date, #timestamp',
                ExpressionAttributeNames={'#date': 'date', '#timestamp': 'timestamp'},
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))
        
        return items
        
    except Exception as e:
        print(f"Error fetching league fixtures: {e}")
        return []


def get_team_fixtures(team_id, league_id, limit=50):
    """
    Get recent fixtures for a specific team.
    Used for team-specific multiplier calculations.
    
    Args:
        team_id: Team identifier
        league_id: League identifier  
        limit: Maximum number of fixtures to return
        
    Returns:
        List of fixture records for the team
    """
    try:
        # This would typically use a GSI on team_id for better performance
        response = webFE_table.scan(
            FilterExpression=(Key('home').attribute_exists() & Key('away').attribute_exists()) &
                           (Key('home.team_id').eq(team_id) | Key('away.team_id').eq(team_id)) &
                           Key('league_id').eq(league_id),
            Limit=limit,
            ProjectionExpression='fixture_id, home, away, predictions, alternate_predictions, #date, #timestamp',
            ExpressionAttributeNames={'#date': 'date', '#timestamp': 'timestamp'}
        )
        return response.get('Items', [])
    except Exception as e:
        print(f"Error fetching team fixtures for team {team_id}: {e}")
        return []


def batch_get_fixtures(fixture_ids):
    """
    Batch retrieve multiple fixtures by their IDs.
    
    Args:
        fixture_ids: List of fixture IDs to retrieve
        
    Returns:
        List of fixture records
    """
    if not fixture_ids:
        return []
    
    try:
        # DynamoDB batch_get_item has a limit of 100 items
        fixtures = []
        for i in range(0, len(fixture_ids), 100):
            batch = fixture_ids[i:i+100]
            keys = [{'fixture_id': fid} for fid in batch]
            
            response = dynamodb.batch_get_item(
                RequestItems={
                    GAME_FIXTURES_TABLE: {
                        'Keys': keys
                    }
                }
            )
            
            fixtures.extend(response.get('Responses', {}).get(GAME_FIXTURES_TABLE, []))
        
        return fixtures
    except Exception as e:
        print(f"Error in batch get fixtures: {e}")
        return []


def update_fixture_scores(fixture_id, home_goals, away_goals, halftime_home=None, halftime_away=None):
    """
    Update fixture with final scores using nested goals structure for backwards compatibility.
    Enhanced functionality from checkScores.py.
    
    Uses nested structure 'goals: {home, away}' to match multiplier calculator expectations.
    Also supports halftime scores in nested 'halftime_scores: {home, away}' structure.

    Args:
        fixture_id: Fixture identifier
        home_goals: Home team final goals
        away_goals: Away team final goals
        halftime_home: Optional halftime home goals
        halftime_away: Optional halftime away goals

    Returns:
        True if successful, False otherwise
    """
    try:
        # Build goals dict in nested structure (backwards compatible with multiplier calculator)
        goals_dict = {
            'home': home_goals,
            'away': away_goals
        }
        
        # Build update expression and attribute values
        update_expr = 'SET goals = :goals, score_updated = :updated'
        expr_values = {
            ':goals': goals_dict,
            ':updated': int(datetime.now().timestamp())
        }
        
        # Add halftime scores if provided
        if halftime_home is not None and halftime_away is not None:
            halftime_dict = {
                'home': halftime_home,
                'away': halftime_away
            }
            update_expr += ', halftime_scores = :halftime'
            expr_values[':halftime'] = halftime_dict
        
        webFE_table.update_item(
            Key={'fixture_id': fixture_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values
        )
        print(f"Successfully updated scores for fixture {fixture_id}: {home_goals}-{away_goals}")
        if halftime_home is not None and halftime_away is not None:
            print(f"  Halftime: {halftime_home}-{halftime_away}")
        return True
    except Exception as e:
        print(f"Error updating scores for fixture {fixture_id}: {e}")
        return False


def update_fixture_best_bet(fixture_id, best_bet_data):
    """
    Update fixture with best bet recommendations.

    Args:
        fixture_id: Fixture identifier
        best_bet_data: List of best bet recommendations

    Returns:
        True if successful, False otherwise
    """
    try:
        # First query to get the timestamp
        response = webFE_table.query(
            KeyConditionExpression=Key('fixture_id').eq(int(fixture_id)),
            Limit=1
        )

        if not response['Items']:
            print(f"No item found with fixture_id: {fixture_id}")
            return False

        timestamp = response['Items'][0]['timestamp']

        # Update the item with best_bet attribute
        update_response = webFE_table.update_item(
            Key={
                'fixture_id': int(fixture_id),
                'timestamp': timestamp
            },
            UpdateExpression="SET best_bet = :val, has_best_bet = :has_bet",
            ExpressionAttributeValues={
                ':val': best_bet_data,
                ':has_bet': True
            },
            ReturnValues="UPDATED_NEW"
        )

        print(f"Successfully updated best bet for fixture {fixture_id}")
        return True
    except Exception as e:
        print(f"Error updating best bet for fixture {fixture_id}: {e}")
        return False


def delete_team_parameters(team_id):
    """
    Delete team parameters from DynamoDB.
    
    Args:
        team_id: Team identifier to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        teams_table.delete_item(Key={'team_id': team_id})
        print(f"Successfully deleted team parameters for {team_id}")
        return True
    except Exception as e:
        print(f"Error deleting team parameters for {team_id}: {e}")
        return False


def health_check():
    """
    Perform a basic health check on database connections.
    
    Returns:
        Dictionary with health status of each table
    """
    health = {}
    
    tables = [
        (GAME_FIXTURES_TABLE, webFE_table),
        (LEAGUE_PARAMETERS_TABLE, league_table),
        (TEAM_PARAMETERS_TABLE, teams_table)
    ]
    
    for table_name, table_resource in tables:
        try:
            # Simple describe call to check connectivity
            table_resource.table_status
            health[table_name] = "healthy"
        except Exception as e:
            health[table_name] = f"error: {str(e)}"
    
    return health


class DatabaseClient:
    """
    Wrapper class for database client functions to maintain compatibility
    with feature modules that expect a class interface.
    """
    
    def __init__(self):
        pass
    
    def get_team_params_from_db(self, team_id, league_id):
        return get_team_params_from_db(team_id, league_id)

    def get_league_params_from_db(self, league_id, season=None):
        return get_league_params_from_db(league_id, season)

    def put_team_parameters(self, team_id, league_id, team_params):
        return put_team_parameters(team_id, league_id, team_params)
    
    def put_league_parameters(self, league_id, league_params):
        return put_league_parameters(league_id, league_params)
    
    def put_fixture_record(self, fixture_record):
        return put_fixture_record(fixture_record)
    
    def query_dynamodb_records(self, country, league_name, start_time, end_time):
        return query_dynamodb_records(country, league_name, start_time, end_time)
    
    def add_attribute_to_dynamodb_item(self, fixture_id, attribute_name, attribute_value):
        return add_attribute_to_dynamodb_item(fixture_id, attribute_name, attribute_value)
    
    def fetch_league_parameters(self, league_id):
        return fetch_league_parameters(league_id)
    
    def fetch_league_fixtures(self, country, league_name, start_time, end_time):
        return fetch_league_fixtures(country, league_name, start_time, end_time)
    
    def get_team_fixtures(self, team_id, league_id, limit=50):
        return get_team_fixtures(team_id, league_id, limit)
    
    def batch_get_fixtures(self, fixture_ids):
        return batch_get_fixtures(fixture_ids)
    
    def update_fixture_scores(self, fixture_id, home_goals, away_goals):
        return update_fixture_scores(fixture_id, home_goals, away_goals)

    def update_fixture_best_bet(self, fixture_id, best_bet_data):
        return update_fixture_best_bet(fixture_id, best_bet_data)
    
    def delete_team_parameters(self, team_id):
        return delete_team_parameters(team_id)
    
    def health_check(self):
        return health_check()


def get_cached_fixture_events(fixture_id):
    """
    Get fixture events from cache or fetch from API if not cached.
    Cache for 7 days for completed fixtures.

    Args:
        fixture_id: Fixture identifier

    Returns:
        Fixture events data from cache or API
    """
    try:
        from .api_client import get_fixture_events

        # Try to get from cache first
        cache_table_name = 'fixture_events_cache'

        if dynamodb:
            try:
                cache_table = dynamodb.Table(cache_table_name)
                response = cache_table.get_item(Key={'fixture_id': str(fixture_id)})

                if 'Item' in response:
                    print(f"Cache hit for fixture {fixture_id}")
                    return response['Item'].get('events')
            except Exception as e:
                print(f"Cache table not available: {e}, fetching from API")

        # Fetch from API if not in cache
        print(f"Fetching events from API for fixture {fixture_id}")
        events = get_fixture_events(fixture_id)

        # Cache the result for 7 days
        if dynamodb and events:
            try:
                cache_table = dynamodb.Table(cache_table_name)
                ttl = int((datetime.now() + timedelta(days=7)).timestamp())

                cache_table.put_item(Item={
                    'fixture_id': str(fixture_id),
                    'events': events,
                    'ttl': ttl,
                    'cached_at': int(datetime.now().timestamp())
                })
                print(f"Cached events for fixture {fixture_id}")
            except Exception as e:
                print(f"Failed to cache events: {e}")

        return events

    except Exception as e:
        print(f"Error in get_cached_fixture_events: {e}")
        return None


# Convenience function to get DynamoDB table directly (for compatibility)
def get_dynamodb_table(table_name=None):
    """
    Get DynamoDB table resource for direct table operations.
    Maintains compatibility with modules that expect this function.
    """
    if table_name == GAME_FIXTURES_TABLE or table_name is None:
        return webFE_table
    elif table_name == LEAGUE_PARAMETERS_TABLE:
        return league_table
    elif table_name == TEAM_PARAMETERS_TABLE:
        return teams_table
    else:
        # Return a general table reference
        return dynamodb.Table(table_name)