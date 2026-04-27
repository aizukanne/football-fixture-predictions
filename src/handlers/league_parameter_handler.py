"""
Thin orchestration layer for the computeLeagueParameters Lambda function.
Coordinates league parameter calculation workflow using modular components.
"""

import json
import requests
import pandas as pd
from datetime import datetime, timedelta

from ..parameters.league_calculator import fit_league_params
from ..parameters.multiplier_calculator import calculate_league_multipliers
from ..statistics.optimization import tune_weights_grid
from ..data.database_client import put_league_parameters, fetch_league_fixtures
from ..data.api_client import get_league_start_date
from ..utils.converters import convert_for_dynamodb
from ..utils.constants import RAPIDAPI_KEY, API_FOOTBALL_BASE_URL, API_FOOTBALL_HOST
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
            season_str = get_league_start_date(league_id)[:4]
            if not season_str:
                print(f"Couldn't determine season for league {league_id}, skipping")
                continue
                
            # Get match data for this league
            all_scores_df = get_match_scores_min_games(
                league_id,
                start_season_year=season_str,
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
            # Pass the entire league_dict as the mu parameter (it's a dictionary of parameters)
            tune_results = tune_weights_grid(
                all_scores_df,
                league_dict,  # Pass entire dict, not just mu value
                league_dict["alpha"],
                league_dict['ref_games']
            )
            league_dict.update(tune_results)
            
            # Calculate league multipliers from historical prediction data
            # Define time window for multiplier calculation (last 210 days, similar to legacy)
            end_time = int((datetime.now() - timedelta(days=1)).timestamp())
            start_time = int((datetime.now() - timedelta(days=210)).timestamp())
            
            # Fetch historical fixtures for this league
            print(f"Fetching fixtures for multiplier calculation: {country} - {league_name}")
            fixtures_data = fetch_league_fixtures(country, league_name, start_time, end_time)
            print(f"Found {len(fixtures_data)} fixtures for multiplier calculation")
            
            # Calculate multipliers using the new version-safe function
            # Pass league_id and fixtures_data as required by the new signature
            multipliers = calculate_league_multipliers(
                league_id=league_id,
                fixtures_data=fixtures_data,
                version_filter=None,  # Use current version
                min_sample_size=20
            )
            league_dict.update(multipliers)
            
            # Add league metadata
            league_dict.update({
                'league_name': league_name,
                'country': country,
                'season': int(season_str),  # Convert to integer for DynamoDB
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
                    'brier_score_home': league_dict.get('brier_home', league_dict.get('brier')),
                    'brier_score_away': league_dict.get('brier_away'),
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


def get_football_match_scores(league_id, season):
    """
    Retrieves football match scores from the API-Football API and returns them as a DataFrame.
    
    Parameters:
    league_id (str): The ID of the league to get scores for
    season (str): The season to get scores for
    
    Returns:
    pd.DataFrame: DataFrame containing home_goals and away_goals for completed matches
    """
    url = f"{API_FOOTBALL_BASE_URL}/fixtures"
    
    querystring = {
        "league": league_id,
        "season": season
    }
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": API_FOOTBALL_HOST
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        data = response.json()
        
        # Initialize empty lists to store our data
        match_data = []
        
        # Process each fixture in the response
        for fixture in data['response']:
            # Check if the match is finished and has fulltime scores
            if (fixture['fixture']['status']['long'] == 'Match Finished' and
                fixture['score']['fulltime']['home'] is not None and
                fixture['score']['fulltime']['away'] is not None):
                
                match_info = {
                    'home_team': fixture['teams']['home']['name'],
                    'away_team': fixture['teams']['away']['name'],
                    'home_goals': fixture['goals']['home'],
                    'away_goals': fixture['goals']['away'],
                    'match_date': fixture['fixture']['date']
                }
                
                match_data.append(match_info)
        
        # Create DataFrame from the collected data
        df = pd.DataFrame(match_data)
        
        # If we have data, return just the goal columns
        if not df.empty:
            result_df = df[['home_goals', 'away_goals']]
            return result_df
        
        return pd.DataFrame()
    
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        return pd.DataFrame()  # Return empty DataFrame on error
    except (KeyError, ValueError) as e:
        print(f"Error processing response data: {e}")
        return pd.DataFrame()  # Return empty DataFrame on error


def get_match_scores_min_games(league_id, start_season_year, min_games=50, max_back=3):
    """
    Returns a DataFrame with at least `min_games` rows.
    Starts with `start_season_year` and walks backwards
    (max `max_back` seasons) until the quota is reached.
    
    Parameters:
    league_id (str): The ID of the league to get scores for
    start_season_year (str): Starting season year (e.g., '2024')
    min_games (int): Minimum number of games required
    max_back (int): Maximum number of seasons to look back
    
    Returns:
    pd.DataFrame: DataFrame with at least min_games matches
    """
    df_total = pd.DataFrame()
    season = start_season_year  # string, e.g. '2024'
    
    for _ in range(max_back + 1):
        print(f"Fetching {season} data for league {league_id}")
        df_season = get_football_match_scores(league_id, season)
        
        # concatenate & drop any NA just in case
        df_total = pd.concat([df_total, df_season], ignore_index=True).dropna()
        
        if len(df_total) >= min_games:
            print(f"Reached {len(df_total)} matches for league {league_id}")
            break
        
        # step back one year and try again
        season = str(int(season) - 1)
    
    if len(df_total) == 0:
        print(f"No match data found for league {league_id}")
    
    return df_total


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