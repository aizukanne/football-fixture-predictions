"""
Thin orchestration layer for the computeTeamParameters Lambda function.
Coordinates team parameter calculation workflow using modular components.

Modes:
1. SQS Mode (NEW): Process single league from SQS message
2. Direct Mode (LEGACY): Process all leagues sequentially (for backward compatibility)
"""

import json
from datetime import datetime, timedelta

from ..parameters.team_calculator import fit_team_params, calculate_team_multipliers
from ..statistics.optimization import tune_weights_grid_team
from ..statistics.brier_feedback import update_brier_ema, compute_k_adjustment
from ..data.database_client import (put_team_parameters, fetch_league_fixtures,
                                    get_team_params_from_db)
from ..data.api_client import get_league_teams, get_league_start_date
from ..utils.converters import convert_for_dynamodb
from ..utils.constants import MINIMUM_GAMES_THRESHOLD
from leagues import allLeagues


def lambda_handler(event, context):
    """
    Main Lambda handler for team parameter calculation.
    
    Supports two invocation modes:
    1. SQS Mode: Process single league from SQS message (NEW - prevents timeout)
    2. Direct Mode: Process all leagues (LEGACY - backward compatibility)
    
    SQS Message Format:
    {
        "league_id": 39,
        "league_name": "Premier League",
        "country": "England",
        "trigger_type": "scheduled",
        "force_recompute": false,
        "timestamp": 1696579200
    }
    """
    # Check if invoked via SQS
    if 'Records' in event and event['Records']:
        print("📩 SQS Mode: Processing single league from SQS message")
        return process_sqs_event(event, context)
    else:
        print("🔄 Direct Mode: Processing all leagues (legacy mode)")
        return process_all_leagues(event, context)


def process_sqs_event(event, context):
    """
    Process team parameters for a single league from SQS message.
    
    Args:
        event: SQS event with Records
        context: Lambda context
    
    Returns:
        Response with processing status
    """
    results = []
    
    # Process each SQS record (typically 1 per invocation with batch size 1)
    for record in event['Records']:
        try:
            # Parse SQS message body
            message_body = json.loads(record['body'])
            
            league_id = message_body['league_id']
            league_name = message_body.get('league_name', f'League {league_id}')
            country = message_body.get('country', 'Unknown')
            trigger_type = message_body.get('trigger_type', 'sqs')
            force_recompute = message_body.get('force_recompute', False)
            
            print(f"\n{'='*70}")
            print(f"Processing League: {league_name} (ID: {league_id})")
            print(f"Country: {country}")
            print(f"Trigger Type: {trigger_type}")
            print(f"Force Recompute: {force_recompute}")
            print(f"{'='*70}\n")
            
            # Create league object in expected format
            league = {
                'id': league_id,
                'name': league_name,
                'country': country
            }
            
            # Process the single league
            league_result = process_single_league(league, force_recompute)
            results.append(league_result)
            
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing SQS message: {e}")
            results.append({
                'status': 'error',
                'error': f'Invalid JSON in message: {str(e)}',
                'message_id': record.get('messageId', 'unknown')
            })
        except KeyError as e:
            print(f"❌ Missing required field in message: {e}")
            results.append({
                'status': 'error',
                'error': f'Missing required field: {str(e)}',
                'message_id': record.get('messageId', 'unknown')
            })
        except Exception as e:
            print(f"❌ Unexpected error processing message: {e}")
            results.append({
                'status': 'error',
                'error': str(e),
                'message_id': record.get('messageId', 'unknown')
            })
    
    # Return response
    successful = len([r for r in results if r.get('status') == 'success'])
    failed = len([r for r in results if r.get('status') != 'success'])
    
    return {
        'statusCode': 200 if failed == 0 else 207,  # 207 = Multi-Status
        'body': json.dumps({
            'mode': 'sqs',
            'records_processed': len(results),
            'successful': successful,
            'failed': failed,
            'results': results
        })
    }


def process_all_leagues(event, context):
    """
    Process team parameters for all leagues (legacy mode).
    Maintains backward compatibility with direct Lambda invocation.
    
    Args:
        event: Direct invocation event
        context: Lambda context
    
    Returns:
        Response with processing status
    """
    all_leagues_flat = [
        { **league, 'country': country }
        for country, leagues in allLeagues.items()
        for league in leagues
    ]

    print(f"📊 Processing {len(all_leagues_flat)} leagues in direct mode")
    results = []
    force_recompute = event.get('force_recompute', False)

    for league in all_leagues_flat:
        league_result = process_single_league(league, force_recompute)
        results.append(league_result)
    
    # Return aggregated results
    successful = len([r for r in results if r.get('status') == 'success'])
    failed = len([r for r in results if r.get('status') != 'success'])
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'mode': 'direct',
            'processed_leagues': len(all_leagues_flat),
            'successful': successful,
            'failed': failed,
            'results': results
        })
    }


def process_single_league(league, force_recompute=False):
    """
    Process team parameters for a single league.
    
    Args:
        league: League dictionary with id, name, and country
        force_recompute: Whether to force recomputation even if recent parameters exist
    
    Returns:
        Dictionary with processing result
    """
    league_id = league['id']
    league_name = league['name']
    country = league['country']
    
    print(f"Processing league: {league_name} (ID: {league_id})")
    
    try:
        # Get season information
        season = get_league_start_date(league_id)[:4]
        if not season:
            print(f"Couldn't determine season for league {league_id}, skipping")
            return {
                'league_id': league_id,
                'league_name': league_name,
                'status': 'skipped',
                'reason': 'no_season_data'
            }
            
        # Verify league parameters exist
        from ..data.database_client import fetch_league_parameters
        league_params = fetch_league_parameters(league_id, season)
        if not league_params:
            print(f"No league parameters found for league {league_id}, season {season}, skipping")
            return {
                'league_id': league_id,
                'league_name': league_name,
                'status': 'skipped',
                'reason': 'no_league_parameters'
            }
        
        # Get teams in this league
        teams = get_league_teams(league_id, season)
        if not teams:
            print(f"No teams found for league {league_id} ({league_name})")
            return {
                'league_id': league_id,
                'league_name': league_name,
                'status': 'skipped',
                'reason': 'no_teams'
            }
            
        # Get match data for the league
        all_scores_df = get_match_scores_min_games(
            league_id,
            start_season_year=season,
            min_games=50,
            max_back=3
        )
        
        if all_scores_df.empty:
            print(f"No match data found for league {league_id} ({league_name})")
            return {
                'league_id': league_id,
                'league_name': league_name,
                'status': 'skipped',
                'reason': 'no_match_data'
            }
        
        # Fetch historical fixtures for multiplier calculation
        end_time = int((datetime.now() - timedelta(days=1)).timestamp())
        start_time = int((datetime.now() - timedelta(days=240)).timestamp())
        league_fixtures = fetch_league_fixtures(country, league_name, start_time, end_time)
        
        # Process each team
        team_results = []
        for team in teams:
            team_id = team['team_id']
            team_name = team['team_name']
            
            print(f"Processing team: {team_name} (ID: {team_id}) in {league_name}")
            
            try:
                # Get team-specific data
                team_games = games_played_per_team(league_id, season, team_id)
                team_scores_df = filter_team_matches(all_scores_df, team_id)

                # Calculate team parameters with season for venue/tactical params
                team_dict = fit_team_params(team_scores_df, team_id, league_id, season=season)
                
                # Mark parameter source
                if team_scores_df.empty or len(team_scores_df) < 10:
                    team_dict['using_league_params'] = True
                else:
                    team_dict['using_league_params'] = not (
                        team_dict.get('using_team_home', False) and 
                        team_dict.get('using_team_away', False)
                    )
                
                # Clean up temporary flags
                team_dict.pop('using_team_home', None)
                team_dict.pop('using_team_away', None)
                
                # Read previous DB record to extract Brier EMA and k values for feedback
                existing_params = get_team_params_from_db(team_id, league_id) or {}
                prev_brier_ema = float(existing_params.get(
                    'brier_ema', existing_params.get('brier', 0.25)))

                # Tune weights if we have enough data
                if not team_dict.get('using_league_params', True) and team_games > MINIMUM_GAMES_THRESHOLD:
                    tune_results = tune_weights_grid_team(
                        team_scores_df,
                        team_dict,
                        team_dict["alpha"],
                        team_games
                    )
                    team_dict.update(tune_results)

                    # Apply Brier EMA feedback: adjust k values based on team's
                    # accumulated prediction quality relative to the league average
                    league_brier = float(league_params.get('brier', 0.25))
                    new_brier_ema = update_brier_ema(
                        current_brier=float(team_dict['brier']),
                        prev_brier_ema=prev_brier_ema,
                    )
                    feedback = compute_k_adjustment(
                        brier_ema=new_brier_ema,
                        league_brier=league_brier,
                        base_k_goals=team_dict['k_goals'],
                        base_k_score=team_dict['k_score'],
                        games_played=team_games,
                    )
                    team_dict.update({
                        'brier_ema':          new_brier_ema,
                        'k_goals':            feedback['k_goals'],
                        'k_score':            feedback['k_score'],
                        'goal_prior_weight':  feedback['k_goals'],
                        'score_prior_weight': feedback['k_score'],
                        'k_feedback_step':    feedback['k_feedback_step'],
                        'k_feedback_reason':  feedback['k_feedback_reason'],
                    })
                    print(
                        f"Brier feedback for {team_name}: ema={new_brier_ema:.4f} "
                        f"vs league={league_brier:.4f}, step={feedback['k_feedback_step']} "
                        f"({feedback['k_feedback_reason']})"
                    )
                else:
                    # Use league parameter values; carry forward EMA unchanged
                    print(f"Using league weight parameters for team {team_name}")
                    team_dict.update({
                        'k_goals': league_params.get('k_goals', 3),
                        'k_score': league_params.get('k_score', 4),
                        'goal_prior_weight': league_params.get('goal_prior_weight', 3),
                        'score_prior_weight': league_params.get('score_prior_weight', 4),
                        'brier': league_params.get('brier', 0.1),
                        'brier_ema': prev_brier_ema,
                        'k_feedback_step': 0,
                        'k_feedback_reason': 'insufficient_games',
                    })
                
                # Calculate multipliers
                multipliers = calculate_team_multipliers(team_id, league_fixtures)
                
                # Use league multipliers if insufficient data
                if multipliers['sample_size'] < MINIMUM_GAMES_THRESHOLD:
                    print(f"Insufficient prediction data for team {team_name}. Using league multipliers.")
                    multipliers = get_default_team_multipliers(league_params)
                
                # Merge all parameters
                team_dict.update(multipliers)
                
                # Add metadata
                team_dict.update({
                    'team_name': team_name,
                    'league_name': league_name,
                    'country': country,
                    'season': season,
                    'games_played': team_games,
                    'updated_at': int(datetime.now().timestamp())
                })

                # Store team parameters with composite key (team_id + league_id)
                success = put_team_parameters(team_id, league_id, team_dict)
                
                if success:
                    print(f"Successfully stored parameters for team {team_name}")
                    team_results.append({
                        'team_id': team_id,
                        'status': 'success',
                        'using_league_params': team_dict.get('using_league_params', False)
                    })
                else:
                    print(f"Failed to store parameters for team {team_name}")
                    team_results.append({
                        'team_id': team_id,
                        'status': 'storage_failed'
                    })

            except Exception as e:
                print(f"Error processing team {team_name}: {e}")
                team_results.append({
                    'team_id': team_id,
                    'status': 'error',
                    'error': str(e)
                })
                continue
        
        # Return league processing result
        successful_teams = len([r for r in team_results if r.get('status') == 'success'])
        failed_teams = len([r for r in team_results if r.get('status') != 'success'])
        
        return {
            'league_id': league_id,
            'league_name': league_name,
            'country': country,
            'status': 'success' if successful_teams > 0 else 'failed',
            'teams_processed': len(teams),
            'teams_successful': successful_teams,
            'teams_failed': failed_teams,
            'team_results': team_results
        }
                
    except Exception as e:
        print(f"Error processing league {league_name}: {e}")
        return {
            'league_id': league_id,
            'league_name': league_name,
            'status': 'error',
            'error': str(e)
        }


def get_match_scores_min_games(league_id, start_season_year, min_games=50, max_back=3):
    """
    Returns a DataFrame with at least `min_games` rows for the league.
    Enhanced to include team IDs for team-specific analysis.
    Starts with `start_season_year` and walks backwards
    (max `max_back` seasons) until the quota is reached.

    Args:
        league_id: League identifier
        start_season_year: Starting season year (e.g., "2024")
        min_games: Minimum number of games required
        max_back: Maximum number of seasons to go back

    Returns:
        pd.DataFrame: Combined match data from multiple seasons
    """
    import pandas as pd
    from ..data.api_client import get_football_match_scores

    df_total = pd.DataFrame()
    season = start_season_year

    for _ in range(max_back + 1):
        print(f"Fetching {season} data for league {league_id}")
        df_season = get_football_match_scores(league_id, season)

        # Only process if we got data with the right columns
        if not df_season.empty and 'home_goals' in df_season.columns and 'away_goals' in df_season.columns:
            df_total = pd.concat([df_total, df_season], ignore_index=True).dropna(subset=['home_goals', 'away_goals'])
        else:
            print(f"No valid match data for season {season}")

        if len(df_total) >= min_games:
            print(f"Reached {len(df_total)} matches")
            break

        season = str(int(season) - 1)

    if len(df_total) == 0:
        print("Still no data after fallback; downstream code will use defaults")

    return df_total


def filter_team_matches(df, team_id):
    """
    Filter matches DataFrame to only include matches involving the specified team.

    Args:
        df: DataFrame with match data
        team_id: Team ID to filter for

    Returns:
        Filtered DataFrame with only matches involving the team
    """
    if df.empty:
        return df

    team_matches = df[
        (df['home_team_id'] == team_id) |
        (df['away_team_id'] == team_id)
    ]

    return team_matches


def games_played_per_team(league_id, season, team_id):
    """
    Get the number of games played by a team in a specific league and season.

    Args:
        league_id: League identifier
        season: Season year
        team_id: Team identifier

    Returns:
        Number of games played
    """
    from ..data.api_client import get_team_statistics

    try:
        team_stats = get_team_statistics(league_id, season, team_id)

        if team_stats and 'response' in team_stats and team_stats['response']:
            fixtures = team_stats['response'].get('fixtures', {})
            games_played = fixtures.get('played', {}).get('total', 0)
            return games_played
        else:
            print(f"No statistics found for team {team_id}")
            return 0
    except Exception as e:
        print(f"Error getting games played for team {team_id}: {e}")
        return 0


def get_default_team_multipliers(league_params):
    """Get default multipliers when insufficient team data."""
    from decimal import Decimal
    from datetime import datetime
    
    return {
        'home_multiplier': league_params.get('home_multiplier', Decimal('1.0')),
        'away_multiplier': league_params.get('away_multiplier', Decimal('1.0')),
        'total_multiplier': league_params.get('total_multiplier', Decimal('1.0')),
        'home_std': league_params.get('home_std', Decimal('1.0')),
        'away_std': league_params.get('away_std', Decimal('1.0')),
        'confidence': Decimal('0.1'),
        'sample_size': 0,
        'timestamp': int(datetime.now().timestamp())
    }