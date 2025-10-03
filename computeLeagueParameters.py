import boto3
import datetime
import json
import logging
import math
import numpy as np
import os
import pandas as pd
import requests
import time

from boto3.dynamodb.conditions import Key
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from leagues import allLeagues, someLeagues
from math import log
from scipy import stats

#allLeagues = someLeagues

rapidapi_key = os.getenv('RAPIDAPI_KEY')
dynamodb = boto3.resource('dynamodb')
parameters_table = dynamodb.Table('league_parameters')
fixtures_table = dynamodb.Table('game_fixtures')

def lambda_handler(event, context):
    all_leagues_flat = [
        { **league, 'country': country }
        for country, leagues in allLeagues.items()
        for league in leagues
    ]

    for league in all_leagues_flat:
        league_id = league['id']
        name = league['name']
        country = league['country']  # Add country info
        #print(league['id'], league['name'], league['country'])

        season = get_league_start_date(league_id)[:4]    
        ref_games = games_played_per_team(league_id, season)
        scores_df = get_match_scores_min_games(
                league_id,
                start_season_year=season,
                min_games=50,
                max_back=3
            )
        league_dict = fit_league_params(scores_df)

        tune = tune_weights_grid(          # or tune_weights_optuna
            scores_df,
            league_dict["mu"],
            league_dict["alpha"],
            ref_games
        )

        # Calculate multipliers based on historical predictions
        # Use a window of the last 90 days
        end_time = int((datetime.now() - timedelta(days=1)).timestamp())
        start_time = int((datetime.now() - timedelta(days=210)).timestamp())
        multipliers = calculate_league_multipliers(country, name, start_time, end_time)
 
        # Merge all parameters
        league_dict.update(tune)
        league_dict.update(multipliers)
        league_dict['league_id'] = league_id
        league_dict['name'] = name
        league_dict['country'] = country
        league_dict['ref_games'] = ref_games

        # Update alpha adjustment factors based on actual performance
        # Higher multipliers should reduce the alpha effect
        league_dict['alpha_home_factor'] = Decimal(str(1.0 / max(float(multipliers['home_multiplier']), 0.5)))
        league_dict['alpha_away_factor'] = Decimal(str(1.0 / max(float(multipliers['away_multiplier']), 0.5)))

        league_dict_printable = convert_for_json(league_dict)
        print(f"{name}: {json.dumps(league_dict_printable, default=decimal_default)}")

        league_record = convert_for_dynamodb(league_dict)

        try:
            # Insert fixture record
            parameters_table.put_item(Item = league_record)
            print(f"Successfully inserted league record into DynamoDB with record ID: {league_record['league_id']}")
            
        except Exception as e:
            print(f"Failed to insert into DynamoDB: {e}")


    return {
        'statusCode': 200,
        'body': json.dumps(league_dict_printable, default=decimal_default)
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

def games_played_per_team(league_id, season, team_id=None):
    """
    Fetches all fixtures for a league and season, and returns number of games played by each team,
    or (if `team_id` provided) for one team only.

    Args:
        league_id (int or str): League ID in API-Football
        season (int or str): Season year
        team_id (int, optional): If provided, return only that team's count

    Returns:
        dict mapping team_id to games_played, OR int if team_id is given
    """
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    querystring = {"league": str(league_id), "season": str(season)}
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }
    try:
        resp = requests.get(url, headers=headers, params=querystring, timeout=30)
        resp.raise_for_status()
        fixtures = resp.json()["response"]
        if not fixtures:
            logging.warning(f"No fixtures found for league {league_id}, season {season}.")
            return {} if team_id is None else 0

        # Build DataFrame (using list comprehensions for speed and clarity)
        fixtures_df = pd.DataFrame({
            "home_id": [fx["teams"]["home"]["id"] for fx in fixtures],
            "away_id": [fx["teams"]["away"]["id"] for fx in fixtures]
        })

        # Stack home and away for counting
        all_team_ids = pd.concat([fixtures_df["home_id"], fixtures_df["away_id"]])
        games_count = all_team_ids.value_counts(sort=False).sort_index()

        games_dict = games_count.to_dict()
        if games_dict:
            first_team_id = next(iter(games_dict))
            return int(games_dict[first_team_id])
        else:
            return 0

    except Exception as e:
        logging.error(f"Error fetching or processing fixtures: {e}")
        return {} if team_id is None else 0


def get_football_match_scores(league_id, season):
    """
    Retrieves football match scores from the API-Football API and returns them as a DataFrame.
    
    Parameters:
    league_id (str): The ID of the league to get scores for
    season (str): The season to get scores for
    
    Returns:
    pd.DataFrame: DataFrame containing home_goals and away_goals for completed matches
    """
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    
    querystring = {
        "league": league_id,
        "season": season
    }
    
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
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
        
        # If we only want home_goals and away_goals as specified
        result_df = df[['home_goals', 'away_goals']]
        
        return result_df
    
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        return pd.DataFrame()  # Return empty DataFrame on error
    except (KeyError, ValueError) as e:
        print(f"Error processing response data: {e}")
        return pd.DataFrame()  # Return empty DataFrame on error


def fit_league_params(df):
    # Add home/away specific parameters
    g_home = df['home_goals']
    g_away = df['away_goals']
    
    # Calculate separate means and variances
    mu_home = g_home.mean()
    mu_away = g_away.mean()
    mu = (mu_home + mu_away) / 2  # Overall mean
    
    var_home = g_home.var()
    var_away = g_away.var()
    
    # Different alpha parameters for home and away
    alpha_home = max((var_home - mu_home) / mu_home**2, 0)
    alpha_away = max((var_away - mu_away) / mu_away**2, 0)
    
    # Overall alpha as weighted average
    alpha_nb = (alpha_home + alpha_away) / 2
    
    # Calculate scoring probabilities separately
    p_score_home = (g_home > 0).mean()
    p_score_away = (g_away > 0).mean()
    p_score = (p_score_home + p_score_away) / 2
    
    # Home advantage
    home_adv = mu_home / mu_away if mu_away != 0 else float('inf')
    
    return {
        'mu': mu, 
        'mu_home': mu_home,
        'mu_away': mu_away,
        'p_score': p_score,
        'p_score_home': p_score_home,
        'p_score_away': p_score_away,
        'alpha': alpha_nb,
        'alpha_home': alpha_home,
        'alpha_away': alpha_away,
        'home_adv': home_adv,
        'variance_home': var_home,
        'variance_away': var_away        
    }

def empirical_hist(goal_series, max_g=6):
    counts = Counter(np.clip(goal_series, 0, max_g))
    total  = sum(counts.values())
    return np.array([counts[g]/total for g in range(max_g+1)])

def nb_probs(mu, alpha, max_g=6):
    r = 1/alpha if alpha else 1e9
    p = 1/(1+alpha*mu) if alpha else 0
    probs = [stats.nbinom.pmf(k, r, p) for k in range(max_g+1)]
    return np.array(probs)/sum(probs)

def brier(obs, exp):        # proper scoring rule
    return np.mean((obs-exp)**2)


def tune_weights_grid(df, mu, alpha_nb, ref_games, k_grid=(np.arange(3, 9), np.arange(4, 11)), defaults=(5, 6)):
    """
    Grid-search the (k_goals, k_score) hyper-parameters that determine
    league-specific prior weights.

    Returns
    -------
    dict
        {
          'k_goals'          : float,
          'k_score'          : float,
          'goal_prior_weight': int,
          'score_prior_weight': int,
          'brier'            : float | None
        }

    Notes
    -----
    * If `alpha_nb` is zero (variance ≈ mean), we fall back to a Poisson PMF.
    * Function is fully guard‑railed: it always returns a valid dictionary
      even for empty DataFrames or numerical edge‑cases.
    """

    # ---------- 0. Early exit when no data -------------------------------
    if df.empty:
        kg_def, ks_def = defaults
        print("No match data - using default prior weights.")
        return {
            "k_goals": kg_def,
            "k_score": ks_def,
            "goal_prior_weight": kg_def,
            "score_prior_weight": ks_def,
            "brier": None,
        }

    # ---------- 1. Pre‑compute constants ---------------------------------
    n_games = len(df)
    obs = empirical_hist(
        pd.concat([df["home_goals"], df["away_goals"]])
    )  # shape (0..max_g)
    best, best_score = None, float("inf")

    # ---------- 2. Grid search -------------------------------------------
    for kg in k_grid[0]:
        for ks in k_grid[1]:
            # map k‑values → actual integer weights
            goal_w = int(np.clip(kg * (ref_games / n_games) ** 0.5, 3, 8))
            score_w = int(np.clip(ks * (ref_games / n_games) ** 0.5, 4, 10))

            # league‑specific blended mean
            mu_hat = (mu * goal_w + obs.mean() * n_games) / (goal_w + n_games)

            # choose PMF: NB when alpha_nb > 0, else Poisson
            if alpha_nb == 0.0 or mu_hat == 0.0:
                exp = stats.poisson.pmf(np.arange(len(obs)), mu_hat)
            else:
                try:
                    exp = nb_probs(mu_hat, alpha_nb)
                except Exception as e:
                    print(f"NB numerical error ({e}) – Poisson fallback")
                    exp = stats.poisson.pmf(np.arange(len(obs)), mu_hat)

            # clean any residual NaNs / infs
            exp = np.nan_to_num(exp, nan=0.0, posinf=0.0, neginf=0.0)
            if exp.sum() == 0.0:
                continue
            exp /= exp.sum()

            # Brier score
            score = brier(obs, exp)
            if np.isnan(score):
                continue

            # keep best
            if score < best_score:
                best, best_score = (kg, ks, goal_w, score_w), score

    # ---------- 3. Fallback if every grid point failed --------------------
    if best is None:
        kg_def, ks_def = defaults
        print("Grid search produced no valid point – using defaults.")
        return {
            "k_goals": kg_def,
            "k_score": ks_def,
            "goal_prior_weight": kg_def,
            "score_prior_weight": ks_def,
            "brier": None,
        }
    #goal_multiplier = 1.4
    
    # ---------- 4. Return best result ------------------------------------
    return {
        "k_goals": best[0],
        "k_score": best[1],
        "goal_prior_weight": best[2],
        "score_prior_weight": best[3],
        "brier": best_score,
    }


def get_match_scores_min_games(league_id, start_season_year, min_games=50, max_back=3):
    """
    Returns a DataFrame with at least `min_games` rows.
    Starts with `start_season_year` and walks backwards
    (max `max_back` seasons) until the quota is reached.
    """
    df_total = pd.DataFrame()
    season   = start_season_year          # string, e.g. '2024'

    for _ in range(max_back + 1):
        print(f"Fetching {season} data for league {league_id}")
        df_season = get_football_match_scores(league_id, season)

        # concatenate & drop any NA just in case
        df_total = pd.concat([df_total, df_season], ignore_index=True).dropna()

        if len(df_total) >= min_games:
            print(f"Reached {len(df_total)} matches")
            break

        # step back one year and try again
        season = str(int(season) - 1)

    if len(df_total) == 0:
        print("Still no data after fallback; downstream code will use defaults")

    return df_total


def log_smoothed_inverse(ratio, confidence, floor=0.1, ceil=10.0):
    """
    Apply log-based smoothing to inverse ratio calculation.
    Ensures stability for extreme values while allowing confidence scaling.
    """
    ratio = max(floor, min(ceil, ratio))
    log_ratio = math.log(ratio)
    smoothed_log = confidence * log_ratio
    return math.exp(-smoothed_log)

def confidence_weighted_multiplier(ratio, confidence, floor=0.1, ceil=10.0):
    """
    Apply confidence-weighted correction directly in the direction of the ratio.
    If model underpredicts (ratio > 1), multiplier > 1.
    If model overpredicts (ratio < 1), multiplier < 1.
    At low confidence, result approaches 1.0.
    """
    ratio = max(floor, min(ceil, ratio))
    multiplier = confidence * ratio + (1 - confidence) * 1.0
    if multiplier > 4.9: print(f'Calculated multiplier: {multiplier}. Capped to 5')
    return max(0.5, min(5.0, multiplier))  # Optional: clamp output to safe range

def calculate_league_multipliers(country, league, start_time=None, end_time=None, min_sample_size=20):
    """
    Calculate data-driven multipliers from historical prediction data.

    Args:
        country (str): Country name
        league (str): League name
        fixtures_table: DynamoDB table reference
        start_time (int): Optional epoch timestamp to start from
        end_time (int): Optional epoch timestamp to end at
        min_sample_size (int): Minimum number of matches required for reliable calculations

    Returns:
        dict: Multipliers and statistics for the league
    """
    if not start_time:
        start_time = int((datetime.now() - timedelta(days=90)).timestamp())
    if not end_time:
        end_time = int(datetime.now().timestamp())

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
            ':start_ts': start_time,
            ':end_ts': end_time
        },
        'FilterExpression': '#ts BETWEEN :start_ts AND :end_ts'
    }

    try:
        response = fixtures_table.query(**params)
        items = response.get('Items', [])
        while 'LastEvaluatedKey' in response:
            params['ExclusiveStartKey'] = response['LastEvaluatedKey']
            response = fixtures_table.query(**params)
            items.extend(response.get('Items', []))

        print(f'Number of Records: {len(items)}')
        home_goals_predicted = []
        home_goals_actual = []
        away_goals_predicted = []
        away_goals_actual = []
        total_goals_predicted = []
        total_goals_actual = []

        count = 0
        
        for item in items:
            if not all(key in item for key in ['home', 'away', 'goals']):
                continue
            try:
                pred_home = float(item['home']['predicted_goals'])
                pred_away = float(item['away']['predicted_goals'])
                actual_home = float(item['goals']['home'])
                actual_away = float(item['goals']['away'])

                home_goals_predicted.append(pred_home)
                home_goals_actual.append(actual_home)
                away_goals_predicted.append(pred_away)
                away_goals_actual.append(actual_away)
                total_goals_predicted.append(pred_home + pred_away)
                total_goals_actual.append(actual_home + actual_away)
                count += 1

            except (KeyError, ValueError, TypeError):
                continue

        sample_size = len(home_goals_predicted)
        print(f'Records Counted: {count}')
        if sample_size < min_sample_size:
            print(f"Warning: Small sample size for {country} {league}: {sample_size} < {min_sample_size}")
            confidence = max(sample_size / min_sample_size, 0.1)
            return {
                'home_multiplier': Decimal('1.0'),
                'away_multiplier': Decimal('1.0'),
                'total_multiplier': Decimal('1.0'),
                'confidence': Decimal(str(confidence)),
                'sample_size': sample_size,
                'timestamp': int(datetime.now().timestamp())
            }

        home_ratios = [actual / max(pred, 0.1) for actual, pred in zip(home_goals_actual, home_goals_predicted)]
        away_ratios = [actual / max(pred, 0.1) for actual, pred in zip(away_goals_actual, away_goals_predicted)]
        total_ratios = [actual / max(pred, 0.1) for actual, pred in zip(total_goals_actual, total_goals_predicted)]

        raw_home_ratio = np.mean(home_ratios)
        raw_away_ratio = np.mean(away_ratios)
        raw_total_ratio = np.mean(total_ratios)

        home_std = np.std(home_ratios)
        away_std = np.std(away_ratios)
        total_std = np.std(total_ratios)

        variance_penalty = min(1.0, 1.0 / (1.0 + math.log(1 + total_std)))
        sample_confidence = min(1.0, sample_size / 100.0)
        confidence = min(sample_confidence * variance_penalty * 2, 0.8)

        home_multiplier = confidence_weighted_multiplier(raw_home_ratio, confidence)
        away_multiplier = confidence_weighted_multiplier(raw_away_ratio, confidence)
        total_multiplier = confidence_weighted_multiplier(raw_total_ratio, confidence)

        return {
            'home_multiplier': Decimal(str(home_multiplier)),
            'away_multiplier': Decimal(str(away_multiplier)),
            'total_multiplier': Decimal(str(total_multiplier)),
            'home_ratio_raw': Decimal(str(raw_home_ratio)),
            'away_ratio_raw': Decimal(str(raw_away_ratio)),
            'total_ratio_raw': Decimal(str(raw_total_ratio)),
            'home_std': Decimal(str(home_std)),
            'away_std': Decimal(str(away_std)),
            'total_std': Decimal(str(total_std)),
            'confidence': Decimal(str(confidence)),
            'sample_size': sample_size,
            'timestamp': int(datetime.now().timestamp())
        }

    except Exception as e:
        print(f"Error calculating multipliers: {e}")
        return {
            'home_multiplier': Decimal('1.0'),
            'away_multiplier': Decimal('1.0'),
            'total_multiplier': Decimal('1.0'),
            'confidence': Decimal('0.0'),
            'sample_size': 0,
            'timestamp': int(datetime.now().timestamp())
        }


def convert_floats_to_decimal(data):
    if isinstance(data, list):
        return [convert_floats_to_decimal(item) for item in data]
    elif isinstance(data, dict):
        return {k: convert_floats_to_decimal(v) for k, v in data.items()}
    elif isinstance(data, float):
        return Decimal(str(data))
    else:
        return data


def convert_for_json(obj):
    """Recursively convert numpy types to Python types so that json.dumps works."""
    if isinstance(obj, dict):
        return {k: convert_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_for_json(i) for i in obj]
    elif isinstance(obj, np.generic):
        return obj.item()
    else:
        return obj


def convert_for_dynamodb(data):
    """
    Recursively convert float to Decimal,
    numpy.float to Decimal,
    and numpy.int to int for DynamoDB compatibility.
    """

    if isinstance(data, dict):
        return {k: convert_for_dynamodb(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_for_dynamodb(item) for item in data]
    elif isinstance(data, float):
        return Decimal(str(data))
    elif isinstance(data, np.floating):
        return Decimal(str(float(data)))
    elif isinstance(data, int):
        return data  # ints are fine
    elif isinstance(data, np.integer):
        return int(data)
    else:
        return data

# Function to convert Decimal to float for JSON serialization
def decimal_default(obj):
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    raise TypeError
