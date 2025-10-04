# accuracy_tracker.py - Comprehensive accuracy tracking and performance monitoring
"""
Phase 6: Accuracy Tracking System
Implements comprehensive accuracy tracking, performance monitoring, and trend analysis
for the advanced football prediction system.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
import logging
from collections import defaultdict, Counter
from ..data.database_client import DatabaseClient
from ..infrastructure.version_manager import VersionManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AccuracyTracker:
    """
    Comprehensive accuracy tracking and performance monitoring system.
    
    Tracks prediction accuracy across different dimensions and contexts,
    analyzes trends, and identifies improvement opportunities.
    """
    
    def __init__(self):
        self.db_client = DatabaseClient()
        self.version_manager = VersionManager()
        self._accuracy_cache = {}
        self._trend_cache = {}
    
    def track_prediction_accuracy(self, league_id: int, season: int, 
                                prediction_window: int = 30) -> Dict:
        """
        Track prediction accuracy across different time windows and contexts.
        
        Args:
            league_id: League identifier
            season: Season to analyze
            prediction_window: Number of days to look back for recent accuracy
            
        Returns:
            {
                'overall_accuracy': {
                    'exact_score': Decimal,         # Exact score prediction accuracy
                    'result_prediction': Decimal,   # Win/draw/loss prediction accuracy
                    'goal_total': Decimal,          # Over/under goals accuracy
                    'both_teams_score': Decimal     # Both teams to score accuracy
                },
                'contextual_accuracy': {
                    'by_opponent_strength': Dict,   # Accuracy vs different opponent tiers
                    'by_venue': Dict,              # Home vs away accuracy
                    'by_match_importance': Dict,    # Big games vs regular matches
                    'by_team_archetype': Dict      # Accuracy for different team types
                },
                'temporal_accuracy': {
                    'by_month': Dict,              # Seasonal accuracy variations
                    'by_match_day': Dict,          # Accuracy by league round
                    'recent_form': Dict            # Recent prediction performance
                }
            }
        """
        try:
            # Get prediction data for the specified period
            predictions = self._get_predictions_data(league_id, season, prediction_window)
            
            if not predictions:
                logger.warning(f"No prediction data found for league {league_id} season {season}")
                return self._default_accuracy_tracking()
            
            # Calculate overall accuracy metrics
            overall_accuracy = self._calculate_overall_accuracy(predictions)
            
            # Calculate contextual accuracy breakdowns
            contextual_accuracy = self._calculate_contextual_accuracy(predictions)
            
            # Calculate temporal accuracy patterns
            temporal_accuracy = self._calculate_temporal_accuracy(predictions, prediction_window)
            
            return {
                'overall_accuracy': overall_accuracy,
                'contextual_accuracy': contextual_accuracy,
                'temporal_accuracy': temporal_accuracy,
                'data_summary': {
                    'total_predictions': len(predictions),
                    'date_range': self._get_date_range(predictions),
                    'league_id': league_id,
                    'season': season
                }
            }
            
        except Exception as e:
            logger.error(f"Error tracking prediction accuracy: {e}")
            return self._default_accuracy_tracking()
    
    def calculate_accuracy_trends(self, historical_data: List[Dict]) -> Dict:
        """
        Calculate accuracy trends and identify patterns.
        
        Args:
            historical_data: Historical accuracy data over time
            
        Returns:
            {
                'trend_analysis': {
                    'overall_trend': str,          # 'improving' | 'declining' | 'stable'
                    'trend_confidence': Decimal,   # Statistical confidence in trend
                    'trend_magnitude': Decimal,    # Rate of change
                    'seasonality_effects': Dict    # Seasonal accuracy patterns
                },
                'performance_cycles': {
                    'peak_periods': List[Dict],    # When accuracy is highest
                    'low_periods': List[Dict],     # When accuracy is lowest
                    'cycle_patterns': Dict         # Recurring accuracy patterns
                }
            }
        """
        try:
            if len(historical_data) < 10:
                logger.warning("Insufficient data for trend analysis")
                return self._default_trend_analysis()
            
            # Extract time series data
            accuracy_series = self._extract_accuracy_time_series(historical_data)
            
            # Analyze overall trend
            trend_analysis = self._analyze_overall_trend(accuracy_series)
            
            # Identify performance cycles
            performance_cycles = self._identify_performance_cycles(accuracy_series)
            
            return {
                'trend_analysis': trend_analysis,
                'performance_cycles': performance_cycles,
                'statistical_summary': self._calculate_trend_statistics(accuracy_series)
            }
            
        except Exception as e:
            logger.error(f"Error calculating accuracy trends: {e}")
            return self._default_trend_analysis()
    
    def analyze_prediction_errors(self, predictions: List[Dict], 
                                actual_results: List[Dict]) -> Dict:
        """
        Analyze prediction errors to identify improvement opportunities.
        
        Args:
            predictions: List of predictions made
            actual_results: List of actual match outcomes
            
        Returns:
            {
                'error_patterns': {
                    'systematic_biases': List[str], # Consistent prediction biases
                    'error_correlation': Dict,      # Which errors occur together
                    'worst_scenarios': List[Dict]   # Scenarios with highest errors
                },
                'improvement_opportunities': {
                    'model_weaknesses': List[str],  # Areas where model struggles
                    'data_quality_issues': List[str], # Data problems affecting accuracy
                    'feature_importance': Dict      # Which features most impact accuracy
                }
            }
        """
        try:
            if len(predictions) != len(actual_results):
                raise ValueError("Predictions and results must have same length")
            
            # Analyze error patterns
            error_patterns = self._analyze_error_patterns(predictions, actual_results)
            
            # Identify improvement opportunities
            improvement_opportunities = self._identify_improvement_opportunities(
                predictions, actual_results, error_patterns
            )
            
            return {
                'error_patterns': error_patterns,
                'improvement_opportunities': improvement_opportunities,
                'error_summary': {
                    'total_errors': len([p for p, r in zip(predictions, actual_results) 
                                       if not self._is_correct_prediction(p, r)]),
                    'error_rate': self._calculate_error_rate(predictions, actual_results),
                    'most_common_errors': self._get_most_common_errors(predictions, actual_results)
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing prediction errors: {e}")
            return self._default_error_analysis()
    
    def generate_accuracy_alerts(self, current_performance: Dict, 
                               historical_baselines: Dict) -> Dict:
        """
        Generate alerts when accuracy falls below expected levels.
        
        Args:
            current_performance: Current accuracy metrics
            historical_baselines: Historical baseline performance levels
            
        Returns:
            {
                'performance_alerts': List[Dict],   # Active performance alerts
                'degradation_warnings': List[Dict], # Early warning indicators
                'threshold_breaches': Dict,         # Performance thresholds crossed
                'recommended_actions': List[str]    # Suggested corrective actions
            }
        """
        try:
            alerts = []
            warnings = []
            threshold_breaches = {}
            recommended_actions = []
            
            # Check overall accuracy degradation
            current_accuracy = float(current_performance.get('overall_accuracy', {}).get('result_prediction', 0))
            baseline_accuracy = float(historical_baselines.get('overall_accuracy', {}).get('result_prediction', 0.75))
            
            accuracy_threshold = baseline_accuracy * 0.95  # 5% degradation threshold
            warning_threshold = baseline_accuracy * 0.98   # 2% warning threshold
            
            if current_accuracy < accuracy_threshold:
                alerts.append({
                    'type': 'accuracy_degradation',
                    'severity': 'high',
                    'message': f'Overall accuracy dropped to {current_accuracy:.3f} (baseline: {baseline_accuracy:.3f})',
                    'timestamp': datetime.now().isoformat()
                })
                threshold_breaches['overall_accuracy'] = {
                    'current': current_accuracy,
                    'threshold': accuracy_threshold,
                    'deviation': current_accuracy - accuracy_threshold
                }
                recommended_actions.append('investigate_model_performance')
                recommended_actions.append('check_data_quality')
                
            elif current_accuracy < warning_threshold:
                warnings.append({
                    'type': 'accuracy_warning',
                    'severity': 'medium',
                    'message': f'Overall accuracy showing decline: {current_accuracy:.3f} (baseline: {baseline_accuracy:.3f})',
                    'timestamp': datetime.now().isoformat()
                })
            
            # Check contextual accuracy patterns
            contextual_alerts = self._check_contextual_accuracy_alerts(
                current_performance, historical_baselines
            )
            alerts.extend(contextual_alerts['alerts'])
            warnings.extend(contextual_alerts['warnings'])
            threshold_breaches.update(contextual_alerts['threshold_breaches'])
            recommended_actions.extend(contextual_alerts['recommended_actions'])
            
            # Check for systematic issues
            systematic_alerts = self._check_systematic_issues(current_performance)
            alerts.extend(systematic_alerts)
            
            # Remove duplicate recommended actions
            recommended_actions = list(set(recommended_actions))
            
            return {
                'performance_alerts': alerts,
                'degradation_warnings': warnings,
                'threshold_breaches': threshold_breaches,
                'recommended_actions': recommended_actions,
                'alert_summary': {
                    'total_alerts': len(alerts),
                    'total_warnings': len(warnings),
                    'highest_severity': self._get_highest_severity(alerts + warnings),
                    'generated_at': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating accuracy alerts: {e}")
            return self._default_accuracy_alerts()
    
    # Private helper methods
    
    def _get_predictions_data(self, league_id: int, season: int, window_days: int) -> List[Dict]:
        """Get prediction data from database."""
        try:
            # This would query the database for predictions and their outcomes
            # Placeholder implementation - in real system would query actual data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=window_days)
            
            # Mock data structure for illustration
            sample_predictions = [
                {
                    'prediction_id': f'pred_{i}',
                    'home_team_id': 1 + (i % 10),
                    'away_team_id': 2 + (i % 10),
                    'predicted_result': 'home_win',
                    'actual_result': 'home_win' if i % 3 != 0 else 'away_win',
                    'predicted_score': {'home': 2, 'away': 1},
                    'actual_score': {'home': 2 if i % 3 != 0 else 1, 'away': 1 if i % 3 != 0 else 2},
                    'prediction_date': start_date + timedelta(days=i % window_days),
                    'match_date': start_date + timedelta(days=(i % window_days) + 1),
                    'venue': 'home' if i % 2 == 0 else 'away',
                    'match_importance': 'regular' if i % 5 != 0 else 'important',
                    'team_archetype': {
                        'home': ['possession_dominant', 'defensive_solid', 'counter_attacking'][i % 3],
                        'away': ['high_pressing', 'inconsistent', 'unpredictable'][i % 3]
                    },
                    'opponent_strength': {
                        'home': ['strong', 'medium', 'weak'][i % 3],
                        'away': ['medium', 'weak', 'strong'][i % 3]
                    }
                }
                for i in range(min(100, window_days * 2))  # Generate sample data
            ]
            
            return sample_predictions
            
        except Exception as e:
            logger.error(f"Error retrieving predictions data: {e}")
            return []
    
    def _calculate_overall_accuracy(self, predictions: List[Dict]) -> Dict:
        """Calculate overall accuracy metrics."""
        if not predictions:
            return self._default_overall_accuracy()
        
        try:
            # Result prediction accuracy (win/draw/loss)
            result_correct = sum(1 for p in predictions 
                               if p['predicted_result'] == p['actual_result'])
            result_accuracy = result_correct / len(predictions)
            
            # Exact score accuracy
            exact_score_correct = sum(1 for p in predictions 
                                    if p['predicted_score'] == p['actual_score'])
            exact_score_accuracy = exact_score_correct / len(predictions)
            
            # Goal total accuracy (over/under 2.5 goals)
            goal_total_correct = sum(1 for p in predictions 
                                   if self._check_goal_total_accuracy(p))
            goal_total_accuracy = goal_total_correct / len(predictions)
            
            # Both teams to score accuracy
            btts_correct = sum(1 for p in predictions 
                             if self._check_btts_accuracy(p))
            btts_accuracy = btts_correct / len(predictions)
            
            return {
                'exact_score': Decimal(str(exact_score_accuracy)).quantize(Decimal('0.001')),
                'result_prediction': Decimal(str(result_accuracy)).quantize(Decimal('0.001')),
                'goal_total': Decimal(str(goal_total_accuracy)).quantize(Decimal('0.001')),
                'both_teams_score': Decimal(str(btts_accuracy)).quantize(Decimal('0.001'))
            }
            
        except Exception as e:
            logger.error(f"Error calculating overall accuracy: {e}")
            return self._default_overall_accuracy()
    
    def _calculate_contextual_accuracy(self, predictions: List[Dict]) -> Dict:
        """Calculate accuracy breakdown by different contexts."""
        try:
            contextual_accuracy = {}
            
            # Accuracy by opponent strength
            contextual_accuracy['by_opponent_strength'] = self._calculate_accuracy_by_context(
                predictions, 'opponent_strength'
            )
            
            # Accuracy by venue
            contextual_accuracy['by_venue'] = self._calculate_accuracy_by_context(
                predictions, 'venue'
            )
            
            # Accuracy by match importance
            contextual_accuracy['by_match_importance'] = self._calculate_accuracy_by_context(
                predictions, 'match_importance'
            )
            
            # Accuracy by team archetype
            contextual_accuracy['by_team_archetype'] = self._calculate_accuracy_by_archetype(
                predictions
            )
            
            return contextual_accuracy
            
        except Exception as e:
            logger.error(f"Error calculating contextual accuracy: {e}")
            return {}
    
    def _calculate_temporal_accuracy(self, predictions: List[Dict], window_days: int) -> Dict:
        """Calculate temporal accuracy patterns."""
        try:
            temporal_accuracy = {}
            
            # Accuracy by month
            temporal_accuracy['by_month'] = self._calculate_accuracy_by_month(predictions)
            
            # Accuracy by match day/round
            temporal_accuracy['by_match_day'] = self._calculate_accuracy_by_match_day(predictions)
            
            # Recent form (accuracy in recent games)
            recent_cutoff = datetime.now() - timedelta(days=min(7, window_days))
            recent_predictions = [p for p in predictions 
                                if datetime.fromisoformat(p['prediction_date'].isoformat()) > recent_cutoff]
            temporal_accuracy['recent_form'] = self._calculate_recent_form(recent_predictions)
            
            return temporal_accuracy
            
        except Exception as e:
            logger.error(f"Error calculating temporal accuracy: {e}")
            return {}
    
    def _extract_accuracy_time_series(self, historical_data: List[Dict]) -> List[Dict]:
        """Extract time series data for trend analysis."""
        # Sort by date and extract accuracy values
        sorted_data = sorted(historical_data, key=lambda x: x.get('date', datetime.now()))
        
        return [
            {
                'date': item['date'],
                'accuracy': float(item.get('accuracy', 0.75)),
                'sample_size': item.get('sample_size', 1)
            }
            for item in sorted_data
        ]
    
    def _analyze_overall_trend(self, accuracy_series: List[Dict]) -> Dict:
        """Analyze overall accuracy trend."""
        if len(accuracy_series) < 3:
            return {
                'overall_trend': 'stable',
                'trend_confidence': Decimal('0.000'),
                'trend_magnitude': Decimal('0.000'),
                'seasonality_effects': {}
            }
        
        # Calculate trend using linear regression
        x = np.arange(len(accuracy_series))
        y = np.array([point['accuracy'] for point in accuracy_series])
        
        # Linear regression
        coefficients = np.polyfit(x, y, 1)
        slope = coefficients[0]
        
        # Calculate trend confidence (R-squared)
        y_pred = np.polyval(coefficients, x)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # Determine trend direction
        if abs(slope) < 0.001:  # Essentially flat
            trend = 'stable'
        elif slope > 0:
            trend = 'improving'
        else:
            trend = 'declining'
        
        # Calculate seasonality effects
        seasonality_effects = self._calculate_seasonality_effects(accuracy_series)
        
        return {
            'overall_trend': trend,
            'trend_confidence': Decimal(str(max(0, r_squared))).quantize(Decimal('0.001')),
            'trend_magnitude': Decimal(str(abs(slope))).quantize(Decimal('0.001')),
            'seasonality_effects': seasonality_effects
        }
    
    def _identify_performance_cycles(self, accuracy_series: List[Dict]) -> Dict:
        """Identify performance cycles and patterns."""
        if len(accuracy_series) < 10:
            return {
                'peak_periods': [],
                'low_periods': [],
                'cycle_patterns': {}
            }
        
        accuracies = [point['accuracy'] for point in accuracy_series]
        dates = [point['date'] for point in accuracy_series]
        
        # Find peaks and valleys
        mean_accuracy = np.mean(accuracies)
        std_accuracy = np.std(accuracies)
        
        peak_threshold = mean_accuracy + 0.5 * std_accuracy
        low_threshold = mean_accuracy - 0.5 * std_accuracy
        
        peak_periods = []
        low_periods = []
        
        for i, (accuracy, date) in enumerate(zip(accuracies, dates)):
            if accuracy > peak_threshold:
                peak_periods.append({
                    'period': date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date),
                    'accuracy': accuracy,
                    'index': i
                })
            elif accuracy < low_threshold:
                low_periods.append({
                    'period': date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date),
                    'accuracy': accuracy,
                    'index': i
                })
        
        # Analyze cycle patterns
        cycle_patterns = self._analyze_cycle_patterns(accuracies)
        
        return {
            'peak_periods': peak_periods,
            'low_periods': low_periods,
            'cycle_patterns': cycle_patterns
        }
    
    def _analyze_error_patterns(self, predictions: List[Dict], actual_results: List[Dict]) -> Dict:
        """Analyze systematic error patterns."""
        systematic_biases = []
        error_correlations = {}
        worst_scenarios = []
        
        # Identify systematic biases
        home_bias = self._calculate_home_bias(predictions, actual_results)
        if abs(home_bias) > 0.1:
            systematic_biases.append(f"home_bias: {home_bias:.3f}")
        
        favorite_bias = self._calculate_favorite_bias(predictions, actual_results)
        if abs(favorite_bias) > 0.1:
            systematic_biases.append(f"favorite_bias: {favorite_bias:.3f}")
        
        # Find worst performing scenarios
        scenario_performance = self._calculate_scenario_performance(predictions, actual_results)
        worst_scenarios = sorted(scenario_performance.items(), 
                               key=lambda x: x[1]['accuracy'])[:5]
        
        return {
            'systematic_biases': systematic_biases,
            'error_correlation': error_correlations,
            'worst_scenarios': [{'scenario': k, 'performance': v} for k, v in worst_scenarios]
        }
    
    def _identify_improvement_opportunities(self, predictions: List[Dict], 
                                          actual_results: List[Dict],
                                          error_patterns: Dict) -> Dict:
        """Identify specific improvement opportunities."""
        model_weaknesses = []
        data_quality_issues = []
        feature_importance = {}
        
        # Identify model weaknesses from error patterns
        if error_patterns['systematic_biases']:
            model_weaknesses.append('systematic_prediction_biases')
        
        worst_scenarios = error_patterns.get('worst_scenarios', [])
        if worst_scenarios:
            worst_scenario = worst_scenarios[0]
            model_weaknesses.append(f"poor_performance_in_{worst_scenario['scenario']}")
        
        # Check for data quality issues
        if self._detect_missing_data_patterns(predictions):
            data_quality_issues.append('missing_data_patterns')
        
        if self._detect_stale_data_patterns(predictions):
            data_quality_issues.append('stale_data_patterns')
        
        # Calculate feature importance (simplified)
        feature_importance = self._calculate_feature_importance(predictions, actual_results)
        
        return {
            'model_weaknesses': model_weaknesses,
            'data_quality_issues': data_quality_issues,
            'feature_importance': feature_importance
        }
    
    def _check_contextual_accuracy_alerts(self, current: Dict, baselines: Dict) -> Dict:
        """Check for contextual accuracy issues."""
        alerts = []
        warnings = []
        threshold_breaches = {}
        recommended_actions = []
        
        # Check venue-specific accuracy
        current_venue = current.get('contextual_accuracy', {}).get('by_venue', {})
        baseline_venue = baselines.get('contextual_accuracy', {}).get('by_venue', {})
        
        for venue in ['home', 'away']:
            if venue in current_venue and venue in baseline_venue:
                current_acc = float(current_venue[venue].get('accuracy', 0))
                baseline_acc = float(baseline_venue[venue].get('accuracy', 0.75))
                
                if current_acc < baseline_acc * 0.9:  # 10% degradation
                    alerts.append({
                        'type': 'venue_accuracy_degradation',
                        'severity': 'medium',
                        'message': f'{venue.title()} venue accuracy dropped to {current_acc:.3f}',
                        'venue': venue
                    })
                    recommended_actions.append(f'investigate_{venue}_venue_factors')
        
        return {
            'alerts': alerts,
            'warnings': warnings,
            'threshold_breaches': threshold_breaches,
            'recommended_actions': recommended_actions
        }
    
    def _check_systematic_issues(self, current_performance: Dict) -> List[Dict]:
        """Check for systematic performance issues."""
        alerts = []
        
        # Check for extremely low accuracy in any category
        overall_acc = current_performance.get('overall_accuracy', {})
        
        for metric, value in overall_acc.items():
            if isinstance(value, (int, float, Decimal)) and float(value) < 0.4:
                alerts.append({
                    'type': 'systematic_failure',
                    'severity': 'critical',
                    'message': f'{metric} accuracy critically low: {value}',
                    'metric': metric
                })
        
        return alerts
    
    # Utility methods for accuracy calculations
    
    def _check_goal_total_accuracy(self, prediction: Dict) -> bool:
        """Check if over/under 2.5 goals prediction was correct."""
        predicted_total = prediction['predicted_score']['home'] + prediction['predicted_score']['away']
        actual_total = prediction['actual_score']['home'] + prediction['actual_score']['away']
        
        predicted_over = predicted_total > 2.5
        actual_over = actual_total > 2.5
        
        return predicted_over == actual_over
    
    def _check_btts_accuracy(self, prediction: Dict) -> bool:
        """Check if both teams to score prediction was correct."""
        predicted_btts = (prediction['predicted_score']['home'] > 0 and 
                         prediction['predicted_score']['away'] > 0)
        actual_btts = (prediction['actual_score']['home'] > 0 and 
                      prediction['actual_score']['away'] > 0)
        
        return predicted_btts == actual_btts
    
    def _calculate_accuracy_by_context(self, predictions: List[Dict], context_key: str) -> Dict:
        """Calculate accuracy grouped by a specific context."""
        context_groups = defaultdict(list)
        
        for prediction in predictions:
            if context_key in prediction:
                context_value = prediction[context_key]
                if isinstance(context_value, dict):
                    # Handle nested contexts like opponent_strength
                    for sub_key, sub_value in context_value.items():
                        context_groups[f"{sub_key}_{sub_value}"].append(prediction)
                else:
                    context_groups[context_value].append(prediction)
        
        accuracy_by_context = {}
        for context, preds in context_groups.items():
            if preds:
                correct = sum(1 for p in preds if p['predicted_result'] == p['actual_result'])
                accuracy_by_context[context] = {
                    'accuracy': Decimal(str(correct / len(preds))).quantize(Decimal('0.001')),
                    'count': len(preds)
                }
        
        return accuracy_by_context
    
    def _calculate_accuracy_by_archetype(self, predictions: List[Dict]) -> Dict:
        """Calculate accuracy by team archetype combinations."""
        archetype_combinations = defaultdict(list)
        
        for prediction in predictions:
            if 'team_archetype' in prediction:
                home_arch = prediction['team_archetype']['home']
                away_arch = prediction['team_archetype']['away']
                combo = f"{home_arch}_vs_{away_arch}"
                archetype_combinations[combo].append(prediction)
        
        accuracy_by_archetype = {}
        for combo, preds in archetype_combinations.items():
            if preds:
                correct = sum(1 for p in preds if p['predicted_result'] == p['actual_result'])
                accuracy_by_archetype[combo] = {
                    'accuracy': Decimal(str(correct / len(preds))).quantize(Decimal('0.001')),
                    'count': len(preds)
                }
        
        return accuracy_by_archetype
    
    def _calculate_accuracy_by_month(self, predictions: List[Dict]) -> Dict:
        """Calculate accuracy by month."""
        monthly_predictions = defaultdict(list)
        
        for prediction in predictions:
            month = prediction['match_date'].strftime('%Y-%m')
            monthly_predictions[month].append(prediction)
        
        monthly_accuracy = {}
        for month, preds in monthly_predictions.items():
            if preds:
                correct = sum(1 for p in preds if p['predicted_result'] == p['actual_result'])
                monthly_accuracy[month] = {
                    'accuracy': Decimal(str(correct / len(preds))).quantize(Decimal('0.001')),
                    'count': len(preds)
                }
        
        return monthly_accuracy
    
    def _calculate_accuracy_by_match_day(self, predictions: List[Dict]) -> Dict:
        """Calculate accuracy by match day/round."""
        # This would require match day information in the data
        # Simplified implementation
        return {'match_day_1': {'accuracy': Decimal('0.750'), 'count': 10}}
    
    def _calculate_recent_form(self, recent_predictions: List[Dict]) -> Dict:
        """Calculate recent prediction form."""
        if not recent_predictions:
            return {'accuracy': Decimal('0.000'), 'count': 0, 'trend': 'no_data'}
        
        correct = sum(1 for p in recent_predictions 
                     if p['predicted_result'] == p['actual_result'])
        accuracy = correct / len(recent_predictions)
        
        # Determine trend (simplified)
        if len(recent_predictions) >= 5:
            first_half = recent_predictions[:len(recent_predictions)//2]
            second_half = recent_predictions[len(recent_predictions)//2:]
            
            first_acc = sum(1 for p in first_half if p['predicted_result'] == p['actual_result']) / len(first_half)
            second_acc = sum(1 for p in second_half if p['predicted_result'] == p['actual_result']) / len(second_half)
            
            if second_acc > first_acc + 0.05:
                trend = 'improving'
            elif second_acc < first_acc - 0.05:
                trend = 'declining'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
        
        return {
            'accuracy': Decimal(str(accuracy)).quantize(Decimal('0.001')),
            'count': len(recent_predictions),
            'trend': trend
        }
    
    # Default/fallback methods
    
    def _default_accuracy_tracking(self) -> Dict:
        """Default accuracy tracking when no data available."""
        return {
            'overall_accuracy': self._default_overall_accuracy(),
            'contextual_accuracy': {},
            'temporal_accuracy': {},
            'data_summary': {
                'total_predictions': 0,
                'date_range': {'start': None, 'end': None},
                'league_id': None,
                'season': None
            }
        }
    
    def _default_overall_accuracy(self) -> Dict:
        """Default overall accuracy metrics."""
        return {
            'exact_score': Decimal('0.000'),
            'result_prediction': Decimal('0.000'),
            'goal_total': Decimal('0.000'),
            'both_teams_score': Decimal('0.000')
        }
    
    def _default_trend_analysis(self) -> Dict:
        """Default trend analysis when insufficient data."""
        return {
            'trend_analysis': {
                'overall_trend': 'stable',
                'trend_confidence': Decimal('0.000'),
                'trend_magnitude': Decimal('0.000'),
                'seasonality_effects': {}
            },
            'performance_cycles': {
                'peak_periods': [],
                'low_periods': [],
                'cycle_patterns': {}
            },
            'statistical_summary': {}
        }
    
    def _default_error_analysis(self) -> Dict:
        """Default error analysis when calculation fails."""
        return {
            'error_patterns': {
                'systematic_biases': [],
                'error_correlation': {},
                'worst_scenarios': []
            },
            'improvement_opportunities': {
                'model_weaknesses': [],
                'data_quality_issues': [],
                'feature_importance': {}
            },
            'error_summary': {
                'total_errors': 0,
                'error_rate': Decimal('0.000'),
                'most_common_errors': []
            }
        }
    
    def _default_accuracy_alerts(self) -> Dict:
        """Default accuracy alerts when generation fails."""
        return {
            'performance_alerts': [],
            'degradation_warnings': [],
            'threshold_breaches': {},
            'recommended_actions': [],
            'alert_summary': {
                'total_alerts': 0,
                'total_warnings': 0,
                'highest_severity': 'none',
                'generated_at': datetime.now().isoformat()
            }
        }
    
    # Additional utility methods
    
    def _get_date_range(self, predictions: List[Dict]) -> Dict:
        """Get date range for predictions."""
        if not predictions:
            return {'start': None, 'end': None}
        
        dates = [p['match_date'] for p in predictions if 'match_date' in p]
        if dates:
            return {
                'start': min(dates).isoformat(),
                'end': max(dates).isoformat()
            }
        return {'start': None, 'end': None}
    
    def _is_correct_prediction(self, prediction: Dict, result: Dict) -> bool:
        """Check if a prediction was correct."""
        return prediction.get('predicted_result') == result.get('actual_result')
    
    def _calculate_error_rate(self, predictions: List[Dict], results: List[Dict]) -> Decimal:
        """Calculate overall error rate."""
        if not predictions or not results:
            return Decimal('0.000')
        
        errors = sum(1 for p, r in zip(predictions, results) 
                    if not self._is_correct_prediction(p, r))
        error_rate = errors / len(predictions)
        return Decimal(str(error_rate)).quantize(Decimal('0.001'))
    
    def _get_most_common_errors(self, predictions: List[Dict], results: List[Dict]) -> List[str]:
        """Get most common types of prediction errors."""
        error_types = []
        
        for pred, result in zip(predictions, results):
            if not self._is_correct_prediction(pred, result):
                predicted = pred.get('predicted_result', 'unknown')
                actual = result.get('actual_result', 'unknown')
                error_types.append(f"{predicted}_predicted_{actual}_actual")
        
        error_counter = Counter(error_types)
        return [error_type for error_type, _ in error_counter.most_common(5)]
    
    def _calculate_seasonality_effects(self, accuracy_series: List[Dict]) -> Dict:
        """Calculate seasonal effects on accuracy."""
        # Simplified seasonality analysis
        monthly_accuracy = defaultdict(list)
        
        for point in accuracy_series:
            month = point['date'].month if hasattr(point['date'], 'month') else 1
            monthly_accuracy[month].append(point['accuracy'])
        
        seasonal_effects = {}
        for month, accuracies in monthly_accuracy.items():
            if accuracies:
                seasonal_effects[f"month_{month}"] = {
                    'average_accuracy': np.mean(accuracies),
                    'count': len(accuracies)
                }
        
        return seasonal_effects
    
    def _analyze_cycle_patterns(self, accuracies: List[float]) -> Dict:
        """Analyze cyclical patterns in accuracy."""
        # Simplified cycle analysis
        return {
            'cycle_length': 'unknown',
            'amplitude': np.std(accuracies) if accuracies else 0,
            'regularity_score': 0.5
        }
    
    def _calculate_trend_statistics(self, accuracy_series: List[Dict]) -> Dict:
        """Calculate statistical summary of trends."""
        if not accuracy_series:
            return {}
        
        accuracies = [point['accuracy'] for point in accuracy_series]
        
        return {
            'mean_accuracy': float(np.mean(accuracies)),
            'std_accuracy': float(np.std(accuracies)),
            'min_accuracy': float(np.min(accuracies)),
            'max_accuracy': float(np.max(accuracies)),
            'data_points': len(accuracies)
        }
    
    def _calculate_home_bias(self, predictions: List[Dict], results: List[Dict]) -> float:
        """Calculate bias toward home team predictions."""
        home_predictions = sum(1 for p in predictions if p.get('predicted_result') == 'home_win')
        home_actual = sum(1 for r in results if r.get('actual_result') == 'home_win')
        
        pred_rate = home_predictions / len(predictions) if predictions else 0
        actual_rate = home_actual / len(results) if results else 0
        
        return pred_rate - actual_rate
    
    def _calculate_favorite_bias(self, predictions: List[Dict], results: List[Dict]) -> float:
        """Calculate bias toward favorite team predictions."""
        # Simplified - would need odds data for proper implementation
        return 0.0
    
    def _calculate_scenario_performance(self, predictions: List[Dict], results: List[Dict]) -> Dict:
        """Calculate performance by scenario."""
        scenarios = defaultdict(lambda: {'correct': 0, 'total': 0})
        
        for pred, result in zip(predictions, results):
            scenario = f"{pred.get('venue', 'unknown')}_{pred.get('match_importance', 'regular')}"
            scenarios[scenario]['total'] += 1
            if self._is_correct_prediction(pred, result):
                scenarios[scenario]['correct'] += 1
        
        # Calculate accuracy for each scenario
        scenario_accuracy = {}
        for scenario, counts in scenarios.items():
            if counts['total'] > 0:
                accuracy = counts['correct'] / counts['total']
                scenario_accuracy[scenario] = {
                    'accuracy': accuracy,
                    'count': counts['total']
                }
        
        return scenario_accuracy
    
    def _detect_missing_data_patterns(self, predictions: List[Dict]) -> bool:
        """Detect patterns indicating missing data issues."""
        # Check for consistent missing fields
        missing_counts = defaultdict(int)
        
        for pred in predictions:
            if 'team_archetype' not in pred:
                missing_counts['team_archetype'] += 1
            if 'opponent_strength' not in pred:
                missing_counts['opponent_strength'] += 1
        
        # If more than 20% of predictions are missing key data
        threshold = len(predictions) * 0.2
        return any(count > threshold for count in missing_counts.values())
    
    def _detect_stale_data_patterns(self, predictions: List[Dict]) -> bool:
        """Detect patterns indicating stale data issues."""
        # Check for predictions with old data timestamps
        now = datetime.now()
        stale_threshold = now - timedelta(days=7)
        
        stale_count = sum(1 for pred in predictions 
                         if 'data_timestamp' in pred and 
                         pred['data_timestamp'] < stale_threshold)
        
        return stale_count > len(predictions) * 0.1  # More than 10% stale data
    
    def _calculate_feature_importance(self, predictions: List[Dict], results: List[Dict]) -> Dict:
        """Calculate simplified feature importance."""
        # This would require more sophisticated analysis in a real system
        # Placeholder implementation
        return {
            'team_archetype': 0.25,
            'venue': 0.20,
            'opponent_strength': 0.15,
            'match_importance': 0.10,
            'recent_form': 0.30
        }
    
    def _get_highest_severity(self, alerts: List[Dict]) -> str:
        """Get highest severity level from alerts."""
        if not alerts:
            return 'none'
        
        severity_order = {'critical': 3, 'high': 2, 'medium': 1, 'low': 0}
        max_severity = max(alerts, key=lambda x: severity_order.get(x.get('severity', 'low'), 0))
        return max_severity.get('severity', 'none')


# Global instance for easy access
accuracy_tracker = AccuracyTracker()

# Main interface functions
def track_prediction_accuracy(league_id: int, season: int, 
                            prediction_window: int = 30) -> Dict:
    """
    Track prediction accuracy across different time windows and contexts.
    
    Returns:
        {
            'overall_accuracy': {
                'exact_score': Decimal,         # Exact score prediction accuracy
                'result_prediction': Decimal,   # Win/draw/loss prediction accuracy
                'goal_total': Decimal,          # Over/under goals accuracy
                'both_teams_score': Decimal     # Both teams to score accuracy
            },
            'contextual_accuracy': {
                'by_opponent_strength': Dict,   # Accuracy vs different opponent tiers
                'by_venue': Dict,              # Home vs away accuracy
                'by_match_importance': Dict,    # Big games vs regular matches
                'by_team_archetype': Dict      # Accuracy for different team types
            },
            'temporal_accuracy': {
                'by_month': Dict,              # Seasonal accuracy variations
                'by_match_day': Dict,          # Accuracy by league round
                'recent_form': Dict            # Recent prediction performance
            }
        }
    """
    return accuracy_tracker.track_prediction_accuracy(league_id, season, prediction_window)

def calculate_accuracy_trends(historical_data: List[Dict]) -> Dict:
    """
    Calculate accuracy trends and identify patterns.
    
    Returns:
        {
            'trend_analysis': {
                'overall_trend': str,          # 'improving' | 'declining' | 'stable'
                'trend_confidence': Decimal,   # Statistical confidence in trend
                'trend_magnitude': Decimal,    # Rate of change
                'seasonality_effects': Dict    # Seasonal accuracy patterns
            },
            'performance_cycles': {
                'peak_periods': List[Dict],    # When accuracy is highest
                'low_periods': List[Dict],     # When accuracy is lowest
                'cycle_patterns': Dict         # Recurring accuracy patterns
            }
        }
    """
    return accuracy_tracker.calculate_accuracy_trends(historical_data)

def analyze_prediction_errors(predictions: List[Dict], 
                            actual_results: List[Dict]) -> Dict:
    """
    Analyze prediction errors to identify improvement opportunities.
    
    Returns:
        {
            'error_patterns': {
                'systematic_biases': List[str], # Consistent prediction biases
                'error_correlation': Dict,      # Which errors occur together
                'worst_scenarios': List[Dict]   # Scenarios with highest errors
            },
            'improvement_opportunities': {
                'model_weaknesses': List[str],  # Areas where model struggles
                'data_quality_issues': List[str], # Data problems affecting accuracy
                'feature_importance': Dict      # Which features most impact accuracy
            }
        }
    """
    return accuracy_tracker.analyze_prediction_errors(predictions, actual_results)

def generate_accuracy_alerts(current_performance: Dict, 
                           historical_baselines: Dict) -> Dict:
    """
    Generate alerts when accuracy falls below expected levels.
    
    Returns:
        {
            'performance_alerts': List[Dict],   # Active performance alerts
            'degradation_warnings': List[Dict], # Early warning indicators
            'threshold_breaches': Dict,         # Performance thresholds crossed
            'recommended_actions': List[str]    # Suggested corrective actions
        }
    """
    return accuracy_tracker.generate_accuracy_alerts(current_performance, historical_baselines)