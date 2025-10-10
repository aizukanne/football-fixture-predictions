"""
Thin orchestration layer for the checkScores Lambda function (enhanced).
Coordinates match data collection workflow using modular components.
Supports both basic score updates and enhanced match statistics collection.
"""

import json
from datetime import datetime, timedelta

from ..data.api_client import get_fixtures_goals, get_league_start_date
from ..data.database_client import (
    query_dynamodb_records,
    add_attribute_to_dynamodb_item,
    update_fixture_scores
)
from ..utils.converters import decimal_default
from leagues import allLeagues


def lambda_handler(event, context):
    """
    Main Lambda handler for match data collection.
    Enhanced version of checkScores with support for comprehensive match statistics.
    """
    print("Match data collection started")
    
    # Parse time range from event or use defaults
    time_range = parse_time_range_from_event(event)
    start_timestamp, end_timestamp = time_range
    
    print(f"Processing matches from {datetime.fromtimestamp(start_timestamp)} to {datetime.fromtimestamp(end_timestamp)}")
    
    all_leagues_flat = [
        { **league, 'country': country }
        for country, leagues in allLeagues.items()
        for league in leagues
    ]
    
    results = {
        'processed_leagues': 0,
        'updated_fixtures': 0,
        'failed_updates': 0,
        'league_results': []
    }
    
    for league in all_leagues_flat:
        league_id = league['id']
        league_name = league['name']
        country = league['country']
        
        print(f"Processing league: {league_name} (ID: {league_id})")
        
        try:
            # Get fixtures from API that finished in the time range
            api_fixtures = get_fixtures_goals(league_id, start_timestamp, end_timestamp)
            
            if not api_fixtures:
                print(f"No finished fixtures found for {league_name}")
                continue
            
            # Get existing records from DynamoDB
            db_records = query_dynamodb_records(country, league_name, start_timestamp, end_timestamp)
            
            # Process fixture updates
            league_result = process_league_fixtures(
                league_id, league_name, country, api_fixtures, db_records
            )
            
            results['league_results'].append(league_result)
            results['processed_leagues'] += 1
            results['updated_fixtures'] += league_result['updated_count']
            results['failed_updates'] += league_result['failed_count']
            
        except Exception as e:
            print(f"Error processing league {league_name}: {e}")
            results['league_results'].append({
                'league_id': league_id,
                'league_name': league_name,
                'status': 'error',
                'error': str(e),
                'updated_count': 0,
                'failed_count': 1
            })
            results['failed_updates'] += 1
            continue
    
    print(f"Match data collection completed. Updated {results['updated_fixtures']} fixtures.")
    
    return {
        'statusCode': 200,
        'body': json.dumps(results, default=decimal_default)
    }


def process_league_fixtures(league_id, league_name, country, api_fixtures, db_records):
    """
    Process fixtures for a specific league, updating scores and match data.
    
    Args:
        league_id: League identifier
        league_name: League name
        country: Country name
        api_fixtures: List of fixtures from API with goals
        db_records: List of existing records from DynamoDB
        
    Returns:
        Dictionary with processing results for the league
    """
    updated_count = 0
    failed_count = 0
    fixture_results = []
    
    # Create lookup for existing records
    db_lookup = {record['fixture_id']: record for record in db_records}
    
    for api_fixture in api_fixtures:
        fixture_id = api_fixture['fixture_id']
        home_goals = api_fixture['home_goals']
        away_goals = api_fixture['away_goals']
        status = api_fixture.get('status', 'FT')
        
        try:
            # Check if we have this fixture in our database
            if fixture_id in db_lookup:
                db_record = db_lookup[fixture_id]
                
                # Check if scores need updating (check nested goals structure for backwards compatibility)
                goals_dict = db_record.get('goals', {})
                current_home = goals_dict.get('home') if goals_dict else None
                current_away = goals_dict.get('away') if goals_dict else None
                
                if current_home != home_goals or current_away != away_goals:
                    # Extract halftime scores from API if available
                    halftime_home = api_fixture.get('halftime_home')
                    halftime_away = api_fixture.get('halftime_away')
                    
                    # Update scores with nested structure (backwards compatible)
                    success = update_fixture_scores(
                        fixture_id,
                        home_goals,
                        away_goals,
                        halftime_home,
                        halftime_away
                    )
                    
                    if success:
                        print(f"Updated fixture {fixture_id}: {home_goals}-{away_goals}")
                        if halftime_home is not None and halftime_away is not None:
                            print(f"  Halftime: {halftime_home}-{halftime_away}")
                        
                        # Collect additional match data if enabled
                        enhanced_data = collect_enhanced_match_data(fixture_id, api_fixture)
                        if enhanced_data:
                            update_enhanced_match_data(fixture_id, enhanced_data)
                        
                        updated_count += 1
                        fixture_results.append({
                            'fixture_id': fixture_id,
                            'status': 'updated',
                            'score': f"{home_goals}-{away_goals}"
                        })
                    else:
                        print(f"Failed to update fixture {fixture_id}")
                        failed_count += 1
                        fixture_results.append({
                            'fixture_id': fixture_id,
                            'status': 'update_failed',
                            'score': f"{home_goals}-{away_goals}"
                        })
                else:
                    # Scores already match
                    fixture_results.append({
                        'fixture_id': fixture_id,
                        'status': 'no_change',
                        'score': f"{home_goals}-{away_goals}"
                    })
            else:
                # Fixture not found in database
                print(f"Fixture {fixture_id} not found in database")
                fixture_results.append({
                    'fixture_id': fixture_id,
                    'status': 'not_found',
                    'score': f"{home_goals}-{away_goals}"
                })
                
        except Exception as e:
            print(f"Error processing fixture {fixture_id}: {e}")
            failed_count += 1
            fixture_results.append({
                'fixture_id': fixture_id,
                'status': 'error',
                'error': str(e)
            })
    
    return {
        'league_id': league_id,
        'league_name': league_name,
        'country': country,
        'status': 'completed',
        'total_fixtures': len(api_fixtures),
        'updated_count': updated_count,
        'failed_count': failed_count,
        'fixtures': fixture_results
    }


def collect_enhanced_match_data(fixture_id, api_fixture):
    """
    Collect enhanced match statistics beyond basic scores.
    This supports the enhanced data collection for Phase 4+ tactical analysis.
    
    Args:
        fixture_id: Fixture identifier
        api_fixture: Basic fixture data from API (may contain halftime scores and statistics)
        
    Returns:
        Dictionary with enhanced match data or None if not available
    """
    try:
        # Extract halftime scores if available in API fixture
        halftime_home = api_fixture.get('halftime_home')
        halftime_away = api_fixture.get('halftime_away')
        
        # Build enhanced data structure
        enhanced_data = {
            'match_statistics': {
                'shots': {'home': api_fixture.get('shots_home'), 'away': api_fixture.get('shots_away')},
                'shots_on_target': {'home': api_fixture.get('shots_on_target_home'), 'away': api_fixture.get('shots_on_target_away')},
                'possession': {'home': api_fixture.get('possession_home'), 'away': api_fixture.get('possession_away')},
                'passes': {'home': api_fixture.get('passes_home'), 'away': api_fixture.get('passes_away')},
                'pass_accuracy': {'home': api_fixture.get('pass_accuracy_home'), 'away': api_fixture.get('pass_accuracy_away')},
                'corners': {'home': api_fixture.get('corners_home'), 'away': api_fixture.get('corners_away')},
                'fouls': {'home': api_fixture.get('fouls_home'), 'away': api_fixture.get('fouls_away')},
                'yellow_cards': {'home': api_fixture.get('yellow_cards_home'), 'away': api_fixture.get('yellow_cards_away')},
                'red_cards': {'home': api_fixture.get('red_cards_home'), 'away': api_fixture.get('red_cards_away')}
            },
            'collected_at': int(datetime.now().timestamp())
        }
        
        # Check if we have any actual statistics (not all None)
        has_stats = any(
            val is not None
            for stat_dict in enhanced_data['match_statistics'].values()
            for val in stat_dict.values()
        )
        
        # Only return enhanced data if we have actual statistics
        if has_stats:
            return enhanced_data
        
        # In a full implementation, this would make additional API calls to:
        # 1. Get detailed match statistics from statistics endpoint
        # 2. Get player statistics if needed
        # 3. Get formation and tactical data
        
        return None
        
    except Exception as e:
        print(f"Error collecting enhanced data for fixture {fixture_id}: {e}")
        return None


def update_enhanced_match_data(fixture_id, enhanced_data):
    """
    Update fixture record with enhanced match data.
    
    Args:
        fixture_id: Fixture identifier
        enhanced_data: Enhanced match data dictionary
    """
    try:
        # Update halftime scores if available
        if enhanced_data.get('halftime_scores'):
            add_attribute_to_dynamodb_item(
                fixture_id, 
                'halftime_scores', 
                enhanced_data['halftime_scores']
            )
        
        # Update match statistics if available
        if enhanced_data.get('match_statistics'):
            add_attribute_to_dynamodb_item(
                fixture_id,
                'match_statistics',
                enhanced_data['match_statistics']
            )
        
        print(f"Updated enhanced data for fixture {fixture_id}")
        
    except Exception as e:
        print(f"Error updating enhanced data for fixture {fixture_id}: {e}")


def parse_time_range_from_event(event):
    """
    Parse time range from Lambda event or use reasonable defaults.
    
    Args:
        event: Lambda event data
        
    Returns:
        Tuple of (start_timestamp, end_timestamp)
    """
    try:
        # Check if time range is provided in event
        if 'time_range' in event:
            start_timestamp = event['time_range']['start']
            end_timestamp = event['time_range']['end']
        else:
            # Default to last 24 hours
            now = datetime.now()
            end_timestamp = int(now.timestamp())
            start_timestamp = int((now - timedelta(days=1)).timestamp())
        
        return start_timestamp, end_timestamp
        
    except Exception as e:
        print(f"Error parsing time range, using defaults: {e}")
        # Fallback to last 24 hours
        now = datetime.now()
        end_timestamp = int(now.timestamp())
        start_timestamp = int((now - timedelta(days=1)).timestamp())
        return start_timestamp, end_timestamp


def validate_fixture_data(api_fixture):
    """
    Validate fixture data from API.
    
    Args:
        api_fixture: Fixture data from API
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = ['fixture_id', 'home_goals', 'away_goals']
    
    for field in required_fields:
        if field not in api_fixture:
            return False
        if api_fixture[field] is None:
            return False
    
    # Validate goal values are non-negative integers
    try:
        home_goals = int(api_fixture['home_goals'])
        away_goals = int(api_fixture['away_goals'])
        
        if home_goals < 0 or away_goals < 0:
            return False
            
    except (TypeError, ValueError):
        return False
    
    return True


def get_fixture_update_summary(fixture_results):
    """
    Create a summary of fixture update results.
    
    Args:
        fixture_results: List of fixture processing results
        
    Returns:
        Dictionary with summary statistics
    """
    summary = {
        'total': len(fixture_results),
        'updated': 0,
        'no_change': 0,
        'not_found': 0,
        'failed': 0,
        'errors': 0
    }
    
    for result in fixture_results:
        status = result.get('status', 'unknown')
        if status == 'updated':
            summary['updated'] += 1
        elif status == 'no_change':
            summary['no_change'] += 1
        elif status == 'not_found':
            summary['not_found'] += 1
        elif status == 'update_failed':
            summary['failed'] += 1
        elif status == 'error':
            summary['errors'] += 1
    
    return summary