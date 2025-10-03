import boto3
import json
import logging
import math
import numpy as np
import os
import random
import requests
import time

from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pymongo import MongoClient
from scipy import stats

#Get API Keys
rapidapi_key = os.getenv('RAPIDAPI_KEY')

dynamodb = boto3.resource('dynamodb')
webFE_table = dynamodb.Table('game_fixtures')
league_table = dynamodb.Table('league_parameters') 
teams_table = dynamodb.Table('team_parameters')


def lambda_handler(event, context):
    print("Events:", json.dumps(event))
    
    # Loop through all records (each record corresponds to a single SQS message) 
    for record in event['Records']:
        # Parse the 'body' field from the SQS message, which contains your actual payload
        body = json.loads(record['body'])
        
        # Now 'fixtures' contains what used to be directly in 'payload'
        fixtures = body.get('payload', [])
        
        # Process each fixture as you normally would
        process_fixtures(fixtures)


def process_fixtures(fixtures):
    """
    Process fixtures with coordinated lambda correction to preserve outcome relationships.
    Drop-in replacement for the original process_fixtures function.
    """
    #print("Fixtures:", json.dumps(fixtures)) 

    for fixture in fixtures:
        try:
            fixture_id = fixture['fixture_id']
            home_team_id = fixture['home_id']
            away_team_id = fixture['away_id']
            league_id = fixture['league_id']
            season = fixture['season']
            date = fixture['date']
            from_date = get_league_start_date(league_id)
            league_params = get_league_params_from_db(league_id)
            league_params = decimal_to_float(league_params)
            print(f'League Params: {json.dumps(league_params, default=decimal_default)}')

            unique_home_id = f"{league_id}-{home_team_id}"
            unique_away_id = f"{league_id}-{away_team_id}"

            home_params = get_team_params_from_db(unique_home_id) or league_params
            print(f'Home Before: {json.dumps(home_params, default=decimal_default)}')

            away_params = get_team_params_from_db(unique_away_id) or league_params
            print(f'Away Before: {json.dumps(away_params, default=decimal_default)}')

            home_params = get_prediction_params(home_params, league_params)
            away_params = get_prediction_params(away_params, league_params)

            #Adjust league parameters with team specific standard deviation
            home_league_params = mod_league_params(home_params, league_params)
            home_league_params = decimal_to_float(home_league_params)
            print(f'Home League: {json.dumps(home_league_params, default=decimal_default)}')

            away_league_params = mod_league_params(away_params, league_params)
            away_league_params = decimal_to_float(away_league_params)
            print(f'Away League: {json.dumps(away_league_params, default=decimal_default)}')

            home_params = decimal_to_float(home_params)
            away_params = decimal_to_float(away_params)
            print(f'Home: {json.dumps(home_params, default=decimal_default)}')
            print(f'Away: {json.dumps(away_params, default=decimal_default)}')

            try:
                venue_ids = get_venue_id(home_team_id, league_id, season)
            except Exception as e:
                print(f"Warning: Could not get venue ID for fixture {fixture_id}: {e}")
                venue_ids = None  # Safe fallback that won't break consuming apps

            #print(f"League ID: {league_id} | Season: {season} | Home Team: {home_team_id} Away Team: {away_team_id} | League Start Date: {from_date}")
            home_team_parameters, home_match_details = fetch_team_match_data(league_id, season, home_team_id, from_date)
            away_team_parameters, away_match_details = fetch_team_match_data(league_id, season, away_team_id, from_date)

            if (home_team_parameters is None or home_match_details is None or 
                away_team_parameters is None or away_match_details is None):
                print(f"Skipping fixture {fixture_id}: Missing team match data")
                continue

            try:
                home_team_data = calculate_team_points(league_id, season, home_team_id, 'home', home_match_details)
                away_team_data = calculate_team_points(league_id, season, away_team_id, 'away', away_match_details)
            except Exception as e:
                print(f"Skipping fixture {fixture_id}: Team points calculation failed - {e}")
                continue            
            
            home_team_stats = home_team_data['team_info']
            away_team_stats = away_team_data['team_info']

            # =================================================================
            # COORDINATED PREDICTION CALCULATION (LEAGUE PARAMETERS)
            # =================================================================
            try:
                print("=== CALCULATING COORDINATED PREDICTIONS (LEAGUE PARAMETERS) ===")
                
                (home_score_league, home_goals_league, hg_likelihood_league, home_probs_league,
                 away_score_league, away_goals_league, ag_likelihood_league, away_probs_league,
                 league_coordination_info) = calculate_coordinated_predictions(
                    home_team_parameters, away_team_parameters, home_league_params, away_league_params, league_id
                )
                
                prediction_summary = create_prediction_summary_dict(home_probs_league, away_probs_league)

                home_team_stats['probability_to_score'] = Decimal(str(home_score_league))
                away_team_stats['probability_to_score'] = Decimal(str(away_score_league))       
                home_team_stats['predicted_goals'] = home_goals_league
                away_team_stats['predicted_goals'] = away_goals_league
                home_team_stats['likelihood'] = Decimal(str(hg_likelihood_league))
                away_team_stats['likelihood'] = Decimal(str(ag_likelihood_league))

            except Exception as e:
                print(f"League coordinated prediction failed for fixture {fixture_id}: {e}")
                print("Falling back to original individual predictions...")
                
                # Fallback to original method
                home_lambda_base = calculate_base_lambda(
                    home_team_parameters, away_team_parameters, home_league_params, is_home=True
                )
                away_lambda_base = calculate_base_lambda(
                    home_team_parameters, away_team_parameters, away_league_params, is_home=False
                )

                home_score_league, home_goals_league, hg_likelihood_league, home_probs_league = calculate_to_score(
                    home_team_parameters, away_team_parameters, home_league_params, 
                    is_home=True, league_id=league_id, opponent_lambda=away_lambda_base
                )
                
                away_score_league, away_goals_league, ag_likelihood_league, away_probs_league = calculate_to_score(
                    home_team_parameters, away_team_parameters, away_league_params, 
                    is_home=False, league_id=league_id, opponent_lambda=home_lambda_base
                )

                prediction_summary = create_prediction_summary_dict(home_probs_league, away_probs_league)
                
                home_team_stats['probability_to_score'] = Decimal(str(home_score_league))
                away_team_stats['probability_to_score'] = Decimal(str(away_score_league))       
                home_team_stats['predicted_goals'] = home_goals_league
                away_team_stats['predicted_goals'] = away_goals_league
                home_team_stats['likelihood'] = Decimal(str(hg_likelihood_league))
                away_team_stats['likelihood'] = Decimal(str(ag_likelihood_league))
                
                league_coordination_info = {"coordination_applied": False, "fallback_reason": str(e)}

            # =================================================================
            # COORDINATED PREDICTION CALCULATION (TEAM PARAMETERS)
            # =================================================================
            try:
                print("=== CALCULATING COORDINATED PREDICTIONS (TEAM PARAMETERS) ===")
                
                (home_score_team, home_goals_team, hg_likelihood_team, home_probs_team,
                 away_score_team, away_goals_team, ag_likelihood_team, away_probs_team,
                 team_coordination_info) = calculate_coordinated_predictions(
                    home_team_parameters, away_team_parameters, home_params, away_params, league_id
                )

                prediction_summary_alt = create_prediction_summary_dict(home_probs_team, away_probs_team)

                home_team_stats['probability_to_score_alt'] = Decimal(str(home_score_team))
                away_team_stats['probability_to_score_alt'] = Decimal(str(away_score_team))      
                home_team_stats['predicted_goals_alt'] = home_goals_team
                away_team_stats['predicted_goals_alt'] = away_goals_team
                home_team_stats['likelihood_alt'] = Decimal(str(hg_likelihood_team))
                away_team_stats['likelihood_alt'] = Decimal(str(ag_likelihood_team))

            except Exception as e:
                print(f"Team coordinated prediction failed for fixture {fixture_id}: {e}")
                print("Falling back to original individual predictions...")
                
                # Fallback to original method
                home_lambda_base_alt = calculate_base_lambda(
                    home_team_parameters, away_team_parameters, home_params, is_home=True
                )
                away_lambda_base_alt = calculate_base_lambda(
                    home_team_parameters, away_team_parameters, away_params, is_home=False
                )

                home_score_team, home_goals_team, hg_likelihood_team, home_probs_team = calculate_to_score(
                    home_team_parameters, away_team_parameters, home_params, 
                    is_home=True, league_id=league_id, opponent_lambda=away_lambda_base_alt
                )

                away_score_team, away_goals_team, ag_likelihood_team, away_probs_team = calculate_to_score(
                    home_team_parameters, away_team_parameters, away_params, 
                    is_home=False, league_id=league_id, opponent_lambda=home_lambda_base_alt
                )

                prediction_summary_alt = create_prediction_summary_dict(home_probs_team, away_probs_team)

                home_team_stats['probability_to_score_alt'] = Decimal(str(home_score_team))
                away_team_stats['probability_to_score_alt'] = Decimal(str(away_score_team))      
                home_team_stats['predicted_goals_alt'] = home_goals_team
                away_team_stats['predicted_goals_alt'] = away_goals_team
                home_team_stats['likelihood_alt'] = Decimal(str(hg_likelihood_team))
                away_team_stats['likelihood_alt'] = Decimal(str(ag_likelihood_team))
                
                team_coordination_info = {"coordination_applied": False, "fallback_reason": str(e)}

            # =================================================================
            # CONTINUE WITH ORIGINAL LOGIC (UNCHANGED)
            # =================================================================

            # Assuming you have a 'team_id' or some unique identifier for the team 
            home_team_stats['record_id'] = f"{fixture['fixture_id']}_home_{home_team_id}"
            away_team_stats['record_id'] = f"{fixture['fixture_id']}_away_{away_team_id}"
            
            home_team_stats['Opponent'] = away_team_stats['team_name']
            away_team_stats['Opponent'] = home_team_stats['team_name'] 
            
            home_team_stats['date'] = date
            away_team_stats['date'] = date
            
            home_next_fixture = get_next_fixture(home_team_id, fixture_id)
            away_next_fixture = get_next_fixture(away_team_id, fixture_id)
            
            if home_next_fixture is not None:
                home_team_stats['Next_Fix_Type'], home_team_stats['Next_Opp'], home_team_stats['Next_Fix_Date'], home_team_stats['Next_League'] = home_next_fixture.values()

            if away_next_fixture is not None:
                away_team_stats['Next_Fix_Type'], away_team_stats['Next_Opp'], away_team_stats['Next_Fix_Date'], away_team_stats['Next_League'] = away_next_fixture.values()
            
            #print("Home Data: ", json.dumps(home_team_stats, default=decimal_default))  
            #print("Away Data: ", json.dumps(away_team_stats, default=decimal_default))
            
            # Create a new dictionary and Aggregate all data for a single fixture  
            home_team_stats['team_id'] = home_team_id
            away_team_stats['team_id'] = away_team_id
            
            home_team_stats['team_logo'] = home_team_data['team_logo']
            away_team_stats['team_logo'] = away_team_data['team_logo']

            home_team_stats['team_goal_stats'] = home_team_data['team_goal_stats']
            away_team_stats['team_goal_stats'] = away_team_data['team_goal_stats']
            
            home_team_stats['past_fixtures'] = get_last_five_games(home_team_id, league_id, season)
            away_team_stats['past_fixtures'] = get_last_five_games(away_team_id, league_id, season)
            
            headtohead = get_head_to_head(home_team_id, away_team_id)

            home_team_stats['injuries'], away_team_stats['injuries'] = get_fixture_injuries(fixture_id, date[:10], home_team_id, away_team_id, season)

            aggregated_fixture_data = {
                "fixture_id" : fixture['fixture_id'],
                'country': home_team_stats['league_country'],
                'league': home_team_stats['league_name'],
                "league_id" : league_id,
                "season" : season,
                "home": home_team_stats,
                "away": away_team_stats,
                "h2h": headtohead,
                "venue": venue_ids,
                "date" : date,
                "predictions": prediction_summary,
                "alternate_predictions": prediction_summary_alt,
                "coordination_info": {
                    "league_coordination": convert_floats_to_decimal(league_coordination_info),
                    "team_coordination": convert_floats_to_decimal(team_coordination_info)
                },
                "timestamp" : fixture['timestamp']
            }

            # Remove 'league_country' and 'league_name' from 'home'
            del aggregated_fixture_data['home']['league_country']
            del aggregated_fixture_data['home']['league_name']
            
            # Remove 'league_country' and 'league_name' from 'away'
            del aggregated_fixture_data['away']['league_country']
            del aggregated_fixture_data['away']['league_name']

            # Remove 'record_id' from 'home' and away'
            del aggregated_fixture_data['home']['record_id']
            del aggregated_fixture_data['away']['record_id']

            fixture_record = convert_floats_to_decimal(aggregated_fixture_data)

            # The aggregated_fixture_data dictionary is now restructured  
            print(json.dumps(aggregated_fixture_data, default=decimal_default))

            try:
                # Insert fixture record
                webFE_table.put_item(Item = fixture_record)
                print(f"Successfully inserted fixture record into DynamoDB with record ID: {fixture_record['fixture_id']}")
                
            except Exception as e:
                print(f"Failed to insert into DynamoDB: {e}")
                
            #Publish to fixturesQueue
            send_to_sqs(aggregated_fixture_data)

            # Step 1: Rename 'league' to 'league_name'
            aggregated_fixture_data['league_name'] = aggregated_fixture_data.pop('league')
            
            # Step 2: Create a new 'league' key at the top level
            aggregated_fixture_data['league'] = {
                'id': aggregated_fixture_data['league_id'],
                'country': aggregated_fixture_data['country'],
                'name': aggregated_fixture_data['league_name']
            }
            
            # Step 3: Remove 'league_id', 'country', and 'league_name' from the top level
            del aggregated_fixture_data['league_id']
            del aggregated_fixture_data['country']
            del aggregated_fixture_data['league_name']

            # The aggregated_fixture_data dictionary is now restructured  
            #print(json.dumps(aggregated_fixture_data, default=decimal_default))
            
            # Write to MongoDB [gamers-Cluster0]
            #write_to_mongo(aggregated_fixture_data)
            
        except Exception as e:
            print(f"Skipping fixture {fixture.get('fixture_id', 'unknown')}: Unexpected error - {e}")
            continue


def get_team_statistics(league_id, season, team_id, max_retries=5):
    url = "https://api-football-v1.p.rapidapi.com/v3/teams/statistics"
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    querystring = {
        "league": str(league_id),
        "season": str(season),
        "team": str(team_id),
        "date": yesterday
    }
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers, params=querystring)
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'response' not in data:
                        print(f"Warning: 'response' key missing in API response. Full response: {data}")
                        return {"response": {}}
                    # If response is a list but we expect a dict, handle it
                    if isinstance(data['response'], list):
                        if len(data['response']) > 0:
                            print("Converting response from list to dict (taking first item)")
                            data = {"response": data['response'][0]}
                        else:
                            print("Empty response list received")
                            data = {"response": {}}
                    return data
                except Exception as e:
                    print(f"Error parsing API response: {e}")
                    print(f"Response content: {response.text[:200]}...")
                    return {"response": {}}
            elif response.status_code == 429:
                wait_time = random.randint(5, 30)
                print(f"Received 429. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                retries += 1
            else:
                print(f"Error in API call: Status code {response.status_code}")
                print(f"Response content: {response.text}")
                return {"response": {}}
        except requests.exceptions.RequestException as e:
            print(f"Request exception: {e}")
            return {"response": {}}
    print("Max retries reached. Request failed.")
    return {"response": {}}


def send_to_sqs(data):
    sqs = boto3.client('sqs')
    second_queue_url = 'https://sqs.eu-west-2.amazonaws.com/985019772236/fixturesQueue'
    payload = json.dumps(data, default=decimal_default)
    sqs.send_message(
        QueueUrl=second_queue_url,
        MessageBody=payload
    )

def bayesian_smooth_rate(observed_values, prior_mean=None, prior_weight=5):
    """
    Apply Bayesian smoothing to a series of observed values.
    
    Parameters:
    - observed_values: List of observed values (e.g., goals per game)
    - prior_mean: Prior belief about the mean (defaults to average across all teams)
    - prior_weight: Weight of the prior (equivalent sample size)
    
    Returns:
    - Smoothed estimate of the rate
    """
    if not observed_values:
        return 0
    
    # Calculate observed statistics
    observed_mean = np.mean(observed_values) if observed_values else 0
    sample_size = len(observed_values)
    
    # If prior_mean is not provided, use a reasonable default
    if prior_mean is None:
        # Default to league average or a conservative estimate
        prior_mean = 1.0  # Can be replaced with actual league average
    
    # Apply Bayesian smoothing formula: weighted average of prior and observed data
    smoothed_rate = (prior_mean * prior_weight + observed_mean * sample_size) / (prior_weight + sample_size)
    
    return smoothed_rate


def bayesian_smooth_binary(binary_values, prior_probability=None, prior_weight=5):
    """
    Apply Bayesian smoothing to binary outcomes (e.g., scored/didn't score).
    
    Parameters:
    - binary_values: List of 1s and 0s representing binary outcomes
    - prior_probability: Prior belief about the probability (defaults to average)
    - prior_weight: Weight of the prior (equivalent sample size)
    
    Returns:
    - Smoothed estimate of the probability
    """
    if not binary_values:
        return 0
    
    # Calculate observed proportion
    successes = sum(binary_values)
    sample_size = len(binary_values)
    observed_prob = successes / sample_size if sample_size > 0 else 0
    
    # If prior_probability is not provided, use a reasonable default
    if prior_probability is None:
        # Default to league average or a moderate estimate
        prior_probability = 0.5  # Can be replaced with actual league average
    
    # Apply Bayesian smoothing formula
    smoothed_prob = (prior_probability * prior_weight + observed_prob * sample_size) / (prior_weight + sample_size)
    
    return smoothed_prob


def apply_smoothing_to_team_data(raw_scores, alpha=0.15, prior_mean=None, prior_weight=5, use_bayesian=True):
    """
    Apply smoothing to a list of raw goal data, with option for either
    exponential or Bayesian smoothing.
    
    Parameters:
    - raw_scores: A list of goal counts per match (most recent first)
    - alpha: Smoothing factor for exponential smoothing
    - prior_mean: Prior mean for Bayesian smoothing
    - prior_weight: Weight of the prior for Bayesian smoothing
    - use_bayesian: If True, use Bayesian smoothing; otherwise use exponential
    
    Returns:
    - The smoothed average goals per game
    """
    if not raw_scores:
        return 0  # If no data, assume 0 goals
    
    if use_bayesian:
        return bayesian_smooth_rate(raw_scores, prior_mean, prior_weight)
    else:
        # Original exponential smoothing logic
        smoothed_value = raw_scores[0]  # Start with the most recent game
        for score in raw_scores[1:]:  # Apply smoothing to the rest
            smoothed_value = alpha * score + (1 - alpha) * smoothed_value
        return smoothed_value


def apply_smoothing_to_binary_rate(binary_data, total_games, alpha=0.15, prior_prob=None, prior_weight=5, use_bayesian=True):
    """
    Apply smoothing to binary outcomes (e.g., scored/didn't score, clean sheets),
    with option for either exponential or Bayesian smoothing.
    
    Parameters:
    - binary_data: List of 0s and 1s (e.g., games scored, clean sheets)
    - total_games: Total number of games played
    - alpha: Smoothing factor for exponential smoothing
    - prior_prob: Prior probability for Bayesian smoothing
    - prior_weight: Weight of the prior for Bayesian smoothing
    - use_bayesian: If True, use Bayesian smoothing; otherwise use exponential
    
    Returns:
    - Smoothed proportion
    """
    if not binary_data or total_games == 0:
        return 0  # Avoid division by zero
    
    if use_bayesian:
        return bayesian_smooth_binary(binary_data, prior_prob, prior_weight)
    else:
        # Original exponential smoothing logic
        smoothed_rate = sum(binary_data) / total_games
        for value in binary_data:
            current_rate = sum(binary_data) / total_games  # Current proportion
            smoothed_rate = alpha * current_rate + (1 - alpha) * smoothed_rate
        return smoothed_rate


def prior_weight_from_k(n_games, k, ref_games, lo=3, hi=8):
    """
    Converts tuned k (float) into integer prior weight for a given sample size.
    RAISES EXCEPTIONS instead of returning default values when input is invalid.
    """
    # Handle None or zero values - RAISE EXCEPTION instead of returning defaults
    if n_games is None or n_games <= 0:
        raise ValueError(f"Invalid n_games value: {n_games}")
        
    if k is None or k <= 0:
        raise ValueError(f"Invalid k value: {k}")
        
    if ref_games is None or ref_games <= 0:
        raise ValueError(f"Invalid ref_games value: {ref_games}")
        
    # Calculate the prior weight
    result = int(np.clip(k * (ref_games / n_games) ** 0.5, lo, hi))
    return result


def apply_smart_correction(lmbda, multiplier, confidence, sample_size, league_stats, opponent_lambda=None):
    """
    Apply intelligent correction with improved confidence scaling for large systematic errors.
    Fixes over-damping issues that prevented proper correction of extreme underprediction.
    
    Parameters:
    - lmbda: Current lambda (expected goals)
    - multiplier: Calculated multiplier from historical data
    - confidence: System confidence in correction
    - sample_size: Number of historical matches
    - league_stats: Dict with std_dev and raw_ratio info
    - opponent_lambda: Lambda of opposing team for ratio preservation
    
    Returns:
    - corrected_lmbda: Adjusted lambda value (as float)
    - correction_info: Dict with detailed correction information
    """
    
    # Convert lmbda to float for calculations
    lmbda_float = float(lmbda) if isinstance(lmbda, Decimal) else lmbda
    
    # Extract std_dev and raw_ratio from league_stats
    std_dev = float(league_stats.get('std_dev', 1.0))
    raw_ratio = float(league_stats.get('raw_ratio', 1.0))

    # Cap extreme multipliers to prevent wild swings (but allow higher values than before)
    original_multiplier = float(multiplier)
    multiplier_capped = max(0.5, min(6.0, original_multiplier))  # Match parameter caps
    
    # Calculate deviation from ideal ratio of 1.0
    deviation = abs(raw_ratio - 1.0)
    
    # IMPROVED: Sample-size-adjusted reliability factor
    # Higher sample sizes reduce penalty from standard deviation
    sample_reliability_boost = min(float(sample_size) / 50.0, 2.0)  # Up to 2x boost for 50+ samples
    base_reliability = 1.0 / (1.0 + (std_dev / 8.0))  # Less harsh penalty (was /5.0)
    reliability_factor = base_reliability * (1.0 + sample_reliability_boost * 0.3)  # 30% boost per reliability unit
    
    # IMPROVED: Deviation handling that recognizes large systematic errors
    if deviation > 2.0 and sample_size >= 30:
        # Large deviations with good sample size indicate systematic bias - BOOST confidence
        deviation_factor = min(1.8, 1.0 + math.log(deviation) * 0.3)
        correction_mode = "systematic_bias"
    elif deviation > 1.0 and sample_size >= 50:
        # Moderate deviations with excellent sample size - slight boost
        deviation_factor = min(1.4, 1.0 + math.log(deviation) * 0.2)
        correction_mode = "reliable_error"
    elif deviation > 0.5:
        # Standard moderate deviation handling
        deviation_factor = 1.0 / (1.0 + math.log(1 + (deviation - 0.5) * 1.5))  # Less aggressive damping
        correction_mode = "moderate_error"
    else:
        # Small deviations - minimal damping
        deviation_factor = 1.0
        correction_mode = "small_error"
    
    # Combine all confidence factors with better scaling
    base_confidence = float(confidence)
    adjusted_confidence = base_confidence * reliability_factor * deviation_factor
    
    # IMPROVED: Higher minimum confidence for well-sampled extreme cases
    if deviation > 3.0 and sample_size >= 50:
        adjusted_confidence = max(adjusted_confidence, 0.5)  # Minimum 50% confidence
    elif deviation > 2.0 and sample_size >= 30:
        adjusted_confidence = max(adjusted_confidence, 0.35)  # Minimum 35% confidence
    else:
        adjusted_confidence = max(adjusted_confidence, 0.15)  # Minimum 15% confidence (was 0.1)
    
    # Cap maximum confidence at 85% (increased from 80%)
    adjusted_confidence = min(adjusted_confidence, 0.85)
    
    # IMPROVED: Sample size weighting with better scaling
    sample_weight = min(float(sample_size) / 40.0, 1.2)  # Can exceed 1.0 for very large samples
    
    # Calculate target lambda
    target_lambda = lmbda_float * multiplier_capped
    
    # IMPROVED: Progressive correction strength based on error magnitude
    if deviation > 3.0:
        max_correction_strength = 0.7  # Up to 70% change for extreme errors
    elif deviation > 2.0:
        max_correction_strength = 0.55  # Up to 55% change for large errors
    elif deviation > 1.0:
        max_correction_strength = 0.4   # Up to 40% change for moderate errors
    else:
        max_correction_strength = 0.25  # Up to 25% change for small errors
    
    correction_strength = adjusted_confidence * sample_weight * max_correction_strength
    
    # Apply correction with smooth blending
    raw_corrected = lmbda_float + correction_strength * (target_lambda - lmbda_float)
    
    # Apply absolute bounds to prevent extreme values (slightly higher ceiling)
    bounded_lambda = max(0.05, min(6.0, raw_corrected))  # Increased ceiling from 4.0 to 6.0
    
    # Ratio preservation check (with more flexible limits)
    final_lambda = bounded_lambda
    ratio_adjustment_applied = False
    
    if opponent_lambda is not None and opponent_lambda > 0:
        opponent_lambda = float(opponent_lambda)
        original_ratio = lmbda_float / max(opponent_lambda, 0.1)
        new_ratio = bounded_lambda / max(opponent_lambda, 0.1)
        
        # IMPROVED: More flexible ratio preservation for extreme corrections
        if correction_mode == "systematic_bias":
            max_ratio_change = 3.0  # Allow up to 200% ratio change for systematic bias
        elif correction_mode == "reliable_error":
            max_ratio_change = 2.5  # Allow up to 150% ratio change for reliable errors
        else:
            max_ratio_change = 2.0  # Allow up to 100% ratio change for moderate errors
        
        if new_ratio > original_ratio * max_ratio_change:
            final_lambda = opponent_lambda * original_ratio * max_ratio_change
            ratio_adjustment_applied = True
        elif new_ratio < original_ratio / max_ratio_change:
            final_lambda = opponent_lambda * original_ratio / max_ratio_change
            ratio_adjustment_applied = True
    
    # IMPROVED: Less aggressive logarithmic damping threshold
    total_change = abs(final_lambda - lmbda_float)
    logarithmic_damping_applied = False
    if total_change > 1.0:  # Increased threshold from 0.5 to 1.0
        sign = 1 if final_lambda > lmbda_float else -1
        damped_change = 1.0 + math.log(total_change) / math.log(2)  # More gentle damping
        final_lambda = lmbda_float + sign * damped_change
        logarithmic_damping_applied = True
    
    # Prepare detailed info for logging/debugging
    correction_info = {
        'original_lambda': lmbda_float,
        'target_lambda': target_lambda,
        'corrected_lambda': final_lambda,
        'original_multiplier': original_multiplier,
        'multiplier_capped': multiplier_capped,
        'multiplier_was_capped': original_multiplier != multiplier_capped,
        'correction_strength': correction_strength,
        'correction_applied_pct': correction_strength * 100,
        'lambda_change_pct': ((final_lambda / lmbda_float - 1) * 100),
        'raw_ratio': raw_ratio,
        'deviation': deviation,
        'std_dev': std_dev,
        'reliability_factor': reliability_factor,
        'deviation_factor': deviation_factor,
        'correction_mode': correction_mode,
        'original_confidence': base_confidence,
        'adjusted_confidence': adjusted_confidence,
        'sample_size': float(sample_size),
        'sample_weight': sample_weight,
        'sample_reliability_boost': sample_reliability_boost,
        'max_correction_strength': max_correction_strength,
        'bounds_applied': bounded_lambda != raw_corrected,
        'ratio_adjustment_applied': ratio_adjustment_applied,
        'logarithmic_damping_applied': logarithmic_damping_applied
    }

    return final_lambda, correction_info


def calculate_adaptive_confidence(base_confidence, venue_ratio, std_dev):
    """
    Calculate confidence with PROPER ratio-based scaling.
    Higher deviation = LOWER confidence (corrected logic).
    
    Parameters:
    - base_confidence: Original confidence value
    - venue_ratio: The venue-specific ratio (home_ratio_raw or away_ratio_raw)
    - std_dev: Standard deviation (indicates prediction reliability)
    
    Returns:
    - adjusted_confidence: Enhanced confidence based on deviation magnitude (DAMPED, not boosted)
    """
    
    # Calculate deviation from ideal ratio of 1.0
    deviation = abs(float(venue_ratio) - 1.0)
    
    # Apply REVERSED logic: higher deviation = lower confidence
    if deviation <= 0.1:  # Very reliable (within 10%)
        deviation_factor = 1.2  # Slight confidence boost for reliable data
    elif deviation <= 0.3:  # Moderately reliable (within 30%)
        deviation_factor = 1.0  # No adjustment
    elif deviation <= 0.5:  # Less reliable (within 50%)
        deviation_factor = 0.8  # Reduce confidence by 20%
    elif deviation <= 1.0:  # Poor reliability (within 100%)
        deviation_factor = 0.6  # Reduce confidence by 40%
    else:  # Very poor reliability (over 100% deviation)
        # Apply logarithmic damping for extreme deviations
        excess_deviation = deviation - 1.0
        log_damping = 1.0 / (1.0 + math.log(1 + excess_deviation * 2))
        deviation_factor = 0.4 * log_damping  # Base 60% reduction, further damped
    
    # Apply standard deviation penalty - higher SD = less reliable predictions
    # Normalize std_dev (typical values range from 1-15 in football data)
    normalized_std = float(std_dev) / 10.0  # Normalize around 10 as typical
    std_penalty = 1.0 / (1.0 + normalized_std)  # Higher SD reduces confidence
    
    # Combine both factors
    adjusted_confidence = float(base_confidence) * deviation_factor * std_penalty
    
    # Apply reasonable bounds (minimum 10%, maximum 80%)
    final_confidence = max(0.1, min(0.8, adjusted_confidence))
    
    return final_confidence


def calculate_to_score(team1_stats, team2_stats, params, is_home=True, league_id=None, opponent_lambda=None):
    """
    Calculate the score for a team using Bayesian smoothing and data-driven multipliers.
    Enhanced with comprehensive error handling and opponent lambda for ratio preservation.
    """

    # Validate input parameters
    if not team1_stats or not team2_stats or not params:
        print("Error: Missing required parameters")
        raise ValueError("Missing required parameters for calculate_to_score")
        
    # Unpack raw match stats with validation
    team1_goals_scored_raw, team1_goals_conceded_raw, team1_games_scored_raw, team1_games_cleanSheet_raw, team1_games_total = team1_stats
    team2_goals_scored_raw, team2_goals_conceded_raw, team2_games_scored_raw, team2_games_cleanSheet_raw, team2_games_total = team2_stats

    # Validate games_total to prevent division by zero
    if team1_games_total is None or team1_games_total <= 0:
        raise ValueError("team1_games_total is invalid or zero")
        
    if team2_games_total is None or team2_games_total <= 0:
        raise ValueError("team2_games_total is invalid or zero")

    # Extract parameters with defaults (matching original code exactly)
    try:
        k_goals = params['k_goals']
        k_score = params['k_score']
        league_home_adv = params['home_adv']
        ref_games = params['ref_games']
        confidence = params['confidence']
        sample_size = params['sample_size']    
        alpha_smooth = 0.15  # Default value as in original function
        
        # Determine which parameters to use based on home/away status
        if is_home:
            goal_prior = params['mu_home']
            score_prior = params['p_score_home']
            alpha_nb = params['alpha_home']
            multiplier = params['home_multiplier']
            alpha_factor = params['alpha_home_factor']
            std_dev = params['home_std']
            raw_ratio = params['home_ratio_raw']                 
        else:
            goal_prior = params['mu_away']
            score_prior = params['p_score_away']
            alpha_nb = params['alpha_away']
            multiplier = params['away_multiplier']
            alpha_factor = params['alpha_away_factor']
            std_dev = params['away_std']
            raw_ratio = params['away_ratio_raw']  

        league_std = {'std_dev': std_dev, 'raw_ratio': raw_ratio}
            
    except KeyError as e:
        raise ValueError(f"Missing required parameter: {e}")

    # Calculate prior weights with error handling
    goal_prior_weight = prior_weight_from_k(team1_games_total, k_goals, ref_games)
    score_prior_weight = prior_weight_from_k(team1_games_total, k_score, ref_games, lo=4, hi=10)
    
    goal_prior_weight = max(goal_prior_weight - 1, 2)
    score_prior_weight = max(score_prior_weight - 1, 3)

    # Apply smoothing to raw match data with error handling
    team1_goals_scored = apply_smoothing_to_team_data(
        team1_goals_scored_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    team1_goals_conceded = apply_smoothing_to_team_data(
        team1_goals_conceded_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    team2_goals_scored = apply_smoothing_to_team_data(
        team2_goals_scored_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    team2_goals_conceded = apply_smoothing_to_team_data(
        team2_goals_conceded_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    
    # Apply smoothing to games scored and clean sheets as rates
    team1_games_scored = apply_smoothing_to_binary_rate(
        team1_games_scored_raw, team1_games_total, alpha_smooth, score_prior, score_prior_weight, use_bayesian=True)
    team1_games_cleanSheet = apply_smoothing_to_binary_rate(
        team1_games_cleanSheet_raw, team1_games_total, alpha_smooth, 1-score_prior, score_prior_weight, use_bayesian=True)
    team2_games_scored = apply_smoothing_to_binary_rate(
        team2_games_scored_raw, team2_games_total, alpha_smooth, score_prior, score_prior_weight, use_bayesian=True)
    team2_games_cleanSheet = apply_smoothing_to_binary_rate(
        team2_games_cleanSheet_raw, team2_games_total, alpha_smooth, 1-score_prior, score_prior_weight, use_bayesian=True)
    
    if is_home:
        lmbda = (team1_goals_scored * team2_goals_conceded * 
                    team1_games_scored * 
                    (1 - team2_games_cleanSheet))
    else:
        lmbda = (team2_goals_scored * team1_goals_conceded * 
                    team2_games_scored * 
                    (1 - team1_games_cleanSheet))      
    
    print(f'Initial Lambda: {lmbda}')

    # Calculate shrinkage factor based on team's game count (from original)
    team_games = team1_games_total if is_home else team2_games_total
    k = ref_games
    shrinkage_factor = k / (k + team_games)
    
    # Store original lambda for reporting
    lmbda_original = lmbda

    # Home advantage adjustment
    if is_home:
        lmbda *= league_home_adv
    else:
        lmbda *= 1/league_home_adv
        
    # Apply smart correction with opponent lambda for ratio preservation
    lmbda, correction_applied = apply_smart_correction(
        lmbda, multiplier, confidence, sample_size, league_std, opponent_lambda
    )

    print(f"Correction Applied: {json.dumps(correction_applied, default=decimal_default)}")

    print(f'Lambda After corrections and boost: {lmbda}')        

    # Adjust alpha using calibrated factor (not hard-inverting multiplier)
    alpha_eff = alpha_nb if alpha_nb is not None else 0.3
    alpha_team = max(alpha_eff * alpha_factor, 0.05)
    
    # Dynamic ceiling based on adjusted alpha
    ceiling = 10.0 / (1 + alpha_team)

    # Apply ceiling to prevent extreme values
    lmbda = min(lmbda, ceiling)
    print(f'Lambda After ceiling: {lmbda}')

    # Probability of scoring at least 1 goal
    score = 1 - math.exp(-lmbda)
    
    # Compute most likely number of goals and its probability
    most_likely_goals, goal_probability, probabilities = calculate_goal_probabilities(lmbda, alpha_team)
            
    return score, most_likely_goals, goal_probability, probabilities


def extract_team_data(json_response, team):
    """
    Extract team data from a JSON response to be used for score calculation.
    
    Parameters:
    - json_response: The JSON response from get_team_statistics
    - team: The team venue ('home' or 'away')
    
    Returns:
    - List containing extracted data for goals and scoring metrics
    - Dictionary with detailed goal statistics
    """
    # First check if response exists and is a dictionary
    if not json_response or 'response' not in json_response:
        raise ValueError("Invalid or empty response in extract_team_data")
    
    # Get the actual response data which should be a dictionary
    response_data = json_response.get('response')
    #print(f"Response type in extract_team_data: {type(response_data)}")    # Debug the response structure
    
    # Check if response_data is a dictionary as expected
    if not isinstance(response_data, dict):
        raise ValueError(f"Unexpected response structure: {type(response_data)}")
    
    # Now extract the data - RAISE EXCEPTION if data is missing
    goals_data = response_data.get('goals')
    if not goals_data:
        raise ValueError("No goals data found in response")
        
    for_data = goals_data.get('for')
    against_data = goals_data.get('against')
    
    if not for_data or not against_data:
        raise ValueError("Missing goals for/against data")
    
    # Extract the values - RAISE EXCEPTION if missing
    team_total = for_data.get('total', {})
    team_avg = for_data.get('average', {})
    against_total = against_data.get('total', {})
    against_avg = against_data.get('average', {})
    
    if team not in team_total or team not in team_avg or team not in against_total or team not in against_avg:
        raise ValueError(f"Missing data for team venue '{team}'")
    
    tgoals_scored = float(team_total[team])
    tgoals_conceded = float(against_total[team])
    goals_scored = float(team_avg[team])
    goals_conceded = float(against_avg[team])
    
    # Extract fixture data
    fixtures_data = response_data.get('fixtures')
    if not fixtures_data:
        raise ValueError("No fixtures data found in response")
        
    played_data = fixtures_data.get('played')
    failed_to_score_data = response_data.get('failed_to_score')
    clean_sheet_data = response_data.get('clean_sheet')
    
    if not played_data or team not in played_data:
        raise ValueError(f"No played data found for team venue '{team}'")
    
    cgoals_total = played_data[team]
    cgoals_scored = cgoals_total - (failed_to_score_data.get(team, 0) if failed_to_score_data else 0)
    cgoals_cleanSheet = clean_sheet_data.get(team, 0) if clean_sheet_data else 0
    
    return [goals_scored, goals_conceded, cgoals_scored, cgoals_cleanSheet, cgoals_total], {
        "goals_scored": tgoals_scored, 
        "goals_conceded": tgoals_conceded, 
        "games_scored": cgoals_scored, 
        "cleansheets": cgoals_cleanSheet, 
        "total_games_played": cgoals_total
    }


def fetch_team_match_data(league, season, team, from_date, max_retries=5):
    """
    Fetch recent match data for a team and return raw values without smoothing.
  
    Parameters:
    - league: The league ID
    - season: The season year
    - team: The team ID
    - from_date: The start date for fetching data (format: YYYY-MM-DD)
    - max_retries: Maximum retries for HTTP 429 errors

    Returns:
    - List containing:
      - Goals scored per match (list)
      - Goals conceded per match (list)
      - Binary list indicating if the team scored in each match (1 = Yes, 0 = No)
      - Binary list indicating if the team kept a clean sheet (1 = Yes, 0 = No)
      - Total games played (integer)
    - List of match data arrays containing:
      - Goals scored
      - Goals conceded
      - Is home game (boolean)
    """
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    to_date = datetime.now().strftime("%Y-%m-%d")
    querystring = {
        "league": league,
        "season": season,
        "team": team,
        "from": from_date,
        "to": to_date
    }
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers, params=querystring, timeout=30)
            if response.status_code == 200:
                data = response.json()
                #print(f"API response: {data}")

                if "response" not in data or not data["response"]:
                    print("Error: Unexpected API response format or no matches found")
                    return None, None

                goals_scored_raw = []
                goals_conceded_raw = []
                games_scored_raw = []
                games_cleanSheet_raw = []
                match_details = []

                for match in data["response"]:
                    if (
                        "goals" in match and
                        match["goals"]["home"] is not None and
                        match["goals"]["away"] is not None
                    ):
                        home_team = match["teams"]["home"]["id"]
                        away_team = match["teams"]["away"]["id"]
                        is_home = team == home_team

                        if is_home:
                            goals_scored = match["goals"]["home"]
                            goals_conceded = match["goals"]["away"]
                        else:
                            goals_scored = match["goals"]["away"]
                            goals_conceded = match["goals"]["home"]

                        goals_scored_raw.append(goals_scored)
                        goals_conceded_raw.append(goals_conceded)
                        games_scored_raw.append(1 if goals_scored > 0 else 0)
                        games_cleanSheet_raw.append(1 if goals_conceded == 0 else 0)
                        match_details.append([goals_scored, goals_conceded, is_home])

                total_games_played = len(goals_scored_raw)
                if total_games_played == 0:
                    print(f"No valid matches found for team {team}")
                    return None, None

                return [
                    goals_scored_raw,
                    goals_conceded_raw,
                    games_scored_raw,
                    games_cleanSheet_raw,
                    total_games_played
                ], match_details

            elif response.status_code == 429:
                wait_time = random.randint(5, 30)
                print(f"Received 429. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                retries += 1
                continue
            else:
                print(f"Error: API request failed with status code {response.status_code}")
                print(f"Response content: {response.text}")
                return None, None
        except Exception as e:
            print(f"Exception in fetch_team_match_data: {e}")
            return None, None
    print("Max retries reached. Request failed.")
    return None, None


def calculate_team_points(league, season, team, venue, match_details, alpha=0.15):
    """
    Calculate a team's performance using exponential smoothing while maintaining all existing functionality.

    Parameters:
    - league: League ID
    - season: Season year
    - team: Team ID
    - venue: Venue type ('home' or 'away')
    - match_details: List of match data [[goals_scored, goals_conceded, is_home], ...]
    - alpha: Smoothing factor for recent performance weighting

    Returns:
    - Dictionary containing team performance metrics with smoothed performance values.
    """
    # Validate match_details before proceeding
    if match_details is None:
        raise ValueError(f"match_details is None for team {team}")
    
    data = get_team_statistics(league, season, team)

    # Check if we got valid data from API
    if not data or 'response' not in data or not data['response']:
        raise ValueError(f"No valid team statistics data for team {team}")
    
    # Extract data for probability calculation
    team_parameters, team_goal_stats = extract_team_data(data, venue)
    
    # Extract the necessary information
    team_name = data["response"]["team"]["name"]
    league_name = data["response"]["league"]["name"]
    league_country = data["response"]["league"]["country"]
    season = data["response"]["league"]["season"]
    total_games_played = data["response"]["fixtures"]["played"]["total"]
    team_logo = data['response']['team']['logo']   

    # Points calculation based on the system you provided
    home_win_points = 3
    away_win_points = 4
    home_draw_points = 1
    away_draw_points = 2
    home_loss_points = -1
    away_loss_points = 0

    # Statistics from API
    home_wins = data["response"]["fixtures"]["wins"]["home"]
    away_wins = data["response"]["fixtures"]["wins"]["away"]
    home_draws = data["response"]["fixtures"]["draws"]["home"]
    away_draws = data["response"]["fixtures"]["draws"]["away"]
    home_losses = data["response"]["fixtures"]["loses"]["home"]
    away_losses = data["response"]["fixtures"]["loses"]["away"]
    
    # Calculate maximum possible points 
    home_max = (home_wins + home_draws + home_losses) * home_win_points
    away_max = (away_wins + away_draws + away_losses) * away_win_points
    max_points = home_max + away_max

    # Calculating total points
    home_points = (home_wins * home_win_points + home_draws * home_draw_points + home_losses * home_loss_points)
    away_points = (away_wins * away_win_points + away_draws * away_draw_points + away_losses * away_loss_points)
    total_points = home_points + away_points

    # Compute per-game points using match details - WITH SAFETY CHECK
    home_points_per_game = []
    away_points_per_game = []
    total_points_per_game = []

    home_max_points_per_game = []
    away_max_points_per_game = []
    total_max_points_per_game = []

    # Safe iteration over match_details
    for goals_scored, goals_conceded, is_home in match_details:
        if goals_scored > goals_conceded:  # Win
            points = home_win_points if is_home else away_win_points
        elif goals_scored == goals_conceded:  # Draw
            points = home_draw_points if is_home else away_draw_points
        else:  # Loss
            points = home_loss_points if is_home else away_loss_points

        max_points = home_win_points if is_home else away_win_points

        # Store separately for home and away matches
        if is_home:
            home_points_per_game.append(points)
            home_max_points_per_game.append(max_points)
        else:
            away_points_per_game.append(points)
            away_max_points_per_game.append(max_points)

        # Store total points across all matches
        total_points_per_game.append(points)
        total_max_points_per_game.append(max_points)

    # Apply exponential smoothing with safe defaults for empty lists
    smoothed_home_points = apply_smoothing_to_team_data(home_points_per_game, alpha) if home_points_per_game else 0
    smoothed_away_points = apply_smoothing_to_team_data(away_points_per_game, alpha) if away_points_per_game else 0
    smoothed_total_points = apply_smoothing_to_team_data(total_points_per_game, alpha) if total_points_per_game else 0

    smoothed_home_max_points = apply_smoothing_to_team_data(home_max_points_per_game, alpha) if home_max_points_per_game else 1
    smoothed_away_max_points = apply_smoothing_to_team_data(away_max_points_per_game, alpha) if away_max_points_per_game else 1
    smoothed_total_max_points = apply_smoothing_to_team_data(total_max_points_per_game, alpha) if total_max_points_per_game else 1

    # Compute smoothed performance metrics with division by zero protection
    smoothed_home_perf = smoothed_home_points / smoothed_home_max_points if smoothed_home_max_points > 0 else 0
    smoothed_away_perf = smoothed_away_points / smoothed_away_max_points if smoothed_away_max_points > 0 else 0
    smoothed_performance = smoothed_total_points / smoothed_total_max_points if smoothed_total_max_points > 0 else 0

    return {
        "team_info": {
            "league_country": league_country,
            "league_name": league_name,
            "team_name": team_name,
            "total_games_played": total_games_played,
            "home_wins": home_wins,
            "home_draws": home_draws,
            "home_losses": home_losses,
            "away_wins": away_wins,
            "away_draws": away_draws,
            "away_losses": away_losses,
            "total_points": total_points,
            "home_performance": smoothed_home_perf,
            "away_performance": smoothed_away_perf,
            "performance": smoothed_performance
        },
        "team_parameters": team_parameters,
        "team_goal_stats": team_goal_stats,
        "team_logo": team_logo
    }


def nb_pmf(k, mu, alpha=0.3):
    """
    Calculate probability mass function for Negative Binomial distribution.
    
    Parameters:
    - k: Number of goals
    - mu: Lambda (expected goals)
    - alpha: Dispersion parameter (higher = more dispersion)
    
    Returns:
    - Probability of exactly k goals with expected value mu
    """
    try:
        # Ensure parameters are valid
        if mu < 0:
            return 0
        
        # Use scipy's implementation for numerical stability
        r = 1 / alpha
        p = 1 / (1 + alpha * mu)
        
        # Handle edge cases
        if k < 0:
            return 0
        if mu == 0 and k == 0:
            return 1
        if mu == 0:
            return 0
            
        return stats.nbinom.pmf(k, r, p)
    except Exception as e:
        # Fallback to Poisson in case of numerical errors
        print(f"Warning: Negative Binomial calculation failed ({e}). Falling back to Poisson.")
        return poisson_pmf(k, mu)


def poisson_pmf(k, lambda_):
    """
    Calculate the Poisson probability mass function (PMF) for given k and lambda.
    Used as a fallback if Negative Binomial calculation fails.

    Parameters:
    - k: The number of events for which the probability is to be calculated.
    - lambda_: The expected number of events that can occur within a fixed interval.

    Returns:
    - The PMF probability for k events to happen.
    """
    try:
        return (lambda_ ** k) * math.exp(-lambda_) / math.factorial(k)
    except OverflowError:
        # For very large k or lambda values
        return 0
    except Exception:
        # Ultimate fallback
        return 0


def squash_lambda(lmbda, ceiling=4.0):
    return lmbda / (1 + lmbda / ceiling)


def calculate_goal_probabilities(lmbda, alpha):
    """
    Calculate the probabilities of scoring different numbers of goals using 
    the Negative Binomial distribution.

    Parameters:
    - lmbda: The lambda (expected rate) of goals
    - alpha: Dispersion parameter for Negative Binomial distribution

    Returns:
    - Most likely number of goals
    - Probability of that many goals
    - Dictionary of all goal probabilities from 0-10
    """
    # Apply a small adjustment to lambda for better alignment with common football scores
    if lmbda > 0.5:
        # Very slight boost for mid-to-high lambdas
        adjusted_lmbda = lmbda * 1.05
    else:
        # No adjustment for very low lambdas
        adjusted_lmbda = lmbda * 1

    # Calculate probabilities for goals 0-10 using the Negative Binomial
    probabilities = {}
    for goals in range(11):  # From 0 to 10 goals
        probabilities[goals] = nb_pmf(goals, adjusted_lmbda, alpha)
    
    # Ensure probabilities sum to 1 (may not due to truncation at 10 goals)
    probability_sum = sum(probabilities.values())
    if probability_sum > 0:  # Avoid division by zero
        for goals in probabilities:
            probabilities[goals] /= probability_sum
    
    # Find the number of goals with the highest probability
    most_likely_goals = max(probabilities, key=probabilities.get)
    
    return most_likely_goals, probabilities[most_likely_goals], probabilities


def analyze_match_probabilities(home_probs, away_probs):
    """
    Analyze match probabilities using probability distributions for home and away teams.
    
    Parameters:
    - home_probs: Dictionary mapping goals (0-10) to probabilities for home team
    - away_probs: Dictionary mapping goals (0-10) to probabilities for away team
    
    Returns:
    - Dictionary with the following keys:
        - most_likely_score: Tuple of (home_goals, away_goals) with highest probability
        - most_likely_score_prob: Probability of the most likely score
        - home_win_prob: Probability of home team winning
        - draw_prob: Probability of a draw
        - away_win_prob: Probability of away team winning
        - over_0_5_prob: Probability of over 0.5 total goals
        - over_1_5_prob: Probability of over 1.5 total goals
        - over_2_5_prob: Probability of over 2.5 total goals
        - over_3_5_prob: Probability of over 3.5 total goals
        - over_4_5_prob: Probability of over 4.5 total goals
        - btts_prob: Probability of both teams scoring (BTTS)
        - exact_score_matrix: 2D array with probabilities for all score combinations
    """
    results = {}
    
    # Create a matrix of all possible score combinations
    max_goals = 10
    score_matrix = np.zeros((max_goals + 1, max_goals + 1))
    
    # Fill the matrix with joint probabilities
    for h_goals in range(max_goals + 1):
        for a_goals in range(max_goals + 1):
            # Joint probability (independent events)
            score_matrix[h_goals, a_goals] = home_probs.get(h_goals, 0) * away_probs.get(a_goals, 0)
    
    # Find the most likely score
    max_prob_idx = np.unravel_index(np.argmax(score_matrix), score_matrix.shape)
    most_likely_home_goals, most_likely_away_goals = max_prob_idx
    most_likely_score_prob = score_matrix[most_likely_home_goals, most_likely_away_goals]
    
    results['most_likely_score'] = (int(most_likely_home_goals), int(most_likely_away_goals))
    results['most_likely_score_prob'] = float(most_likely_score_prob)
    
    # Calculate match outcome probabilities
    home_win_prob = 0
    draw_prob = 0
    away_win_prob = 0
    
    for h_goals in range(max_goals + 1):
        for a_goals in range(max_goals + 1):
            prob = score_matrix[h_goals, a_goals]
            if h_goals > a_goals:
                home_win_prob += prob
            elif h_goals == a_goals:
                draw_prob += prob
            else:
                away_win_prob += prob
    
    results['home_win_prob'] = float(home_win_prob)
    results['draw_prob'] = float(draw_prob)
    results['away_win_prob'] = float(away_win_prob)
    
    # Calculate over/under probabilities
    over_0_5_prob = 0
    over_1_5_prob = 0
    over_2_5_prob = 0
    over_3_5_prob = 0
    over_4_5_prob = 0
    
    for h_goals in range(max_goals + 1):
        for a_goals in range(max_goals + 1):
            total_goals = h_goals + a_goals
            prob = score_matrix[h_goals, a_goals]
            
            if total_goals > 0:
                over_0_5_prob += prob
            if total_goals > 1:
                over_1_5_prob += prob
            if total_goals > 2:
                over_2_5_prob += prob
            if total_goals > 3:
                over_3_5_prob += prob
            if total_goals > 4:
                over_4_5_prob += prob
    
    results['over_0_5_prob'] = float(over_0_5_prob)
    results['over_1_5_prob'] = float(over_1_5_prob)
    results['over_2_5_prob'] = float(over_2_5_prob)
    results['over_3_5_prob'] = float(over_3_5_prob)
    results['over_4_5_prob'] = float(over_4_5_prob)  # Fixed: This was incorrectly assigned to over_3_5_prob
    
    # Calculate both teams to score probability
    btts_prob = 0
    for h_goals in range(1, max_goals + 1):
        for a_goals in range(1, max_goals + 1):
            btts_prob += score_matrix[h_goals, a_goals]
    
    results['btts_prob'] = float(btts_prob)
    
    # Include a subset of the exact score probabilities (most common ones)
    common_scores = {}
    for h_goals in range(5):
        for a_goals in range(5):
            score_key = f"{h_goals}-{a_goals}"
            common_scores[score_key] = float(score_matrix[h_goals, a_goals])
    
    results['common_scores'] = common_scores

    flat_scores = [
        (f"{h}-{a}", score_matrix[h, a])
        for h in range(max_goals + 1)
        for a in range(max_goals + 1)
    ]
    
    results['flat_scores'] = flat_scores

    # Store the full score matrix (converted to list for JSON compatibility)
    results['exact_score_matrix'] = score_matrix.tolist()
    
    # Calculate additional useful metrics
    results['expected_home_goals'] = float(sum(g * p for g, p in home_probs.items()))
    results['expected_away_goals'] = float(sum(g * p for g, p in away_probs.items()))
    results['expected_total_goals'] = float(results['expected_home_goals'] + results['expected_away_goals'])
    
    # Calculate under probabilities as complement of over
    results['under_0_5_prob'] = float(1 - over_0_5_prob)
    results['under_1_5_prob'] = float(1 - over_1_5_prob)
    results['under_2_5_prob'] = float(1 - over_2_5_prob)
    results['under_3_5_prob'] = float(1 - over_3_5_prob)
    results['under_4_5_prob'] = float(1 - over_4_5_prob)  # Added under 4.5 goals probability
    
    # Add no BTTS probability
    results['no_btts_prob'] = float(1 - btts_prob)
    
    return results


def create_prediction_summary_dict(home_probs, away_probs):
    """
    Create a structured dictionary summary of prediction results for API responses.
    
    Parameters:
    - prediction_results: Dictionary returned by analyze_match_probabilities
    
    Returns:
    - Dictionary with formatted prediction summary suitable for JSON API responses
    """
    prediction_results = analyze_match_probabilities(home_probs, away_probs)

    most_likely = prediction_results['most_likely_score']
    
    # Get most likely scores
    common_scores = prediction_results['common_scores']
    flat_scores = prediction_results['flat_scores']
    top_scores = sorted(common_scores.items(), key=lambda x: x[1], reverse=True)[:5]
    #top_scores = sorted(flat_scores, key=lambda x: x[1], reverse=True)[:5] 
    
    # Format into more API-friendly structure
    summary = {
        "most_likely_score": {
            "score": f"{most_likely[0]}-{most_likely[1]}",
            "probability": round(prediction_results['most_likely_score_prob'] * 100, 1)
        },
        "expected_goals": {
            "home": round(prediction_results['expected_home_goals'], 2),
            "away": round(prediction_results['expected_away_goals'], 2),
            "total": round(prediction_results['expected_total_goals'], 2)
        },
        "match_outcome": {
            "home_win": round(prediction_results['home_win_prob'] * 100, 1),
            "draw": round(prediction_results['draw_prob'] * 100, 1),
            "away_win": round(prediction_results['away_win_prob'] * 100, 1)
        },
        "goals": {
            "over": {
                "0.5": round(prediction_results['over_0_5_prob'] * 100, 1),
                "1.5": round(prediction_results['over_1_5_prob'] * 100, 1),
                "2.5": round(prediction_results['over_2_5_prob'] * 100, 1),
                "3.5": round(prediction_results['over_3_5_prob'] * 100, 1),
                "4.5": round(prediction_results['over_4_5_prob'] * 100, 1)
            },
            "under": {
                "0.5": round(prediction_results['under_0_5_prob'] * 100, 1),
                "1.5": round(prediction_results['under_1_5_prob'] * 100, 1),
                "2.5": round(prediction_results['under_2_5_prob'] * 100, 1),
                "3.5": round(prediction_results['under_3_5_prob'] * 100, 1),
                "4.5": round(prediction_results['under_4_5_prob'] * 100, 1)
            },
            "btts": {
                "yes": round(prediction_results['btts_prob'] * 100, 1),
                "no": round(prediction_results['no_btts_prob'] * 100, 1)
            }
        },
        "top_scores": [
            {
                "score": score,
                "probability": round(prob * 100, 1)
            } for score, prob in top_scores
        ]
    }
    
    # Add decimal odds (European format) for common bet types
    # Formula: odds = 1 / probability
    summary["odds"] = {
        "match_outcome": {
            "home_win": round(1 / max(prediction_results['home_win_prob'], 0.01), 2),
            "draw": round(1 / max(prediction_results['draw_prob'], 0.01), 2),
            "away_win": round(1 / max(prediction_results['away_win_prob'], 0.01), 2)
        },
        "over_under": {
            "over_2.5": round(1 / max(prediction_results['over_2_5_prob'], 0.01), 2),
            "under_2.5": round(1 / max(prediction_results['under_2_5_prob'], 0.01), 2)
        },
        "btts": {
            "yes": round(1 / max(prediction_results['btts_prob'], 0.01), 2),
            "no": round(1 / max(prediction_results['no_btts_prob'], 0.01), 2)
        }
    }
    
    return summary

# Function to convert Decimal to float for JSON serialization 
def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    # Handle numpy types
    if hasattr(obj, 'item'):  # numpy scalars
        return obj.item()
    if hasattr(obj, 'tolist'):  # numpy arrays
        return obj.tolist()
    # Handle other numeric types
    if isinstance(obj, (np.int64, np.int32, np.float64, np.float32)):
        return obj.item()
    # If we can't convert it, return the string representation
    return str(obj)
    
def convert_floats_to_decimal(data):
    if isinstance(data, list):
        return [convert_floats_to_decimal(item) for item in data]
    elif isinstance(data, dict):
        return {k: convert_floats_to_decimal(v) for k, v in data.items()}
    elif isinstance(data, float):
        return Decimal(str(data))
    else:
        return data


def get_venue_id(team_id, league_id, season, max_retries=5):
    """
    Returns the venue ID for a given team in a league and season using API-Football.

    Args:
        team_id (int/str): API-Football team ID.
        league_id (int/str): API-Football league ID.
        season (int/str): Season year.
        max_retries (int): Maximum times to retry for HTTP 429.

    Returns:
        int: Venue ID

    Raises:
        Exception: Descriptive message if unable to fetch or parse the venue ID.
    """
    url = "https://api-football-v1.p.rapidapi.com/v3/teams"
    querystring = {
        "id": str(team_id),
        "league": str(league_id),
        "season": str(season)
    }
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers, params=querystring, timeout=15)
            if response.status_code == 200:
                result = response.json()
                # Uncomment for debugging or logging
                # print(result)
                if 'errors' in result and result['errors']:
                    raise Exception(f"API error: {result['errors']}")
                if 'response' not in result or not isinstance(result['response'], list) or not result['response']:
                    raise Exception("No response data found for given team/league/season.")
                venue = result['response'][0].get('venue')
                if not venue or 'id' not in venue:
                    raise Exception("Venue not found in API response for this team.")
                return venue['id']
            elif response.status_code == 429:
                wait_time = random.randint(5, 30)
                print(f"Received 429. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                retries += 1
                continue
            else:
                logging.error(f"API call failed: status code {response.status_code}, content: {response.text}")
                raise Exception(f"HTTP error: status code {response.status_code}")
        except requests.RequestException as e:
            logging.error(f"Network or HTTP error: {e}")
            raise Exception(f"Network/HTTP error when fetching venue for team {team_id}: {str(e)}")
        except (KeyError, IndexError, TypeError, ValueError) as e:
            logging.error(f"Parsing error: {e}")
            raise Exception(f"Unexpected or missing venue data for team {team_id}: {str(e)}")
        except Exception as e:
            logging.error(str(e))
            raise
    raise Exception(f"Max retries reached for team {team_id}. 429 Too Many Requests persist.")

    
def get_next_fixture(team_id, current_fixture_id, max_retries=5):
    """
    Fetch the next fixture for a given team, ensuring it is not the same as the current fixture.

    Parameters:
    - team_id: The team ID.
    - current_fixture_id: The fixture ID of the current game under review.
    - max_retries: Maximum retries for 429 errors.

    Returns:
    - Dictionary containing fixture details or None if no suitable fixture is found.
    """
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    querystring = {"team": team_id, "next": "3"}  # Fetch next three fixtures
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers, params=querystring, timeout=20)
            if response.status_code == 200:
                data = response.json()
                if "response" not in data or not data["response"]:
                    print("Error: Unexpected API response format or no upcoming fixtures found")
                    return None

                fixtures = data["response"]
                # Find the first fixture that is NOT the current fixture
                next_fixture = None
                for fixture in fixtures:
                    fixture_id = fixture["fixture"]["id"]
                    if fixture_id != current_fixture_id:
                        next_fixture = fixture
                        break  # Found the next valid fixture

                if not next_fixture:
                    return None  # No valid future fixture found

                fixture_date = datetime.strptime(
                    next_fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z"
                ).strftime("%Y-%m-%d %H:%M")
                home_team_id = next_fixture["teams"]["home"]["id"]
                away_team_id = next_fixture["teams"]["away"]["id"]
                home_team_name = next_fixture["teams"]["home"]["name"]
                away_team_name = next_fixture["teams"]["away"]["name"]
                league = next_fixture["league"]["name"]

                if home_team_id == team_id:
                    fixture_type = "home"
                    opponent = away_team_name
                else:
                    fixture_type = "away"
                    opponent = home_team_name

                return {
                    "fixture_type": fixture_type,
                    "opponent": opponent,
                    "fixture_date": fixture_date,
                    "league": league
                }
            elif response.status_code == 429:
                wait_time = random.randint(5, 30)
                print(f"Received 429. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                retries += 1
                continue
            else:
                print(f"Error: API request failed with status code {response.status_code}")
                print(f"Response content: {response.text}")
                return None
        except Exception as e:
            print(f"Exception in get_next_fixture: {e}")
            return None
    print("Max retries reached. Request failed.")
    return None


def get_last_five_games(team_id, league, season, max_retries=5):
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    querystring = {
        "league": league,
        "season": season,
        "team": team_id,
        "last": "5"
    }
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers, params=querystring)
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    return "Error: Unable to parse JSON response."

                # Check if 'response' exists in the JSON data
                if 'response' not in data:
                    return "Error: 'response' key missing in API response."
                games = []
                for game in data['response']:
                    try:
                        fixture_date = game['fixture']['date']
                        teams = {
                            'home': game['teams']['home']['name'],
                            'away': game['teams']['away']['name']
                        }
                        scores = {
                            'home': game['goals']['home'],
                            'away': game['goals']['away']
                        }
                        games.append({
                            'date': fixture_date,
                            'teams': teams,
                            'scores': scores
                        })
                    except KeyError as e:
                        return f"Error: Missing key in game data: {e}"
                return games
            elif response.status_code == 429:
                wait_time = random.randint(5, 30)
                print(f"Received 429. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                retries += 1
                continue
            else:
                return f"Error: Received status code {response.status_code} from the API."
        except requests.exceptions.RequestException as e:
            return f"Error: Request failed - {e}"
    return "Error: Max retries reached for API rate limit."
    

def get_head_to_head(home_team_id, away_team_id, max_retries=5):
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures/headtohead"
    querystring = {
        "h2h": f"{home_team_id}-{away_team_id}",
        "last": "5"
    }
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers, params=querystring)
            if response.status_code == 200:
                try:
                    h2h_data = response.json().get('response', [])
                except ValueError:
                    return "Error: Unable to parse JSON response."

                games = []
                for game in h2h_data:
                    try:
                        fixture_date = game['fixture']['date']
                        teams = {
                            'home': game['teams']['home']['name'],
                            'away': game['teams']['away']['name']
                        }
                        scores = {
                            'home': game['goals']['home'],
                            'away': game['goals']['away']
                        }
                        games.append({
                            'date': fixture_date,
                            'teams': teams,
                            'scores': scores
                        })
                    except KeyError as e:
                        return f"Error: Missing key in game data: {e}"
                return games
            elif response.status_code == 429:
                wait_time = random.randint(5, 30)
                print(f"Received 429. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                retries += 1
            else:
                return f"Error: Received status code {response.status_code} from the API."
        except requests.exceptions.RequestException as e:
            return f"Error: Request failed - {e}"
    return "Error: Max retries reached for API rate limit."


def get_league_start_date(league_id, max_retries=5):
    """
    Fetch the start date of the current season for a given league.
  
    Parameters:
    - league_id: The league ID.
    - rapidapi_key: Your API key.
    - max_retries: Maximum number of retries for 429 errors.

    Returns:
    - The start date of the league season (format: YYYY-MM-DD) or None if not found.
    """
    url = "https://api-football-v1.p.rapidapi.com/v3/leagues"
    querystring = {"id": league_id, "current": "true"}
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }
  
    retries = 0
    while retries < max_retries:
        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code == 200:
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
        elif response.status_code == 429:
            wait_time = random.randint(5, 30)
            print(f"Received 429. Waiting {wait_time} seconds before retrying...")
            time.sleep(wait_time)
            retries += 1
        else:
            print(f"Error: API request failed with status code {response.status_code}")
            return None
    print("Max retries reached. Request failed.")
    return None


def get_injured_players(fixture_id, date, max_retries=5):
    """
    Fetches a list of injured players for a given fixture on a specific date.

    :param fixture_id: The ID of the fixture.
    :param date: The date of the fixture in 'YYYY-MM-DD' format.
    :param max_retries: Maximum retry attempts on HTTP 429.
    :return: A list of dictionaries containing details of injured players or an error message.
    """
    url = "https://api-football-v1.p.rapidapi.com/v3/injuries"
    querystring = {"fixture": str(fixture_id), "date": date}
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers, params=querystring)
            if response.status_code == 200:
                data = response.json()
                # Check if the response contains injury details
                if data.get('results', 0) > 0:
                    return [player for player in data.get('response', [])]
                else:
                    print(f"No injury data found for the provided fixture: {str(fixture_id)} on {date}.")
                    return None
            elif response.status_code == 429:
                wait_time = random.randint(5, 30)
                print(f"Received 429. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                retries += 1
                continue
            else:
                print(f"Error: API request failed with status code {response.status_code}")
                return {"error": f"API request failed with status code {response.status_code}"}
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    print("Max retries reached. Request failed.")
    return {"error": "Max retries reached. Request failed."}


def get_player_statistics(player_id, team_id, league_id, season, max_retries=5):
    """
    Fetches statistics for a given player in a specific team, league, and season.

    :param player_id: The ID of the player.
    :param team_id: The ID of the team the player belongs to.
    :param league_id: The ID of the league.
    :param season: The season year.
    :param max_retries: Max times to retry on 429.
    :return: A JSON response containing the player's statistics.
    """
    url = "https://api-football-v1.p.rapidapi.com/v3/players"
    querystring = {
        "id": str(player_id), 
        "team": str(team_id), 
        "league": str(league_id), 
        "season": str(season)
    }
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
  
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, headers=headers, params=querystring)
            if response.status_code == 200:
                json_data = response.json()
                # Check if there are errors in the API response
                if 'errors' in json_data and json_data['errors']:
                    return {"error": "API returned an error: " + str(json_data['errors'])}
                # Extract the 'response' part of the JSON, with error handling
                if 'response' in json_data and json_data.get('results', 0) > 0:
                    return json_data['response'][0]
                else:
                    return {}
            elif response.status_code == 429:
                wait_time = random.randint(5, 30)
                print(f"Received 429. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                retries += 1
                continue
            else:
                return {"error": f"API request failed with status code {response.status_code}"}
        except requests.exceptions.RequestException as e:
            return {"error": "Request failed: " + str(e)}
        except KeyError as e:
            return {"error": "Key error: " + str(e)}
    return {"error": "Max retries reached. Request failed."}

def extract_player_info(player_data):
    player_info = player_data.get('player', {})
    player_name = player_info.get('name')
    player_id = player_info.get('id')
    player_photo = player_info.get('photo')

    if 'statistics' in player_data and player_data['statistics']:
        stat = player_data['statistics'][0]  # Process only the first statistics entry
        games = stat.get('games', {})
        position = games.get('position', 'Unknown')  # Extract player position
        minutes_played = games.get('minutes', 0) or 0
        player_rating = games.get('rating', 0) or 0

        goals_data = stat.get('goals', {})
        total_goals = goals_data.get('total', 0) or 0
        assists = goals_data.get('assists', 0) or 0
        goal_involvement = total_goals + assists  # Ensure both are integers

        shots_data = stat.get('shots', {})
        total_shots = shots_data.get('total', 0) or 0
        shots_on_target = shots_data.get('on', 0) or 0

        dribbles_data = stat.get('dribbles', {})
        dribbles_attempted = dribbles_data.get('attempts', 0) or 0
        dribbles_successful = dribbles_data.get('success', 0) or 0

        duels_data = stat.get('duels', {})
        duels_total = duels_data.get('total', 0) or 0
        duels_won = duels_data.get('won', 0) or 0

        passes_data = stat.get('passes', {})
        key_passes = passes_data.get('key', 0) or 0

        return {
            'id': player_id,
            'name': player_name,
            'position': position,
            'photo': player_photo,
            'minutes': minutes_played,
            'rating': player_rating,
            'goal_involvement': goal_involvement,
            'total_goals': total_goals,
            'assists': assists,
            'total_shots': total_shots,
            'shots_on_target': shots_on_target,
            'dribbles_attempted': dribbles_attempted,
            'dribbles_successful': dribbles_successful,
            'duels_total': duels_total,
            'duels_won': duels_won,
            'key_passes': key_passes
        }

    # Return basic info if no stats are available
    return {}


def process_injuries(injury_list, home_team_id, away_team_id, season):
    home_injured = []
    away_injured = []

    for entry in injury_list:
        player_id = entry['player']['id']
        team_id = entry['team']['id']
        league_id = entry['league']['id']

        player_stats = get_player_statistics(player_id, team_id, league_id, season)

        # Ensure player_stats contains statistics before extracting player info
        if player_stats and 'statistics' in player_stats and player_stats['statistics']:
            player_info = extract_player_info(player_stats)
            #print(json.dumps(player_info))  # Debugging output

            if team_id == home_team_id:
                home_injured.append(player_info)
            elif team_id == away_team_id:
                away_injured.append(player_info)

    return home_injured, away_injured


def get_fixture_injuries(fixture_id, game_date, home_team_id, away_team_id, season):
    """
    Get injuries for a fixture and return home and away injuries separately.
    
    Args:
        fixture_id (int): The ID of the fixture
        game_date (str): Full date string (will be trimmed to YYYY-MM-DD)
        home_team_id (int): ID of the home team
        away_team_id (int): ID of the away team
        season (str): Current season identifier
        
    Returns:
        tuple: Two lists (home_injured, away_injured) with injury information
    """
    # Get the injury list for this fixture
    injury_list = get_injured_players(fixture_id, game_date[:10])
    # print(f"Injury List: {json.dumps(injury_list)}")
    
    # Initialize empty lists for home and away injuries
    home_injured = []
    away_injured = []
    
    # Check if injury_list is not empty and not None
    if injury_list:
        home_injured, away_injured = process_injuries(injury_list, home_team_id, away_team_id, season)
    
    # Return the two separate lists
    return home_injured, away_injured


def decimal_to_float(x):
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, dict):
        return {k: decimal_to_float(v) for k, v in x.items()}
    if isinstance(x, list):
        return [decimal_to_float(v) for v in x]
    return x


def write_to_mongo(document):
    # Process the entire document
    processed_document = process_document(document)

    # MongoDB connection URL from Lambda's environment variables
    mongo_url = os.environ['MONGO_URL']

    # Connect to MongoDB
    client = MongoClient(mongo_url)

    # Select the database and collection
    db_name = 'gamers-Cluster0'
    collection_name = 'gamers-data-2024'
    db = client[db_name]
    collection = db[collection_name]

    # Insert the processed document
    collection.insert_one(processed_document)

    # Close the connection
    client.close()

def process_document(document):
    # Function to recursively process the document
    if isinstance(document, dict):
        return {k: process_document(v) for k, v in document.items()}
    elif isinstance(document, list):
        return [process_document(elem) for elem in document]
    else:
        return decimal_to_float(document)
        
def get_league_params_from_db(league_id):
    response = league_table.query(
        KeyConditionExpression=Key('league_id').eq(league_id),
        Limit=1,
        ScanIndexForward=False  # get the latest messages first
    )
    messages = response['Items'][0] if 'Items' in response else {}
    return messages  # return the whole item, not just the message

def get_team_params_from_db(id):
    response = teams_table.query(
        KeyConditionExpression=Key('id').eq(id),
        Limit=1,
        ScanIndexForward=False
    )
    items = response.get('Items', [])
    return items[0] if items else None


def get_prediction_params(team_params, league_params):
    """
    Merge team and league parameters for prediction.
    Copies missing statistical parameters from league if not present in team.
    Enhanced with multiplier capping for safety and bootstrap defaults for first-run scenarios.
    
    Parameters:
    - team_params: Dictionary containing team-specific parameters
    - league_params: Dictionary containing league-wide parameters
    
    Returns:
    - params: Complete parameter dictionary with all required fields
    """
    # Start with a copy of team parameters
    params = team_params.copy()
    
    # Override with league-wide parameters (these should always come from league level)
    league_wide_keys = ['k_goals', 'k_score', 'ref_games']
    for key in league_wide_keys:
        if key in league_params:
            params[key] = league_params[key]
    
    # Define bootstrap defaults for missing parameters (first-run scenario)
    bootstrap_defaults = {
        'home_ratio_raw': 1.0,        # Neutral ratio - no systematic bias
        'away_ratio_raw': 1.0,        # Neutral ratio - no systematic bias  
        'total_ratio_raw': 1.0,       # Neutral ratio - no systematic bias
        'home_std': 1.0,              # Reasonable default standard deviation
        'away_std': 1.0,              # Reasonable default standard deviation
        'total_std': 1.0,             # Reasonable default standard deviation
        'sample_size': 0,             # Indicates no historical prediction data
        'confidence': 0.1,            # Low confidence when no historical data
        'home_multiplier': 1.0,       # Neutral multiplier
        'away_multiplier': 1.0,       # Neutral multiplier  
        'total_multiplier': 1.0,      # Neutral multiplier
        'alpha_home_factor': 1.0,     # Neutral alpha adjustment
        'alpha_away_factor': 1.0      # Neutral alpha adjustment
    }
    
    # Copy statistical parameters from league if missing in team, with bootstrap fallback
    statistical_keys = [
        'home_std', 'away_std', 'total_std',
        'home_ratio_raw', 'away_ratio_raw', 'total_ratio_raw',
        'sample_size', 'confidence',
        'home_multiplier', 'away_multiplier', 'total_multiplier',
        'alpha_home_factor', 'alpha_away_factor'
    ]
    
    copied_from_league = []
    applied_bootstrap = []
    
    for key in statistical_keys:
        if key not in params:
            if key in league_params:
                # Copy from league parameters
                params[key] = league_params[key]
                copied_from_league.append(key)
            else:
                # Apply bootstrap default
                params[key] = bootstrap_defaults[key]
                applied_bootstrap.append(key)
                print(f"Applied bootstrap default {bootstrap_defaults[key]} for missing parameter: {key}")
    
    # Add metadata about parameter sources for debugging
    if copied_from_league:
        params['copied_from_league'] = copied_from_league
    if applied_bootstrap:
        params['bootstrap_defaults_applied'] = applied_bootstrap
    
    # Cap extreme multipliers at load time to prevent wild predictions
    multiplier_keys = ['home_multiplier', 'away_multiplier', 'total_multiplier']
    capped_multipliers = {}
    
    for key in multiplier_keys:
        if key in params:
            original_value = float(params[key])
            capped_value = max(0.5, min(6.0, original_value))
            
            if original_value != capped_value:
                capped_multipliers[key] = {
                    'original': original_value,
                    'capped': capped_value,
                    'was_capped': True
                }
                print(f"Warning: {key} capped from {original_value:.3f} to {capped_value:.3f}")
            
            params[key] = capped_value
    
    # Add capping info for debugging/logging
    if capped_multipliers:
        params['multiplier_capping_applied'] = capped_multipliers
    
    # Validate confidence parameters and cap if necessary
    if 'confidence' in params:
        original_confidence = float(params['confidence'])
        capped_confidence = max(0.1, min(0.9, original_confidence))  # Cap between 10% and 90%
        
        if original_confidence != capped_confidence:
            print(f"Warning: confidence capped from {original_confidence:.3f} to {capped_confidence:.3f}")
            params['confidence_capping_applied'] = {
                'original': original_confidence,
                'capped': capped_confidence
            }
        
        params['confidence'] = capped_confidence
    
    # Validate alpha factors and cap if necessary
    alpha_factor_keys = ['alpha_home_factor', 'alpha_away_factor']
    for key in alpha_factor_keys:
        if key in params:
            original_alpha = float(params[key])
            capped_alpha = max(0.5, min(2.0, original_alpha))  # Cap between 0.5 and 2.0
            
            if original_alpha != capped_alpha:
                print(f"Warning: {key} capped from {original_alpha:.3f} to {capped_alpha:.3f}")
                if 'alpha_factor_capping_applied' not in params:
                    params['alpha_factor_capping_applied'] = {}
                params['alpha_factor_capping_applied'][key] = {
                    'original': original_alpha,
                    'capped': capped_alpha
                }
            
            params[key] = capped_alpha
    
    # Log summary of applied defaults for debugging
    if applied_bootstrap:
        print(f"Bootstrap mode: Applied {len(applied_bootstrap)} default values for first-run scenario")
    
    return params


def mod_league_params(team_params, league_params):
    """
    Create a copy of league parameters with team-specific std_dev and raw_ratio values.
    
    This function replaces the league-wide statistical values with team-specific ones
    to enable personalized lambda adjustments while maintaining league-based foundations.
    
    Parameters:
    - team_params: Dictionary containing team-specific parameters
    - league_params: Dictionary containing league-wide parameters
    
    Returns:
    - adjusted_params: Copy of league_params with team-specific std/ratio values
    """
    
    # Start with a copy of league parameters
    adjusted_params = league_params.copy()
    
    # Statistical keys to replace with team-specific values
    team_specific_keys = [
        'home_std',
        'away_std', 
        'total_std',
        'home_ratio_raw',
        'away_ratio_raw',
        'total_ratio_raw'
    ]
    
    # Replace league values with team values if they exist
    for key in team_specific_keys:
        if key in team_params:
            adjusted_params[key] = team_params[key]
    
    return adjusted_params


def calculate_base_lambda(team1_stats, team2_stats, params, is_home=True):
    """
    Calculate base lambda before corrections for ratio preservation.
    This function extracts the core lambda calculation logic without applying
    smart corrections, allowing for coordinated home/away adjustments.
    
    Parameters:
    - team1_stats: Raw match stats for team 1 (attacking team)
    - team2_stats: Raw match stats for team 2 (defending team)
    - params: League/team parameters
    - is_home: Whether this is for home team calculation
    
    Returns:
    - base_lambda: Lambda value before smart corrections (float)
    """
    
    # Validate input parameters
    if not team1_stats or not team2_stats or not params:
        raise ValueError("Missing required parameters for calculate_base_lambda")
        
    # Unpack raw match stats
    team1_goals_scored_raw, team1_goals_conceded_raw, team1_games_scored_raw, team1_games_cleanSheet_raw, team1_games_total = team1_stats
    team2_goals_scored_raw, team2_goals_conceded_raw, team2_games_scored_raw, team2_games_cleanSheet_raw, team2_games_total = team2_stats

    # Validate games_total
    if team1_games_total is None or team1_games_total <= 0 or team2_games_total is None or team2_games_total <= 0:
        raise ValueError("Invalid games_total values")

    # Extract parameters
    try:
        k_goals = params['k_goals']
        k_score = params['k_score']
        league_home_adv = params['home_adv']
        ref_games = params['ref_games']
        alpha_smooth = 0.15
        
        # Get appropriate priors based on home/away
        if is_home:
            goal_prior = params['mu_home']
            score_prior = params['p_score_home']
        else:
            goal_prior = params['mu_away']
            score_prior = params['p_score_away']
            
    except KeyError as e:
        raise ValueError(f"Missing required parameter: {e}")

    # Calculate prior weights
    goal_prior_weight = prior_weight_from_k(team1_games_total, k_goals, ref_games)
    score_prior_weight = prior_weight_from_k(team1_games_total, k_score, ref_games, lo=4, hi=10)
    
    goal_prior_weight = max(goal_prior_weight - 1, 2)
    score_prior_weight = max(score_prior_weight - 1, 3)

    # Apply smoothing to raw match data
    team1_goals_scored = apply_smoothing_to_team_data(
        team1_goals_scored_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    team1_goals_conceded = apply_smoothing_to_team_data(
        team1_goals_conceded_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    team2_goals_scored = apply_smoothing_to_team_data(
        team2_goals_scored_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    team2_goals_conceded = apply_smoothing_to_team_data(
        team2_goals_conceded_raw, alpha_smooth, goal_prior, goal_prior_weight, use_bayesian=True)
    
    # Apply smoothing to games scored and clean sheets as rates
    team1_games_scored = apply_smoothing_to_binary_rate(
        team1_games_scored_raw, team1_games_total, alpha_smooth, score_prior, score_prior_weight, use_bayesian=True)
    team1_games_cleanSheet = apply_smoothing_to_binary_rate(
        team1_games_cleanSheet_raw, team1_games_total, alpha_smooth, 1-score_prior, score_prior_weight, use_bayesian=True)
    team2_games_scored = apply_smoothing_to_binary_rate(
        team2_games_scored_raw, team2_games_total, alpha_smooth, score_prior, score_prior_weight, use_bayesian=True)
    team2_games_cleanSheet = apply_smoothing_to_binary_rate(
        team2_games_cleanSheet_raw, team2_games_total, alpha_smooth, 1-score_prior, score_prior_weight, use_bayesian=True)
    
    # Calculate base lambda using the same formula as calculate_to_score
    if is_home:
        base_lambda = (team1_goals_scored * team2_goals_conceded * 
                      team1_games_scored * 
                      (1 - team2_games_cleanSheet))
    else:
        base_lambda = (team2_goals_scored * team1_goals_conceded * 
                      team2_games_scored * 
                      (1 - team1_games_cleanSheet))
    
    # Apply home advantage adjustment
    if is_home:
        base_lambda *= league_home_adv
    else:
        base_lambda *= 1/league_home_adv
    
    return float(base_lambda)


def apply_coordinated_correction(home_lambda, away_lambda, home_params, away_params, home_stats, away_stats):
    """
    Apply corrections to both home and away lambdas while preserving realistic outcome relationships.
    
    Parameters:
    - home_lambda: Original home team lambda
    - away_lambda: Original away team lambda  
    - home_params: Home team parameters (including multipliers, confidence, etc.)
    - away_params: Away team parameters (including multipliers, confidence, etc.)
    - home_stats: League stats for home team (std_dev, raw_ratio)
    - away_stats: League stats for away team (std_dev, raw_ratio)
    
    Returns:
    - home_final: Coordinated home lambda
    - away_final: Coordinated away lambda
    - coordination_info: Dict with coordination details
    """
    
    # Calculate individual corrections independently first
    home_corrected, home_info = apply_smart_correction(
        home_lambda, 
        home_params['home_multiplier'], 
        home_params['confidence'], 
        home_params['sample_size'], 
        {'std_dev': home_params['home_std'], 'raw_ratio': home_params['home_ratio_raw']}, 
        opponent_lambda=away_lambda
    )
    
    away_corrected, away_info = apply_smart_correction(
        away_lambda, 
        away_params['away_multiplier'], 
        away_params['confidence'], 
        away_params['sample_size'], 
        {'std_dev': away_params['away_std'], 'raw_ratio': away_params['away_ratio_raw']}, 
        opponent_lambda=home_lambda
    )
    
    # Analyze the impact of corrections on outcomes
    original_ratio = home_lambda / max(away_lambda, 0.1)
    corrected_ratio = home_corrected / max(away_corrected, 0.1)
    ratio_change_factor = corrected_ratio / original_ratio
    
    # Calculate most likely outcomes before and after
    original_home_goals = int(round(home_lambda))
    original_away_goals = int(round(away_lambda))
    corrected_home_goals = int(round(home_corrected))
    corrected_away_goals = int(round(away_corrected))
    
    # Check for winner/outcome changes
    original_outcome = "home" if original_home_goals > original_away_goals else ("away" if original_away_goals > original_home_goals else "draw")
    corrected_outcome = "home" if corrected_home_goals > corrected_away_goals else ("away" if corrected_away_goals > corrected_home_goals else "draw")
    outcome_changed = original_outcome != corrected_outcome
    
    # Define coordination thresholds
    MAX_RATIO_CHANGE = 2.5  # Allow up to 150% ratio change
    EXTREME_RATIO_CHANGE = 4.0  # Threshold for extreme coordination
    
    coordination_applied = False
    coordination_reason = "none"
    
    # Apply coordination if needed
    if ratio_change_factor > MAX_RATIO_CHANGE or ratio_change_factor < (1.0 / MAX_RATIO_CHANGE):
        # Extreme ratio change - apply strong coordination
        coordination_applied = True
        coordination_reason = "extreme_ratio_change"
        
        # Calculate scaling factor to bring ratio change within bounds
        if ratio_change_factor > MAX_RATIO_CHANGE:
            target_ratio_change = MAX_RATIO_CHANGE * 0.9  # Slightly under the limit
        else:
            target_ratio_change = (1.0 / MAX_RATIO_CHANGE) * 1.1  # Slightly over the limit
        
        scaling_factor = target_ratio_change / ratio_change_factor
        
        # Apply proportional scaling to both corrections
        home_adjustment = (home_corrected - home_lambda) * scaling_factor
        away_adjustment = (away_corrected - away_lambda) * scaling_factor
        
        home_final = home_lambda + home_adjustment
        away_final = away_lambda + away_adjustment
        
    elif outcome_changed and abs(ratio_change_factor - 1.0) > 0.8:
        # Outcome changed significantly - apply moderate coordination
        coordination_applied = True
        coordination_reason = "outcome_preservation"
        
        # Reduce corrections by 30% to preserve original outcome tendency
        home_adjustment = (home_corrected - home_lambda) * 0.7
        away_adjustment = (away_corrected - away_lambda) * 0.7
        
        home_final = home_lambda + home_adjustment
        away_final = away_lambda + away_adjustment
        
    else:
        # No coordination needed - use individual corrections
        home_final = home_corrected
        away_final = away_corrected
    
    # Ensure reasonable bounds
    home_final = max(0.1, min(6.0, home_final))
    away_final = max(0.1, min(6.0, away_final))
    
    # Prepare coordination info
    coordination_info = {
        'coordination_applied': coordination_applied,
        'coordination_reason': coordination_reason,
        'original_ratio': original_ratio,
        'corrected_ratio': corrected_ratio,
        'final_ratio': home_final / max(away_final, 0.1),
        'ratio_change_factor': ratio_change_factor,
        'outcome_changed': outcome_changed,
        'original_outcome': original_outcome,
        'corrected_outcome': corrected_outcome,
        'final_outcome': "home" if home_final > away_final else ("away" if away_final > home_final else "draw"),
        'original_score_estimate': f"{original_home_goals}-{original_away_goals}",
        'corrected_score_estimate': f"{corrected_home_goals}-{corrected_away_goals}",
        'final_score_estimate': f"{int(round(home_final))}-{int(round(away_final))}",
        'home_lambda_change_pct': ((home_final / home_lambda - 1) * 100),
        'away_lambda_change_pct': ((away_final / away_lambda - 1) * 100),
        'individual_corrections': {
            'home': home_info,
            'away': away_info
        }
    }
    
    return home_final, away_final, coordination_info


def calculate_coordinated_predictions(home_team_parameters, away_team_parameters, home_params, away_params, league_id):
    """
    Modified prediction function that applies coordinated corrections.
    This replaces the separate calculate_to_score calls in your main code.
    """
    
    # Calculate base lambdas (without corrections) for both teams
    home_lambda_base = calculate_base_lambda(
        home_team_parameters, 
        away_team_parameters, 
        home_params, 
        is_home=True
    )
    
    away_lambda_base = calculate_base_lambda(
        home_team_parameters, 
        away_team_parameters, 
        away_params, 
        is_home=False
    )
    
    print(f'Initial Lambdas: home={home_lambda_base:.3f}, away={away_lambda_base:.3f}')
    
    # Apply coordinated corrections
    home_lambda_final, away_lambda_final, coordination_info = apply_coordinated_correction(
        home_lambda_base, away_lambda_base, home_params, away_params, home_params, away_params
    )
    
    print(f"Coordinated Correction Applied: {json.dumps(coordination_info, default=decimal_default, indent=2)}")
    
    # Now generate final predictions using corrected lambdas
    # We need to create modified versions of calculate_to_score that accept pre-calculated lambdas
    home_score, home_goals, home_likelihood, home_probs = generate_final_predictions(
        home_lambda_final, home_params, is_home=True
    )
    
    away_score, away_goals, away_likelihood, away_probs = generate_final_predictions(
        away_lambda_final, away_params, is_home=False
    )
    
    return (home_score, home_goals, home_likelihood, home_probs, 
            away_score, away_goals, away_likelihood, away_probs, 
            coordination_info)


def generate_final_predictions(lambda_corrected, params, is_home=True):
    """
    Generate final predictions using pre-corrected lambda.
    This replaces the lambda calculation portion of calculate_to_score.
    """
    
    # Extract alpha parameters
    if is_home:
        alpha_nb = params['alpha_home']
        alpha_factor = params['alpha_home_factor']
    else:
        alpha_nb = params['alpha_away']  
        alpha_factor = params['alpha_away_factor']
    
    # Calculate effective alpha
    alpha_eff = alpha_nb if alpha_nb is not None else 0.3
    alpha_team = max(alpha_eff * alpha_factor, 0.05)
    
    # Apply ceiling (same as original)
    ceiling = 10.0 / (1 + alpha_team)
    lambda_final = min(lambda_corrected, ceiling)
    
    print(f'Lambda after ceiling: {lambda_final}')
    
    # Calculate probability to score at least 1 goal
    score = 1 - math.exp(-lambda_final)
    
    # Generate goal probabilities
    most_likely_goals, goal_probability, probabilities = calculate_goal_probabilities(lambda_final, alpha_team)
    
    return score, most_likely_goals, goal_probability, probabilities