"""
Version Tracking Infrastructure for Multiplier Contamination Prevention

This module implements version tracking to prevent circular error propagation
where old correction multipliers contaminate new architecture predictions.

Critical Problem Solved:
- Old multipliers were calculated against v1.0 predictions (no segmentation)
- Applying these to v2.0 predictions (with segmentation) creates double-correction
- This causes inflated predictions and degrades accuracy

Solution:
- Track architecture version for all parameters and predictions
- Only use multipliers calculated against same architecture version
- Fallback to neutral baseline when versions don't match
"""

import boto3
from datetime import datetime
from typing import Dict, Optional, List, Tuple
import json
import logging

# Configuration
CURRENT_ARCHITECTURE_VERSION = '8.0'

ARCHITECTURE_FEATURES = {
    '1.0': {
        'segmentation': False,
        'form_adjustment': False,
        'tactical_features': False,
        'description': 'Original architecture with overall venue averages'
    },
    '2.0': {
        'segmentation': True,
        'form_adjustment': True,
        'tactical_features': True,
        'description': 'Enhanced architecture with opponent stratification, form, and tactical features'
    },
    '6.0': {
        'segmentation': True,
        'form_adjustment': True,
        'tactical_features': True,
        'opponent_stratification': True,
        'venue_analysis': True,
        'temporal_evolution': True,
        'tactical_intelligence': True,
        'adaptive_classification': True,
        'confidence_calibration': True,
        'description': 'Complete 6-phase advanced football prediction system'
    },
    '7.0': {
        'segmentation': True,
        'form_adjustment': True,
        'tactical_features': True,
        'opponent_stratification': True,
        'venue_analysis': True,
        'temporal_evolution': True,
        'tactical_intelligence': True,
        'adaptive_classification': True,
        'confidence_calibration': True,
        'opponent_aware_defense': True,
        'additive_confidence': True,
        'description': 'Opponent-aware defensive factor and additive confidence calibration'
    },
    '8.0': {
        'segmentation': True,
        'form_adjustment': True,
        'tactical_features': True,
        'opponent_stratification': True,
        'venue_analysis': True,
        'temporal_evolution': True,
        'tactical_intelligence': True,
        'adaptive_classification': True,
        'confidence_calibration': True,
        'opponent_aware_defense': True,
        'additive_confidence': True,
        'symmetric_league_anchor': True,
        'home_adv_deduplication': True,
        'post_anchor_scale_correction': True,
        'description': 'Symmetric league anchor (mu_bar/p_bar denominator), home_adv deduplication, and 1.35 post-anchor scale correction'
    }
}

class VersionManager:
    """
    Manages architecture version tracking and compatibility validation.
    
    This is the critical foundation that prevents multiplier contamination
    by ensuring parameters and predictions are version-consistent.
    """
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.logger = logging.getLogger(__name__)
        
        # Version table for tracking system versions and transitions
        try:
            self.version_table = self.dynamodb.Table('system_versions')
        except Exception as e:
            self.logger.warning(f"Could not connect to system_versions table: {e}")
            self.version_table = None
    
    def get_current_version(self) -> str:
        """
        Returns current system architecture version.
        
        Returns:
            str: Current version (e.g., "2.0")
        """
        return CURRENT_ARCHITECTURE_VERSION
    
    def get_baseline_version(self) -> str:
        """
        Returns the baseline version for transition management.
        
        This is the "clean" version without multiplier contamination.
        For v2.0 deployment, baseline is also v2.0 since we start fresh.
        
        Returns:
            str: Baseline version for clean calculations
        """
        return CURRENT_ARCHITECTURE_VERSION
    
    def is_version_compatible(self, data_version: str, system_version: str) -> bool:
        """
        Checks if data from data_version can be used in system_version.
        
        This prevents multiplier contamination by rejecting incompatible versions.
        
        Args:
            data_version: Version of the data/parameters
            system_version: Current system version
            
        Returns:
            bool: True if versions are compatible, False otherwise
        """
        if not data_version or not system_version:
            return False
            
        # Exact version match is always compatible
        if data_version == system_version:
            return True
            
        # v1.0 and v2.0 are NOT compatible due to fundamental architecture differences
        if {data_version, system_version} == {'1.0', '2.0'}:
            return False
            
        # Future versions can define their own compatibility rules here
        return False
    
    def get_version_metadata(self) -> Dict:
        """
        Returns metadata about current version capabilities.
        
        Used for feature flags and compatibility checks throughout the system.
        
        Returns:
            dict: Version metadata including features and deployment info
        """
        return {
            'version': CURRENT_ARCHITECTURE_VERSION,
            'features': ARCHITECTURE_FEATURES[CURRENT_ARCHITECTURE_VERSION].copy(),
            'deployment_date': '2025-10-15',  # Update with actual deployment date
            'compatible_versions': [CURRENT_ARCHITECTURE_VERSION],  # Only v2 compatible with v2
            'baseline_definition': 'raw_enhanced_model_output_no_multipliers'
        }
    
    def validate_multiplier_compatibility(self, multiplier_version: str, prediction_version: str) -> Tuple[bool, str]:
        """
        Check if multipliers calculated against one version can be applied to predictions
        from another version.
        
        This is the KEY anti-contamination mechanism.
        
        Args:
            multiplier_version: Version used to calculate the multipliers
            prediction_version: Version that generated the predictions
            
        Returns:
            tuple: (is_compatible: bool, reason: str)
        """
        if not multiplier_version or not prediction_version:
            return False, "Missing version information"
            
        if multiplier_version == prediction_version:
            return True, "Versions match exactly"
        
        # v1 and v2 use fundamentally different prediction methods - NOT compatible
        if {multiplier_version, prediction_version} == {'1.0', '2.0'}:
            return False, "v1 and v2 use fundamentally different prediction methods - multipliers would cause contamination"
        
        return False, f"Unknown version compatibility: {multiplier_version} vs {prediction_version}"
    
    def should_use_baseline(self, params: Dict, current_version: str = None) -> Tuple[bool, str]:
        """
        Determines if baseline should be used instead of potentially contaminated historical data.
        
        Args:
            params: Parameter dictionary that may contain version info
            current_version: System version to check against (defaults to current)
            
        Returns:
            tuple: (use_baseline: bool, reason: str)
        """
        if current_version is None:
            current_version = self.get_current_version()
            
        # No version specified - use baseline (neutral multipliers)
        if not params or 'architecture_version' not in params:
            return True, "No architecture version in parameters"
        
        # Check version compatibility
        param_version = params['architecture_version']
        compatible, reason = self.validate_multiplier_compatibility(param_version, current_version)
        if not compatible:
            return True, f"Version incompatibility: {reason}"
        
        # Check sample size sufficiency
        sample_size = params.get('sample_size', 0)
        min_sample_size = 15  # Configurable threshold
        if sample_size < min_sample_size:
            return True, f"Insufficient v{current_version} predictions (n={sample_size} < {min_sample_size})"
        
        # All checks passed - parameters are compatible and sufficient
        return False, "Parameters compatible and sufficient"
    
    def register_version_transition(self, from_version: str, to_version: str, 
                                   metadata: Optional[Dict] = None):
        """
        Records version transitions for audit trail.
        
        Critical for debugging contamination issues and tracking system evolution.
        
        Args:
            from_version: Previous version
            to_version: New version
            metadata: Additional transition information
        """
        if not self.version_table:
            self.logger.warning("Version table not available, skipping transition record")
            return
            
        transition_record = {
            'transition_id': f"{from_version}-to-{to_version}-{int(datetime.now().timestamp())}",
            'from_version': from_version,
            'to_version': to_version,
            'timestamp': int(datetime.now().timestamp()),
            'metadata': metadata or {}
        }
        
        try:
            self.version_table.put_item(Item=transition_record)
            self.logger.info(f"Recorded version transition: {from_version} → {to_version}")
        except Exception as e:
            self.logger.error(f"Failed to record version transition: {e}")
    
    def get_version_features(self, version: str) -> Dict:
        """
        Get feature set for a specific version.
        
        Args:
            version: Version to get features for
            
        Returns:
            dict: Feature set for the version
        """
        return ARCHITECTURE_FEATURES.get(version, {})
    
    def is_feature_enabled(self, feature: str, version: str = None) -> bool:
        """
        Check if a specific feature is enabled in a version.
        
        Args:
            feature: Feature name to check
            version: Version to check (defaults to current)
            
        Returns:
            bool: True if feature is enabled
        """
        if version is None:
            version = self.get_current_version()
            
        features = self.get_version_features(version)
        return features.get(feature, False)


def get_architecture_metadata() -> Dict:
    """
    Convenience function to get current architecture metadata.
    
    Returns:
        dict: Current version metadata
    """
    manager = VersionManager()
    return manager.get_version_metadata()


def validate_multiplier_compatibility(multiplier_version: str, prediction_version: str) -> Tuple[bool, str]:
    """
    Convenience function for multiplier compatibility validation.
    
    Args:
        multiplier_version: Version used to calculate multipliers
        prediction_version: Version that generated predictions
        
    Returns:
        tuple: (is_compatible: bool, reason: str)
    """
    manager = VersionManager()
    return manager.validate_multiplier_compatibility(multiplier_version, prediction_version)


def should_use_neutral_baseline(params: Dict, current_version: str = None) -> Tuple[bool, str]:
    """
    Convenience function to determine if neutral baseline (multiplier=1.0) should be used.
    
    This is a critical function called throughout the system to prevent contamination.
    
    Args:
        params: Parameter dictionary
        current_version: Current system version
        
    Returns:
        tuple: (use_baseline: bool, reason: str)
    """
    manager = VersionManager()
    return manager.should_use_baseline(params, current_version)