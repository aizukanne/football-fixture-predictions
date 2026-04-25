"""
Best Bets Handler
Analyzes fixture predictions and generates betting recommendations.
"""
import json
import boto3
import os
from datetime import datetime
from decimal import Decimal

from ..data.database_client import update_fixture_best_bet

# ─────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────
THRESHOLD = 1.10            # Minimum odds for any recommendation
LIMIT = 4.5                 # Maximum odds for any recommendation
HIGH_PROB_THRESHOLD = 75
VERY_HIGH_PROB_THRESHOLD = 82
SIGNIFICANT_DIFF = 40       # Minimum probability gap (home vs away) for outright winner

# Performance differential thresholds — base and streak-adjusted
PERF_DIFF_BASE = 0.40
PERF_DIFF_ELEVATED_3 = 0.48    # Required when winner on 3-game winless streak
PERF_DIFF_ELEVATED_4 = 0.55    # Required when winner on 4-game winless streak
WINLESS_STREAK_EXCLUDE = 5     # Hard-exclude DC if streak reaches this

# Projected margin gate: minimum worst-case goal margin required
MIN_PROJECTED_MARGIN = 1


def lambda_handler(event, context):
    """
    Process fixture predictions and generate best bet recommendations.

    Triggered by SQS messages from the prediction handler containing
    completed fixture predictions.
    """
    print(f"Events: {json.dumps(event)}")

    # Loop through all records (each record corresponds to a single SQS message)
    for record in event['Records']:
        try:
            # Parse the 'body' field from the SQS message
            fixture = json.loads(record['body'])
            print(f'Processing fixture: {json.dumps(fixture, default=decimal_default)}')

            # Process each fixture using the prediction-based function
            recommendations = get_recommendations_from_predictions(fixture)

            if recommendations:
                fixture_id = recommendations[0]['fixture_id']
                # Remove fixture_id from each recommendation dict
                recommendations = [{k: v for k, v in d.items() if k != 'fixture_id'} for d in recommendations]
                fixture_bets = convert_floats_to_decimal(recommendations)
                print(f'Best Bet: {fixture_bets}')
                update_fixture_best_bet(fixture_id, fixture_bets)
        except Exception as e:
            print(f"Error processing record: {e}")
            continue

    return {
        'statusCode': 200,
        'body': json.dumps('Processing complete')
    }


def get_predictions_based_odds(fixture_data):
    """
    Extract odds from the predictions object in the fixture data.
    This replaces the external API call to get_fixture_odds.

    Parameters:
    - fixture_data (dict): A dictionary containing fixture data with predictions object

    Returns:
    - dict: A dictionary containing odds data
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

    # Goals Over/Under odds
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
    btts_no_prob = min(1 / btts_no_odds, 0.95)

    # Calculate clean sheet probabilities
    home_win_weight = home_win_prob / max(home_win_prob + draw_prob/2, 0.1)
    away_win_weight = away_win_prob / max(away_win_prob + draw_prob/2, 0.1)

    home_cs_prob = btts_no_prob * home_win_weight
    away_cs_prob = btts_no_prob * away_win_weight

    # Safety checks and normalization
    home_cs_prob = min(max(home_cs_prob, 0.05), 0.9)
    away_cs_prob = min(max(away_cs_prob, 0.05), 0.9)

    # Convert probabilities to odds with bookmaker margin
    margin_factor = 0.9
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
    match_outcome = predictions.get("odds", {}).get("match_outcome", {})
    home_win_odds = float(match_outcome.get("home_win", 5.0))
    draw_odds = float(match_outcome.get("draw", 3.5))
    away_win_odds = float(match_outcome.get("away_win", 5.0))

    # Convert to probabilities
    p_home = min(1 / home_win_odds * 1.1, 0.9)
    p_draw = min(1 / draw_odds * 1.1, 0.7)
    p_away = min(1 / away_win_odds * 1.1, 0.9)

    # Calculate combined probabilities for double chance
    p_home_draw = min(p_home + p_draw, 0.95)
    p_draw_away = min(p_draw + p_away, 0.95)
    p_home_away = min(p_home + p_away, 0.95)

    # Convert back to odds with margin
    dc_margin = 0.92
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
    Priority: Match Winner → Double Chance → Over 1.5 Goals.

    Gap fixes applied:
      Gap 1: check_qualified_win_consistency — venue dominance (GD≥2) from past_fixtures
      Gap 2: get_adjusted_perf_threshold — dynamic threshold + hard exclude at streak ≥ 5
      Gap 3: is_table_proximity_risk — applied globally before all priorities
      Gap 4: check_projected_margin — ±1 band on top_scores applied to Winner AND DC

    Diagnostic logging: every silent fall-through appends a tagged reason
    string to skip_log; the consolidated NO_BET line at the end gives one
    place to read why a fixture didn't produce a recommendation.
    """
    recommendations = []
    skip_log = []
    fixture_id = fixture_data["fixture_id"]
    predictions = fixture_data.get("predictions", {})

    if not predictions:
        print(f'[{fixture_id}] NO_BET gate=NO_PREDICTIONS reason=fixture_data has no predictions block')
        return recommendations

    odds = get_predictions_based_odds(fixture_data)

    # ── Probabilities ──────────────────────────────────────────────────────────
    match_outcome = predictions.get("match_outcome", {})
    home_win_prob = match_outcome.get("home_win", 0)
    draw_prob = match_outcome.get("draw", 0)
    away_win_prob = match_outcome.get("away_win", 0)

    goals_data = predictions.get("goals", {})
    print(f'Goals Data: {json.dumps(goals_data, default=decimal_default)}')
    over_goals = goals_data.get("over", {})
    btts = goals_data.get("btts", {})
    btts_yes_prob = btts.get("yes", 0)

    top_scores = predictions.get("top_scores", [])
    most_likely_score = predictions.get("most_likely_score", {}).get("score", "0-0")
    home_wins, draws, away_wins = analyze_score_predictions(top_scores, most_likely_score)

    try:
        score_parts = most_likely_score.split("-")
        home_predicted_goals = int(score_parts[0].strip())
        away_predicted_goals = int(score_parts[1].strip())
        total_predicted_goals = home_predicted_goals + away_predicted_goals
    except (ValueError, IndexError):
        home_predicted_goals = 0
        away_predicted_goals = 0
        total_predicted_goals = 0

    # One consolidated input line per fixture so we can read what V1 produced
    # without correlating with the per-fixture predictions log.
    home_perf_input = fixture_data.get("home", {}).get("home_performance", 0)
    away_perf_input = fixture_data.get("away", {}).get("away_performance", 0)
    print(
        f'[{fixture_id}] inputs: '
        f'mw=H{home_win_prob}/D{draw_prob}/A{away_win_prob} '
        f'btts={btts_yes_prob} '
        f'o1.5={over_goals.get("1.5", 0)} o2.5={over_goals.get("2.5", 0)} '
        f'mls={most_likely_score} pred_goals_total={total_predicted_goals} '
        f'top_scores={len(top_scores)}(H={home_wins},D={draws},A={away_wins}) '
        f'perf=H{home_perf_input}/A{away_perf_input}'
    )

    # ── Gap 3: Table proximity — blocks ALL bet types if triggered ─────────────
    if is_table_proximity_risk(fixture_data):
        print(f'[{fixture_id}] NO_BET gate=TABLE_PROXIMITY reason=points-gap within catchable range late-season')
        return recommendations

    # ── PRIORITY 1: Match Winner ───────────────────────────────────────────────
    mw_home_diff = home_win_prob - away_win_prob
    if home_win_prob > VERY_HIGH_PROB_THRESHOLD and mw_home_diff > SIGNIFICANT_DIFF:
        if home_wins == len(top_scores) and home_wins > 0:
            margin_ok, min_margin = check_projected_margin(top_scores, is_home_winner=True)
            if not margin_ok:
                print(f'[{fixture_id}] Home win SKIPPED — projected margin insufficient (min={min_margin})')
                skip_log.append(f'MW_HOME(margin={min_margin}<{MIN_PROJECTED_MARGIN})')
            else:
                qualifying = False
                for option in odds.get("Match Winner", []):
                    if option["value"] == "Home" and THRESHOLD <= float(option["odd"]) <= LIMIT:
                        qualifying = True
                        recommendations.append({
                            "fixture_id": fixture_id,
                            "recommendation": "Home Win",
                            "value": "Home",
                            "odds": float(option["odd"]),
                            "confidence": "High",
                            "reasoning": (
                                f"Strong home win probability ({home_win_prob}%) confirmed by all "
                                f"top score predictions. Worst-case projected margin: {min_margin} goals."
                            )
                        })
                        return recommendations
                if not qualifying:
                    home_odd = next(
                        (o["odd"] for o in odds.get("Match Winner", []) if o["value"] == "Home"),
                        None
                    )
                    skip_log.append(
                        f'MW_HOME(no_odds_in[{THRESHOLD},{LIMIT}],home_odd={home_odd})'
                    )
        else:
            skip_log.append(
                f'MW_HOME(top_scores not unanimous home: '
                f'home_wins={home_wins}/{len(top_scores)})'
            )
    else:
        skip_log.append(
            f'MW_HOME(prob={home_win_prob}<={VERY_HIGH_PROB_THRESHOLD} '
            f'or diff={mw_home_diff:.1f}<={SIGNIFICANT_DIFF})'
        )

    mw_away_diff = away_win_prob - home_win_prob
    if away_win_prob > VERY_HIGH_PROB_THRESHOLD and mw_away_diff > SIGNIFICANT_DIFF:
        if away_wins == len(top_scores) and away_wins > 0:
            margin_ok, min_margin = check_projected_margin(top_scores, is_home_winner=False)
            if not margin_ok:
                print(f'[{fixture_id}] Away win SKIPPED — projected margin insufficient (min={min_margin})')
                skip_log.append(f'MW_AWAY(margin={min_margin}<{MIN_PROJECTED_MARGIN})')
            else:
                qualifying = False
                for option in odds.get("Match Winner", []):
                    if option["value"] == "Away" and THRESHOLD <= float(option["odd"]) <= LIMIT:
                        qualifying = True
                        recommendations.append({
                            "fixture_id": fixture_id,
                            "recommendation": "Away Win",
                            "value": "Away",
                            "odds": float(option["odd"]),
                            "confidence": "High",
                            "reasoning": (
                                f"Strong away win probability ({away_win_prob}%) confirmed by all "
                                f"top score predictions. Worst-case projected margin: {min_margin} goals."
                            )
                        })
                        return recommendations
                if not qualifying:
                    away_odd = next(
                        (o["odd"] for o in odds.get("Match Winner", []) if o["value"] == "Away"),
                        None
                    )
                    skip_log.append(
                        f'MW_AWAY(no_odds_in[{THRESHOLD},{LIMIT}],away_odd={away_odd})'
                    )
        else:
            skip_log.append(
                f'MW_AWAY(top_scores not unanimous away: '
                f'away_wins={away_wins}/{len(top_scores)})'
            )
    else:
        skip_log.append(
            f'MW_AWAY(prob={away_win_prob}<={VERY_HIGH_PROB_THRESHOLD} '
            f'or diff={mw_away_diff:.1f}<={SIGNIFICANT_DIFF})'
        )

    # ── PRIORITY 2: Double Chance ──────────────────────────────────────────────
    home_perf = fixture_data.get("home", {}).get("home_performance", 0)
    away_perf = fixture_data.get("away", {}).get("away_performance", 0)
    perf_diff = home_perf - away_perf
    perf_diff_mag = abs(perf_diff)
    is_home_favourite = perf_diff > 0

    # Gap 2: dynamic threshold — float('inf') hard-excludes streak ≥ WINLESS_STREAK_EXCLUDE
    perf_diff_threshold = get_adjusted_perf_threshold(fixture_data, is_home_favourite)

    if perf_diff_mag >= perf_diff_threshold:
        print(f'[{fixture_id}] Perf_Diff: {perf_diff_mag:.2f} (threshold: {perf_diff_threshold})')

        if perf_diff > 0 and away_wins == 0 and len(top_scores) > 0:
            # Gap 4: ±1 band margin check (consistent with Match Winner gate)
            margin_ok, min_margin = check_projected_margin(top_scores, is_home_winner=True)
            if not margin_ok:
                print(f'[{fixture_id}] DC Home/Draw SKIPPED — projected margin insufficient (min={min_margin})')
                skip_log.append(f'DC_HD(margin={min_margin}<{MIN_PROJECTED_MARGIN})')
            elif check_qualified_win_consistency(fixture_data, is_home_favourite=True):
                qualifying = False
                for option in odds.get("Double Chance", []):
                    if option["value"] == "Home/Draw" and THRESHOLD <= float(option["odd"]) <= LIMIT:
                        qualifying = True
                        recommendations.append({
                            "fixture_id": fixture_id,
                            "recommendation": "Double Chance",
                            "value": "Home/Draw",
                            "odds": float(option["odd"]),
                            "confidence": "High",
                            "reasoning": (
                                f"Home stronger (perf: {home_perf:.2f} vs {away_perf:.2f}), "
                                f"worst-case projected margin {min_margin} goals, "
                                f"venue dominance confirmed, no predicted away wins"
                            )
                        })
                        return recommendations
                if not qualifying:
                    hd_odd = next(
                        (o["odd"] for o in odds.get("Double Chance", []) if o["value"] == "Home/Draw"),
                        None
                    )
                    skip_log.append(
                        f'DC_HD(no_odds_in[{THRESHOLD},{LIMIT}],hd_odd={hd_odd})'
                    )
            else:
                skip_log.append('DC_HD(venue dominance check failed)')

        elif perf_diff < 0 and home_wins == 0 and len(top_scores) > 0:
            margin_ok, min_margin = check_projected_margin(top_scores, is_home_winner=False)
            if not margin_ok:
                print(f'[{fixture_id}] DC Draw/Away SKIPPED — projected margin insufficient (min={min_margin})')
                skip_log.append(f'DC_DA(margin={min_margin}<{MIN_PROJECTED_MARGIN})')
            elif check_qualified_win_consistency(fixture_data, is_home_favourite=False):
                qualifying = False
                for option in odds.get("Double Chance", []):
                    if option["value"] == "Draw/Away" and THRESHOLD <= float(option["odd"]) <= LIMIT:
                        qualifying = True
                        recommendations.append({
                            "fixture_id": fixture_id,
                            "recommendation": "Double Chance",
                            "value": "Draw/Away",
                            "odds": float(option["odd"]),
                            "confidence": "High",
                            "reasoning": (
                                f"Away stronger (perf: {away_perf:.2f} vs {home_perf:.2f}), "
                                f"worst-case projected margin {min_margin} goals, "
                                f"venue dominance confirmed, no predicted home wins"
                            )
                        })
                        return recommendations
                if not qualifying:
                    da_odd = next(
                        (o["odd"] for o in odds.get("Double Chance", []) if o["value"] == "Draw/Away"),
                        None
                    )
                    skip_log.append(
                        f'DC_DA(no_odds_in[{THRESHOLD},{LIMIT}],da_odd={da_odd})'
                    )
            else:
                skip_log.append('DC_DA(venue dominance check failed)')
        else:
            # perf_diff_mag passed threshold but the side that's "favoured" doesn't
            # have unanimous support from top_scores (e.g. perf_diff>0 but away_wins>0).
            skip_log.append(
                f'DC(top_scores contradict favourite: '
                f'perf_diff={perf_diff:.2f}, home_wins={home_wins}, away_wins={away_wins})'
            )
    else:
        thr_str = (
            f'inf(streak>={WINLESS_STREAK_EXCLUDE})'
            if perf_diff_threshold == float('inf')
            else f'{perf_diff_threshold:.2f}'
        )
        skip_log.append(
            f'DC(perf_diff_mag={perf_diff_mag:.2f}<threshold={thr_str})'
        )

    # PRIORITY 3: Over 1.5 Goals
    over_1_5_prob = over_goals.get("1.5", 0)
    over_2_5_prob = over_goals.get("2.5", 0)

    over_1_5_recommended = False
    recommendation_reason = ""

    if over_2_5_prob > HIGH_PROB_THRESHOLD and btts_yes_prob > HIGH_PROB_THRESHOLD and total_predicted_goals > 3:
        over_1_5_recommended = True
        recommendation_reason = f"High over 2.5 goals ({over_2_5_prob}%) and BTTS ({btts_yes_prob}%) with {total_predicted_goals} predicted goals"

    elif btts_yes_prob > HIGH_PROB_THRESHOLD and home_predicted_goals >= 1 and away_predicted_goals >= 1 and total_predicted_goals > 2:
        over_1_5_recommended = True
        recommendation_reason = f"High BTTS probability ({btts_yes_prob}%) with {total_predicted_goals} predicted goals"

    elif over_1_5_prob > VERY_HIGH_PROB_THRESHOLD and total_predicted_goals > 2:
        over_1_5_recommended = True
        recommendation_reason = f"Very high over 1.5 goals probability ({over_1_5_prob}%) with {total_predicted_goals} predicted goals"

    if over_1_5_recommended:
        over_1_5_odds_value = odds.get("Goals Over/Under 1.5", "0")
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
        else:
            skip_log.append(
                f'O1.5(eligible but odds={over_1_5_odds} outside [{THRESHOLD},{LIMIT}])'
            )
    else:
        skip_log.append(
            f'O1.5(none of 3 conditions: o2.5={over_2_5_prob}+btts={btts_yes_prob}+pred={total_predicted_goals}>3 '
            f'| btts={btts_yes_prob}+H>=1+A>=1+pred>2 '
            f'| o1.5={over_1_5_prob}+pred>2)'
        )

    # No recommendations from any priority — emit a single consolidated NO_BET
    # line so each fixture's full rejection trail is visible in one log entry.
    print(f'[{fixture_id}] NO_BET reasons: {" | ".join(skip_log) if skip_log else "(none recorded)"}')
    return recommendations


def check_qualified_win_consistency(fixture_data, is_home_favourite):
    """
    Check if the projected winner has demonstrated recent dominance at their venue.
    Returns True if they have >= 2 qualified wins (GD >= 2) in their last venue-specific
    matches from past_fixtures.
    """
    team_key = "home" if is_home_favourite else "away"
    team = fixture_data.get(team_key, {})
    team_name = team.get("team_name", "")
    past_fixtures = team.get("past_fixtures", [])

    venue_fixtures = []
    for f in past_fixtures:
        teams = f.get("teams", {})
        scores = f.get("scores", {})
        if is_home_favourite:
            if teams.get("home") == team_name:
                gf = int(scores.get("home") or 0)
                ga = int(scores.get("away") or 0)
                venue_fixtures.append((gf, ga))
        else:
            if teams.get("away") == team_name:
                gf = int(scores.get("away") or 0)
                ga = int(scores.get("home") or 0)
                venue_fixtures.append((gf, ga))

    if len(venue_fixtures) < 3:
        return False  # Insufficient venue-specific data

    qualified_wins = sum(1 for gf, ga in venue_fixtures[:5] if gf - ga >= 2)
    return qualified_wins >= 2


def check_projected_margin(top_scores, is_home_winner):
    """
    Apply a ±1 goal uncertainty band to every top predicted score and check
    whether the projected winner still leads in the worst-case scenario.

    For each score, worst case = winner scores -1, loser scores +1.
    Returns True only if min_margin >= MIN_PROJECTED_MARGIN across all scores.

    Args:
        top_scores:    list of {"score": "H-A", ...} dicts from predictions.top_scores
        is_home_winner: True if home team is the projected winner

    Returns:
        (passes: bool, min_margin: int)
    """
    if not top_scores:
        return False, 0

    margins = []
    for score_obj in top_scores:
        score = score_obj.get("score", "0-0")
        try:
            home_g, away_g = map(int, score.split("-"))
        except (ValueError, IndexError):
            continue
        if is_home_winner:
            margin = (home_g - 1) - (away_g + 1)   # worst case: home -1, away +1
        else:
            margin = (away_g - 1) - (home_g + 1)   # worst case: away -1, home +1
        margins.append(margin)

    if not margins:
        return False, 0

    min_margin = min(margins)
    return min_margin >= MIN_PROJECTED_MARGIN, min_margin


def get_adjusted_perf_threshold(fixture_data, is_home_favourite):
    """
    Return adjusted performance differential threshold based on the projected winner's
    recent form across all competitions.

    Thresholds:
        streak 0-2  → 0.40 (standard)
        streak 3    → 0.48 (elevated)
        streak 4    → 0.55 (elevated)
        streak 5+   → float('inf') (hard exclude — too much uncertainty)

    Uses past_fixtures (the actual stored field) with teams/scores sub-objects.
    """
    team_key = "home" if is_home_favourite else "away"
    team = fixture_data.get(team_key, {})
    team_name = team.get("team_name", "")
    past_fixtures = team.get("past_fixtures", [])

    consecutive_without_win = 0
    for f in past_fixtures[:5]:
        teams = f.get("teams", {})
        scores = f.get("scores", {})
        if teams.get("home") == team_name:
            gf = int(scores.get("home") or 0)
            ga = int(scores.get("away") or 0)
        else:
            gf = int(scores.get("away") or 0)
            ga = int(scores.get("home") or 0)
        if gf > ga:
            break
        consecutive_without_win += 1

    if consecutive_without_win >= WINLESS_STREAK_EXCLUDE:
        return float('inf')   # Hard exclude — streak too long
    elif consecutive_without_win >= 4:
        return PERF_DIFF_ELEVATED_4
    elif consecutive_without_win >= 3:
        return PERF_DIFF_ELEVATED_3
    else:
        return PERF_DIFF_BASE


_TYPICAL_SEASON_GAMES = 34  # Conservative estimate covering most European league formats


def is_table_proximity_risk(fixture_data):
    """
    Returns True if this is a proximity pressure match where the points gap between
    the two teams is within catching distance (gap_ratio < 0.5).
    Computes league points from stored wins/draws and estimates remaining games.
    """
    home = fixture_data.get("home", {})
    away = fixture_data.get("away", {})

    home_total_wins = (home.get("home_wins") or 0) + (home.get("away_wins") or 0)
    home_total_draws = (home.get("home_draws") or 0) + (home.get("away_draws") or 0)
    away_total_wins = (away.get("home_wins") or 0) + (away.get("away_wins") or 0)
    away_total_draws = (away.get("home_draws") or 0) + (away.get("away_draws") or 0)

    home_points = home_total_wins * 3 + home_total_draws
    away_points = away_total_wins * 3 + away_total_draws

    home_games = home.get("total_games_played") or 0
    away_games = away.get("total_games_played") or 0

    if home_games == 0 or away_games == 0:
        return False  # Can't assess, don't block

    avg_games_played = (home_games + away_games) / 2
    remaining_games = max(0, _TYPICAL_SEASON_GAMES - avg_games_played)

    if remaining_games == 0:
        return True  # Final-round fixture — maximum pressure, skip bet

    points_gap = abs(home_points - away_points)
    catchable_points = remaining_games * 3
    gap_ratio = points_gap / catchable_points
    return gap_ratio < 0.5



def analyze_score_predictions(top_scores, most_likely_score):
    """
    Analyzes the top scores and most likely score to determine outcome distribution.

    Parameters:
    - top_scores (list): List of dictionaries with predicted scores and probabilities
    - most_likely_score (str): The most likely score prediction

    Returns:
    - tuple: (home_wins, draws, away_wins) counts
    """
    home_wins = 0
    draws = 0
    away_wins = 0

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
    """Convert floats to Decimal for DynamoDB storage."""
    if isinstance(data, list):
        return [convert_floats_to_decimal(item) for item in data]
    elif isinstance(data, dict):
        return {k: convert_floats_to_decimal(v) for k, v in data.items()}
    elif isinstance(data, float):
        return Decimal(str(data))
    else:
        return data


def decimal_default(obj):
    """JSON serializer for Decimal objects."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
