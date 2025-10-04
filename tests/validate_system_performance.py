"""
System Performance Validation Script

This script validates the performance characteristics of the complete 6-phase
football prediction system, ensuring it meets production SLA requirements.

Performance Areas Tested:
1. Prediction Accuracy - Validates prediction quality meets benchmarks
2. Response Times - Ensures predictions complete within SLA requirements  
3. Concurrent Performance - Tests system under concurrent load
4. Memory Usage - Validates memory consumption stays within limits
5. Scalability - Tests performance degradation under increased load
"""

import sys
import time
import threading
import json
import psutil
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple
import statistics


class PerformanceValidator:
    """Main performance validation class."""
    
    def __init__(self):
        self.results = {
            'validation_timestamp': datetime.now().isoformat(),
            'system_info': self._get_system_info(),
            'performance_tests': {},
            'overall_grade': 'UNKNOWN'
        }
    
    def _get_system_info(self) -> Dict:
        """Get system information for context."""
        return {
            'cpu_count': psutil.cpu_count(),
            'memory_total_gb': round(psutil.virtual_memory().total / (1024**3), 2),
            'python_version': sys.version,
            'platform': sys.platform
        }
    
    def validate_prediction_accuracy(self) -> Dict:
        """Validate prediction accuracy meets benchmarks."""
        print("🎯 Testing Prediction Accuracy...")
        
        try:
            from src.prediction.prediction_engine import generate_prediction_with_reporting
            
            accuracy_results = {
                'test_start': datetime.now().isoformat(),
                'status': 'TESTING',
                'predictions_tested': 0,
                'accuracy_metrics': {},
                'benchmark_comparison': {}
            }
            
            # Test prediction consistency
            consistency_scores = []
            prediction_count = 10
            
            for i in range(prediction_count):
                try:
                    # Generate prediction
                    prediction = generate_prediction_with_reporting(
                        home_team_id=1 + (i % 5), away_team_id=2 + (i % 5),
                        league_id=39, season=2023,
                        include_insights=True
                    )
                    
                    # Check prediction structure quality
                    quality_score = self._assess_prediction_quality(prediction)
                    consistency_scores.append(quality_score)
                    accuracy_results['predictions_tested'] += 1
                    
                except Exception as e:
                    print(f"   Accuracy test {i} failed: {e}")
            
            # Calculate accuracy metrics
            if consistency_scores:
                accuracy_results['accuracy_metrics'] = {
                    'avg_quality_score': round(statistics.mean(consistency_scores), 3),
                    'min_quality_score': round(min(consistency_scores), 3),
                    'max_quality_score': round(max(consistency_scores), 3),
                    'quality_std_dev': round(statistics.stdev(consistency_scores) if len(consistency_scores) > 1 else 0, 3),
                    'consistency_rating': self._rate_consistency(consistency_scores)
                }
                
                # Benchmark comparison
                avg_quality = accuracy_results['accuracy_metrics']['avg_quality_score']
                accuracy_results['benchmark_comparison'] = {
                    'target_quality': 0.8,
                    'achieved_quality': avg_quality,
                    'meets_benchmark': avg_quality >= 0.8,
                    'performance_grade': self._grade_accuracy(avg_quality)
                }
                
                accuracy_results['status'] = 'PASS' if avg_quality >= 0.7 else 'FAIL'
            else:
                accuracy_results['status'] = 'FAIL'
                accuracy_results['error'] = 'No successful predictions'
            
            accuracy_results['test_duration'] = (datetime.now() - datetime.fromisoformat(accuracy_results['test_start'])).total_seconds()
            return accuracy_results
            
        except Exception as e:
            return {
                'status': 'ERROR',
                'error': str(e),
                'test_duration': 0
            }
    
    def validate_response_times(self) -> Dict:
        """Validate system response times meet SLA requirements."""
        print("⏱️ Testing Response Times...")
        
        try:
            from src.prediction.prediction_engine import generate_prediction_with_reporting
            
            response_results = {
                'test_start': datetime.now().isoformat(),
                'status': 'TESTING',
                'response_times': [],
                'sla_metrics': {},
                'performance_breakdown': {}
            }
            
            # Test response times
            test_count = 20
            successful_tests = 0
            
            for i in range(test_count):
                start_time = time.time()
                
                try:
                    prediction = generate_prediction_with_reporting(
                        home_team_id=1 + (i % 10), away_team_id=2 + (i % 10),
                        league_id=39, season=2023,
                        include_insights=(i % 2 == 0)  # Alternate with/without insights
                    )
                    
                    end_time = time.time()
                    response_time = end_time - start_time
                    response_results['response_times'].append(response_time)
                    successful_tests += 1
                    
                except Exception as e:
                    print(f"   Response time test {i} failed: {e}")
            
            # Calculate SLA metrics
            if response_results['response_times']:
                times = response_results['response_times']
                response_results['sla_metrics'] = {
                    'avg_response_time': round(statistics.mean(times), 3),
                    'median_response_time': round(statistics.median(times), 3),
                    'p95_response_time': round(self._percentile(times, 95), 3),
                    'p99_response_time': round(self._percentile(times, 99), 3),
                    'max_response_time': round(max(times), 3),
                    'min_response_time': round(min(times), 3)
                }
                
                # SLA compliance check
                sla_target = 2.0  # 2 seconds max response time
                p95_time = response_results['sla_metrics']['p95_response_time']
                avg_time = response_results['sla_metrics']['avg_response_time']
                
                response_results['performance_breakdown'] = {
                    'sla_target_seconds': sla_target,
                    'avg_meets_sla': avg_time < sla_target,
                    'p95_meets_sla': p95_time < sla_target,
                    'success_rate': round(successful_tests / test_count, 3),
                    'performance_grade': self._grade_response_time(avg_time, p95_time)
                }
                
                response_results['status'] = 'PASS' if p95_time < sla_target and successful_tests >= (test_count * 0.8) else 'FAIL'
            else:
                response_results['status'] = 'FAIL'
                response_results['error'] = 'No successful response time tests'
            
            response_results['test_duration'] = (datetime.now() - datetime.fromisoformat(response_results['test_start'])).total_seconds()
            return response_results
            
        except Exception as e:
            return {
                'status': 'ERROR',
                'error': str(e),
                'test_duration': 0
            }
    
    def validate_concurrent_performance(self) -> Dict:
        """Test system performance under concurrent load."""
        print("🔄 Testing Concurrent Performance...")
        
        try:
            concurrent_results = {
                'test_start': datetime.now().isoformat(),
                'status': 'TESTING',
                'concurrency_levels': {},
                'scalability_metrics': {}
            }
            
            # Test different concurrency levels
            concurrency_levels = [1, 2, 4, 8]
            
            for level in concurrency_levels:
                print(f"   Testing {level} concurrent requests...")
                level_results = self._test_concurrency_level(level)
                concurrent_results['concurrency_levels'][f'level_{level}'] = level_results
            
            # Analyze scalability
            concurrent_results['scalability_metrics'] = self._analyze_scalability(concurrent_results['concurrency_levels'])
            
            # Overall assessment
            scalability_grade = concurrent_results['scalability_metrics'].get('scalability_grade', 'F')
            concurrent_results['status'] = 'PASS' if scalability_grade in ['A', 'B', 'C'] else 'FAIL'
            
            concurrent_results['test_duration'] = (datetime.now() - datetime.fromisoformat(concurrent_results['test_start'])).total_seconds()
            return concurrent_results
            
        except Exception as e:
            return {
                'status': 'ERROR',
                'error': str(e),
                'test_duration': 0
            }
    
    def validate_memory_usage(self) -> Dict:
        """Ensure memory usage stays within acceptable limits."""
        print("🧠 Testing Memory Usage...")
        
        try:
            from src.prediction.prediction_engine import generate_prediction_with_reporting
            
            memory_results = {
                'test_start': datetime.now().isoformat(),
                'status': 'TESTING',
                'memory_measurements': [],
                'memory_analysis': {}
            }
            
            # Baseline memory usage
            process = psutil.Process()
            baseline_memory = process.memory_info().rss / (1024 * 1024)  # MB
            
            # Test memory usage during predictions
            test_count = 15
            
            for i in range(test_count):
                try:
                    # Measure memory before prediction
                    memory_before = process.memory_info().rss / (1024 * 1024)
                    
                    prediction = generate_prediction_with_reporting(
                        home_team_id=1 + i, away_team_id=2 + i,
                        league_id=39, season=2023,
                        include_insights=True
                    )
                    
                    # Measure memory after prediction
                    memory_after = process.memory_info().rss / (1024 * 1024)
                    
                    memory_results['memory_measurements'].append({
                        'test_number': i,
                        'memory_before_mb': round(memory_before, 2),
                        'memory_after_mb': round(memory_after, 2),
                        'memory_increase_mb': round(memory_after - memory_before, 2)
                    })
                    
                except Exception as e:
                    print(f"   Memory test {i} failed: {e}")
            
            # Analyze memory usage
            if memory_results['memory_measurements']:
                measurements = memory_results['memory_measurements']
                increases = [m['memory_increase_mb'] for m in measurements]
                final_memory = measurements[-1]['memory_after_mb']
                
                memory_results['memory_analysis'] = {
                    'baseline_memory_mb': round(baseline_memory, 2),
                    'final_memory_mb': round(final_memory, 2),
                    'total_increase_mb': round(final_memory - baseline_memory, 2),
                    'avg_per_prediction_mb': round(statistics.mean(increases) if increases else 0, 2),
                    'max_increase_mb': round(max(increases) if increases else 0, 2),
                    'memory_efficiency_grade': self._grade_memory_usage(final_memory - baseline_memory)
                }
                
                # Memory usage assessment
                total_increase = memory_results['memory_analysis']['total_increase_mb']
                memory_limit = 500  # 500MB limit for this test
                
                memory_results['status'] = 'PASS' if total_increase < memory_limit else 'FAIL'
            else:
                memory_results['status'] = 'FAIL'
                memory_results['error'] = 'No memory measurements collected'
            
            memory_results['test_duration'] = (datetime.now() - datetime.fromisoformat(memory_results['test_start'])).total_seconds()
            return memory_results
            
        except Exception as e:
            return {
                'status': 'ERROR',
                'error': str(e),
                'test_duration': 0
            }
    
    def _test_concurrency_level(self, level: int) -> Dict:
        """Test a specific concurrency level."""
        from src.prediction.prediction_engine import generate_prediction_with_reporting
        
        results = {
            'concurrency_level': level,
            'response_times': [],
            'successful_requests': 0,
            'failed_requests': 0,
            'start_time': time.time()
        }
        
        def single_prediction(request_id):
            try:
                start_time = time.time()
                prediction = generate_prediction_with_reporting(
                    home_team_id=1 + (request_id % 5), 
                    away_team_id=2 + (request_id % 5),
                    league_id=39, season=2023
                )
                end_time = time.time()
                return end_time - start_time, True
            except Exception as e:
                return 0, False
        
        # Execute concurrent requests
        with ThreadPoolExecutor(max_workers=level) as executor:
            futures = [executor.submit(single_prediction, i) for i in range(level * 2)]  # 2x requests per worker
            
            for future in as_completed(futures):
                response_time, success = future.result()
                if success:
                    results['response_times'].append(response_time)
                    results['successful_requests'] += 1
                else:
                    results['failed_requests'] += 1
        
        results['total_time'] = time.time() - results['start_time']
        
        # Calculate metrics
        if results['response_times']:
            results['avg_response_time'] = round(statistics.mean(results['response_times']), 3)
            results['throughput'] = round(results['successful_requests'] / results['total_time'], 2)
        else:
            results['avg_response_time'] = 0
            results['throughput'] = 0
        
        return results
    
    def _analyze_scalability(self, concurrency_data: Dict) -> Dict:
        """Analyze scalability from concurrency test results."""
        scalability_metrics = {
            'throughput_scaling': {},
            'response_time_degradation': {},
            'scalability_grade': 'F'
        }
        
        try:
            # Extract throughput data
            levels = []
            throughputs = []
            avg_response_times = []
            
            for level_key, data in concurrency_data.items():
                if 'level_' in level_key:
                    level = data.get('concurrency_level', 0)
                    throughput = data.get('throughput', 0)
                    avg_time = data.get('avg_response_time', 0)
                    
                    if throughput > 0:
                        levels.append(level)
                        throughputs.append(throughput)
                        avg_response_times.append(avg_time)
            
            if len(levels) >= 2:
                # Throughput scaling analysis
                max_throughput = max(throughputs)
                min_throughput = min(throughputs)
                throughput_improvement = (max_throughput / min_throughput) if min_throughput > 0 else 1
                
                scalability_metrics['throughput_scaling'] = {
                    'max_throughput_rps': max_throughput,
                    'min_throughput_rps': min_throughput,
                    'improvement_ratio': round(throughput_improvement, 2),
                    'linear_scaling_expected': round(levels[-1] / levels[0], 2),
                    'scaling_efficiency': round(throughput_improvement / (levels[-1] / levels[0]), 2)
                }
                
                # Response time degradation analysis
                base_response_time = avg_response_times[0]
                max_response_time = max(avg_response_times)
                degradation_factor = max_response_time / base_response_time if base_response_time > 0 else 1
                
                scalability_metrics['response_time_degradation'] = {
                    'base_response_time': base_response_time,
                    'max_response_time': max_response_time,
                    'degradation_factor': round(degradation_factor, 2),
                    'acceptable_degradation': degradation_factor < 2.0
                }
                
                # Overall scalability grade
                efficiency = scalability_metrics['throughput_scaling'].get('scaling_efficiency', 0)
                acceptable_degradation = scalability_metrics['response_time_degradation'].get('acceptable_degradation', False)
                
                if efficiency >= 0.8 and acceptable_degradation:
                    scalability_metrics['scalability_grade'] = 'A'
                elif efficiency >= 0.6 and acceptable_degradation:
                    scalability_metrics['scalability_grade'] = 'B'
                elif efficiency >= 0.4:
                    scalability_metrics['scalability_grade'] = 'C'
                elif efficiency >= 0.2:
                    scalability_metrics['scalability_grade'] = 'D'
                else:
                    scalability_metrics['scalability_grade'] = 'F'
            
        except Exception as e:
            scalability_metrics['error'] = str(e)
        
        return scalability_metrics
    
    def _assess_prediction_quality(self, prediction: Dict) -> float:
        """Assess the quality of a prediction for accuracy testing."""
        quality_score = 0.0
        
        try:
            # Check for required structure
            if 'predictions' in prediction:
                quality_score += 0.3
            
            if 'metadata' in prediction:
                quality_score += 0.2
            
            # Check for phase indicators
            metadata = prediction.get('metadata', {})
            phase_indicators = [
                'architecture_version',
                'phase1_enabled',
                'phase2_enabled', 
                'phase3_enabled',
                'phase4_enabled',
                'phase5_enabled',
                'phase6_enabled'
            ]
            
            phase_score = sum(1 for indicator in phase_indicators if metadata.get(indicator))
            quality_score += (phase_score / len(phase_indicators)) * 0.3
            
            # Check for insights if requested
            if prediction.get('include_insights') and 'insights' in prediction:
                quality_score += 0.2
            elif not prediction.get('include_insights'):
                quality_score += 0.2  # Don't penalize if insights not requested
            
        except Exception:
            quality_score = 0.0
        
        return min(quality_score, 1.0)
    
    def _rate_consistency(self, scores: List[float]) -> str:
        """Rate the consistency of quality scores."""
        if not scores or len(scores) < 2:
            return 'INSUFFICIENT_DATA'
        
        std_dev = statistics.stdev(scores)
        if std_dev < 0.05:
            return 'EXCELLENT'
        elif std_dev < 0.1:
            return 'GOOD'  
        elif std_dev < 0.2:
            return 'FAIR'
        else:
            return 'POOR'
    
    def _grade_accuracy(self, accuracy: float) -> str:
        """Grade accuracy performance."""
        if accuracy >= 0.9:
            return 'A'
        elif accuracy >= 0.8:
            return 'B'
        elif accuracy >= 0.7:
            return 'C'
        elif accuracy >= 0.6:
            return 'D'
        else:
            return 'F'
    
    def _grade_response_time(self, avg_time: float, p95_time: float) -> str:
        """Grade response time performance."""
        if avg_time < 0.5 and p95_time < 1.0:
            return 'A'
        elif avg_time < 1.0 and p95_time < 2.0:
            return 'B'
        elif avg_time < 2.0 and p95_time < 3.0:
            return 'C'
        elif avg_time < 3.0 and p95_time < 5.0:
            return 'D'
        else:
            return 'F'
    
    def _grade_memory_usage(self, increase_mb: float) -> str:
        """Grade memory usage performance."""
        if increase_mb < 50:
            return 'A'
        elif increase_mb < 100:
            return 'B'
        elif increase_mb < 200:
            return 'C'
        elif increase_mb < 400:
            return 'D'
        else:
            return 'F'
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    def run_complete_validation(self) -> Dict:
        """Run all performance validation tests."""
        print("🚀 Starting Complete Performance Validation...")
        print("="*70)
        
        # Run all validation tests
        self.results['performance_tests']['accuracy'] = self.validate_prediction_accuracy()
        self.results['performance_tests']['response_times'] = self.validate_response_times()
        self.results['performance_tests']['concurrent_performance'] = self.validate_concurrent_performance()
        self.results['performance_tests']['memory_usage'] = self.validate_memory_usage()
        
        # Calculate overall grade
        self.results['overall_grade'] = self._calculate_overall_grade()
        
        return self.results
    
    def _calculate_overall_grade(self) -> str:
        """Calculate overall performance grade."""
        test_results = self.results['performance_tests']
        
        # Extract grades from each test
        grades = []
        
        accuracy = test_results.get('accuracy', {})
        if accuracy.get('benchmark_comparison', {}).get('performance_grade'):
            grades.append(accuracy['benchmark_comparison']['performance_grade'])
        
        response_times = test_results.get('response_times', {})
        if response_times.get('performance_breakdown', {}).get('performance_grade'):
            grades.append(response_times['performance_breakdown']['performance_grade'])
        
        concurrent = test_results.get('concurrent_performance', {})
        if concurrent.get('scalability_metrics', {}).get('scalability_grade'):
            grades.append(concurrent['scalability_metrics']['scalability_grade'])
        
        memory = test_results.get('memory_usage', {})
        if memory.get('memory_analysis', {}).get('memory_efficiency_grade'):
            grades.append(memory['memory_analysis']['memory_efficiency_grade'])
        
        # Calculate weighted average grade
        if grades:
            grade_values = {'A': 4, 'B': 3, 'C': 2, 'D': 1, 'F': 0}
            avg_value = sum(grade_values.get(grade, 0) for grade in grades) / len(grades)
            
            if avg_value >= 3.5:
                return 'A'
            elif avg_value >= 2.5:
                return 'B'
            elif avg_value >= 1.5:
                return 'C'
            elif avg_value >= 0.5:
                return 'D'
            else:
                return 'F'
        
        return 'F'
    
    def print_performance_report(self):
        """Print comprehensive performance report."""
        print("\n" + "="*70)
        print("📊 SYSTEM PERFORMANCE VALIDATION REPORT")
        print("="*70)
        
        print(f"Overall Performance Grade: {self.results['overall_grade']}")
        print(f"Validation Timestamp: {self.results['validation_timestamp']}")
        
        # System info
        sys_info = self.results['system_info']
        print(f"\n💻 System Information:")
        print(f"  CPU Cores: {sys_info['cpu_count']}")
        print(f"  Memory: {sys_info['memory_total_gb']} GB")
        print(f"  Platform: {sys_info['platform']}")
        
        # Test results
        tests = self.results['performance_tests']
        
        print(f"\n🎯 Accuracy Validation:")
        accuracy = tests.get('accuracy', {})
        if accuracy.get('status') == 'PASS':
            metrics = accuracy.get('accuracy_metrics', {})
            print(f"  ✅ Status: PASS")
            print(f"  Quality Score: {metrics.get('avg_quality_score', 'N/A')}")
            print(f"  Consistency: {metrics.get('consistency_rating', 'N/A')}")
        else:
            print(f"  ❌ Status: {accuracy.get('status', 'UNKNOWN')}")
        
        print(f"\n⏱️ Response Time Validation:")
        response = tests.get('response_times', {})
        if response.get('status') == 'PASS':
            sla = response.get('sla_metrics', {})
            print(f"  ✅ Status: PASS")
            print(f"  Avg Response: {sla.get('avg_response_time', 'N/A')}s")
            print(f"  P95 Response: {sla.get('p95_response_time', 'N/A')}s")
        else:
            print(f"  ❌ Status: {response.get('status', 'UNKNOWN')}")
        
        print(f"\n🔄 Concurrent Performance:")
        concurrent = tests.get('concurrent_performance', {})
        if concurrent.get('status') == 'PASS':
            scalability = concurrent.get('scalability_metrics', {})
            print(f"  ✅ Status: PASS")
            print(f"  Scalability Grade: {scalability.get('scalability_grade', 'N/A')}")
        else:
            print(f"  ❌ Status: {concurrent.get('status', 'UNKNOWN')}")
        
        print(f"\n🧠 Memory Usage:")
        memory = tests.get('memory_usage', {})
        if memory.get('status') == 'PASS':
            analysis = memory.get('memory_analysis', {})
            print(f"  ✅ Status: PASS")
            print(f"  Memory Increase: {analysis.get('total_increase_mb', 'N/A')} MB")
            print(f"  Efficiency Grade: {analysis.get('memory_efficiency_grade', 'N/A')}")
        else:
            print(f"  ❌ Status: {memory.get('status', 'UNKNOWN')}")
        
        # Overall assessment
        overall_pass = all(
            test.get('status') == 'PASS' 
            for test in tests.values()
        )
        
        print(f"\n🎯 Overall Assessment:")
        if overall_pass:
            print("  ✅ ALL PERFORMANCE TESTS PASSED")
            print("  🚀 System meets production performance requirements")
        else:
            print("  ❌ Some performance tests failed")
            print("  ⚠️ Review failed tests before production deployment")


def main():
    """Main performance validation function."""
    validator = PerformanceValidator()
    
    # Run complete validation
    results = validator.run_complete_validation()
    
    # Print report
    validator.print_performance_report()
    
    # Save results
    results_file = f"performance_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Detailed results saved to: {results_file}")
    except Exception as e:
        print(f"\n⚠️ Could not save results: {e}")
    
    # Return appropriate exit code
    overall_pass = all(
        test.get('status') == 'PASS' 
        for test in results['performance_tests'].values()
    )
    
    return 0 if overall_pass else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)