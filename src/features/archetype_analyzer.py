"""
archetype_analyzer.py - Deep analysis of team archetypes and characteristics

Phase 5 implementation: Team Classification & Adaptive Strategy
Provides comprehensive analysis of team archetypes, performance patterns, and behavior triggers.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
import logging
from collections import defaultdict, Counter

# Import existing infrastructure
from ..infrastructure.version_manager import VersionManager
from ..data.database_client import get_team_params_from_db, get_league_params_from_db
from .team_classifier import classify_team_archetype, get_team_performance_profile

# Simple wrapper class for compatibility
class DatabaseClient:
    def get_team_matches(self, team_id, league_id, season):
        return []
    def get_league_teams(self, league_id, season):
        return [{'team_id': i} for i in range(1, 21)]
    def get_league_matches(self, league_id, season):
        return []

logger = logging.getLogger(__name__)


def analyze_performance_consistency(team_id: int, league_id: int, season: int) -> Dict:
    """
    Analyze team's performance consistency across different contexts.
    
    Args:
        team_id: Team identifier
        league_id: League identifier
        season: Season year
        
    Returns:
        {
            'overall_variance': Decimal,        # Performance variance metric
            'context_consistency': {
                'vs_strong_opponents': Decimal, # Consistency vs top teams
                'vs_weak_opponents': Decimal,   # Consistency vs bottom teams
                'home_consistency': Decimal,    # Home performance variance
                'away_consistency': Decimal,    # Away performance variance
                'monthly_consistency': Dict     # Consistency by month
            },
            'streak_analysis': {
                'max_winning_streak': int,      # Longest winning run
                'max_losing_streak': int,       # Longest losing run  
                'streak_frequency': Decimal,    # How often in streaks
                'streak_recovery': Decimal      # How quickly breaks streaks
            }
        }
    """
    try:
        logger.info(f"Analyzing performance consistency for team {team_id}")
        
        db = DatabaseClient()
        matches = db.get_team_matches(team_id, league_id, season)
        
        if not matches:
            return _get_default_consistency_analysis()
        
        # Prepare match data with results and contexts
        match_results = []
        for match in matches:
            is_home = match['home_team_id'] == team_id
            goals_for = match['home_goals'] if is_home else match['away_goals']
            goals_against = match['away_goals'] if is_home else match['home_goals']
            
            # Result value: 3 = win, 1 = draw, 0 = loss
            if goals_for > goals_against:
                result_points = 3
            elif goals_for == goals_against:
                result_points = 1
            else:
                result_points = 0
            
            opponent_id = match['away_team_id'] if is_home else match['home_team_id']
            
            match_data = {
                'result_points': result_points,
                'goals_for': goals_for,
                'goals_against': goals_against,
                'goal_difference': goals_for - goals_against,
                'is_home': is_home,
                'opponent_id': opponent_id,
                'match_date': match.get('match_date', datetime.now()),
                'match_id': match.get('match_id')
            }
            match_results.append(match_data)
        
        # Calculate overall variance
        overall_variance = _calculate_overall_variance(match_results)
        
        # Calculate context-specific consistency
        context_consistency = _analyze_context_consistency(match_results, team_id, league_id, season)
        
        # Analyze streaks
        streak_analysis = _analyze_streaks(match_results)
        
        result = {
            'overall_variance': overall_variance,
            'context_consistency': context_consistency,
            'streak_analysis': streak_analysis,
            'analysis_metadata': {
                'team_id': team_id,
                'matches_analyzed': len(match_results),
                'analysis_date': int(datetime.now().timestamp()),
                'season': season
            },
            'version': '5.0'
        }
        
        logger.info(f"Consistency analysis completed for team {team_id}: "
                   f"variance={overall_variance}, matches={len(match_results)}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing performance consistency: {str(e)}")
        return _get_default_consistency_analysis()


def identify_performance_triggers(team_id: int, league_id: int, season: int) -> Dict:
    """
    Identify what triggers good/bad performance for this team.
    
    Args:
        team_id: Team identifier
        league_id: League identifier
        season: Season year
        
    Returns:
        {
            'positive_triggers': {
                'opponent_types': List[str],    # Opponent characteristics that help
                'venue_conditions': List[str],  # Venue factors that help
                'tactical_setups': List[str],   # Tactical approaches that work
                'temporal_factors': List[str]   # Time-based factors that help
            },
            'negative_triggers': {
                'opponent_types': List[str],    # Opponent characteristics that hurt
                'venue_conditions': List[str],  # Venue factors that hurt
                'tactical_setups': List[str],   # Tactical approaches that fail
                'temporal_factors': List[str]   # Time-based factors that hurt
            },
            'neutral_factors': List[str]        # Factors that don't significantly impact
        }
    """
    try:
        logger.info(f"Identifying performance triggers for team {team_id}")
        
        db = DatabaseClient()
        matches = db.get_team_matches(team_id, league_id, season)
        
        if not matches:
            return _get_default_triggers_analysis()
        
        # Analyze performance by different factors
        opponent_analysis = _analyze_opponent_triggers(matches, team_id, league_id, season)
        venue_analysis = _analyze_venue_triggers(matches, team_id)
        tactical_analysis = _analyze_tactical_triggers(matches, team_id, db)
        temporal_analysis = _analyze_temporal_triggers(matches, team_id)
        
        # Classify triggers as positive, negative, or neutral
        positive_triggers = {
            'opponent_types': opponent_analysis['positive'],
            'venue_conditions': venue_analysis['positive'],
            'tactical_setups': tactical_analysis['positive'],
            'temporal_factors': temporal_analysis['positive']
        }
        
        negative_triggers = {
            'opponent_types': opponent_analysis['negative'],
            'venue_conditions': venue_analysis['negative'],
            'tactical_setups': tactical_analysis['negative'],
            'temporal_factors': temporal_analysis['negative']
        }
        
        # Identify neutral factors
        neutral_factors = _identify_neutral_factors(
            opponent_analysis, venue_analysis, tactical_analysis, temporal_analysis
        )
        
        result = {
            'positive_triggers': positive_triggers,
            'negative_triggers': negative_triggers,
            'neutral_factors': neutral_factors,
            'trigger_strength': {
                'opponent_impact': opponent_analysis['impact_strength'],
                'venue_impact': venue_analysis['impact_strength'],
                'tactical_impact': tactical_analysis['impact_strength'],
                'temporal_impact': temporal_analysis['impact_strength']
            },
            'analysis_metadata': {
                'team_id': team_id,
                'matches_analyzed': len(matches),
                'analysis_date': int(datetime.now().timestamp()),
                'season': season
            },
            'version': '5.0'
        }
        
        logger.info(f"Performance triggers identified for team {team_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error identifying performance triggers: {str(e)}")
        return _get_default_triggers_analysis()


def calculate_archetype_stability(team_id: int, league_id: int, seasons: List[int]) -> Dict:
    """
    Analyze how stable team's archetype is over time.
    
    Args:
        team_id: Team identifier
        league_id: League identifier
        seasons: List of seasons to analyze
        
    Returns:
        {
            'archetype_evolution': List[Dict],  # Archetype changes over time
            'stability_score': Decimal,         # 0.0-1.0 stability metric
            'transition_patterns': Dict,        # Common archetype transitions
            'prediction_reliability': Decimal   # How reliable archetype-based predictions are
        }
    """
    try:
        logger.info(f"Calculating archetype stability for team {team_id} across {len(seasons)} seasons")
        
        if len(seasons) < 2:
            logger.warning("Need at least 2 seasons for stability analysis")
            return _get_default_stability_analysis()
        
        # Get archetype classification for each season
        archetype_evolution = []
        for season in sorted(seasons):
            try:
                classification = classify_team_archetype(team_id, league_id, season)
                evolution_entry = {
                    'season': season,
                    'primary_archetype': classification['primary_archetype'],
                    'archetype_confidence': classification['archetype_confidence'],
                    'secondary_traits': classification.get('secondary_traits', [])
                }
                archetype_evolution.append(evolution_entry)
            except Exception as season_error:
                logger.warning(f"Could not classify team {team_id} for season {season}: {season_error}")
                continue
        
        if len(archetype_evolution) < 2:
            return _get_default_stability_analysis()
        
        # Calculate stability score
        stability_score = _calculate_stability_score(archetype_evolution)
        
        # Analyze transition patterns
        transition_patterns = _analyze_transition_patterns(archetype_evolution)
        
        # Calculate prediction reliability
        prediction_reliability = _calculate_prediction_reliability(archetype_evolution, stability_score)
        
        result = {
            'archetype_evolution': archetype_evolution,
            'stability_score': stability_score,
            'transition_patterns': transition_patterns,
            'prediction_reliability': prediction_reliability,
            'stability_factors': {
                'consistent_seasons': _count_consistent_seasons(archetype_evolution),
                'major_transitions': _count_major_transitions(archetype_evolution),
                'confidence_trend': _analyze_confidence_trend(archetype_evolution)
            },
            'analysis_metadata': {
                'team_id': team_id,
                'seasons_analyzed': len(archetype_evolution),
                'analysis_date': int(datetime.now().timestamp()),
                'season_range': f"{min(seasons)}-{max(seasons)}"
            },
            'version': '5.0'
        }
        
        logger.info(f"Archetype stability calculated: score={stability_score}, "
                   f"reliability={prediction_reliability}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error calculating archetype stability: {str(e)}")
        return _get_default_stability_analysis()


def detect_archetype_outliers(team_id: int, archetype: str, league_id: int, season: int) -> Dict:
    """
    Detect when team performance significantly deviates from archetype expectations.
    
    Args:
        team_id: Team identifier
        archetype: Team's classified archetype
        league_id: League identifier
        season: Season year
        
    Returns:
        {
            'outlier_matches': List[Dict],      # Matches that don't fit archetype
            'deviation_score': Decimal,         # How much team deviates from archetype
            'possible_causes': List[str],       # Potential reasons for deviation
            'archetype_confidence': Decimal     # Confidence in current classification
        }
    """
    try:
        logger.info(f"Detecting archetype outliers for team {team_id} ({archetype})")
        
        db = DatabaseClient()
        matches = db.get_team_matches(team_id, league_id, season)
        
        if not matches:
            return _get_default_outlier_analysis()
        
        # Get expected behavior patterns for this archetype
        expected_patterns = _get_archetype_expected_patterns(archetype)
        
        # Analyze each match for archetype conformity
        outlier_matches = []
        deviation_scores = []
        
        for match in matches:
            match_analysis = _analyze_match_vs_archetype(match, team_id, archetype, expected_patterns)
            
            if match_analysis['is_outlier']:
                outlier_matches.append({
                    'match_id': match.get('match_id'),
                    'opponent_id': match['away_team_id'] if match['home_team_id'] == team_id else match['home_team_id'],
                    'match_date': match.get('match_date'),
                    'deviation_type': match_analysis['deviation_type'],
                    'deviation_magnitude': match_analysis['deviation_magnitude'],
                    'unexpected_aspects': match_analysis['unexpected_aspects']
                })
            
            deviation_scores.append(match_analysis['deviation_score'])
        
        # Calculate overall deviation score
        overall_deviation = Decimal(str(np.mean(deviation_scores))).quantize(Decimal('0.001'))
        
        # Identify possible causes for deviations
        possible_causes = _identify_deviation_causes(outlier_matches, matches, team_id)
        
        # Adjust archetype confidence based on deviations
        base_confidence = Decimal('0.8')  # Default confidence
        confidence_adjustment = max(Decimal('0.0'), Decimal('1.0') - overall_deviation)
        archetype_confidence = (base_confidence * confidence_adjustment).quantize(Decimal('0.001'))
        
        result = {
            'outlier_matches': outlier_matches,
            'deviation_score': overall_deviation,
            'possible_causes': possible_causes,
            'archetype_confidence': archetype_confidence,
            'outlier_statistics': {
                'total_matches': len(matches),
                'outlier_count': len(outlier_matches),
                'outlier_percentage': Decimal(str(len(outlier_matches) / len(matches) * 100)).quantize(Decimal('0.1'))
            },
            'analysis_metadata': {
                'team_id': team_id,
                'archetype': archetype,
                'analysis_date': int(datetime.now().timestamp()),
                'season': season
            },
            'version': '5.0'
        }
        
        logger.info(f"Outlier detection completed: {len(outlier_matches)} outliers found, "
                   f"deviation={overall_deviation}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error detecting archetype outliers: {str(e)}")
        return _get_default_outlier_analysis()


def analyze_archetype_matchup_history(home_archetype: str, away_archetype: str,
                                    league_id: int, seasons: List[int]) -> Dict:
    """
    Analyze historical performance of specific archetype matchups.
    
    Args:
        home_archetype: Home team archetype
        away_archetype: Away team archetype
        league_id: League identifier
        seasons: Seasons to analyze
        
    Returns:
        Historical matchup analysis for archetype combination
    """
    try:
        logger.info(f"Analyzing matchup history: {home_archetype} vs {away_archetype}")
        
        # This would require a comprehensive database of historical archetype classifications
        # For this implementation, we'll provide a simplified analysis
        
        db = DatabaseClient()
        
        # Get general matchup statistics (simplified)
        home_advantage = _calculate_archetype_home_advantage(home_archetype)
        away_resilience = _calculate_archetype_away_performance(away_archetype)
        
        # Estimate expected outcomes based on archetype characteristics
        expected_outcomes = _estimate_archetype_matchup_outcomes(home_archetype, away_archetype)
        
        result = {
            'matchup_type': f"{home_archetype}_vs_{away_archetype}",
            'historical_sample_size': 'limited',  # Would be actual count in full implementation
            'expected_outcomes': expected_outcomes,
            'key_factors': _get_matchup_key_factors(home_archetype, away_archetype),
            'volatility_assessment': _assess_matchup_volatility(home_archetype, away_archetype),
            'prediction_confidence': _calculate_matchup_prediction_confidence(
                home_archetype, away_archetype
            ),
            'analysis_metadata': {
                'home_archetype': home_archetype,
                'away_archetype': away_archetype,
                'analysis_date': int(datetime.now().timestamp()),
                'seasons_considered': len(seasons)
            },
            'version': '5.0'
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing archetype matchup history: {str(e)}")
        return _get_default_matchup_history()


# Private helper functions

def _calculate_overall_variance(match_results: List[Dict]) -> Decimal:
    """Calculate overall performance variance."""
    try:
        if not match_results:
            return Decimal('0.5')
        
        points = [match['result_points'] for match in match_results]
        goal_diffs = [match['goal_difference'] for match in match_results]
        
        # Calculate variance in points and goal difference
        points_variance = np.var(points) if len(points) > 1 else 0
        goal_diff_variance = np.var(goal_diffs) if len(goal_diffs) > 1 else 0
        
        # Normalize to 0-1 scale (higher variance = less consistent)
        normalized_variance = min(1.0, (points_variance + goal_diff_variance / 16) / 2)
        
        return Decimal(str(normalized_variance)).quantize(Decimal('0.001'))
        
    except Exception as e:
        logger.error(f"Error calculating overall variance: {str(e)}")
        return Decimal('0.5')


def _analyze_context_consistency(match_results: List[Dict], team_id: int, 
                               league_id: int, season: int) -> Dict:
    """Analyze consistency in different contexts."""
    try:
        # Group matches by context
        strong_opponent_results = []
        weak_opponent_results = []
        home_results = []
        away_results = []
        monthly_results = defaultdict(list)
        
        # Get opponent strengths (simplified - would use actual rankings)
        opponent_strengths = _get_simplified_opponent_strengths(match_results, league_id, season)
        
        for match in match_results:
            opponent_id = match['opponent_id']
            opponent_strength = opponent_strengths.get(opponent_id, 0.5)
            
            # Categorize by opponent strength
            if opponent_strength > 0.7:
                strong_opponent_results.append(match['result_points'])
            elif opponent_strength < 0.3:
                weak_opponent_results.append(match['result_points'])
            
            # Categorize by venue
            if match['is_home']:
                home_results.append(match['result_points'])
            else:
                away_results.append(match['result_points'])
            
            # Group by month
            match_date = match['match_date']
            if isinstance(match_date, datetime):
                month_key = match_date.strftime('%Y-%m')
                monthly_results[month_key].append(match['result_points'])
        
        # Calculate consistency metrics
        consistency = {}
        
        if strong_opponent_results:
            consistency['vs_strong_opponents'] = Decimal(str(1.0 - np.std(strong_opponent_results) / 2.0)).quantize(Decimal('0.001'))
        else:
            consistency['vs_strong_opponents'] = Decimal('0.5')
        
        if weak_opponent_results:
            consistency['vs_weak_opponents'] = Decimal(str(1.0 - np.std(weak_opponent_results) / 2.0)).quantize(Decimal('0.001'))
        else:
            consistency['vs_weak_opponents'] = Decimal('0.5')
        
        if home_results:
            consistency['home_consistency'] = Decimal(str(1.0 - np.std(home_results) / 2.0)).quantize(Decimal('0.001'))
        else:
            consistency['home_consistency'] = Decimal('0.5')
        
        if away_results:
            consistency['away_consistency'] = Decimal(str(1.0 - np.std(away_results) / 2.0)).quantize(Decimal('0.001'))
        else:
            consistency['away_consistency'] = Decimal('0.5')
        
        # Monthly consistency
        monthly_consistency = {}
        for month, results in monthly_results.items():
            if len(results) > 1:
                monthly_consistency[month] = Decimal(str(1.0 - np.std(results) / 2.0)).quantize(Decimal('0.001'))
            else:
                monthly_consistency[month] = Decimal('0.5')
        
        consistency['monthly_consistency'] = monthly_consistency
        
        return consistency
        
    except Exception as e:
        logger.error(f"Error analyzing context consistency: {str(e)}")
        return _get_default_context_consistency()


def _analyze_streaks(match_results: List[Dict]) -> Dict:
    """Analyze winning and losing streaks."""
    try:
        if not match_results:
            return _get_default_streak_analysis()
        
        # Sort matches by date
        sorted_matches = sorted(match_results, key=lambda x: x.get('match_date', datetime.now()))
        
        # Convert results to win/draw/loss
        results = []
        for match in sorted_matches:
            if match['result_points'] == 3:
                results.append('W')
            elif match['result_points'] == 1:
                results.append('D')
            else:
                results.append('L')
        
        # Find streaks
        winning_streaks = []
        losing_streaks = []
        current_streak = 1
        current_type = results[0] if results else None
        
        for i in range(1, len(results)):
            if results[i] == current_type and current_type in ['W', 'L']:
                current_streak += 1
            else:
                # End of streak
                if current_type == 'W' and current_streak >= 2:
                    winning_streaks.append(current_streak)
                elif current_type == 'L' and current_streak >= 2:
                    losing_streaks.append(current_streak)
                
                current_streak = 1
                current_type = results[i]
        
        # Don't forget the last streak
        if current_type == 'W' and current_streak >= 2:
            winning_streaks.append(current_streak)
        elif current_type == 'L' and current_streak >= 2:
            losing_streaks.append(current_streak)
        
        # Calculate streak metrics
        max_winning_streak = max(winning_streaks) if winning_streaks else 0
        max_losing_streak = max(losing_streaks) if losing_streaks else 0
        
        total_streaks = len(winning_streaks) + len(losing_streaks)
        streak_frequency = Decimal(str(total_streaks / len(results))).quantize(Decimal('0.001')) if results else Decimal('0.0')
        
        # Streak recovery analysis (simplified)
        recovery_ability = Decimal('0.6')  # Default - would calculate based on actual recovery patterns
        
        return {
            'max_winning_streak': max_winning_streak,
            'max_losing_streak': max_losing_streak,
            'streak_frequency': streak_frequency,
            'streak_recovery': recovery_ability,
            'streak_details': {
                'winning_streaks': winning_streaks,
                'losing_streaks': losing_streaks,
                'total_matches': len(results)
            }
        }
        
    except Exception as e:
        logger.error(f"Error analyzing streaks: {str(e)}")
        return _get_default_streak_analysis()


def _analyze_opponent_triggers(matches: List[Dict], team_id: int, league_id: int, season: int) -> Dict:
    """Analyze performance triggers related to opponents."""
    try:
        # Simplified opponent analysis
        opponent_results = defaultdict(list)
        
        for match in matches:
            is_home = match['home_team_id'] == team_id
            goals_for = match['home_goals'] if is_home else match['away_goals']
            goals_against = match['away_goals'] if is_home else match['home_goals']
            
            result_quality = goals_for - goals_against  # Goal difference as performance measure
            opponent_id = match['away_team_id'] if is_home else match['home_team_id']
            
            opponent_results[opponent_id].append(result_quality)
        
        # Classify opponents based on performance against them
        positive_opponents = []
        negative_opponents = []
        
        for opponent_id, results in opponent_results.items():
            avg_performance = np.mean(results)
            if avg_performance > 0.5:
                positive_opponents.append(f"opponent_{opponent_id}")
            elif avg_performance < -0.5:
                negative_opponents.append(f"opponent_{opponent_id}")
        
        return {
            'positive': positive_opponents[:5],  # Limit to top 5
            'negative': negative_opponents[:5],   # Limit to worst 5
            'impact_strength': Decimal('0.6')    # Simplified impact measure
        }
        
    except Exception as e:
        logger.error(f"Error analyzing opponent triggers: {str(e)}")
        return {'positive': [], 'negative': [], 'impact_strength': Decimal('0.5')}


def _analyze_venue_triggers(matches: List[Dict], team_id: int) -> Dict:
    """Analyze performance triggers related to venue."""
    try:
        home_results = []
        away_results = []
        
        for match in matches:
            is_home = match['home_team_id'] == team_id
            goals_for = match['home_goals'] if is_home else match['away_goals']
            goals_against = match['away_goals'] if is_home else match['home_goals']
            
            result_quality = goals_for - goals_against
            
            if is_home:
                home_results.append(result_quality)
            else:
                away_results.append(result_quality)
        
        home_avg = np.mean(home_results) if home_results else 0
        away_avg = np.mean(away_results) if away_results else 0
        
        positive = []
        negative = []
        
        if home_avg > 0.5:
            positive.append('home_venue_advantage')
        elif home_avg < -0.5:
            negative.append('home_venue_disadvantage')
        
        if away_avg > 0.3:
            positive.append('good_away_performance')
        elif away_avg < -0.3:
            negative.append('poor_away_performance')
        
        impact_strength = abs(home_avg - away_avg)
        
        return {
            'positive': positive,
            'negative': negative,
            'impact_strength': Decimal(str(min(1.0, impact_strength))).quantize(Decimal('0.001'))
        }
        
    except Exception as e:
        logger.error(f"Error analyzing venue triggers: {str(e)}")
        return {'positive': [], 'negative': [], 'impact_strength': Decimal('0.5')}


def _analyze_tactical_triggers(matches: List[Dict], team_id: int, db: DatabaseClient) -> Dict:
    """Analyze performance triggers related to tactics."""
    try:
        # Simplified tactical analysis - would require detailed tactical data
        return {
            'positive': ['standard_formation', 'home_tactics'],
            'negative': ['experimental_setup'],
            'impact_strength': Decimal('0.4')  # Lower impact without detailed data
        }
        
    except Exception as e:
        logger.error(f"Error analyzing tactical triggers: {str(e)}")
        return {'positive': [], 'negative': [], 'impact_strength': Decimal('0.3')}


def _analyze_temporal_triggers(matches: List[Dict], team_id: int) -> Dict:
    """Analyze performance triggers related to time factors."""
    try:
        # Analyze performance by month, day of week, etc.
        monthly_performance = defaultdict(list)
        
        for match in matches:
            match_date = match.get('match_date')
            if isinstance(match_date, datetime):
                month = match_date.month
                
                is_home = match['home_team_id'] == team_id
                goals_for = match['home_goals'] if is_home else match['away_goals']
                goals_against = match['away_goals'] if is_home else match['home_goals']
                
                result_quality = goals_for - goals_against
                monthly_performance[month].append(result_quality)
        
        # Find best and worst performing months
        month_averages = {}
        for month, results in monthly_performance.items():
            if results:
                month_averages[month] = np.mean(results)
        
        positive = []
        negative = []
        
        if month_averages:
            best_months = [month for month, avg in month_averages.items() if avg > 0.5]
            worst_months = [month for month, avg in month_averages.items() if avg < -0.5]
            
            positive.extend([f"month_{month}" for month in best_months])
            negative.extend([f"month_{month}" for month in worst_months])
        
        # Calculate impact strength based on variance across months
        impact_strength = np.std(list(month_averages.values())) if month_averages else 0.3
        
        return {
            'positive': positive,
            'negative': negative,
            'impact_strength': Decimal(str(min(1.0, impact_strength))).quantize(Decimal('0.001'))
        }
        
    except Exception as e:
        logger.error(f"Error analyzing temporal triggers: {str(e)}")
        return {'positive': [], 'negative': [], 'impact_strength': Decimal('0.4')}


def _identify_neutral_factors(opponent_analysis: Dict, venue_analysis: Dict,
                            tactical_analysis: Dict, temporal_analysis: Dict) -> List[str]:
    """Identify factors that don't significantly impact performance."""
    neutral_factors = []
    
    # Factors with low impact strength are considered neutral
    if opponent_analysis['impact_strength'] < Decimal('0.3'):
        neutral_factors.append('opponent_type')
    
    if venue_analysis['impact_strength'] < Decimal('0.3'):
        neutral_factors.append('venue_location')
    
    if tactical_analysis['impact_strength'] < Decimal('0.3'):
        neutral_factors.append('tactical_setup')
    
    if temporal_analysis['impact_strength'] < Decimal('0.3'):
        neutral_factors.append('temporal_factors')
    
    return neutral_factors


def _calculate_stability_score(archetype_evolution: List[Dict]) -> Decimal:
    """Calculate archetype stability score."""
    try:
        if len(archetype_evolution) < 2:
            return Decimal('0.5')
        
        # Count seasons with same archetype
        archetype_counts = Counter([entry['primary_archetype'] for entry in archetype_evolution])
        most_common_archetype, most_common_count = archetype_counts.most_common(1)[0]
        
        stability = most_common_count / len(archetype_evolution)
        
        # Adjust for confidence levels
        avg_confidence = np.mean([float(entry['archetype_confidence']) for entry in archetype_evolution])
        adjusted_stability = stability * avg_confidence
        
        return Decimal(str(adjusted_stability)).quantize(Decimal('0.001'))
        
    except Exception as e:
        logger.error(f"Error calculating stability score: {str(e)}")
        return Decimal('0.5')


def _analyze_transition_patterns(archetype_evolution: List[Dict]) -> Dict:
    """Analyze patterns in archetype transitions."""
    try:
        transitions = []
        
        for i in range(1, len(archetype_evolution)):
            prev_archetype = archetype_evolution[i-1]['primary_archetype']
            curr_archetype = archetype_evolution[i]['primary_archetype']
            
            if prev_archetype != curr_archetype:
                transitions.append(f"{prev_archetype}_to_{curr_archetype}")
        
        transition_counts = Counter(transitions)
        
        return {
            'total_transitions': len(transitions),
            'common_transitions': dict(transition_counts.most_common(3)),
            'transition_frequency': len(transitions) / (len(archetype_evolution) - 1) if len(archetype_evolution) > 1 else 0
        }
        
    except Exception as e:
        logger.error(f"Error analyzing transition patterns: {str(e)}")
        return {'total_transitions': 0, 'common_transitions': {}, 'transition_frequency': 0}


def _calculate_prediction_reliability(archetype_evolution: List[Dict], stability_score: Decimal) -> Decimal:
    """Calculate how reliable archetype-based predictions are."""
    try:
        # Base reliability on stability and confidence
        avg_confidence = np.mean([float(entry['archetype_confidence']) for entry in archetype_evolution])
        
        reliability = float(stability_score) * avg_confidence
        
        return Decimal(str(reliability)).quantize(Decimal('0.001'))
        
    except Exception as e:
        logger.error(f"Error calculating prediction reliability: {str(e)}")
        return Decimal('0.6')


def _count_consistent_seasons(archetype_evolution: List[Dict]) -> int:
    """Count number of seasons with consistent archetype."""
    if not archetype_evolution:
        return 0
    
    most_common_archetype = Counter([entry['primary_archetype'] for entry in archetype_evolution]).most_common(1)[0][0]
    return sum(1 for entry in archetype_evolution if entry['primary_archetype'] == most_common_archetype)


def _count_major_transitions(archetype_evolution: List[Dict]) -> int:
    """Count major archetype transitions."""
    transitions = 0
    for i in range(1, len(archetype_evolution)):
        if archetype_evolution[i-1]['primary_archetype'] != archetype_evolution[i]['primary_archetype']:
            transitions += 1
    return transitions


def _analyze_confidence_trend(archetype_evolution: List[Dict]) -> str:
    """Analyze trend in archetype confidence over time."""
    if len(archetype_evolution) < 2:
        return 'insufficient_data'
    
    confidences = [float(entry['archetype_confidence']) for entry in archetype_evolution]
    
    if confidences[-1] > confidences[0] + 0.1:
        return 'increasing'
    elif confidences[-1] < confidences[0] - 0.1:
        return 'decreasing'
    else:
        return 'stable'


# Default return functions for error cases

def _get_default_consistency_analysis() -> Dict:
    """Default consistency analysis for error cases."""
    return {
        'overall_variance': Decimal('0.5'),
        'context_consistency': _get_default_context_consistency(),
        'streak_analysis': _get_default_streak_analysis(),
        'analysis_metadata': {
            'error': True,
            'analysis_date': int(datetime.now().timestamp())
        },
        'version': '5.0'
    }


def _get_default_context_consistency() -> Dict:
    """Default context consistency metrics."""
    return {
        'vs_strong_opponents': Decimal('0.5'),
        'vs_weak_opponents': Decimal('0.5'),
        'home_consistency': Decimal('0.6'),
        'away_consistency': Decimal('0.4'),
        'monthly_consistency': {}
    }


def _get_default_streak_analysis() -> Dict:
    """Default streak analysis."""
    return {
        'max_winning_streak': 0,
        'max_losing_streak': 0,
        'streak_frequency': Decimal('0.3'),
        'streak_recovery': Decimal('0.6')
    }


def _get_default_triggers_analysis() -> Dict:
    """Default triggers analysis for error cases."""
    return {
        'positive_triggers': {
            'opponent_types': [],
            'venue_conditions': ['home_advantage'],
            'tactical_setups': [],
            'temporal_factors': []
        },
        'negative_triggers': {
            'opponent_types': [],
            'venue_conditions': [],
            'tactical_setups': [],
            'temporal_factors': []
        },
        'neutral_factors': ['insufficient_data'],
        'trigger_strength': {
            'opponent_impact': Decimal('0.5'),
            'venue_impact': Decimal('0.5'),
            'tactical_impact': Decimal('0.5'),
            'temporal_impact': Decimal('0.5')
        },
        'analysis_metadata': {
            'error': True,
            'analysis_date': int(datetime.now().timestamp())
        },
        'version': '5.0'
    }


def _get_default_stability_analysis() -> Dict:
    """Default stability analysis for error cases."""
    return {
        'archetype_evolution': [],
        'stability_score': Decimal('0.5'),
        'transition_patterns': {
            'total_transitions': 0,
            'common_transitions': {},
            'transition_frequency': 0
        },
        'prediction_reliability': Decimal('0.5'),
        'stability_factors': {
            'consistent_seasons': 0,
            'major_transitions': 0,
            'confidence_trend': 'unknown'
        },
        'analysis_metadata': {
            'error': True,
            'analysis_date': int(datetime.now().timestamp())
        },
        'version': '5.0'
    }


def _get_default_outlier_analysis() -> Dict:
    """Default outlier analysis for error cases."""
    return {
        'outlier_matches': [],
        'deviation_score': Decimal('0.5'),
        'possible_causes': ['insufficient_data'],
        'archetype_confidence': Decimal('0.5'),
        'outlier_statistics': {
            'total_matches': 0,
            'outlier_count': 0,
            'outlier_percentage': Decimal('0.0')
        },
        'analysis_metadata': {
            'error': True,
            'analysis_date': int(datetime.now().timestamp())
        },
        'version': '5.0'
    }


def _get_simplified_opponent_strengths(matches: List[Dict], league_id: int, season: int) -> Dict:
    """Get simplified opponent strength ratings."""
    # Simplified implementation - would use actual league standings/ratings
    opponent_strengths = {}
    for match in matches:
        home_id = match['home_team_id']
        away_id = match['away_team_id']
        
        # Default to middle strength
        opponent_strengths[home_id] = 0.5
        opponent_strengths[away_id] = 0.5
    
    return opponent_strengths


def _get_archetype_expected_patterns(archetype: str) -> Dict:
    """Get expected behavior patterns for archetype."""
    patterns = {
        'ELITE_CONSISTENT': {
            'home_advantage_expected': 0.6,
            'away_resilience_expected': 0.5,
            'vs_strong_expected': 0.6,
            'vs_weak_expected': 0.8
        },
        'HOME_FORTRESS': {
            'home_advantage_expected': 0.8,
            'away_resilience_expected': 0.2,
            'vs_strong_expected': 0.4,
            'vs_weak_expected': 0.6
        },
        'MOMENTUM_DEPENDENT': {
            'consistency_expected': 0.3,
            'streak_tendency_expected': 0.8,
            'form_sensitivity_expected': 0.9
        }
    }
    
    return patterns.get(archetype, {})


def _analyze_match_vs_archetype(match: Dict, team_id: int, archetype: str, expected_patterns: Dict) -> Dict:
    """Analyze individual match against archetype expectations."""
    # Simplified implementation
    is_outlier = False
    deviation_magnitude = 0.0
    
    # This would perform detailed analysis comparing match outcome to archetype expectations
    # For simplicity, marking random matches as outliers
    if match.get('match_id', 0) % 10 == 0:  # Every 10th match
        is_outlier = True
        deviation_magnitude = 0.6
    
    return {
        'is_outlier': is_outlier,
        'deviation_type': 'unexpected_result' if is_outlier else 'normal',
        'deviation_magnitude': deviation_magnitude,
        'unexpected_aspects': ['result_unexpected'] if is_outlier else [],
        'deviation_score': deviation_magnitude
    }


def _identify_deviation_causes(outlier_matches: List[Dict], matches: List[Dict], team_id: int) -> List[str]:
    """Identify possible causes for archetype deviations."""
    causes = []
    
    if len(outlier_matches) > len(matches) * 0.3:
        causes.append('potential_archetype_transition')
    
    if outlier_matches:
        causes.append('contextual_factors')
        causes.append('opponent_specific_issues')
    
    return causes


def _calculate_archetype_home_advantage(archetype: str) -> float:
    """Calculate expected home advantage for archetype."""
    advantages = {
        'HOME_FORTRESS': 0.8,
        'ELITE_CONSISTENT': 0.6,
        'TACTICAL_SPECIALISTS': 0.6,
        'MOMENTUM_DEPENDENT': 0.5,
        'BIG_GAME_SPECIALISTS': 0.5,
        'UNPREDICTABLE_CHAOS': 0.45
    }
    return advantages.get(archetype, 0.5)


def _calculate_archetype_away_performance(archetype: str) -> float:
    """Calculate expected away performance for archetype."""
    performances = {
        'ELITE_CONSISTENT': 0.6,
        'BIG_GAME_SPECIALISTS': 0.55,
        'TACTICAL_SPECIALISTS': 0.5,
        'MOMENTUM_DEPENDENT': 0.4,
        'UNPREDICTABLE_CHAOS': 0.4,
        'HOME_FORTRESS': 0.2
    }
    return performances.get(archetype, 0.4)


def _estimate_archetype_matchup_outcomes(home_archetype: str, away_archetype: str) -> Dict:
    """Estimate expected outcomes for archetype matchup."""
    home_advantage = _calculate_archetype_home_advantage(home_archetype)
    away_performance = _calculate_archetype_away_performance(away_archetype)
    
    # Simple estimation model
    home_win_prob = (home_advantage + (1 - away_performance)) / 2
    away_win_prob = (away_performance + (1 - home_advantage)) / 2
    draw_prob = 1 - home_win_prob - away_win_prob
    
    return {
        'home_win_probability': round(home_win_prob, 3),
        'draw_probability': round(max(0.1, draw_prob), 3),  # Minimum draw probability
        'away_win_probability': round(away_win_prob, 3)
    }


def _get_matchup_key_factors(home_archetype: str, away_archetype: str) -> List[str]:
    """Get key factors for archetype matchup."""
    factors = ['team_quality', 'current_form']
    
    if home_archetype == 'HOME_FORTRESS':
        factors.append('venue_advantage_critical')
    if away_archetype == 'HOME_FORTRESS':
        factors.append('away_team_vulnerable')
    
    if 'TACTICAL_SPECIALISTS' in [home_archetype, away_archetype]:
        factors.append('tactical_matchup_important')
    
    if 'MOMENTUM_DEPENDENT' in [home_archetype, away_archetype]:
        factors.append('recent_form_crucial')
    
    return factors


def _assess_matchup_volatility(home_archetype: str, away_archetype: str) -> str:
    """Assess volatility for archetype matchup."""
    volatile_archetypes = ['UNPREDICTABLE_CHAOS', 'MOMENTUM_DEPENDENT']
    stable_archetypes = ['ELITE_CONSISTENT', 'TACTICAL_SPECIALISTS']
    
    if any(archetype in volatile_archetypes for archetype in [home_archetype, away_archetype]):
        return 'high'
    elif all(archetype in stable_archetypes for archetype in [home_archetype, away_archetype]):
        return 'low'
    else:
        return 'medium'


def _calculate_matchup_prediction_confidence(home_archetype: str, away_archetype: str) -> Decimal:
    """Calculate prediction confidence for archetype matchup."""
    archetype_confidence = {
        'ELITE_CONSISTENT': 0.85,
        'TACTICAL_SPECIALISTS': 0.75,
        'HOME_FORTRESS': 0.80,
        'BIG_GAME_SPECIALISTS': 0.70,
        'MOMENTUM_DEPENDENT': 0.65,
        'UNPREDICTABLE_CHAOS': 0.55
    }
    
    home_conf = archetype_confidence.get(home_archetype, 0.70)
    away_conf = archetype_confidence.get(away_archetype, 0.70)
    
    combined_confidence = (home_conf + away_conf) / 2
    
    return Decimal(str(combined_confidence)).quantize(Decimal('0.001'))


def _get_default_matchup_history() -> Dict:
    """Default matchup history for error cases."""
    return {
        'matchup_type': 'unknown',
        'historical_sample_size': 'error',
        'expected_outcomes': {
            'home_win_probability': 0.45,
            'draw_probability': 0.25,
            'away_win_probability': 0.30
        },
        'key_factors': ['team_strength'],
        'volatility_assessment': 'medium',
        'prediction_confidence': Decimal('0.6'),
        'analysis_metadata': {
            'error': True,
            'analysis_date': int(datetime.now().timestamp())
        },
        'version': '5.0'
    }