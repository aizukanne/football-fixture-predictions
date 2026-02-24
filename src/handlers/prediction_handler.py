"""
Thin orchestration layer for the makeTeamRankings Lambda function.
Coordinates prediction workflow using modular components.
"""

import json
import boto3
from decimal import Decimal
from datetime import datetime

from ..prediction.prediction_engine import (
    calculate_coordinated_predictions,
    calculate_to_score,
    calculate_base_lambda,
    create_prediction_summary_dict
)
from ..data.api_client import (
    get_team_statistics,
    get_venue_id,
    fetch_team_match_data,
    get_next_fixture,
    get_last_five_games,
    get_head_to_head,
    get_injured_players,
    get_league_start_date,
    process_injuries,
    log_rate_limit_summary,
    reset_rate_limit_stats
)
from ..data.database_client import (
    get_team_params_from_db,
    get_league_params_from_db,
    put_fixture_record
)
from ..parameters.team_calculator import calculate_team_points
from ..utils.converters import convert_floats_to_decimal, decimal_default, decimal_to_float
from ..utils.constants import BEST_BETS_QUEUE_URL
from ..utils.manager_multipliers import apply_manager_adjustments, get_opponent_tier_from_standings
from ..infrastructure.version_manager import VersionManager


def lambda_handler(event, context):
    """
    Main Lambda handler for prediction processing.
    Thin orchestration layer that delegates to modular components.
    """
    print("Events:", json.dumps(event))

    # Reset rate limiting stats at start of each Lambda invocation
    reset_rate_limit_stats()

    # Loop through all records (each record corresponds to a single SQS message)
    for record in event['Records']:
        # Parse the 'body' field from the SQS message
        body = json.loads(record['body'])

        # Extract fixtures from payload
        fixtures = body.get('payload', [])

        # Process each fixture
        process_fixtures(fixtures)

    # Log rate limiting summary at end of execution
    log_rate_limit_summary()


def process_fixtures(fixtures):
    """
    Process fixtures with coordinated lambda correction to preserve outcome relationships.
    Drop-in replacement for the original process_fixtures function.
    """
    # Initialize version manager
    version_manager = VersionManager()
    current_version = version_manager.get_current_version()
    print(f"Processing fixtures with architecture version: {current_version}")
    
    for fixture in fixtures:
        try:
            fixture_id = fixture['fixture_id']
            home_team_id = fixture['home_id']
            away_team_id = fixture['away_id']
            league_id = fixture['league_id']
            season = fixture['season']
            date = fixture['date']
            print(f"DEBUG: date type={type(date)}, value={date}")
            
            # Convert string date to datetime object for temporal analysis
            try:
                if isinstance(date, str):
                    # Parse ISO format date string
                    date_dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    print(f"DEBUG: Converted date to datetime: {date_dt}")
                else:
                    date_dt = date
            except Exception as e:
                print(f"Warning: Could not convert date to datetime: {e}, using string")
                date_dt = date

            # Get league parameters with season
            league_params = get_league_params_from_db(league_id, season)
            if not league_params:
                print(f"No league parameters found for league {league_id}, season {season}, skipping fixture {fixture_id}")
                continue
                
            league_params = decimal_to_float(league_params)
            print(f'League Params: {json.dumps(league_params, default=decimal_default)}')

            # Get team parameters using composite key (fallback to league if not available)
            home_params_from_db = get_team_params_from_db(home_team_id, league_id)
            away_params_from_db = get_team_params_from_db(away_team_id, league_id)
            
            # Track parameter sources for metadata
            used_team_params_home = home_params_from_db is not None
            used_team_params_away = away_params_from_db is not None
            
            home_params = home_params_from_db or league_params
            away_params = away_params_from_db or league_params
            
            print(f'Home Before: {json.dumps(home_params, default=decimal_default)}')
            print(f'Away Before: {json.dumps(away_params, default=decimal_default)}')

            home_params = get_prediction_params(home_params, league_params)
            away_params = get_prediction_params(away_params, league_params)

            # Adjust league parameters with team specific standard deviation
            home_league_params = mod_league_params(home_params, league_params)
            home_league_params = decimal_to_float(home_league_params)
            
            away_league_params = mod_league_params(away_params, league_params)
            away_league_params = decimal_to_float(away_league_params)

            home_params = decimal_to_float(home_params)
            away_params = decimal_to_float(away_params)

            print(f'Home: {json.dumps(home_params, default=decimal_default)}')
            print(f'Away: {json.dumps(away_params, default=decimal_default)}')

            # Apply manager tactical multipliers (Phase 4.1 enhancement)
            try:
                # Determine opponent tiers (simplified - using middle tier as default)
                # In production, this would use actual league standings
                home_opponent_tier = 'middle'  # Away team tier from home's perspective
                away_opponent_tier = 'middle'  # Home team tier from away's perspective

                print("=== APPLYING MANAGER TACTICAL MULTIPLIERS ===")
                home_params, away_params = apply_manager_adjustments(
                    home_params, away_params, home_opponent_tier, away_opponent_tier
                )

                home_multiplier = home_params.get('manager_multiplier_applied', 1.0)
                away_multiplier = away_params.get('manager_multiplier_applied', 1.0)
                print(f"Manager multipliers applied - Home: {home_multiplier}, Away: {away_multiplier}")

            except Exception as e:
                print(f"Warning: Could not apply manager multipliers: {e}")
                # Continue without manager adjustments if there's an error

            # Get venue information
            try:
                venue_info = get_venue_id(home_team_id, league_id, season)
                print(f"DEBUG: venue_info type={type(venue_info)}, value={venue_info}")

                # Extract integer venue_id for prediction calculations
                if isinstance(venue_info, dict):
                    venue_id_for_prediction = venue_info.get('venue_id')
                    print(f"DEBUG: Extracted venue_id={venue_id_for_prediction} from dict for predictions")
                else:
                    venue_id_for_prediction = venue_info

            except Exception as e:
                print(f"Warning: Could not get venue ID for fixture {fixture_id}: {e}")
                venue_info = None
                venue_id_for_prediction = None

            # =================================================================
            # FETCH MATCH DATA - TWO APPROACHES FOR 2x2 PREDICTION MATRIX
            # =================================================================

            # Approach 1: Total stats (all matches) - for primary & alternate predictions
            # Uses home_adv multiplier to account for venue effect
            home_team_parameters_total, home_match_details_total = fetch_team_match_data(
                league_id, season, home_team_id,
                get_league_start_date(league_id),
                venue=None  # All matches
            )
            away_team_parameters_total, away_match_details_total = fetch_team_match_data(
                league_id, season, away_team_id,
                get_league_start_date(league_id),
                venue=None  # All matches
            )

            # Approach 2: Venue-specific stats - for venue_predictions
            # Home team uses only home matches, away team uses only away matches
            # No home_adv multiplier needed (venue effect already in data)
            home_team_parameters_venue, home_match_details_venue = fetch_team_match_data(
                league_id, season, home_team_id,
                get_league_start_date(league_id),
                venue='home'
            )
            away_team_parameters_venue, away_match_details_venue = fetch_team_match_data(
                league_id, season, away_team_id,
                get_league_start_date(league_id),
                venue='away'
            )

            # Check if we have data for at least one approach
            has_total_data = (home_team_parameters_total is not None and
                              away_team_parameters_total is not None)
            has_venue_data = (home_team_parameters_venue is not None and
                              away_team_parameters_venue is not None)

            if not has_total_data and not has_venue_data:
                print(f"Skipping fixture {fixture_id}: Missing team match data for both approaches")
                continue

            # Use total data as primary for backward compatibility
            home_team_parameters = home_team_parameters_total or home_team_parameters_venue
            away_team_parameters = away_team_parameters_total or away_team_parameters_venue
            home_match_details = home_match_details_total or home_match_details_venue
            away_match_details = away_match_details_total or away_match_details_venue

            # Calculate team points/stats
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
                
                print(f"DEBUG: Calling league prediction with venue_id={venue_id_for_prediction}, prediction_date type={type(date_dt)}")
                (home_score_league, home_goals_league, hg_likelihood_league, home_probs_league,
                 away_score_league, away_goals_league, ag_likelihood_league, away_probs_league,
                 league_coordination_info) = calculate_coordinated_predictions(
                    home_team_parameters, away_team_parameters, home_league_params, away_league_params, league_id,
                    season=season,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    venue_id=venue_id_for_prediction,
                    prediction_date=date_dt
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
                
                print(f"DEBUG: Calling team prediction with venue_id={venue_id_for_prediction}, prediction_date type={type(date_dt)}")
                (home_score_team, home_goals_team, hg_likelihood_team, home_probs_team,
                 away_score_team, away_goals_team, ag_likelihood_team, away_probs_team,
                 team_coordination_info) = calculate_coordinated_predictions(
                    home_team_parameters, away_team_parameters, home_params, away_params, league_id,
                    season=season,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    venue_id=venue_id_for_prediction,
                    prediction_date=date_dt
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
            # VENUE-SPECIFIC PREDICTIONS (skip_home_adv=True)
            # Uses venue-filtered match data, no home_adv multiplier
            # =================================================================
            venue_prediction_summary = None
            venue_prediction_summary_alt = None
            venue_coordination_info = {"venue_predictions_available": False}

            if has_venue_data:
                # VENUE PREDICTIONS (League Parameters + Venue-Specific Data)
                try:
                    print("=== CALCULATING VENUE PREDICTIONS (LEAGUE PARAMS, NO HOME_ADV) ===")

                    (home_score_venue, home_goals_venue, hg_likelihood_venue, home_probs_venue,
                     away_score_venue, away_goals_venue, ag_likelihood_venue, away_probs_venue,
                     venue_league_coordination_info) = calculate_coordinated_predictions(
                        home_team_parameters_venue, away_team_parameters_venue,
                        home_league_params, away_league_params, league_id,
                        season=season,
                        home_team_id=home_team_id,
                        away_team_id=away_team_id,
                        venue_id=venue_id_for_prediction,
                        prediction_date=date_dt,
                        skip_home_adv=True  # Venue effect already in data
                    )

                    venue_prediction_summary = create_prediction_summary_dict(home_probs_venue, away_probs_venue)

                    home_team_stats['probability_to_score_venue'] = Decimal(str(home_score_venue))
                    away_team_stats['probability_to_score_venue'] = Decimal(str(away_score_venue))
                    home_team_stats['predicted_goals_venue'] = home_goals_venue
                    away_team_stats['predicted_goals_venue'] = away_goals_venue
                    home_team_stats['likelihood_venue'] = Decimal(str(hg_likelihood_venue))
                    away_team_stats['likelihood_venue'] = Decimal(str(ag_likelihood_venue))

                except Exception as e:
                    print(f"Venue prediction (league params) failed for fixture {fixture_id}: {e}")
                    venue_prediction_summary = None

                # VENUE ALTERNATE PREDICTIONS (Team Parameters + Venue-Specific Data)
                try:
                    print("=== CALCULATING VENUE ALTERNATE PREDICTIONS (TEAM PARAMS, NO HOME_ADV) ===")

                    (home_score_venue_alt, home_goals_venue_alt, hg_likelihood_venue_alt, home_probs_venue_alt,
                     away_score_venue_alt, away_goals_venue_alt, ag_likelihood_venue_alt, away_probs_venue_alt,
                     venue_team_coordination_info) = calculate_coordinated_predictions(
                        home_team_parameters_venue, away_team_parameters_venue,
                        home_params, away_params, league_id,
                        season=season,
                        home_team_id=home_team_id,
                        away_team_id=away_team_id,
                        venue_id=venue_id_for_prediction,
                        prediction_date=date_dt,
                        skip_home_adv=True  # Venue effect already in data
                    )

                    venue_prediction_summary_alt = create_prediction_summary_dict(home_probs_venue_alt, away_probs_venue_alt)

                    home_team_stats['probability_to_score_venue_alt'] = Decimal(str(home_score_venue_alt))
                    away_team_stats['probability_to_score_venue_alt'] = Decimal(str(away_score_venue_alt))
                    home_team_stats['predicted_goals_venue_alt'] = home_goals_venue_alt
                    away_team_stats['predicted_goals_venue_alt'] = away_goals_venue_alt
                    home_team_stats['likelihood_venue_alt'] = Decimal(str(hg_likelihood_venue_alt))
                    away_team_stats['likelihood_venue_alt'] = Decimal(str(ag_likelihood_venue_alt))

                    venue_coordination_info = {
                        "venue_predictions_available": True,
                        "venue_league_coordination": convert_floats_to_decimal(venue_league_coordination_info) if venue_prediction_summary else None,
                        "venue_team_coordination": convert_floats_to_decimal(venue_team_coordination_info)
                    }

                except Exception as e:
                    print(f"Venue alternate prediction (team params) failed for fixture {fixture_id}: {e}")
                    venue_prediction_summary_alt = None
            else:
                print(f"Venue-specific predictions not available for fixture {fixture_id}: insufficient venue-filtered data")

            # Add additional fixture data
            home_team_stats['record_id'] = f"{fixture['fixture_id']}_home_{home_team_id}"
            away_team_stats['record_id'] = f"{fixture['fixture_id']}_away_{away_team_id}"
            
            home_team_stats['Opponent'] = away_team_stats['team_name']
            away_team_stats['Opponent'] = home_team_stats['team_name'] 
            
            home_team_stats['date'] = date
            away_team_stats['date'] = date
            
            # Get next fixtures
            home_next_fixture = get_next_fixture(home_team_id, fixture_id)
            away_next_fixture = get_next_fixture(away_team_id, fixture_id)
            
            if home_next_fixture:
                home_team_stats.update(home_next_fixture)

            if away_next_fixture:
                away_team_stats.update(away_next_fixture)
            
            # Add team metadata
            home_team_stats['team_id'] = home_team_id
            away_team_stats['team_id'] = away_team_id
            
            home_team_stats['team_logo'] = home_team_data['team_logo']
            away_team_stats['team_logo'] = away_team_data['team_logo']

            home_team_stats['team_goal_stats'] = home_team_data['team_goal_stats']
            away_team_stats['team_goal_stats'] = away_team_data['team_goal_stats']

            # Also include total stats for backward compatibility
            home_team_stats['team_goal_stats_total'] = home_team_data['team_goal_stats_total']
            away_team_stats['team_goal_stats_total'] = away_team_data['team_goal_stats_total']
            
            # Get additional match data
            home_team_stats['past_fixtures'] = get_last_five_games(home_team_id, league_id, season)
            away_team_stats['past_fixtures'] = get_last_five_games(away_team_id, league_id, season)
            
            headtohead = get_head_to_head(home_team_id, away_team_id, league_id)
            home_team_stats['injuries'], away_team_stats['injuries'] = get_fixture_injuries(fixture_id, date[:10], home_team_id, away_team_id, season)

            # Create aggregated fixture data
            aggregated_fixture_data = {
                "fixture_id": fixture['fixture_id'],
                'country': home_team_stats['league_country'],
                'league': home_team_stats['league_name'],
                "league_id": league_id,
                "season": season,
                "home": home_team_stats,
                "away": away_team_stats,
                "h2h": headtohead,
                "venue": venue_info,
                "date": date,
                "predictions": prediction_summary,
                "alternate_predictions": prediction_summary_alt,
                "venue_predictions": venue_prediction_summary,
                "venue_alternate_predictions": venue_prediction_summary_alt,
                "coordination_info": {
                    "league_coordination": convert_floats_to_decimal(league_coordination_info),
                    "team_coordination": convert_floats_to_decimal(team_coordination_info),
                    "venue_coordination": venue_coordination_info
                },
                "prediction_metadata": {
                    "architecture_version": current_version,
                    "prediction_date": int(datetime.now().timestamp()),
                    "parameters_used": {
                        "home_source": "team" if used_team_params_home else "league",
                        "away_source": "team" if used_team_params_away else "league"
                    }
                },
                "timestamp": fixture['timestamp']
            }

            # Clean up the structure
            del aggregated_fixture_data['home']['league_country']
            del aggregated_fixture_data['home']['league_name']
            del aggregated_fixture_data['away']['league_country']
            del aggregated_fixture_data['away']['league_name']
            del aggregated_fixture_data['home']['record_id']
            del aggregated_fixture_data['away']['record_id']

            # Convert for storage
            fixture_record = convert_floats_to_decimal(aggregated_fixture_data)
            print(json.dumps(aggregated_fixture_data, default=decimal_default))

            # Store fixture record
            put_fixture_record(fixture_record)
            
            # Send to SQS
            send_to_sqs(aggregated_fixture_data)

            # Restructure for additional processing if needed
            aggregated_fixture_data['league_name'] = aggregated_fixture_data.pop('league')
            aggregated_fixture_data['league'] = {
                'id': aggregated_fixture_data['league_id'],
                'country': aggregated_fixture_data['country'],
                'name': aggregated_fixture_data['league_name']
            }
            
            del aggregated_fixture_data['league_id']
            del aggregated_fixture_data['country']
            del aggregated_fixture_data['league_name']
            
        except Exception as e:
            print(f"Skipping fixture {fixture.get('fixture_id', 'unknown')}: Unexpected error - {e}")
            continue


def send_to_sqs(data):
    """Send processed fixture data to best bets queue for analysis."""
    sqs = boto3.client('sqs')
    payload = json.dumps(data, default=decimal_default)
    sqs.send_message(
        QueueUrl=BEST_BETS_QUEUE_URL,
        MessageBody=payload
    )


def get_fixture_injuries(fixture_id, date, home_team_id, away_team_id, season):
    """
    Get injury data for both teams in a fixture with enriched player information.
    
    Args:
        fixture_id: Fixture identifier
        date: Game date (YYYY-MM-DD format)
        home_team_id: Home team identifier
        away_team_id: Away team identifier
        season: Season year
        
    Returns:
        Tuple of (home_injuries, away_injuries) with enriched player data
    """
    try:
        # Get raw injury list from API
        injury_list = get_injured_players(fixture_id, date)
        
        # Initialize empty lists
        home_injured = []
        away_injured = []
        
        # Process injuries if data is available
        if injury_list:
            home_injured, away_injured = process_injuries(
                injury_list, home_team_id, away_team_id, season
            )
        
        return home_injured, away_injured
        
    except Exception as e:
        print(f"Error getting injuries for fixture {fixture_id}: {e}")
        return [], []


def get_prediction_params(team_params, league_params):
    """Extract and format prediction parameters."""
    # Add missing parameters with defaults from league params
    result = team_params.copy()
    
    # Ensure all required prediction parameters exist
    required_params = [
        'ref_games', 'confidence', 'sample_size', 'home_multiplier', 'away_multiplier',
        'alpha_home_factor', 'alpha_away_factor', 'home_std', 'away_std',
        'home_ratio_raw', 'away_ratio_raw'
    ]
    
    defaults = {
        'ref_games': 20,
        'confidence': 0.5,
        'sample_size': 20,
        'home_multiplier': 1.0,
        'away_multiplier': 1.0,
        'alpha_home_factor': 1.0,
        'alpha_away_factor': 1.0,
        'home_std': 0.5,
        'away_std': 0.5,
        'home_ratio_raw': 1.0,
        'away_ratio_raw': 1.0
    }
    
    for param in required_params:
        if param not in result:
            result[param] = league_params.get(param, defaults[param])
    
    return result


def mod_league_params(team_params, league_params):
    """Modify league parameters with team-specific adjustments."""
    modified = league_params.copy()
    
    # Apply team-specific standard deviations if available
    if 'home_std' in team_params:
        modified['home_std'] = team_params['home_std']
    if 'away_std' in team_params:
        modified['away_std'] = team_params['away_std']
        
    return modified