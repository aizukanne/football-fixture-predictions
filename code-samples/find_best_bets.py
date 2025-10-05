import json
import boto3
import os
import requests
import time
import math

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

#Get API Keys
rapidapi_key = os.getenv('RAPIDAPI_KEY')

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('game_fixtures')  # Replace with your DynamoDB Table Name


def lambda_handler(event, context):
    print("Events:", json.dumps(event))
    
    # Loop through all records (each record corresponds to a single SQS message) 
    for record in event['Records']:
        # Parse the 'body' field from the SQS message, which contains your actual payload
        fixture = json.loads(record['body'])
        print(f'Fixtures: {json.dumps(fixture)}')
        
        # Process each fixture using the new prediction-based function
        recommendations = get_recommendations_from_predictions(fixture)
        
        if recommendations:
            fixture_id = recommendations[0]['fixture_id']
            recommendations = [{k: v for k, v in d.items() if k != 'fixture_id'} for d in recommendations]
            fixture_bets = convert_floats_to_decimal(recommendations)
            print(f'Best Bet: {fixture_bets}')
            add_best_bet_attribute(fixture_id, fixture_bets)
    
    return


def get_predictions_based_odds(fixture_data):
    """
    Extract odds from the predictions object in the fixture data.
    This replaces the external API call to get_fixture_odds.
    
    Parameters:
    - fixture_data (dict): A dictionary containing fixture data with predictions object
    
    Returns:
    - dict: A dictionary containing odds data in the same format as get_fixture_odds
    """
    predictions = fixture_data.get("predictions", {})
    result = {
        "Match Winner": [],
        "Goals Over/Under": [],
        "Clean Sheet - Home": [],
        "Clean Sheet - Away": [],
        "Double Chance": []
    }
    
    # Match Winner odds
    if "odds" in predictions and "match_outcome" in predictions["odds"]:
        match_outcome = predictions["odds"]["match_outcome"]
        result["Match Winner"] = [
            {"value": "Home", "odd": str(match_outcome.get("home_win", 0))},
            {"value": "Draw", "odd": str(match_outcome.get("draw", 0))},
            {"value": "Away", "odd": str(match_outcome.get("away_win", 0))}
        ]
    
    # Goals Over/Under odds - Fixed to handle both 1.5 and 2.5 properly
    if "odds" in predictions and "over_under" in predictions["odds"]:
        over_under = predictions["odds"]["over_under"]
        
        # Extract the Over 2.5 odds directly
        over_2_5_odds = over_under.get("over_2.5", 0)
        
        # Calculate proper Over 1.5 odds based on probability
        over_1_5_probability = predictions.get("goals", {}).get("over", {}).get("1.5", 0) / 100
        over_2_5_probability = predictions.get("goals", {}).get("over", {}).get("2.5", 0) / 100
        
        # Convert probability to fair odds with bookmaker margin
        if over_1_5_probability > 0:
            # Apply typical bookmaker margin of ~15%
            over_1_5_odds = max(1 / over_1_5_probability * 0.85, 1.01)
        else:
            over_1_5_odds = 1.3  # Default fallback
        
        # Ensure Over 1.5 odds are lower than Over 2.5 odds
        if float(over_2_5_odds) > 0:
            # Over 1.5 should be lower odds than Over 2.5 (higher probability)
            # Typical difference is about 15-25%
            over_1_5_odds = min(over_1_5_odds, float(over_2_5_odds) * 0.85)
        
        # Add both odds types separately
        result["Goals Over/Under 1.5"] = str(round(over_1_5_odds, 2))
        result["Goals Over/Under 2.5"] = str(over_2_5_odds)
    
    # BTTS odds
    if "odds" in predictions and "btts" in predictions["odds"]:
        btts_odds = predictions["odds"]["btts"]
        result["BTTS"] = [
            {"value": "Yes", "odd": str(btts_odds.get("yes", 0))},
            {"value": "No", "odd": str(btts_odds.get("no", 0))}
        ]
    else:
        btts_odds = {"yes": 1.6, "no": 2.67}  # Default values
    
    # Calculate implied probabilities for clean sheets based on BTTS
    btts_yes_odds = float(btts_odds.get("yes", 1.6))
    btts_no_odds = float(btts_odds.get("no", 2.67))
    
    # Get match outcome probabilities
    home_win_prob = predictions.get("match_outcome", {}).get("home_win", 0) / 100
    away_win_prob = predictions.get("match_outcome", {}).get("away_win", 0) / 100
    draw_prob = predictions.get("match_outcome", {}).get("draw", 0) / 100
    
    # Calculate BTTS No probability from odds
    btts_no_prob = min(1 / btts_no_odds, 0.95)  # Cap at 95% to avoid division by zero issues
    
    # Calculate clean sheet probabilities
    # A team keeps a clean sheet when they don't concede, which is more likely when they win
    # and BTTS is No. We weight by the probability of winning vs not losing.
    home_win_weight = home_win_prob / max(home_win_prob + draw_prob/2, 0.1)
    away_win_weight = away_win_prob / max(away_win_prob + draw_prob/2, 0.1)
    
    home_cs_prob = btts_no_prob * home_win_weight
    away_cs_prob = btts_no_prob * away_win_weight
    
    # Safety checks and normalization
    home_cs_prob = min(max(home_cs_prob, 0.05), 0.9)
    away_cs_prob = min(max(away_cs_prob, 0.05), 0.9)
    
    # Convert probabilities to odds (1/probability) with bookmaker margin
    margin_factor = 0.9  # Typical 10% margin
    home_cs_yes_odds = round(1 / (home_cs_prob * margin_factor), 2)
    home_cs_no_odds = round(1 / ((1 - home_cs_prob) * margin_factor), 2)
    away_cs_yes_odds = round(1 / (away_cs_prob * margin_factor), 2)
    away_cs_no_odds = round(1 / ((1 - away_cs_prob) * margin_factor), 2)
    
    # Add Clean Sheet odds
    result["Clean Sheet - Home"] = [
        {"value": "Yes", "odd": str(home_cs_yes_odds)},
        {"value": "No", "odd": str(home_cs_no_odds)}
    ]
    result["Clean Sheet - Away"] = [
        {"value": "Yes", "odd": str(away_cs_yes_odds)},
        {"value": "No", "odd": str(away_cs_no_odds)}
    ]
    
    # Calculate Double Chance odds
    home_win_odds = float(match_outcome.get("home_win", 5.0))
    draw_odds = float(match_outcome.get("draw", 3.5))
    away_win_odds = float(match_outcome.get("away_win", 5.0))
    
    # Convert to probabilities (with adjustment for bookmaker margin)
    p_home = min(1 / home_win_odds * 1.1, 0.9)
    p_draw = min(1 / draw_odds * 1.1, 0.7)
    p_away = min(1 / away_win_odds * 1.1, 0.9)
    
    # Calculate combined probabilities for double chance
    p_home_draw = min(p_home + p_draw, 0.95)
    p_draw_away = min(p_draw + p_away, 0.95)
    p_home_away = min(p_home + p_away, 0.95)
    
    # Convert back to odds with margin
    dc_margin = 0.92  # 8% margin
    home_draw_odds = round(1 / (p_home_draw * dc_margin), 2)
    draw_away_odds = round(1 / (p_draw_away * dc_margin), 2)
    home_away_odds = round(1 / (p_home_away * dc_margin), 2)
    
    # Ensure all odds are within reasonable bounds
    home_draw_odds = max(min(home_draw_odds, 9.99), 1.01)
    draw_away_odds = max(min(draw_away_odds, 9.99), 1.01)
    home_away_odds = max(min(home_away_odds, 9.99), 1.01)
    
    result["Double Chance"] = [
        {"value": "Home/Draw", "odd": str(home_draw_odds)},
        {"value": "Draw/Away", "odd": str(draw_away_odds)},
        {"value": "Home/Away", "odd": str(home_away_odds)}
    ]
    
    return result


def get_recommendations_from_predictions(fixture_data):
    """
    Generate betting recommendations based on the predictions in the fixture data.
    Prioritizes match winner, then double chance, then over 1.5 goals.
    
    Parameters:
    - fixture_data (dict): A dictionary containing fixture data including predictions
    
    Returns:
    - list: List of recommendations with fixture ID, recommendation type, value, and associated odds.
    """
    # Configuration thresholds
    THRESHOLD = 1.10             # Minimum acceptable odds
    LIMIT = 4.5                  # Maximum acceptable odds
    HIGH_PROB_THRESHOLD = 75     # High probability threshold (%)
    VERY_HIGH_PROB_THRESHOLD = 82 # Very high probability threshold (%)
    SIGNIFICANT_DIFF = 40        # Significant difference in outcome probabilities (%)
    
    recommendations = []
    fixture_id = fixture_data["fixture_id"]
    predictions = fixture_data.get("predictions", {})
    
    # If predictions data is missing, fall back to the original function
    if not predictions:
        return get_recommendations(fixture_data)
    
    # Extract odds data in the same format as expected by the original function
    odds = get_predictions_based_odds(fixture_data)
    
    # Extract match outcome probabilities
    match_outcome = predictions.get("match_outcome", {})
    home_win_prob = match_outcome.get("home_win", 0)
    draw_prob = match_outcome.get("draw", 0)
    away_win_prob = match_outcome.get("away_win", 0)
    
    # Extract goals data
    goals_data = predictions.get("goals", {})
    print(f'Goals Data: {json.dumps(goals_data)}')    
    over_goals = goals_data.get("over", {})
    btts = goals_data.get("btts", {})
    btts_yes_prob = btts.get("yes", 0)
    
    # Extract top scores data
    top_scores = predictions.get("top_scores", [])
    most_likely_score = predictions.get("most_likely_score", {}).get("score", "0-0")
    
    # Analyze the predicted scores
    home_wins, draws, away_wins = analyze_score_predictions(top_scores, most_likely_score)
    
    # Extract predicted goals from most_likely_score
    try:
        # Parse the score string (e.g., "2-1") into home and away goals
        score_parts = most_likely_score.split("-")
        home_predicted_goals = int(score_parts[0].strip())
        away_predicted_goals = int(score_parts[1].strip())
        total_predicted_goals = home_predicted_goals + away_predicted_goals
    except (ValueError, IndexError):
        # If there's an issue parsing the score, default to 0
        home_predicted_goals = 0
        away_predicted_goals = 0
        total_predicted_goals = 0
    
    # Expected goals
    expected_goals = predictions.get("expected_goals", {})
    home_xg = expected_goals.get("home", 0)
    away_xg = expected_goals.get("away", 0)
    xg_diff = home_xg - away_xg
    
    # --- PRIORITY 1: Identify the team that will win (Match Winner) ---
    
    # Strong Home Win prediction
    if home_win_prob > VERY_HIGH_PROB_THRESHOLD and home_win_prob - away_win_prob > SIGNIFICANT_DIFF:
        # Additional check: ALL top scores must predict a home win
        if home_wins == len(top_scores) and home_wins > 0:
            for option in odds.get("Match Winner", []):
                if option["value"] == "Home" and THRESHOLD <= float(option["odd"]) <= LIMIT:
                    recommendations.append({
                        "fixture_id": fixture_id,
                        "recommendation": "Home Win",
                        "value": "Home",
                        "odds": float(option["odd"]),
                        "confidence": "High",
                        "reasoning": f"Strong home win probability ({home_win_prob}%) confirmed by all top score predictions"
                    })
                    return recommendations
    
    # Strong Away Win prediction
    if away_win_prob > VERY_HIGH_PROB_THRESHOLD and away_win_prob - home_win_prob > SIGNIFICANT_DIFF:
        # Additional check: ALL top scores must predict an away win
        if away_wins == len(top_scores) and away_wins > 0:
            for option in odds.get("Match Winner", []):
                if option["value"] == "Away" and THRESHOLD <= float(option["odd"]) <= LIMIT:
                    recommendations.append({
                        "fixture_id": fixture_id,
                        "recommendation": "Away Win",
                        "value": "Away",
                        "odds": float(option["odd"]),
                        "confidence": "High",
                        "reasoning": f"Strong away win probability ({away_win_prob}%) confirmed by all top score predictions"
                    })
                    return recommendations
    
    # --- PRIORITY 2: Identify the team that will not lose (Double Chance) ---
    home_perf = fixture_data.get("home", {}).get("home_performance", 0)
    away_perf = fixture_data.get("away", {}).get("away_performance", 0)
    perf_diff = home_perf - away_perf
    perf_diff_mag = abs(perf_diff)
    PERF_DIFF_SIGNIFICANT = 0.40  # 30% performance gap

    # Only consider any Double Chance if performance gap is large enough
    if perf_diff_mag >= PERF_DIFF_SIGNIFICANT:
        print(f'Perf_Diff: {perf_diff_mag}')
        # 2A) Pure performance‑based Double Chance
        if perf_diff > 0 and xg_diff >= 1.5:  # Home clearly stronger
            # Additional check: No top scores should predict an away win
            if away_wins == 0 and len(top_scores) > 0:
                for option in odds.get("Double Chance", []):
                    if option["value"] == "Home/Draw" and THRESHOLD <= float(option["odd"]) <= LIMIT:
                        recommendations.append({
                            "fixture_id": fixture_id,
                            "recommendation": "Double Chance",
                            "value": "Home/Draw",
                            "odds": float(option["odd"]),
                            "confidence": "High",
                            "reasoning": (
                                f"Home stronger (perf: {home_perf:.2f} vs {away_perf:.2f}), "
                                f"xG gap of {xg_diff:.1f}, and no predicted away wins in top scores"
                            )
                        })
                        return recommendations

        elif perf_diff < 0 and xg_diff <= -1.5:  # Away clearly stronger
            # Additional check: No top scores should predict a home win
            if home_wins == 0 and len(top_scores) > 0:
                for option in odds.get("Double Chance", []):
                    if option["value"] == "Draw/Away" and THRESHOLD <= float(option["odd"]) <= LIMIT:
                        recommendations.append({
                            "fixture_id": fixture_id,
                            "recommendation": "Double Chance",
                            "value": "Draw/Away",
                            "odds": float(option["odd"]),
                            "confidence": "High",
                            "reasoning": (
                                f"Away stronger (perf: {away_perf:.2f} vs {home_perf:.2f}), "
                                f"xG gap of {abs(xg_diff):.1f}, and no predicted home wins in top scores"
                            )
                        })
                        return recommendations

        # 2B) Performance‑based DC + Over/Under combo
        over_1_5_prob = over_goals.get("1.5", 0)
        under_4_5_prob = goals_data.get("under", {}).get("4.5", 0)
        if over_1_5_prob > 90 or under_4_5_prob > 65:
            # pick goal market
            if over_1_5_prob > 90:
                goal_market = "O 1.5"
                prob = over_1_5_prob
                odds_value = 100 * (1 / prob)
            else:
                goal_market = "U 4.5"
                prob = under_4_5_prob
                odds_value = 100 * (1 / prob)

            # Home/Draw + goal combo if home performance is stronger
            if perf_diff > 0 and away_wins == 0 and len(top_scores) > 0:
                for dc_option in odds.get("Double Chance", []):
                    if dc_option["value"] == "Home/Draw":
                        dc_prob = 1 / float(dc_option["odd"])
                        goal_prob = 1 / odds_value
                        combined = dc_prob * goal_prob
                        combined_odds = round(1 / combined, 2) if combined > 0 else 0

                        if THRESHOLD <= combined_odds <= LIMIT:
                            recommendations.append({
                                "fixture_id": fixture_id,
                                "recommendation": f"DC + {goal_market}",
                                "value":        f"Home/Draw & {goal_market}",
                                "odds":         combined_odds,
                                "confidence":   "High",
                                "reasoning":    (
                                    f"Home stronger (gap: {perf_diff_mag:.2f}), "
                                    f"{prob}% for {goal_market}, and no predicted away wins in top scores"
                                )
                            })
                            return recommendations

            # Draw/Away + goal combo if away performance is stronger
            elif perf_diff < 0 and home_wins == 0 and len(top_scores) > 0:
                for dc_option in odds.get("Double Chance", []):
                    if dc_option["value"] == "Draw/Away":
                        dc_prob = 1 / float(dc_option["odd"])
                        goal_prob = 1 / odds_value
                        combined = dc_prob * goal_prob
                        combined_odds = round(1 / combined, 2) if combined > 0 else 0

                        if THRESHOLD <= combined_odds <= LIMIT:
                            recommendations.append({
                                "fixture_id": fixture_id,
                                "recommendation": f"DC + {goal_market}",
                                "value":        f"Draw/Away & {goal_market}",
                                "odds":         combined_odds,
                                "confidence":   "High",
                                "reasoning":    (
                                    f"Away stronger (gap: {perf_diff_mag:.2f}), "
                                    f"{prob}% for {goal_market}, and no predicted home wins in top scores"
                                )
                            })
                            return recommendations

        # 2C) Fallback Double Chance based on win‑prob gaps
        if home_win_prob > HIGH_PROB_THRESHOLD and home_win_prob - away_win_prob > SIGNIFICANT_DIFF:
            # Verify no away wins in top scores
            if away_wins == 0 and len(top_scores) > 0:
                for option in odds.get("Double Chance", []):
                    if option["value"] == "Home/Draw" and THRESHOLD <= float(option["odd"]) <= LIMIT:
                        recommendations.append({
                            "fixture_id": fixture_id,
                            "recommendation": "Double Chance",
                            "value": "Home/Draw",
                            "odds": float(option["odd"]),
                            "confidence": "High",
                            "reasoning": f"Strong home win probability ({home_win_prob}%) with no predicted away wins in top scores"
                        })
                        return recommendations

        elif away_win_prob > HIGH_PROB_THRESHOLD and away_win_prob - home_win_prob > SIGNIFICANT_DIFF:
            # Verify no home wins in top scores
            if home_wins == 0 and len(top_scores) > 0:
                for option in odds.get("Double Chance", []):
                    if option["value"] == "Draw/Away" and THRESHOLD <= float(option["odd"]) <= LIMIT:
                        recommendations.append({
                            "fixture_id": fixture_id,
                            "recommendation": "Double Chance",
                            "value": "Draw/Away",
                            "odds": float(option["odd"]),
                            "confidence": "High",
                            "reasoning": f"Strong away win probability ({away_win_prob}%) with no predicted home wins in top scores"
                        })
                        return recommendations
    
    # --- PRIORITY 3: Combined goal-related recommendations (Over 1.5) ---
    
    # Combine conditions for over 1.5 goals recommendations
    over_1_5_prob = over_goals.get("1.5", 0)
    over_2_5_prob = over_goals.get("2.5", 0)
    
    # Check if ANY of the conditions for Over 1.5 are met
    over_1_5_recommended = False
    recommendation_reason = ""
    
    # Condition 1: Over 2.5 Goals is highly probable
    if over_2_5_prob > HIGH_PROB_THRESHOLD and btts_yes_prob > HIGH_PROB_THRESHOLD and total_predicted_goals > 3:
        over_1_5_recommended = True
        recommendation_reason = f"High probability for over 2.5 goals ({over_2_5_prob}%) and BTTS ({btts_yes_prob}%) with predicted score {most_likely_score} ({total_predicted_goals} goals)"
    
    # Condition 2: Both teams are likely to score
    elif btts_yes_prob > HIGH_PROB_THRESHOLD and home_predicted_goals >= 1 and away_predicted_goals >= 1 and total_predicted_goals > 2:
        over_1_5_recommended = True
        recommendation_reason = f"High probability for both teams to score ({btts_yes_prob}%), which implies at least 2 goals, with predicted score {most_likely_score} ({total_predicted_goals} goals)"
    
    # Condition 3: Very high probability for over 1.5 goals directly
    elif over_1_5_prob > VERY_HIGH_PROB_THRESHOLD and total_predicted_goals > 2:
        over_1_5_recommended = True
        recommendation_reason = f"Very high probability for over 1.5 goals ({over_1_5_prob}%) with predicted score {most_likely_score} ({total_predicted_goals} goals)"
    
    # If any condition is met, recommend Over 1.5 Goals
    if over_1_5_recommended:
        # Handle the "Goals Over/Under 1.5" format from your function
        over_1_5_odds_value = odds.get("Goals Over/Under 1.5", "0")
        # Convert from string to float (your function returns strings for odds)
        try:
            over_1_5_odds = float(over_1_5_odds_value)
        except (ValueError, TypeError):
            over_1_5_odds = 0
            
        if THRESHOLD <= over_1_5_odds <= LIMIT:
            recommendations.append({
                "fixture_id": fixture_id,
                "recommendation": "Over 1.5 Goals",
                "value": "Over 1.5",
                "odds": over_1_5_odds,
                "confidence": "High",
                "reasoning": recommendation_reason
            })
            return recommendations
    
    # If we reach here, we couldn't make any recommendation
    return recommendations


def add_best_bet_attribute(partition_key_value, new_value):
    try:
        # First, query the item to get the timestamp
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('fixture_id').eq(int(partition_key_value)),
            Limit=1
        )
        
        # Check if the item exists
        if not response['Items']:
            print(f"No item found with fixture_id: {partition_key_value}")
            return
        
        # Get the timestamp from the queried item
        timestamp = response['Items'][0]['timestamp']
        
        # Now update the item with both partition key and sort key
        update_response = table.update_item(
            Key={
                'fixture_id': int(partition_key_value),
                'timestamp': timestamp
            },
            UpdateExpression="SET best_bet = :val",
            ExpressionAttributeValues={
                ':val': new_value
            },
            ReturnValues="UPDATED_NEW"
        )
        
        print("Update successful:", update_response['Attributes'])
    
    except ClientError as e:
        print("Error:", e.response['Error']['Message'])
    except Exception as e:
        print("An error occurred:", str(e))


def analyze_score_predictions(top_scores, most_likely_score):
    """
    Analyzes the top scores and most likely score to determine outcome distribution.
    Returns counts of home wins, draws, and away wins.
    
    Parameters:
    - top_scores (list): List of dictionaries with predicted scores and probabilities
    - most_likely_score (str): The most likely score prediction
    
    Returns:
    - tuple: (home_wins, draws, away_wins) counts
    """
    home_wins = 0
    draws = 0
    away_wins = 0
    
    # First analyze the most likely score if it exists and is valid
    if most_likely_score and most_likely_score != "0-0":
        try:
            home_goals, away_goals = map(int, most_likely_score.split("-"))
            if home_goals > away_goals:
                home_wins += 1
            elif home_goals == away_goals:
                draws += 1
            else:
                away_wins += 1
        except (ValueError, IndexError):
            pass
    
    # Then analyze all scores in the top_scores list
    for score_obj in top_scores:
        score = score_obj.get("score", "0-0")
        try:
            home_goals, away_goals = map(int, score.split("-"))
            if home_goals > away_goals:
                home_wins += 1
            elif home_goals == away_goals:
                draws += 1
            else:
                away_wins += 1
        except (ValueError, IndexError):
            continue
    
    return home_wins, draws, away_wins


def convert_floats_to_decimal(data):
    if isinstance(data, list):
        return [convert_floats_to_decimal(item) for item in data]
    elif isinstance(data, dict):
        return {k: convert_floats_to_decimal(v) for k, v in data.items()}
    elif isinstance(data, float):
        return Decimal(str(data))
    else:
        return data
