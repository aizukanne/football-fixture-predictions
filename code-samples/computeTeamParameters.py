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
parameters_table = dynamodb.Table('team_parameters')
fixtures_table = dynamodb.Table('game_fixtures')


def lambda_handler(event, context):
    """
    Main Lambda function to calculate team-specific parameters.
    Uses league parameters as fallback when team data is insufficient.
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
        
        # Get season start year
        season = get_league_start_date(league_id)[:4]
        if not season:
            print(f"Couldn't determine season for league {league_id}, skipping")
            continue
            
        # Verify league parameters exist before proceeding
        league_params = fetch_league_parameters(league_id)
        if not league_params:
            print(f"No league parameters found for league {league_id}, skipping")
            continue
        
        # Get list of teams in this league
        teams = get_league_teams(league_id, season)
        if not teams:
            print(f"No teams found for league {league_id} ({league_name})")
            continue
            
        # Get match data for this league with enough history
        all_scores_df = get_match_scores_min_games(
            league_id,
            start_season_year=season,
            min_games=50,
            max_back=3
        )
        
        if all_scores_df.empty:
            print(f"No match data found for league {league_id} ({league_name})")
            continue
        
        # Fetch all historical fixtures for this league in one query
        end_time = int((datetime.now() - timedelta(days=1)).timestamp())
        start_time = int((datetime.now() - timedelta(days=240)).timestamp())
        league_fixtures = fetch_league_fixtures(country, league_name, start_time, end_time)
        
        # Process each team in the league
        for team in teams:
            team_id = team['team_id']
            team_name = team['team_name']
            
            print(f"Processing team: {team_name} (ID: {team_id}) in {league_name}")
            
            # Get games played by this team
            team_games = games_played_per_team(league_id, season, team_id)
            
            # Filter matches for this team
            team_scores_df = filter_team_matches(all_scores_df, team_id)
            
            # Calculate team parameters using league params as fallback
            team_dict = fit_team_params(team_scores_df, team_id, league_id)
            
            # Mark if we're using league parameters
            if team_scores_df.empty or len(team_scores_df) < 10:
                team_dict['using_league_params'] = True
            else:
                team_dict['using_league_params'] = not (team_dict.get('using_team_home', False) and 
                                                      team_dict.get('using_team_away', False))
            
            # Clean up temporary flags
            if 'using_team_home' in team_dict:
                del team_dict['using_team_home']
            if 'using_team_away' in team_dict:
                del team_dict['using_team_away']
            
            # Tune weights for this team only if we have enough data
            if not team_dict.get('using_league_params', True) and team_games > 10:
                tune = tune_weights_grid_team(
                    team_scores_df,
                    team_dict["mu"],
                    team_dict["alpha"],
                    team_games
                )
                team_dict.update(tune)
            else:
                # Use league parameter values for weights
                print(f"Using league weight parameters for team {team_name}")
                team_dict.update({
                    'k_goals': league_params.get('k_goals', 3),
                    'k_score': league_params.get('k_score', 4),
                    'goal_prior_weight': league_params.get('goal_prior_weight', 3),
                    'score_prior_weight': league_params.get('score_prior_weight', 4),
                    'brier': league_params.get('brier', 0.1)
                })
            
            # Calculate multipliers based on historical predictions for this team
            multipliers = calculate_team_multipliers(team_id, league_fixtures)
            
            # If we don't have enough fixture data, use league multipliers
            if multipliers['sample_size'] < 10:
                print(f"Insufficient prediction data for team {team_name}. Using league multipliers.")
                multipliers = {
                    'home_multiplier': league_params.get('home_multiplier', Decimal('1.0')),
                    'away_multiplier': league_params.get('away_multiplier', Decimal('1.0')),
                    'total_multiplier': league_params.get('total_multiplier', Decimal('1.0')),
                    'home_std': league_params.get('home_std', Decimal('1.0')),
                    'away_std': league_params.get('away_std', Decimal('1.0')),
                    'confidence': Decimal('0.1'),  # Low confidence since we're using league values
                    'sample_size': 0,  # Mark as using league values
                    'timestamp': int(datetime.now().timestamp())
                }
            
            # Merge all parameters
            team_dict.update(multipliers)
            team_dict['league_id'] = league_id
            team_dict['team_id'] = team_id
            team_dict['team_name'] = team_name
            team_dict['league_name'] = league_name
            team_dict['country'] = country
            team_dict['ref_games'] = team_games
            
            # Update alpha adjustment factors
            team_dict['alpha_home_factor'] = Decimal(str(1.0 / max(float(multipliers['home_multiplier']), 0.5)))
            team_dict['alpha_away_factor'] = Decimal(str(1.0 / max(float(multipliers['away_multiplier']), 0.5)))

            # Create Unique key
            team_dict['id'] = f"{league_id}-{team_id}"
            
            # Convert to printable format for logging
            team_dict_printable = convert_for_json(team_dict)
            print(f"{team_name}: {json.dumps(team_dict_printable, default=decimal_default)}")
            
            # Convert to DynamoDB format
            team_record = convert_for_dynamodb(team_dict)
            
            try:
                # Insert team record - use team_parameters table
                parameters_table.put_item(Item = team_record)
                print(f"Successfully inserted team record into DynamoDB for {team_name}")
                results.append(team_dict_printable)
            except Exception as e:
                print(f"Failed to insert into DynamoDB: {e}")

    return {
        'statusCode': 200,
        'body': 'Task Completed!'
    }


def get_league_teams(league_id, season):
    """
    Fetch all teams in a given league for the specified season.
    
    Parameters:
    - league_id: The league ID.
    - season: The season year.
    
    Returns:
    - List of dictionaries, each containing team_id and team_name.
    """
    url = "https://api-football-v1.p.rapidapi.com/v3/teams"
    querystring = {"league": str(league_id), "season": str(season)}
    
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        
        data = response.json()
        teams = []
        
        for item in data.get("response", []):
            team = item.get("team", {})
            teams.append({
                "team_id": team.get("id"),
                "team_name": team.get("name")
            })
        
        print(f"Found {len(teams)} teams for league {league_id}, season {season}")
        return teams
        
    except Exception as e:
        print(f"Error fetching teams for league {league_id}, season {season}: {e}")
        return []


def filter_team_matches(df, team_id):
    """
    Filter a DataFrame of matches to only include those involving a specific team.
    
    Parameters:
    - df: DataFrame containing match data with home_team_id and away_team_id columns
    - team_id: The team ID to filter for
    
    Returns:
    - DataFrame containing only matches involving the specified team
    """
    if df.empty:
        return pd.DataFrame()
        
    # Filter matches where the team is either home or away
    team_matches = df[(df['home_team_id'] == team_id) | (df['away_team_id'] == team_id)].copy()
    
    return team_matches


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

def games_played_per_team(league_id, season, team_id):
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
        
        if team_id is not None:
            # Return the count for the specific team_id
            return int(games_dict.get(team_id, 0))
        else:
            # Return the whole dictionary
            return games_dict

    except Exception as e:
        logging.error(f"Error fetching or processing fixtures: {e}")
        return {} if team_id is None else 0


def get_football_match_scores(league_id, season):
    """
    Retrieves football match scores from the API-Football API and returns them as a DataFrame.
    Enhanced to include team IDs for team-specific analysis.
    
    Parameters:
    league_id (str): The ID of the league to get scores for
    season (str): The season to get scores for
    
    Returns:
    pd.DataFrame: DataFrame containing match details including team IDs and goals
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
                    'home_team_id': fixture['teams']['home']['id'],
                    'away_team_id': fixture['teams']['away']['id'],
                    'home_team': fixture['teams']['home']['name'],
                    'away_team': fixture['teams']['away']['name'],
                    'home_goals': fixture['goals']['home'],
                    'away_goals': fixture['goals']['away'],
                    'match_date': fixture['fixture']['date'],
                    'fixture_id': fixture['fixture']['id']
                }
                
                match_data.append(match_info)
        
        # Create DataFrame from the collected data
        df = pd.DataFrame(match_data)
        
        if df.empty:
            print(f"No match data found for league {league_id}, season {season}")
            # Return empty DataFrame with correct column structure
            return pd.DataFrame(columns=['home_team_id', 'away_team_id', 'home_team', 'away_team', 
                                       'home_goals', 'away_goals', 'match_date', 'fixture_id'])
            
        return df
    
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        # Return empty DataFrame with correct column structure on error
        return pd.DataFrame(columns=['home_team_id', 'away_team_id', 'home_team', 'away_team', 
                                   'home_goals', 'away_goals', 'match_date', 'fixture_id'])
    except (KeyError, ValueError) as e:
        print(f"Error processing response data: {e}")
        # Return empty DataFrame with correct column structure on error
        return pd.DataFrame(columns=['home_team_id', 'away_team_id', 'home_team', 'away_team', 
                                   'home_goals', 'away_goals', 'match_date', 'fixture_id'])


def fetch_league_parameters(league_id):
    """
    Retrieve the league parameters from the league_parameters DynamoDB table
    
    Parameters:
    - league_id: The league ID to fetch parameters for
    
    Returns:
    - Dictionary of league parameters or None if not found
    """
    try:
        # Define the table
        league_parameters_table = dynamodb.Table('league_parameters')
        
        # Query the table with the league_id as the partition key
        response = league_parameters_table.get_item(
            Key={'league_id': int(league_id)}
        )
        
        if 'Item' in response:
            #return response['Item']
            return {k: _safe_convert_to_float(v) if isinstance(v, Decimal) else v for k, v in response['Item'].items()}
        else:
            print(f"No league parameters found for league ID {league_id}")
            return None
            
    except Exception as e:
        print(f"Error fetching league parameters for league ID {league_id}: {e}")
        return None


def fit_team_params(df, team_id, league_id):
    """
    Calculate team-specific parameters from match data.
    If insufficient data, use league parameters.
    
    Parameters:
    - df: DataFrame containing match data with team IDs
    - team_id: ID of the team to analyze
    - league_id: ID of the league this team belongs to
    
    Returns:
    - Dictionary of team parameters
    """
    # Define the minimum matches needed for reliable parameter calculation
    MIN_HOME_MATCHES = 5
    MIN_AWAY_MATCHES = 5
    
    # Fetch league parameters to use as fallback
    league_params = fetch_league_parameters(league_id)
    
    if df.empty or len(df) < 10:  # Too little data overall
        if league_params:
            print(f"Insufficient match data for team {team_id}. Using league parameters for league {league_id}.")
            return {
                'mu': league_params.get('mu', 1.35),
                'mu_home': league_params.get('mu_home', 1.5),
                'mu_away': league_params.get('mu_away', 1.2),
                'p_score': league_params.get('p_score', 0.7),
                'p_score_home': league_params.get('p_score_home', 0.75),
                'p_score_away': league_params.get('p_score_away', 0.65),
                'alpha': league_params.get('alpha', 0.1),
                'alpha_home': league_params.get('alpha_home', 0.1),
                'alpha_away': league_params.get('alpha_away', 0.1),
                'home_adv': league_params.get('home_adv', 1.25),
                'variance_home': league_params.get('variance_home', 1.0),
                'variance_away': league_params.get('variance_away', 1.0)
            }
        else:
            print(f"Insufficient match data for team {team_id} and no league parameters found. Using default values.")
            return {
                'mu': 1.35, 
                'mu_home': 1.5,
                'mu_away': 1.2,
                'p_score': 0.7,
                'p_score_home': 0.75,
                'p_score_away': 0.65,
                'alpha': 0.1,
                'alpha_home': 0.1,
                'alpha_away': 0.1,
                'home_adv': 1.25,
                'variance_home': 1.0,
                'variance_away': 1.0
            }
    
    # Split into home and away matches
    home_matches = df[df['home_team_id'] == team_id]
    away_matches = df[df['away_team_id'] == team_id]
    
    # Calculate team scoring when playing at home
    g_home = home_matches['home_goals'] if not home_matches.empty else pd.Series([])
    
    # Calculate team scoring when playing away
    g_away = away_matches['away_goals'] if not away_matches.empty else pd.Series([])
    
    # Calculate conceding (goals against)
    g_home_against = home_matches['away_goals'] if not home_matches.empty else pd.Series([])
    g_away_against = away_matches['home_goals'] if not away_matches.empty else pd.Series([])
    
    # Initialize using league parameters if available, otherwise use reasonable defaults
    if league_params:
        mu_home = league_params.get('mu_home', 1.5)
        mu_away = league_params.get('mu_away', 1.2)
        p_score_home = league_params.get('p_score_home', 0.75)
        p_score_away = league_params.get('p_score_away', 0.65)
        alpha_home = league_params.get('alpha_home', 0.1)
        alpha_away = league_params.get('alpha_away', 0.1)
        home_adv = league_params.get('home_adv', 1.25)
    else:
        mu_home = 1.5
        mu_away = 1.2
        p_score_home = 0.75
        p_score_away = 0.65
        alpha_home = 0.1
        alpha_away = 0.1
        home_adv = 1.25
    
    # Initialize variance values
    var_home = 1.65
    var_away = 1.3
    
    # Flag to track if team-specific values are used
    using_team_home = False
    using_team_away = False
    
    # Calculate parameters if we have enough data
    if len(g_home) >= MIN_HOME_MATCHES:
        mu_home = g_home.mean()
        var_home = g_home.var() if len(g_home) > 1 else 1.65
        p_score_home = (g_home > 0).mean()
        using_team_home = True
    else:
        print(f"Insufficient home match data for team {team_id} ({len(g_home)} < {MIN_HOME_MATCHES}). Using league values.")
    
    if len(g_away) >= MIN_AWAY_MATCHES:
        mu_away = g_away.mean()
        var_away = g_away.var() if len(g_away) > 1 else 1.3
        p_score_away = (g_away > 0).mean()
        using_team_away = True
    else:
        print(f"Insufficient away match data for team {team_id} ({len(g_away)} < {MIN_AWAY_MATCHES}). Using league values.")
    
    # Overall averages (weighted by sample size)
    home_weight = len(g_home) / max(len(g_home) + len(g_away), 1)
    away_weight = len(g_away) / max(len(g_home) + len(g_away), 1)
    
    # Calculate weighted mu and p_score
    mu = (mu_home * home_weight + mu_away * away_weight) / (home_weight + away_weight)
    p_score = (p_score_home * home_weight + p_score_away * away_weight) / (home_weight + away_weight)
    
    # Calculate home advantage as ratio of scoring at home vs away
    if mu_away > 0:
        home_adv = mu_home / mu_away
    
    # Calculate alpha parameters (overdispersion)
    if using_team_home:
        alpha_home = max((var_home - mu_home) / mu_home**2, 0) if mu_home > 0 else 0.1
    
    if using_team_away:
        alpha_away = max((var_away - mu_away) / mu_away**2, 0) if mu_away > 0 else 0.1
    
    # Use weighted average for overall alpha
    if using_team_home or using_team_away:
        weights_sum = (home_weight if using_team_home else 0) + (away_weight if using_team_away else 0)
        if weights_sum > 0:
            alpha_nb = ((alpha_home * home_weight if using_team_home else 0) + 
                        (alpha_away * away_weight if using_team_away else 0)) / weights_sum
        else:
            alpha_nb = league_params.get('alpha', 0.1) if league_params else 0.1
    else:
        alpha_nb = league_params.get('alpha', 0.1) if league_params else 0.1
    
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
        'using_team_home': using_team_home,
        'using_team_away': using_team_away,
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


def tune_weights_grid_team(df, mu, alpha_nb, ref_games, k_grid=(np.arange(3, 9), np.arange(4, 11)), defaults=(5, 6)):
    """
    Grid-search the (k_goals, k_score) hyper-parameters that determine
    team-specific prior weights.
    
    Parameters:
    - df: DataFrame containing matches involving the team
    - mu: Team's mean goals per match
    - alpha_nb: Team's negative binomial alpha parameter
    - ref_games: Reference number of games played by team
    - k_grid: Grid of k values to search
    - defaults: Default k values to use if grid search fails
    
    Returns:
    - Dictionary with tuned parameters
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
    
    # Get all goals scored by this team (both home and away)
    team_goals = []
    for idx, row in df.iterrows():
        if 'home_team_id' in row and 'away_team_id' in row:
            team_id = None
            if 'team_id' in df.columns:
                team_id = row['team_id']
            
            if team_id is not None:
                if row['home_team_id'] == team_id:
                    team_goals.append(row['home_goals'])
                elif row['away_team_id'] == team_id:
                    team_goals.append(row['away_goals'])
            else:
                # If we don't have team_id in the dataframe, try to infer from the function context
                # This is a less reliable fallback
                team_goals.append(row['home_goals'])
                team_goals.append(row['away_goals'])
    
    team_goals = pd.Series(team_goals)
    
    obs = empirical_hist(team_goals)  # shape (0..max_g)
    best, best_score = None, float("inf")

    # ---------- 2. Grid search - use larger default weights for team-level analysis
    # since we have less data per team than per league
    for kg in k_grid[0]:
        for ks in k_grid[1]:
            # map k‑values → actual integer weights, with higher minimum for teams
            # to prevent overfitting to small samples
            goal_w = int(np.clip(kg * (ref_games / max(n_games, 1)) ** 0.5, 4, 10))
            score_w = int(np.clip(ks * (ref_games / max(n_games, 1)) ** 0.5, 5, 12))

            # team‑specific blended mean
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
    Returns a DataFrame with at least `min_games` rows for the league.
    Enhanced to include team IDs for team-specific analysis.
    Starts with `start_season_year` and walks backwards
    (max `max_back` seasons) until the quota is reached.
    """
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
    if multiplier > 5.9: print(f'Calculated multiplier: {multiplier}. Capped to 6')
    return max(0.5, min(6.0, multiplier))  # Optional: clamp output to safe range

def fetch_league_fixtures(country, league, start_time=None, end_time=None):
    """
    Fetch all fixtures for a specific league and time period from DynamoDB.
    This allows us to query once per league rather than once per team.
    
    Args:
        country (str): Country name
        league (str): League name
        start_time (int): Optional epoch timestamp to start from
        end_time (int): Optional epoch timestamp to end at
        
    Returns:
        list: All fixture items for the specified league and time period
    """
    if not start_time:
        start_time = int((datetime.now() - timedelta(days=180)).timestamp())  # Use longer history for teams
    if not end_time:
        end_time = int(datetime.now().timestamp())

    # Query using the country-league-index
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

    fixtures_items = []
    try:
        response = fixtures_table.query(**params)
        fixtures_items = response.get('Items', [])
        
        # Handle pagination for large result sets
        while 'LastEvaluatedKey' in response:
            params['ExclusiveStartKey'] = response['LastEvaluatedKey']
            response = fixtures_table.query(**params)
            fixtures_items.extend(response.get('Items', []))
        
        print(f'Total fixtures fetched for {country} {league}: {len(fixtures_items)}')
        return fixtures_items
        
    except Exception as e:
        print(f"Error fetching fixtures for {country} {league}: {e}")
        return []


def calculate_team_multipliers(team_id, fixtures_data, min_sample_size=10):
    """
    Calculate data-driven multipliers from historical prediction data for a specific team.
    This function extracts team-specific data from the pre-loaded fixtures for a league.

    Args:
        team_id (int): Team ID to calculate multipliers for
        fixtures_data (list): Pre-loaded list of fixture items from DynamoDB
        min_sample_size (int): Minimum number of matches required for reliable calculations
                              (lower than league version since we expect fewer matches per team)

    Returns:
        dict: Multipliers and statistics for the team
    """
    home_goals_predicted = []
    home_goals_actual = []
    away_goals_predicted = []
    away_goals_actual = []
    total_goals_predicted = []
    total_goals_actual = []
    count = 0
    
    # Process team as home team
    home_items = [item for item in fixtures_data if 'home' in item and 'team_id' in item['home'] and int(item['home']['team_id']) == team_id]
    for item in home_items:
        if not all(key in item for key in ['home', 'away', 'goals']):
            continue
        try:
            pred_home = float(item['home']['predicted_goals'])
            pred_away = float(item['away']['predicted_goals'])
            actual_home = float(item['goals']['home'])
            actual_away = float(item['goals']['away'])

            home_goals_predicted.append(pred_home)
            home_goals_actual.append(actual_home)
            total_goals_predicted.append(pred_home + pred_away)
            total_goals_actual.append(actual_home + actual_away)
            count += 1
        except (KeyError, ValueError, TypeError):
            continue
            
    # Process team as away team
    away_items = [item for item in fixtures_data if 'away' in item and 'team_id' in item['away'] and int(item['away']['team_id']) == team_id]
    for item in away_items:
        if not all(key in item for key in ['home', 'away', 'goals']):
            continue
        try:
            pred_home = float(item['home']['predicted_goals'])
            pred_away = float(item['away']['predicted_goals'])
            actual_home = float(item['goals']['home'])
            actual_away = float(item['goals']['away'])

            away_goals_predicted.append(pred_away)
            away_goals_actual.append(actual_away)
            # Don't double-count if team was already counted as home team
            if item not in home_items:
                total_goals_predicted.append(pred_home + pred_away)
                total_goals_actual.append(actual_home + actual_away)
                count += 1
        except (KeyError, ValueError, TypeError):
            continue

    sample_size = len(home_goals_predicted) + len(away_goals_predicted)
    print(f'Team {team_id} Records Counted: {count}, Sample Size: {sample_size}')
    
    # Use lower min_sample_size for teams compared to leagues
    if sample_size < min_sample_size:
        print(f"Warning: Small sample size for team {team_id}: {sample_size} < {min_sample_size}")
        confidence = max(sample_size / min_sample_size, 0.1)
        return {
            'home_multiplier': Decimal('1.0'),
            'away_multiplier': Decimal('1.0'),
            'total_multiplier': Decimal('1.0'),
            'confidence': Decimal(str(confidence)),
            'sample_size': sample_size,
            'timestamp': int(datetime.now().timestamp())
        }

    # Calculate ratios carefully handling empty lists
    home_ratios = [actual / max(pred, 0.1) for actual, pred in zip(home_goals_actual, home_goals_predicted)] if home_goals_predicted else [1.0]
    away_ratios = [actual / max(pred, 0.1) for actual, pred in zip(away_goals_actual, away_goals_predicted)] if away_goals_predicted else [1.0]
    total_ratios = [actual / max(pred, 0.1) for actual, pred in zip(total_goals_actual, total_goals_predicted)] if total_goals_predicted else [1.0]

    # Use median to be robust to outliers
    raw_home_ratio = np.mean(home_ratios)
    raw_away_ratio = np.mean(away_ratios)
    raw_total_ratio = np.mean(total_ratios)

    # Calculate standard deviations for confidence estimation
    home_std = np.std(home_ratios) if len(home_ratios) > 1 else 0.5
    away_std = np.std(away_ratios) if len(away_ratios) > 1 else 0.5
    total_std = np.std(total_ratios) if len(total_ratios) > 1 else 0.5

    # Adjust confidence based on sample size and variance
    variance_penalty = min(1.0, 1.0 / (1.0 + math.log(1 + total_std)))
    sample_confidence = min(1.0, sample_size / min_sample_size)  # Scale down from league version
    confidence = min(sample_confidence * variance_penalty * 2, 0.8)

    # Calculate final multipliers
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

def _safe_convert_to_int(value):
    """Safely convert a value to an integer"""
    try:
        if isinstance(value, (int, float)):
            return int(value)
        elif isinstance(value, Decimal):
            return int(value)
        elif isinstance(value, str) and value.strip():
            return int(float(value))
        return None
    except (ValueError, TypeError):
        return None

def _safe_convert_to_float(value):
    """Safely convert a value to a float"""
    try:
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, str) and value.strip():
            return float(value)
        return 0.0
    except (ValueError, TypeError):
        return 0.0