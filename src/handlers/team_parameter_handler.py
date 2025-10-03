"""
Thin orchestration layer for the computeTeamParameters Lambda function.
Coordinates team parameter calculation workflow using modular components.
"""

import json
from datetime import datetime

from ..parameters.team_calculator import fit_team_params, calculate_team_multipliers
from ..statistics.optimization import tune_weights_grid_team
from ..data.database_client import put_team_parameters, fetch_league_fixtures
from ..data.api_client import get_league_teams, get_league_start_date
from ..utils.converters import convert_for_dynamodb
from leagues import allLeagues


def lambda_handler(event, context):
    """
    Main Lambda handler for team parameter calculation.
    Thin orchestration layer that delegates to modular components.
    """
    all_leagues_flat = [
        { **league, 'country': country }
        for country, leagues in allLeagues.items()
        for league in leagues
    ]

    results = []

    for league in all_leagues_flat:
        league_id = league['id']
        league_name = league['name']
        country = league['country']
        
        print(f"Processing league: {league_name} (ID: {league_id})")
        
        try:
            # Get season information
            season = get_league_start_date(league_id)[:4]
            if not season:
                print(f"Couldn't determine season for league {league_id}, skipping")
                continue
                
            # Verify league parameters exist
            from ..data.database_client import fetch_league_parameters
            league_params = fetch_league_parameters(league_id)
            if not league_params:
                print(f"No league parameters found for league {league_id}, skipping")
                continue
            
            # Get teams in this league
            teams = get_league_teams(league_id, season)
            if not teams:
                print(f"No teams found for league {league_id} ({league_name})")
                continue
                
            # Get match data for the league
            all_scores_df = get_match_scores_min_games(
                league_id,
                start_season_year=season,
                min_games=50,
                max_back=3
            )
            
            if all_scores_df.empty:
                print(f"No match data found for league {league_id} ({league_name})")
                continue
            
            # Fetch historical fixtures for multiplier calculation
            end_time = int((datetime.now() - timedelta(days=1)).timestamp())
            start_time = int((datetime.now() - timedelta(days=240)).timestamp())
            league_fixtures = fetch_league_fixtures(country, league_name, start_time, end_time)
            
            # Process each team
            for team in teams:
                team_id = team['team_id']
                team_name = team['team_name']
                
                print(f"Processing team: {team_name} (ID: {team_id}) in {league_name}")
                
                try:
                    # Get team-specific data
                    team_games = games_played_per_team(league_id, season, team_id)
                    team_scores_df = filter_team_matches(all_scores_df, team_id)
                    
                    # Calculate team parameters
                    team_dict = fit_team_params(team_scores_df, team_id, league_id)
                    
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
                    
                    # Tune weights if we have enough data
                    if not team_dict.get('using_league_params', True) and team_games > 10:
                        tune_results = tune_weights_grid_team(
                            team_scores_df,
                            team_dict["mu"],
                            team_dict["alpha"],
                            team_games
                        )
                        team_dict.update(tune_results)
                    else:
                        # Use league parameter values
                        print(f"Using league weight parameters for team {team_name}")
                        team_dict.update({
                            'k_goals': league_params.get('k_goals', 3),
                            'k_score': league_params.get('k_score', 4),
                            'goal_prior_weight': league_params.get('goal_prior_weight', 3),
                            'score_prior_weight': league_params.get('score_prior_weight', 4),
                            'brier': league_params.get('brier', 0.1)
                        })
                    
                    # Calculate multipliers
                    multipliers = calculate_team_multipliers(team_id, league_fixtures)
                    
                    # Use league multipliers if insufficient data
                    if multipliers['sample_size'] < 10:
                        print(f"Insufficient prediction data for team {team_name}. Using league multipliers.")
                        multipliers = get_default_team_multipliers(league_params)
                    
                    # Merge all parameters
                    team_dict.update(multipliers)
                    
                    # Add metadata
                    team_dict.update({
                        'team_name': team_name,
                        'league_id': league_id,
                        'league_name': league_name,
                        'country': country,
                        'season': season,
                        'games_played': team_games,
                        'updated_at': int(datetime.now().timestamp())
                    })
                    
                    # Store team parameters
                    unique_team_id = f"{league_id}-{team_id}"
                    success = put_team_parameters(unique_team_id, team_dict)
                    
                    if success:
                        print(f"Successfully stored parameters for team {team_name}")
                        results.append({
                            'team_id': unique_team_id,
                            'status': 'success',
                            'using_league_params': team_dict.get('using_league_params', False)
                        })
                    else:
                        print(f"Failed to store parameters for team {team_name}")
                        results.append({
                            'team_id': unique_team_id,
                            'status': 'storage_failed'
                        })
                        
                except Exception as e:
                    print(f"Error processing team {team_name}: {e}")
                    results.append({
                        'team_id': f"{league_id}-{team_id}",
                        'status': 'error',
                        'error': str(e)
                    })
                    continue
                    
        except Exception as e:
            print(f"Error processing league {league_name}: {e}")
            results.append({
                'league_id': league_id,
                'status': 'league_error',
                'error': str(e)
            })
            continue
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed_teams': len([r for r in results if r['status'] == 'success']),
            'failed_teams': len([r for r in results if r['status'] != 'success']),
            'results': results
        })
    }


def get_match_scores_min_games(league_id, start_season_year, min_games=50, max_back=3):
    """
    Get match scores with minimum games requirement.
    This would need to be implemented based on the original logic.
    """
    # Placeholder - would implement the actual data fetching logic
    import pandas as pd
    return pd.DataFrame()


def filter_team_matches(df, team_id):
    """Filter matches for a specific team."""
    from ..parameters.team_calculator import filter_team_matches as filter_func
    return filter_func(df, team_id)


def games_played_per_team(league_id, season, team_id):
    """Get number of games played by team."""
    from ..parameters.team_calculator import games_played_per_team as games_func
    return games_func(league_id, season, team_id)


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