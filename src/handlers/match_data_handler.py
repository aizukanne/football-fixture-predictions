"""
Thin orchestration layer for the checkScores Lambda function (enhanced).
Coordinates match data collection workflow using modular components.
Supports both basic score updates and enhanced match statistics collection.
"""

import json
from datetime import datetime, timedelta

from ..data.api_client import (
    get_fixtures_goals_by_ids,
    get_league_start_date,
    get_fixture_statistics,
)
from ..data.database_client import (
    query_dynamodb_records,
    add_attribute_to_dynamodb_item,
    update_fixture_scores
)
from ..data.match_statistics import FixtureMeta, write_fixture_statistics
from ..utils.converters import decimal_default
from leagues import allLeagues


def lambda_handler(event, context):
    """
    Main Lambda handler for match data collection.
    Enhanced version of checkScores with support for comprehensive match statistics.

    Supports invocation via:
    1. Direct invocation with time_range in event
    2. SQS message with time_range in message body
    3. EventBridge scheduled event (uses default 24h range)
    """
    print("Match data collection started")

    # Check if invoked via SQS and parse message body
    if 'Records' in event and event['Records']:
        try:
            message_body = json.loads(event['Records'][0]['body'])
            print(f"Processing SQS message: {message_body}")
            event = message_body  # Use parsed body as event
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Error parsing SQS message, using event directly: {e}")

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
            # Get existing records from DynamoDB FIRST (database-first approach)
            db_records = query_dynamodb_records(country, league_name, start_timestamp, end_timestamp)

            if not db_records:
                print(f"No fixtures in database for {league_name} in time range")
                continue

            # Extract fixture IDs from database records
            fixture_ids = [record['fixture_id'] for record in db_records]
            print(f"Found {len(fixture_ids)} fixtures in database for {league_name}")

            # Get goals for these specific fixtures from API
            goals_dict = get_fixtures_goals_by_ids(fixture_ids)

            if not goals_dict:
                print(f"No finished fixtures found for {league_name}")
                continue

            print(f"Found {len(goals_dict)} finished fixtures from API for {league_name}")

            # Process fixture updates
            league_result = process_league_fixtures(
                league_id, league_name, country, goals_dict, db_records
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


def process_league_fixtures(league_id, league_name, country, goals_dict, db_records):
    """
    Process fixtures for a specific league, updating scores and match data.

    Args:
        league_id: League identifier
        league_name: League name
        country: Country name
        goals_dict: Dictionary mapping fixture_id -> goal data from API
        db_records: List of existing records from DynamoDB

    Returns:
        Dictionary with processing results for the league
    """
    updated_count = 0
    failed_count = 0
    fixture_results = []

    # Create lookup for existing records
    db_lookup = {record['fixture_id']: record for record in db_records}

    # Iterate through finished fixtures from API
    for fixture_id, goal_data in goals_dict.items():
        home_goals = goal_data['home']
        away_goals = goal_data['away']
        halftime_home = goal_data.get('halftime_home')
        halftime_away = goal_data.get('halftime_away')
        status = goal_data.get('status', 'FT')

        try:
            # Check if we have this fixture in our database
            if fixture_id in db_lookup:
                db_record = db_lookup[fixture_id]

                # Check if scores need updating (check nested goals structure for backwards compatibility)
                goals_obj = db_record.get('goals', {})
                current_home = goals_obj.get('home') if goals_obj else None
                current_away = goals_obj.get('away') if goals_obj else None

                if current_home != home_goals or current_away != away_goals:
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

                        # Collect per-team match statistics for V2 xG engine.
                        # This writes to football_match_statistics_prod and
                        # has no effect on the V1 game_fixtures record.
                        enhanced_data = collect_enhanced_match_data(
                            fixture_id, goal_data, db_record=db_record
                        )
                        if enhanced_data and enhanced_data.get('match_statistics'):
                            # Preserve the legacy match_statistics attribute on the
                            # game_fixtures item for backward-compatible consumers.
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
                # This should never happen since we queried by fixture IDs from our database
                print(f"WARNING: Fixture {fixture_id} returned by API but not in our database lookup")
                fixture_results.append({
                    'fixture_id': fixture_id,
                    'status': 'not_in_db',
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
        'total_fixtures': len(goals_dict),
        'updated_count': updated_count,
        'failed_count': failed_count,
        'fixtures': fixture_results
    }


def _extract_fixture_meta(fixture_id, db_record):
    """Pull the (league_id, season, date, home_team_id, away_team_id) tuple
    from a game_fixtures DynamoDB record so we can build a FixtureMeta.

    Returns None if any required field is missing.
    """
    if not db_record:
        return None
    try:
        league_id = db_record.get('league_id')
        season = db_record.get('season')
        match_date = db_record.get('date')
        home = db_record.get('home') or {}
        away = db_record.get('away') or {}
        home_team_id = home.get('team_id')
        away_team_id = away.get('team_id')

        if None in (league_id, season, match_date, home_team_id, away_team_id):
            return None

        return FixtureMeta(
            league_id=int(league_id),
            season=int(season),
            match_date=str(match_date),
            home_team_id=int(home_team_id),
            away_team_id=int(away_team_id),
        )
    except (TypeError, ValueError, KeyError) as e:
        print(f"Could not build FixtureMeta for fixture {fixture_id}: {e}")
        return None


def collect_enhanced_match_data(fixture_id, goal_data, db_record=None):
    """Fetch per-team match statistics for a finished fixture and persist them.

    Called from process_league_fixtures immediately after the goal update.
    Writes to football_match_statistics_prod. Does NOT modify the
    game_fixtures record directly — that's still done by
    update_enhanced_match_data() using the summary dict we return.

    Args:
        fixture_id: Fixture identifier.
        goal_data: Goal dict from the /fixtures endpoint (home, away,
            halftime_*, status). Used for the legacy match_statistics
            attribute written to game_fixtures.
        db_record: The existing game_fixtures item for this fixture, used
            to derive league/team/season context. If missing, we skip the
            V2 stats write (no way to key the match_statistics item
            correctly without it) but still return a legacy summary so
            V1 handling remains intact.

    Returns:
        dict with keys:
            'match_statistics' — legacy nested shape for the V1 attribute,
            'v2_stats_ingestion' — { items_written, xg_sources, skipped },
            'collected_at' — unix timestamp.
        Or None only on unexpected errors (never on a quiet API miss).
    """
    try:
        api_response = get_fixture_statistics(fixture_id)
        teams = (api_response or {}).get('response') or []

        # Build legacy-shape nested summary from the API response (for the
        # existing game_fixtures.match_statistics attribute, which some
        # downstream consumers may still read).
        legacy_stats = _build_legacy_stats_shape(teams, db_record)

        enhanced_data = {
            'match_statistics': legacy_stats,
            'collected_at': int(datetime.now().timestamp()),
        }

        # V2 ingestion: write 18-field per-team rows to match_statistics.
        fixture_meta = _extract_fixture_meta(fixture_id, db_record)
        if fixture_meta is None:
            print(f"V2 stats skipped for fixture {fixture_id}: no FixtureMeta")
            enhanced_data['v2_stats_ingestion'] = {
                'items_written': 0,
                'skipped': True,
                'reason': 'no_fixture_meta',
            }
        elif not teams:
            print(f"V2 stats: API returned no team entries for fixture {fixture_id}")
            enhanced_data['v2_stats_ingestion'] = {
                'items_written': 0,
                'skipped': True,
                'reason': 'empty_api_response',
            }
        else:
            result = write_fixture_statistics(fixture_id, fixture_meta, api_response)
            enhanced_data['v2_stats_ingestion'] = result
            print(
                f"V2 stats: fixture {fixture_id} wrote {result['items_written']} items "
                f"(sources={result['xg_sources']})"
            )

        return enhanced_data

    except Exception as e:
        print(f"Error collecting enhanced data for fixture {fixture_id}: {e}")
        return None


def _build_legacy_stats_shape(team_entries, db_record):
    """Project the flat 18-field per-team stats into the legacy nested
    {stat_name: {'home': X, 'away': Y}} shape that V1-era consumers expect.

    Uses db_record to identify which entry is 'home' vs 'away' — not the
    API payload order, which isn't guaranteed.
    """
    shape = {
        'shots': {'home': None, 'away': None},
        'shots_on_target': {'home': None, 'away': None},
        'possession': {'home': None, 'away': None},
        'passes': {'home': None, 'away': None},
        'pass_accuracy': {'home': None, 'away': None},
        'corners': {'home': None, 'away': None},
        'fouls': {'home': None, 'away': None},
        'yellow_cards': {'home': None, 'away': None},
        'red_cards': {'home': None, 'away': None},
    }

    if not team_entries or not db_record:
        return shape

    home_team_id = (db_record.get('home') or {}).get('team_id')
    if home_team_id is None:
        return shape

    try:
        home_id = int(home_team_id)
    except (TypeError, ValueError):
        return shape

    api_to_legacy = {
        'Total Shots':      'shots',
        'Shots on Goal':    'shots_on_target',
        'Ball Possession':  'possession',
        'Total passes':     'passes',
        'Passes %':         'pass_accuracy',
        'Corner Kicks':     'corners',
        'Fouls':            'fouls',
        'Yellow Cards':     'yellow_cards',
        'Red Cards':        'red_cards',
    }

    for entry in team_entries:
        team = entry.get('team') or {}
        tid = team.get('id')
        if tid is None:
            continue
        side = 'home' if int(tid) == home_id else 'away'
        for stat in entry.get('statistics') or []:
            api_type = stat.get('type')
            legacy_key = api_to_legacy.get(api_type)
            if legacy_key is None:
                continue
            shape[legacy_key][side] = stat.get('value')

    return shape


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