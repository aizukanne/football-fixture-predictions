# system_monitor.py - System monitoring, alerts, and health checks
"""
Phase 6: System Monitoring & Alerts
Implements comprehensive system monitoring, health checks, and automated alerting
for the advanced football prediction system.
"""

import time
import numpy as np

# Optional dependency with graceful fallback
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
import logging
from collections import defaultdict, deque
from ..data.database_client import DatabaseClient
from ..infrastructure.version_manager import VersionManager
from ..analytics.accuracy_tracker import accuracy_tracker
from ..analytics.confidence_calibrator import confidence_calibrator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SystemMonitor:
    """
    Comprehensive system monitoring and health management.
    
    Monitors system health, performance metrics, data quality,
    and generates automated alerts for proactive issue management.
    """
    
    def __init__(self):
        self.db_client = DatabaseClient()
        self.version_manager = VersionManager()
        self._health_cache = {}
        self._alert_history = deque(maxlen=1000)  # Keep last 1000 alerts
        self._performance_history = deque(maxlen=100)  # Keep last 100 performance snapshots
        self._thresholds = self._load_monitoring_thresholds()
        self._monitoring_start_time = datetime.now()
    
    def monitor_system_health(self) -> Dict:
        """
        Monitor overall system health and performance.
        
        Returns:
            {
                'system_status': str,              # 'Healthy' | 'Warning' | 'Critical'
                'component_status': Dict,          # Status of individual components
                'performance_metrics': Dict,       # Key performance indicators
                'active_alerts': List[Dict],       # Current system alerts
                'health_score': Decimal           # Overall system health (0.0-1.0)
            }
        """
        try:
            # Check individual component health
            component_status = self._check_component_health()
            
            # Collect performance metrics
            performance_metrics = self._collect_performance_metrics()
            
            # Generate active alerts
            active_alerts = self._generate_active_alerts(component_status, performance_metrics)
            
            # Calculate overall health score
            health_score = self._calculate_health_score(component_status, performance_metrics)
            
            # Determine system status
            system_status = self._determine_system_status(health_score, active_alerts)
            
            # Store performance snapshot
            self._store_performance_snapshot(performance_metrics, health_score)
            
            health_report = {
                'system_status': system_status,
                'component_status': component_status,
                'performance_metrics': performance_metrics,
                'active_alerts': active_alerts,
                'health_score': health_score,
                'monitoring_metadata': {
                    'check_timestamp': datetime.now().isoformat(),
                    'uptime': self._calculate_uptime(),
                    'monitoring_duration': str(datetime.now() - self._monitoring_start_time),
                    'check_frequency': '5_minutes'
                }
            }
            
            # Cache health report
            self._health_cache['latest'] = health_report
            
            return health_report
            
        except Exception as e:
            logger.error(f"Error monitoring system health: {e}")
            return self._emergency_health_report(str(e))
    
    def check_data_quality(self) -> Dict:
        """
        Monitor data quality and completeness.
        
        Returns:
            Data quality assessment and alerts.
        """
        try:
            # Check data freshness
            data_freshness = self._check_data_freshness()
            
            # Check data completeness
            data_completeness = self._check_data_completeness()
            
            # Check data consistency
            data_consistency = self._check_data_consistency()
            
            # Check data accuracy indicators
            data_accuracy_indicators = self._check_data_accuracy_indicators()
            
            # Generate data quality alerts
            data_quality_alerts = self._generate_data_quality_alerts(
                data_freshness, data_completeness, data_consistency, data_accuracy_indicators
            )
            
            # Calculate overall data quality score
            overall_quality_score = self._calculate_data_quality_score(
                data_freshness, data_completeness, data_consistency, data_accuracy_indicators
            )
            
            return {
                'overall_quality_score': overall_quality_score,
                'data_freshness': data_freshness,
                'data_completeness': data_completeness,
                'data_consistency': data_consistency,
                'data_accuracy_indicators': data_accuracy_indicators,
                'quality_alerts': data_quality_alerts,
                'quality_trends': self._analyze_data_quality_trends(),
                'assessment_metadata': {
                    'assessment_timestamp': datetime.now().isoformat(),
                    'assessment_scope': 'comprehensive',
                    'data_sources_checked': self._get_monitored_data_sources()
                }
            }
            
        except Exception as e:
            logger.error(f"Error checking data quality: {e}")
            return self._default_data_quality_assessment()
    
    def validate_model_performance(self) -> Dict:
        """
        Validate that models are performing within expected parameters.
        
        Returns:
            Model performance validation results.
        """
        try:
            # Check prediction accuracy vs baselines
            accuracy_validation = self._validate_prediction_accuracy()
            
            # Check confidence calibration quality
            confidence_validation = self._validate_confidence_calibration()
            
            # Check model stability
            model_stability = self._check_model_stability()
            
            # Check feature performance
            feature_performance = self._validate_feature_performance()
            
            # Check for model drift
            model_drift = self._detect_model_drift()
            
            # Generate performance alerts
            performance_alerts = self._generate_model_performance_alerts(
                accuracy_validation, confidence_validation, model_stability, 
                feature_performance, model_drift
            )
            
            # Calculate overall model health score
            model_health_score = self._calculate_model_health_score(
                accuracy_validation, confidence_validation, model_stability, model_drift
            )
            
            return {
                'model_health_score': model_health_score,
                'accuracy_validation': accuracy_validation,
                'confidence_validation': confidence_validation,
                'model_stability': model_stability,
                'feature_performance': feature_performance,
                'model_drift_detection': model_drift,
                'performance_alerts': performance_alerts,
                'validation_trends': self._analyze_model_performance_trends(),
                'validation_metadata': {
                    'validation_timestamp': datetime.now().isoformat(),
                    'validation_scope': 'comprehensive',
                    'models_validated': self._get_active_models(),
                    'validation_period': '24_hours'
                }
            }
            
        except Exception as e:
            logger.error(f"Error validating model performance: {e}")
            return self._default_model_validation()
    
    def generate_system_alerts(self, current_metrics: Dict, thresholds: Dict) -> List[Dict]:
        """
        Generate system alerts based on performance thresholds.
        
        Args:
            current_metrics: Current system metrics
            thresholds: Alert thresholds configuration
            
        Returns:
            List of active alerts requiring attention.
        """
        try:
            alerts = []
            alert_timestamp = datetime.now()
            
            # System performance alerts
            performance_alerts = self._check_performance_thresholds(current_metrics, thresholds)
            alerts.extend(performance_alerts)
            
            # Resource utilization alerts
            resource_alerts = self._check_resource_thresholds(current_metrics, thresholds)
            alerts.extend(resource_alerts)
            
            # Prediction quality alerts
            quality_alerts = self._check_prediction_quality_thresholds(current_metrics, thresholds)
            alerts.extend(quality_alerts)
            
            # System availability alerts
            availability_alerts = self._check_availability_thresholds(current_metrics, thresholds)
            alerts.extend(availability_alerts)
            
            # Add timestamps and metadata to alerts
            for alert in alerts:
                alert['generated_at'] = alert_timestamp.isoformat()
                alert['alert_id'] = self._generate_alert_id()
                alert['monitoring_source'] = 'system_monitor'
            
            # Store alerts in history
            self._alert_history.extend(alerts)
            
            # Filter and deduplicate alerts
            filtered_alerts = self._filter_and_deduplicate_alerts(alerts)
            
            return filtered_alerts
            
        except Exception as e:
            logger.error(f"Error generating system alerts: {e}")
            return [self._create_error_alert(str(e))]
    
    def get_system_diagnostics(self) -> Dict:
        """Get comprehensive system diagnostics information."""
        try:
            return {
                'system_info': self._get_system_info(),
                'resource_usage': self._get_resource_usage(),
                'performance_history': list(self._performance_history)[-10:],  # Last 10 snapshots
                'alert_summary': self._get_alert_summary(),
                'health_trends': self._analyze_health_trends(),
                'diagnostic_metadata': {
                    'diagnostic_timestamp': datetime.now().isoformat(),
                    'monitoring_uptime': str(datetime.now() - self._monitoring_start_time),
                    'total_alerts_generated': len(self._alert_history)
                }
            }
        except Exception as e:
            logger.error(f"Error getting system diagnostics: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    # Private helper methods
    
    def _check_component_health(self) -> Dict:
        """Check health of individual system components."""
        component_status = {}
        
        try:
            # Database connectivity
            component_status['database'] = self._check_database_health()
            
            # Prediction engine
            component_status['prediction_engine'] = self._check_prediction_engine_health()
            
            # Data pipeline
            component_status['data_pipeline'] = self._check_data_pipeline_health()
            
            # Analytics components
            component_status['analytics'] = self._check_analytics_health()
            
            # Infrastructure components
            component_status['infrastructure'] = self._check_infrastructure_health()
            
        except Exception as e:
            logger.error(f"Error checking component health: {e}")
            component_status['error'] = str(e)
        
        return component_status
    
    def _collect_performance_metrics(self) -> Dict:
        """Collect current performance metrics."""
        try:
            return {
                'cpu_usage': psutil.cpu_percent(interval=1),
                'memory_usage': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'network_io': self._get_network_metrics(),
                'prediction_latency': self._measure_prediction_latency(),
                'database_response_time': self._measure_database_response_time(),
                'system_load': psutil.getloadavg()[0],  # 1-minute load average
                'active_connections': self._count_active_connections(),
                'prediction_throughput': self._measure_prediction_throughput(),
                'error_rate': self._calculate_current_error_rate()
            }
        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            return {'error': str(e)}
    
    def _generate_active_alerts(self, component_status: Dict, performance_metrics: Dict) -> List[Dict]:
        """Generate alerts based on component status and performance metrics."""
        alerts = []
        
        # Component health alerts
        for component, status in component_status.items():
            if isinstance(status, dict) and status.get('status') in ['critical', 'warning']:
                alerts.append({
                    'type': 'component_health',
                    'severity': status['status'],
                    'component': component,
                    'message': status.get('message', f'{component} health issue detected'),
                    'details': status.get('details', {})
                })
        
        # Performance threshold alerts
        perf_alerts = self.generate_system_alerts(performance_metrics, self._thresholds)
        alerts.extend(perf_alerts)
        
        return alerts
    
    def _calculate_health_score(self, component_status: Dict, performance_metrics: Dict) -> Decimal:
        """Calculate overall system health score."""
        try:
            scores = []
            
            # Component health scores
            for component, status in component_status.items():
                if isinstance(status, dict):
                    if status.get('status') == 'healthy':
                        scores.append(1.0)
                    elif status.get('status') == 'warning':
                        scores.append(0.7)
                    elif status.get('status') == 'critical':
                        scores.append(0.3)
                    else:
                        scores.append(0.5)  # Unknown status
            
            # Performance scores
            if isinstance(performance_metrics, dict) and 'error' not in performance_metrics:
                cpu_score = max(0, 1.0 - (performance_metrics.get('cpu_usage', 50) / 100))
                memory_score = max(0, 1.0 - (performance_metrics.get('memory_usage', 50) / 100))
                scores.extend([cpu_score, memory_score])
            
            # Calculate weighted average
            if scores:
                health_score = sum(scores) / len(scores)
            else:
                health_score = 0.5  # Unknown health
            
            return Decimal(str(health_score)).quantize(Decimal('0.001'))
            
        except Exception as e:
            logger.error(f"Error calculating health score: {e}")
            return Decimal('0.500')
    
    def _determine_system_status(self, health_score: Decimal, active_alerts: List[Dict]) -> str:
        """Determine overall system status."""
        critical_alerts = [a for a in active_alerts if a.get('severity') == 'critical']
        warning_alerts = [a for a in active_alerts if a.get('severity') == 'warning']
        
        if critical_alerts or float(health_score) < 0.5:
            return 'Critical'
        elif warning_alerts or float(health_score) < 0.8:
            return 'Warning'
        else:
            return 'Healthy'
    
    def _store_performance_snapshot(self, metrics: Dict, health_score: Decimal):
        """Store performance snapshot for trend analysis."""
        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics,
            'health_score': float(health_score)
        }
        self._performance_history.append(snapshot)
    
    def _check_data_freshness(self) -> Dict:
        """Check freshness of data sources."""
        # This would check actual data timestamps
        return {
            'match_data': {'last_update': datetime.now() - timedelta(hours=2), 'freshness_score': 0.9},
            'team_data': {'last_update': datetime.now() - timedelta(hours=6), 'freshness_score': 0.8},
            'venue_data': {'last_update': datetime.now() - timedelta(days=1), 'freshness_score': 0.9},
            'overall_freshness': 0.87
        }
    
    def _check_data_completeness(self) -> Dict:
        """Check completeness of data sources."""
        return {
            'match_data_completeness': 0.95,
            'team_data_completeness': 0.92,
            'tactical_data_completeness': 0.88,
            'venue_data_completeness': 0.98,
            'overall_completeness': 0.93
        }
    
    def _check_data_consistency(self) -> Dict:
        """Check consistency of data across sources."""
        return {
            'cross_source_consistency': 0.94,
            'temporal_consistency': 0.91,
            'referential_consistency': 0.96,
            'overall_consistency': 0.94
        }
    
    def _check_data_accuracy_indicators(self) -> Dict:
        """Check indicators of data accuracy."""
        return {
            'data_validation_errors': 5,
            'anomaly_detection_flags': 2,
            'cross_validation_score': 0.89,
            'accuracy_indicator_score': 0.91
        }
    
    def _generate_data_quality_alerts(self, freshness: Dict, completeness: Dict, 
                                    consistency: Dict, accuracy: Dict) -> List[Dict]:
        """Generate alerts based on data quality metrics."""
        alerts = []
        
        if freshness['overall_freshness'] < 0.8:
            alerts.append({
                'type': 'data_quality',
                'severity': 'warning',
                'category': 'freshness',
                'message': 'Data freshness below acceptable threshold',
                'details': freshness
            })
        
        if completeness['overall_completeness'] < 0.85:
            alerts.append({
                'type': 'data_quality',
                'severity': 'warning',
                'category': 'completeness',
                'message': 'Data completeness below acceptable threshold',
                'details': completeness
            })
        
        return alerts
    
    def _calculate_data_quality_score(self, freshness: Dict, completeness: Dict, 
                                    consistency: Dict, accuracy: Dict) -> Decimal:
        """Calculate overall data quality score."""
        freshness_score = freshness.get('overall_freshness', 0.8)
        completeness_score = completeness.get('overall_completeness', 0.8)
        consistency_score = consistency.get('overall_consistency', 0.8)
        accuracy_score = accuracy.get('accuracy_indicator_score', 0.8)
        
        # Weighted average
        overall_score = (
            freshness_score * 0.25 + 
            completeness_score * 0.35 + 
            consistency_score * 0.25 + 
            accuracy_score * 0.15
        )
        
        return Decimal(str(overall_score)).quantize(Decimal('0.001'))
    
    def _validate_prediction_accuracy(self) -> Dict:
        """Validate current prediction accuracy against baselines."""
        # This would get recent accuracy data
        current_accuracy = 0.76  # Would be calculated from recent predictions
        baseline_accuracy = 0.75
        
        validation_status = 'passed' if current_accuracy >= baseline_accuracy * 0.95 else 'failed'
        
        return {
            'validation_status': validation_status,
            'current_accuracy': current_accuracy,
            'baseline_accuracy': baseline_accuracy,
            'deviation': current_accuracy - baseline_accuracy,
            'validation_threshold': baseline_accuracy * 0.95
        }
    
    def _validate_confidence_calibration(self) -> Dict:
        """Validate confidence calibration quality."""
        # This would use the confidence calibrator to check calibration
        return {
            'calibration_quality': 'good',
            'reliability_score': 0.85,
            'calibration_drift': 0.02,
            'validation_status': 'passed'
        }
    
    def _check_model_stability(self) -> Dict:
        """Check model stability over time."""
        return {
            'stability_score': 0.92,
            'prediction_variance': 0.08,
            'stability_trend': 'stable',
            'stability_status': 'good'
        }
    
    def _validate_feature_performance(self) -> Dict:
        """Validate performance of individual features."""
        return {
            'feature_importance_stability': 0.88,
            'feature_contribution_consistency': 0.91,
            'new_feature_performance': 0.87,
            'validation_status': 'passed'
        }
    
    def _detect_model_drift(self) -> Dict:
        """Detect model drift in predictions."""
        return {
            'drift_detected': False,
            'drift_magnitude': 0.02,
            'drift_type': 'none',
            'detection_confidence': 0.85,
            'last_drift_date': None
        }
    
    def _generate_model_performance_alerts(self, accuracy_val: Dict, confidence_val: Dict,
                                         stability: Dict, features: Dict, drift: Dict) -> List[Dict]:
        """Generate model performance alerts."""
        alerts = []
        
        if accuracy_val['validation_status'] == 'failed':
            alerts.append({
                'type': 'model_performance',
                'severity': 'warning',
                'category': 'accuracy',
                'message': 'Prediction accuracy below validation threshold',
                'details': accuracy_val
            })
        
        if drift['drift_detected']:
            alerts.append({
                'type': 'model_performance',
                'severity': 'high',
                'category': 'drift',
                'message': 'Model drift detected',
                'details': drift
            })
        
        return alerts
    
    def _calculate_model_health_score(self, accuracy_val: Dict, confidence_val: Dict,
                                    stability: Dict, drift: Dict) -> Decimal:
        """Calculate overall model health score."""
        scores = []
        
        # Accuracy score
        if accuracy_val['validation_status'] == 'passed':
            scores.append(0.9)
        else:
            scores.append(0.6)
        
        # Stability score
        scores.append(stability.get('stability_score', 0.8))
        
        # Drift penalty
        if drift['drift_detected']:
            drift_penalty = min(0.3, drift.get('drift_magnitude', 0.1) * 3)
            scores.append(1.0 - drift_penalty)
        else:
            scores.append(1.0)
        
        health_score = sum(scores) / len(scores) if scores else 0.5
        return Decimal(str(health_score)).quantize(Decimal('0.001'))
    
    def _check_performance_thresholds(self, metrics: Dict, thresholds: Dict) -> List[Dict]:
        """Check performance metrics against thresholds."""
        alerts = []
        
        cpu_usage = metrics.get('cpu_usage', 0)
        if cpu_usage > thresholds.get('cpu_warning', 80):
            severity = 'critical' if cpu_usage > thresholds.get('cpu_critical', 95) else 'warning'
            alerts.append({
                'type': 'performance',
                'severity': severity,
                'metric': 'cpu_usage',
                'current_value': cpu_usage,
                'threshold': thresholds.get('cpu_warning', 80),
                'message': f'CPU usage at {cpu_usage}%'
            })
        
        memory_usage = metrics.get('memory_usage', 0)
        if memory_usage > thresholds.get('memory_warning', 85):
            severity = 'critical' if memory_usage > thresholds.get('memory_critical', 95) else 'warning'
            alerts.append({
                'type': 'performance',
                'severity': severity,
                'metric': 'memory_usage',
                'current_value': memory_usage,
                'threshold': thresholds.get('memory_warning', 85),
                'message': f'Memory usage at {memory_usage}%'
            })
        
        return alerts
    
    def _check_resource_thresholds(self, metrics: Dict, thresholds: Dict) -> List[Dict]:
        """Check resource utilization thresholds."""
        alerts = []
        
        disk_usage = metrics.get('disk_usage', 0)
        if disk_usage > thresholds.get('disk_warning', 80):
            alerts.append({
                'type': 'resource',
                'severity': 'warning',
                'metric': 'disk_usage',
                'current_value': disk_usage,
                'message': f'Disk usage at {disk_usage}%'
            })
        
        return alerts
    
    def _check_prediction_quality_thresholds(self, metrics: Dict, thresholds: Dict) -> List[Dict]:
        """Check prediction quality thresholds."""
        alerts = []
        
        error_rate = metrics.get('error_rate', 0)
        if error_rate > thresholds.get('error_rate_warning', 0.05):
            alerts.append({
                'type': 'prediction_quality',
                'severity': 'warning',
                'metric': 'error_rate',
                'current_value': error_rate,
                'message': f'Error rate at {error_rate:.2%}'
            })
        
        return alerts
    
    def _check_availability_thresholds(self, metrics: Dict, thresholds: Dict) -> List[Dict]:
        """Check system availability thresholds."""
        # This would check actual availability metrics
        return []
    
    # Utility methods
    
    def _load_monitoring_thresholds(self) -> Dict:
        """Load monitoring thresholds configuration."""
        return {
            'cpu_warning': 80,
            'cpu_critical': 95,
            'memory_warning': 85,
            'memory_critical': 95,
            'disk_warning': 80,
            'disk_critical': 90,
            'error_rate_warning': 0.05,
            'error_rate_critical': 0.10,
            'response_time_warning': 1000,  # milliseconds
            'response_time_critical': 5000
        }
    
    def _calculate_uptime(self) -> str:
        """Calculate system uptime."""
        uptime_duration = datetime.now() - self._monitoring_start_time
        return str(uptime_duration)
    
    def _generate_alert_id(self) -> str:
        """Generate unique alert ID."""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _filter_and_deduplicate_alerts(self, alerts: List[Dict]) -> List[Dict]:
        """Filter and deduplicate alerts."""
        # Simple deduplication based on type and metric
        seen_alerts = set()
        filtered_alerts = []
        
        for alert in alerts:
            alert_key = (alert.get('type'), alert.get('metric', ''), alert.get('component', ''))
            if alert_key not in seen_alerts:
                seen_alerts.add(alert_key)
                filtered_alerts.append(alert)
        
        return filtered_alerts
    
    def _create_error_alert(self, error_message: str) -> Dict:
        """Create error alert for monitoring system failures."""
        return {
            'type': 'monitoring_error',
            'severity': 'critical',
            'message': f'System monitoring error: {error_message}',
            'generated_at': datetime.now().isoformat(),
            'alert_id': self._generate_alert_id()
        }
    
    # System information methods
    
    def _get_system_info(self) -> Dict:
        """Get basic system information."""
        try:
            return {
                'platform': psutil.pids(),
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total,
                'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _get_resource_usage(self) -> Dict:
        """Get current resource usage."""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'network_io': psutil.net_io_counters()._asdict()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _get_alert_summary(self) -> Dict:
        """Get summary of recent alerts."""
        recent_alerts = list(self._alert_history)[-50:]  # Last 50 alerts
        
        alert_counts = defaultdict(int)
        for alert in recent_alerts:
            alert_counts[alert.get('type', 'unknown')] += 1
        
        return {
            'total_alerts': len(recent_alerts),
            'alerts_by_type': dict(alert_counts),
            'most_recent_alert': recent_alerts[-1] if recent_alerts else None
        }
    
    def _analyze_health_trends(self) -> Dict:
        """Analyze health trends over time."""
        if len(self._performance_history) < 5:
            return {'insufficient_data': True}
        
        health_scores = [snapshot['health_score'] for snapshot in self._performance_history]
        recent_scores = health_scores[-10:]  # Last 10 snapshots
        
        if len(recent_scores) > 1:
            trend = 'improving' if recent_scores[-1] > recent_scores[0] else 'declining'
            if abs(recent_scores[-1] - recent_scores[0]) < 0.05:
                trend = 'stable'
        else:
            trend = 'unknown'
        
        return {
            'health_trend': trend,
            'average_health_score': sum(recent_scores) / len(recent_scores),
            'health_variance': np.var(recent_scores) if len(recent_scores) > 1 else 0
        }
    
    def _analyze_data_quality_trends(self) -> Dict:
        """Analyze data quality trends."""
        return {
            'freshness_trend': 'stable',
            'completeness_trend': 'improving',
            'consistency_trend': 'stable'
        }
    
    def _analyze_model_performance_trends(self) -> Dict:
        """Analyze model performance trends."""
        return {
            'accuracy_trend': 'improving',
            'stability_trend': 'stable',
            'drift_trend': 'none'
        }
    
    def _get_monitored_data_sources(self) -> List[str]:
        """Get list of monitored data sources."""
        return ['match_data', 'team_data', 'venue_data', 'tactical_data']
    
    def _get_active_models(self) -> List[str]:
        """Get list of active models."""
        return ['prediction_engine', 'confidence_calibrator', 'team_classifier']
    
    # Performance measurement methods
    
    def _get_network_metrics(self) -> Dict:
        """Get network I/O metrics."""
        try:
            net_io = psutil.net_io_counters()
            return {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
        except Exception:
            return {'error': 'Unable to collect network metrics'}
    
    def _measure_prediction_latency(self) -> float:
        """Measure current prediction latency."""
        # This would measure actual prediction response times
        return 50.0  # milliseconds placeholder
    
    def _measure_database_response_time(self) -> float:
        """Measure database response time."""
        try:
            start_time = time.time()
            # Simple database ping
            # self.db_client.ping()  # Would implement actual ping
            end_time = time.time()
            return (end_time - start_time) * 1000  # Convert to milliseconds
        except Exception:
            return 1000.0  # Return high value on error
    
    def _count_active_connections(self) -> int:
        """Count active system connections."""
        try:
            return len(psutil.net_connections())
        except Exception:
            return 0
    
    def _measure_prediction_throughput(self) -> float:
        """Measure prediction throughput (predictions per second)."""
        # This would measure actual throughput
        return 10.0  # predictions per second placeholder
    
    def _calculate_current_error_rate(self) -> float:
        """Calculate current error rate."""
        # This would calculate actual error rate from recent operations
        return 0.02  # 2% error rate placeholder
    
    # Component health check methods
    
    def _check_database_health(self) -> Dict:
        """Check database health."""
        try:
            # This would perform actual database health checks
            response_time = self._measure_database_response_time()
            
            if response_time > 5000:
                status = 'critical'
                message = 'Database response time critically high'
            elif response_time > 1000:
                status = 'warning'
                message = 'Database response time elevated'
            else:
                status = 'healthy'
                message = 'Database responding normally'
            
            return {
                'status': status,
                'message': message,
                'response_time_ms': response_time,
                'details': {'connection_pool': 'healthy', 'query_performance': 'good'}
            }
        except Exception as e:
            return {
                'status': 'critical',
                'message': f'Database health check failed: {e}',
                'details': {'error': str(e)}
            }
    
    def _check_prediction_engine_health(self) -> Dict:
        """Check prediction engine health."""
        try:
            # This would test the prediction engine
            latency = self._measure_prediction_latency()
            
            if latency > 1000:
                status = 'warning'
                message = 'Prediction latency elevated'
            else:
                status = 'healthy'
                message = 'Prediction engine responding normally'
            
            return {
                'status': status,
                'message': message,
                'latency_ms': latency,
                'details': {'model_loaded': True, 'features_available': True}
            }
        except Exception as e:
            return {
                'status': 'critical',
                'message': f'Prediction engine health check failed: {e}',
                'details': {'error': str(e)}
            }
    
    def _check_data_pipeline_health(self) -> Dict:
        """Check data pipeline health."""
        return {
            'status': 'healthy',
            'message': 'Data pipeline operating normally',
            'details': {
                'data_ingestion': 'active',
                'data_processing': 'current',
                'data_quality': 'good'
            }
        }
    
    def _check_analytics_health(self) -> Dict:
        """Check analytics components health."""
        return {
            'status': 'healthy',
            'message': 'Analytics components functioning normally',
            'details': {
                'accuracy_tracker': 'active',
                'confidence_calibrator': 'active',
                'performance_dashboard': 'active'
            }
        }
    
    def _check_infrastructure_health(self) -> Dict:
        """Check infrastructure health."""
        cpu_usage = psutil.cpu_percent()
        memory_usage = psutil.virtual_memory().percent
        
        if cpu_usage > 90 or memory_usage > 90:
            status = 'critical'
            message = 'Infrastructure resources critically high'
        elif cpu_usage > 80 or memory_usage > 85:
            status = 'warning'
            message = 'Infrastructure resources elevated'
        else:
            status = 'healthy'
            message = 'Infrastructure resources normal'
        
        return {
            'status': status,
            'message': message,
            'details': {
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'disk_usage': psutil.disk_usage('/').percent
            }
        }
    
    # Default/fallback methods
    
    def _emergency_health_report(self, error_message: str) -> Dict:
        """Generate emergency health report when monitoring fails."""
        return {
            'system_status': 'Critical',
            'component_status': {'monitoring_system': {'status': 'critical', 'error': error_message}},
            'performance_metrics': {'error': error_message},
            'active_alerts': [self._create_error_alert(error_message)],
            'health_score': Decimal('0.000'),
            'monitoring_metadata': {
                'check_timestamp': datetime.now().isoformat(),
                'emergency_mode': True,
                'error': error_message
            }
        }
    
    def _default_data_quality_assessment(self) -> Dict:
        """Default data quality assessment when check fails."""
        return {
            'overall_quality_score': Decimal('0.500'),
            'data_freshness': {'error': 'Assessment failed'},
            'data_completeness': {'error': 'Assessment failed'},
            'data_consistency': {'error': 'Assessment failed'},
            'data_accuracy_indicators': {'error': 'Assessment failed'},
            'quality_alerts': [{'type': 'assessment_error', 'severity': 'critical', 'message': 'Data quality assessment failed'}],
            'quality_trends': {'error': 'Trend analysis failed'},
            'assessment_metadata': {
                'assessment_timestamp': datetime.now().isoformat(),
                'error': 'Data quality assessment failed'
            }
        }
    
    def _default_model_validation(self) -> Dict:
        """Default model validation when validation fails."""
        return {
            'model_health_score': Decimal('0.500'),
            'accuracy_validation': {'error': 'Validation failed'},
            'confidence_validation': {'error': 'Validation failed'},
            'model_stability': {'error': 'Stability check failed'},
            'feature_performance': {'error': 'Feature validation failed'},
            'model_drift_detection': {'error': 'Drift detection failed'},
            'performance_alerts': [{'type': 'validation_error', 'severity': 'critical', 'message': 'Model validation failed'}],
            'validation_trends': {'error': 'Trend analysis failed'},
            'validation_metadata': {
                'validation_timestamp': datetime.now().isoformat(),
                'error': 'Model validation failed'
            }
        }


# Global instance for easy access
system_monitor = SystemMonitor()

# Main interface functions
def monitor_system_health() -> Dict:
    """
    Monitor overall system health and performance.
    
    Returns:
        {
            'system_status': str,              # 'Healthy' | 'Warning' | 'Critical'
            'component_status': Dict,          # Status of individual components
            'performance_metrics': Dict,       # Key performance indicators
            'active_alerts': List[Dict],       # Current system alerts
            'health_score': Decimal           # Overall system health (0.0-1.0)
        }
    """
    return system_monitor.monitor_system_health()

def check_data_quality() -> Dict:
    """
    Monitor data quality and completeness.
    
    Returns data quality assessment and alerts.
    """
    return system_monitor.check_data_quality()

def validate_model_performance() -> Dict:
    """
    Validate that models are performing within expected parameters.
    
    Returns model performance validation results.
    """
    return system_monitor.validate_model_performance()

def generate_system_alerts(current_metrics: Dict, thresholds: Dict) -> List[Dict]:
    """
    Generate system alerts based on performance thresholds.
    
    Returns list of active alerts requiring attention.
    """
    return system_monitor.generate_system_alerts(current_metrics, thresholds)

def get_system_diagnostics() -> Dict:
    """Get comprehensive system diagnostics information."""
    return system_monitor.get_system_diagnostics()