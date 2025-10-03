"""
Transition Management System for Architecture Version Migration

This module implements the hierarchical fallback strategy to prevent multiplier
contamination during architecture transitions. It ensures that only compatible
multipliers are used and provides safe fallbacks when clean data is unavailable.

Hierarchical Fallback Strategy:
1. Team-level v2 multipliers (if available, sample_size >= 15)
2. League-level v2 multipliers (if available, sample_size >= 30)  
3. Neutral baseline (multiplier = 1.0)

This prevents circular error propagation by never mixing multipliers from
different architecture versions.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import logging

from .version_manager import VersionManager

class TransitionManager:
    """
    Manages architecture version transitions and implements fallback strategies.
    
    This is the core component that prevents multiplier contamination by ensuring
    only same-version multipliers are used in calculations.
    """
    
    def __init__(self):
        self.version_manager = VersionManager()
        self.logger = logging.getLogger(__name__)
        
        # Configuration - adjust based on data availability and accuracy requirements
        self.config = {
            'strategy': 'hierarchical_fallback',
            'v2_deployment_date': datetime(2025, 10, 15),  # Update with actual deployment date
            'min_team_sample_size': 15,   # Minimum v2 predictions needed for team multipliers
            'min_league_sample_size': 30, # Minimum v2 predictions needed for league multipliers
            'confidence_reduction_factor': 0.7,  # Reduce confidence when falling back to league level
        }
    
    def get_baseline_definition(self) -> Dict:
        """
        Returns the "clean baseline" - parameters calculated WITHOUT
        any correction multipliers to prevent contamination.
        
        The baseline for v2.0 architecture is the raw enhanced model output:
        - Segmented parameters by opponent strength
        - Form adjustments (when implemented)
        - Tactical matchup adjustments (when implemented)
        - Home advantage factors
        - NO multipliers applied
        
        Returns:
            dict: Baseline definition and metadata
        """
        return {
            'definition': 'raw_enhanced_model_output_no_multipliers',
            'components': [
                'segmented_parameter_by_opponent_tier',
                'form_adjustment_when_available',
                'tactical_matchup_adjustment_when_available',
                'home_advantage_factor'
            ],
            'excluded_components': [
                'correction_multipliers',
                'legacy_adjustments'
            ],
            'architecture_version': self.version_manager.get_current_version(),
            'multiplier_strategy': 'hierarchical_fallback_same_version_only'
        }
    
    def should_use_baseline(self, requested_version: str) -> Tuple[bool, str]:
        """
        Determines if baseline should be used instead of potentially contaminated historical data.
        
        Args:
            requested_version: Version being requested for calculations
            
        Returns:
            tuple: (use_baseline: bool, reason: str)
        """
        current_version = self.version_manager.get_current_version()
        
        # If versions don't match, use baseline to prevent contamination
        if requested_version != current_version:
            return True, f"Version mismatch: requested {requested_version}, current {current_version}"
        
        # Check if we're still in early deployment phase
        deployment_date = self.config['v2_deployment_date']
        days_since_deployment = (datetime.now() - deployment_date).days
        
        if days_since_deployment < 0:
            return True, f"Pre-deployment: {abs(days_since_deployment)} days until v2.0 deployment"
        
        if days_since_deployment < 7:
            return True, f"Early deployment phase: only {days_since_deployment} days since v2.0 deployment"
        
        return False, "Sufficient time has passed since deployment for data accumulation"
    
    def get_transition_strategy(self, target_version: str) -> Dict:
        """
        Returns strategy for transitioning to new architecture version.
        
        Implements "Hierarchical Fallback with Version Tracking" approach.
        
        Args:
            target_version: Version to transition to
            
        Returns:
            dict: Transition strategy configuration
        """
        current_version = self.version_manager.get_current_version()
        
        return {
            'strategy_name': 'hierarchical_fallback_with_version_tracking',
            'current_version': current_version,
            'target_version': target_version,
            'hierarchy': [
                {
                    'level': 1,
                    'source': 'team_level_same_version',
                    'min_sample_size': self.config['min_team_sample_size'],
                    'confidence_factor': 1.0
                },
                {
                    'level': 2,
                    'source': 'league_level_same_version', 
                    'min_sample_size': self.config['min_league_sample_size'],
                    'confidence_factor': self.config['confidence_reduction_factor']
                },
                {
                    'level': 3,
                    'source': 'neutral_baseline',
                    'min_sample_size': 0,
                    'confidence_factor': 0.2
                }
            ],
            'contamination_prevention': {
                'version_filtering_enabled': True,
                'cross_version_multipliers_blocked': True,
                'fallback_to_neutral_when_incompatible': True
            }
        }
    
    def validate_data_integrity(self, data: Dict, expected_version: str) -> Tuple[bool, str]:
        """
        Validates that data hasn't been contaminated by wrong-version multipliers.
        
        CRITICAL for preventing circular error propagation.
        
        Args:
            data: Data dictionary to validate
            expected_version: Expected architecture version
            
        Returns:
            tuple: (is_valid: bool, validation_message: str)
        """
        if not data:
            return False, "No data provided for validation"
        
        # Check for version information
        if 'architecture_version' not in data:
            return False, "Missing architecture version in data - potential contamination risk"
        
        data_version = data['architecture_version']
        
        # Validate version compatibility
        compatible, reason = self.version_manager.validate_multiplier_compatibility(
            data_version, expected_version
        )
        
        if not compatible:
            return False, f"Data integrity violation: {reason}"
        
        # Check for contamination indicators
        contamination_indicators = [
            'mixed_version_calculations',
            'cross_version_multipliers_applied',
            'legacy_adjustments_mixed_with_new'
        ]
        
        for indicator in contamination_indicators:
            if data.get(indicator, False):
                return False, f"Contamination detected: {indicator}"
        
        # Validate sample size consistency
        sample_size = data.get('sample_size', 0)
        calculation_count = data.get('calculation_count', sample_size)
        
        if abs(sample_size - calculation_count) > 1:  # Allow for small rounding differences
            return False, f"Sample size inconsistency: reported {sample_size}, calculated {calculation_count}"
        
        return True, "Data integrity validated - no contamination detected"
    
    def get_effective_multipliers(self, team_params: Dict, league_params: Dict) -> Dict:
        """
        Central function to determine which multipliers to use during transition.
        
        Implements hierarchical fallback strategy to prevent multiplier contamination.
        
        Args:
            team_params: Team-level parameters
            league_params: League-level parameters
            
        Returns:
            dict: Effective multipliers with metadata about source and confidence
        """
        return self._hierarchical_fallback_strategy(team_params, league_params)
    
    def _hierarchical_fallback_strategy(self, team_params: Dict, league_params: Dict) -> Dict:
        """
        Strategy: Use hierarchy - team v2 → league v2 → neutral.
        Only use multipliers calculated against same architecture version.
        
        Args:
            team_params: Team-level parameters 
            league_params: League-level parameters
            
        Returns:
            dict: Selected multipliers with source tracking
        """
        current_version = self.version_manager.get_current_version()
        
        # Level 1: Try team-level same-version multipliers
        team_result = self._try_team_level_multipliers(team_params, current_version)
        if team_result:
            return team_result
        
        # Level 2: Try league-level same-version multipliers
        league_result = self._try_league_level_multipliers(league_params, current_version)
        if league_result:
            return league_result
        
        # Level 3: Fallback to neutral baseline
        return self._get_neutral_baseline_multipliers(team_params, league_params, current_version)
    
    def _try_team_level_multipliers(self, team_params: Dict, current_version: str) -> Optional[Dict]:
        """Try to use team-level multipliers if they meet quality criteria."""
        if not team_params or team_params.get('architecture_version') != current_version:
            return None
        
        sample_size = team_params.get('sample_size', 0)
        if sample_size < self.config['min_team_sample_size']:
            return None
        
        # Validate data integrity
        is_valid, validation_msg = self.validate_data_integrity(team_params, current_version)
        if not is_valid:
            self.logger.warning(f"Team-level data failed validation: {validation_msg}")
            return None
        
        return {
            'home_multiplier': Decimal(str(team_params.get('home_multiplier', 1.0))),
            'away_multiplier': Decimal(str(team_params.get('away_multiplier', 1.0))),
            'total_multiplier': Decimal(str(team_params.get('total_multiplier', 1.0))),
            'confidence': Decimal(str(team_params.get('confidence', 0.8))),
            'source': 'team_level_v2',
            'strategy': 'hierarchical_fallback',
            'sample_size': sample_size,
            'architecture_version': current_version,
            'validation_passed': True
        }
    
    def _try_league_level_multipliers(self, league_params: Dict, current_version: str) -> Optional[Dict]:
        """Try to use league-level multipliers if they meet quality criteria."""
        if not league_params or league_params.get('architecture_version') != current_version:
            return None
        
        sample_size = league_params.get('sample_size', 0)
        if sample_size < self.config['min_league_sample_size']:
            return None
        
        # Validate data integrity
        is_valid, validation_msg = self.validate_data_integrity(league_params, current_version)
        if not is_valid:
            self.logger.warning(f"League-level data failed validation: {validation_msg}")
            return None
        
        # Reduce confidence for league-level multipliers
        base_confidence = league_params.get('confidence', 0.6)
        reduced_confidence = float(base_confidence) * self.config['confidence_reduction_factor']
        
        return {
            'home_multiplier': Decimal(str(league_params.get('home_multiplier', 1.0))),
            'away_multiplier': Decimal(str(league_params.get('away_multiplier', 1.0))),
            'total_multiplier': Decimal(str(league_params.get('total_multiplier', 1.0))),
            'confidence': Decimal(str(reduced_confidence)),
            'source': 'league_level_v2',
            'strategy': 'hierarchical_fallback',
            'sample_size': sample_size,
            'architecture_version': current_version,
            'validation_passed': True,
            'confidence_reduction_applied': True
        }
    
    def _get_neutral_baseline_multipliers(self, team_params: Dict, league_params: Dict, 
                                        current_version: str) -> Dict:
        """Fallback to neutral baseline when no compatible multipliers are available."""
        deployment_date = self.config['v2_deployment_date']
        days_since_deployment = (datetime.now() - deployment_date).days
        
        # Determine why we're using neutral baseline
        reasons = []
        
        if team_params.get('architecture_version') != current_version:
            reasons.append('team_version_mismatch')
        if team_params.get('sample_size', 0) < self.config['min_team_sample_size']:
            reasons.append('insufficient_team_samples')
            
        if league_params.get('architecture_version') != current_version:
            reasons.append('league_version_mismatch')
        if league_params.get('sample_size', 0) < self.config['min_league_sample_size']:
            reasons.append('insufficient_league_samples')
        
        return {
            'home_multiplier': Decimal('1.0'),
            'away_multiplier': Decimal('1.0'),
            'total_multiplier': Decimal('1.0'),
            'confidence': Decimal('0.2'),
            'source': 'neutral_baseline_insufficient_clean_data',
            'strategy': 'hierarchical_fallback',
            'days_since_deployment': days_since_deployment,
            'team_sample_size': team_params.get('sample_size', 0),
            'league_sample_size': league_params.get('sample_size', 0),
            'fallback_reasons': reasons,
            'architecture_version': current_version,
            'contamination_prevention': 'active'
        }


# Convenience functions for external use

def get_transition_multipliers(team_params: Dict, league_params: Dict) -> Dict:
    """
    Convenience function to get effective multipliers during transition.
    
    This is the main entry point used throughout the system.
    
    Args:
        team_params: Team-level parameters
        league_params: League-level parameters
        
    Returns:
        dict: Effective multipliers with source tracking
    """
    manager = TransitionManager()
    return manager.get_effective_multipliers(team_params, league_params)


def validate_parameter_integrity(data: Dict, expected_version: str = None) -> Tuple[bool, str]:
    """
    Convenience function to validate parameter integrity.
    
    Args:
        data: Parameter data to validate
        expected_version: Expected version (defaults to current)
        
    Returns:
        tuple: (is_valid: bool, validation_message: str)
    """
    manager = TransitionManager()
    if expected_version is None:
        expected_version = manager.version_manager.get_current_version()
    
    return manager.validate_data_integrity(data, expected_version)


def get_baseline_calculation_approach() -> Dict:
    """
    Convenience function to get baseline calculation approach.
    
    Returns:
        dict: Baseline definition for current architecture
    """
    manager = TransitionManager()
    return manager.get_baseline_definition()