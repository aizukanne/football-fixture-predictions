"""
Thin orchestration layer for the computeLeagueParameters Lambda function.
Coordinates league parameter calculation workflow using modular components.
"""

import json
from datetime import datetime, timedelta

from ..parameters.league_calculator import fit_league_params, calculate_league_multipliers
from ..statistics.optimization import tune_weights_grid
from ..data.database_client import put_league_parameters
from ..data.api_client import get_league_start_date
from ..utils.converters import convert_for_dynamodb
from leagues import allLeagues


def lambda_handler(event, context):
    """
    Main Lambda handler for league parameter calculation.
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
                
            # Get match data for this league
            all_scores_df = get_match_scores_min_games(
                league_id,
                start_season_year=season,
                min_games=50,
                max_back=3
            )
            
            if all_scores_df.empty:
                print(f"No match data found for league {league_id} ({league_name})")
                continue
            
            print(f"Found {len(all_scores_df)} matches for league {league_name}")
            
            # Calculate base league parameters
            league_dict = fit_league_params(all_scores_df)
            
            # Add reference games for parameter calculations
            league_dict['ref_games'] = max(20, len(all_scores_df) // 10)
            
            # Tune weights using grid search
            tune_results = tune_weights_grid(
                all_scores_df,
                league_dict["mu"],
                league_dict["alpha"],
                league_dict['ref_games']
            )
            league_dict.update(tune_results)
            
            # Calculate league multipliers from historical prediction data
            multipliers = calculate_league_multipliers(
                country, 
                league_name,
                min_sample_size=20
            )
            league_dict.update(multipliers)
            
            # Add league metadata
            league_dict.update({
                'league_name': league_name,
                'country': country,
                'season': season,
                'total_matches': len(all_scores_df),
                'updated_at': int(datetime.now().timestamp())
            })
            
            # Store league parameters
            success = put_league_parameters(league_id, league_dict)
            
            if success:
                print(f"Successfully stored parameters for league {league_name}")
                results.append({
                    'league_id': league_id,
                    'league_name': league_name,
                    'status': 'success',
                    'matches_analyzed': len(all_scores_df),
                    'brier_score': league_dict.get('brier'),
                    'multiplier_confidence': float(league_dict.get('confidence', 0))
                })
            else:
                print(f"Failed to store parameters for league {league_name}")
                results.append({
                    'league_id': league_id,
                    'league_name': league_name,
                    'status': 'storage_failed'
                })
                
        except Exception as e:
            print(f"Error processing league {league_name}: {e}")
            results.append({
                'league_id': league_id,
                'league_name': league_name,
                'status': 'error',
                'error': str(e)
            })
            continue
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed_leagues': len([r for r in results if r['status'] == 'success']),
            'failed_leagues': len([r for r in results if r['status'] != 'success']),
            'results': results
        })
    }


def get_match_scores_min_games(league_id, start_season_year, min_games=50, max_back=3):
    """
    Get match scores with minimum games requirement.
    This would fetch historical match data for the league from the appropriate source.
    """
    # This is a placeholder - would implement the actual data fetching logic
    # that was in the original computeLeagueParameters.py file
    import pandas as pd
    
    # In the real implementation, this would:
    # 1. Query match data from API or database
    # 2. Filter by league_id and date range
    # 3. Ensure minimum number of games
    # 4. Return DataFrame with columns: home_team_id, away_team_id, home_goals, away_goals, date
    
    return pd.DataFrame()


def validate_league_data(df, league_name, min_games=50):
    """
    Validate that league data meets minimum requirements for parameter calculation.
    
    Args:
        df: DataFrame with match data
        league_name: Name of the league for logging
        min_games: Minimum number of games required
        
    Returns:
        bool: True if data is valid, False otherwise
    """
    if df.empty:
        print(f"No match data available for {league_name}")
        return False
        
    if len(df) < min_games:
        print(f"Insufficient matches for {league_name}: {len(df)} < {min_games}")
        return False
        
    # Check for required columns
    required_columns = ['home_goals', 'away_goals']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        print(f"Missing required columns for {league_name}: {missing_columns}")
        return False
        
    # Check for null values in critical columns
    null_counts = df[required_columns].isnull().sum()
    if null_counts.any():
        print(f"Found null values in {league_name} data: {null_counts.to_dict()}")
        return False
        
    return True


def calculate_league_statistics(df):
    """
    Calculate basic statistics for league validation and reporting.
    
    Args:
        df: DataFrame with match data
        
    Returns:
        dict: Dictionary with league statistics
    """
    if df.empty:
        return {}
        
    stats = {
        'total_matches': len(df),
        'total_goals': df['home_goals'].sum() + df['away_goals'].sum(),
        'avg_goals_per_match': (df['home_goals'].sum() + df['away_goals'].sum()) / len(df),
        'home_wins': (df['home_goals'] > df['away_goals']).sum(),
        'draws': (df['home_goals'] == df['away_goals']).sum(),
        'away_wins': (df['home_goals'] < df['away_goals']).sum(),
        'home_win_percentage': (df['home_goals'] > df['away_goals']).mean() * 100,
        'avg_home_goals': df['home_goals'].mean(),
        'avg_away_goals': df['away_goals'].mean()
    }
    
    return stats