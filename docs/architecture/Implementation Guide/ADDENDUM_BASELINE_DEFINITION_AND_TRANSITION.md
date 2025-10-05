# Addendum: Baseline Definition & Transition Strategy

**Document Version:** 1.0  
**Date:** 2025-10-03  
**Status:** CRITICAL - READ BEFORE IMPLEMENTING PHASES 1-2

---

## Executive Summary

**CRITICAL ISSUE IDENTIFIED:** The current correction multiplier system was calibrated against predictions made with the OLD architecture (no segmentation, no form adjustments, no tactical features). Applying these old multipliers to NEW architecture predictions creates a circular error problem that will degrade prediction quality.

**SOLUTION:** Reset baseline definition and implement version-aware correction system during transition.

**IMPACT:** Requires additional implementation tasks in Phases 1-2 to prevent error amplification.

---

## The Baseline Correction Problem

### What Went Wrong

The existing system calculates correction multipliers by comparing:
- **Predicted goals** (from old model without segmentation/form/tactical features)
- **Actual goals** (ground truth from matches)

These multipliers capture systematic biases in the OLD prediction methodology. When you deploy the NEW architecture with fundamentally different prediction methods, these old multipliers become invalid and potentially harmful.

### Concrete Example

**Old System:**
```
Team A away prediction = 1.2 goals (using overall away average)
Team A actual away goals = 2.4 goals (against strong opponents)
Calculated multiplier = 2.4 / 1.2 = 2.0
```

**New System:**
```
Team A away prediction = 2.1 goals (using segmented parameter vs strong opponents)
If we apply old multiplier: 2.1 × 2.0 = 4.2 goals ❌ WRONG
```

The new system ALREADY accounts for opponent strength through segmentation. Applying the old multiplier (which was compensating for lack of segmentation) double-corrects and produces inflated predictions.

### Why This Is Critical

- **Prediction Inflation:** Goals predicted will be systematically too high
- **Unstable Feedback Loop:** New multipliers calculated from inflated predictions will compound errors
- **Loss of Improvements:** All benefits from new architecture negated by bad corrections
- **Delayed Discovery:** Problem won't be obvious for 4-6 weeks until enough new data accumulates

---

## New Baseline Definition

### Baseline = Raw Enhanced Model Output (No Multipliers)

In the new architecture, your baseline prediction is:

```python
baseline_lambda = (
    segmented_parameter[opponent_tier]  # Phase 1
    + form_adjustment                    # Phase 3
    + tactical_matchup_adjustment        # Phase 4
) × home_advantage_factor
```

**Multipliers are NOT part of the baseline.** They are corrections applied AFTER baseline calculation, and only using multipliers calculated against the SAME architecture version.

### What This Means Practically

1. **First 15-20 matches per team:** Use multiplier = 1.0 (neutral)
2. **After 15-20 matches:** Calculate NEW multipliers from NEW baseline's errors
3. **Going forward:** Apply NEW multipliers to future predictions
4. **Old multipliers:** Discard entirely or phase out rapidly

---

## Transition Strategy Options

### Option A: Clean Slate Reset (RECOMMENDED)

**Approach:** Set all multipliers to 1.0 for 4-6 weeks while new architecture learns.

**Pros:**
- Clean, consistent feedback loop
- No contamination from old system
- Clear before/after comparison
- Simplest to implement

**Cons:**
- Temporary accuracy reduction during learning period
- No correction capability for 4-6 weeks
- May concern stakeholders

**Implementation Effort:** LOW (2-3 hours)

**Use When:** You can accept short-term accuracy reduction for long-term improvement.

---

### Option B: Confidence Decay (PRAGMATIC)

**Approach:** Gradually reduce old multipliers over 30 days while new ones develop.

**Pros:**
- Smooth transition
- Maintains some correction initially
- Automatically phases out old corrections

**Cons:**
- Still somewhat contaminated
- More complex logic
- Harder to debug issues

**Implementation Effort:** MEDIUM (6-8 hours)

**Use When:** Stakeholders require continuous correction capability.

---

### Option C: Parallel Systems (ROBUST)

**Approach:** Run old and new systems side-by-side, switch when new proves superior.

**Pros:**
- Zero accuracy loss during transition
- Clear performance comparison
- Can revert if needed

**Cons:**
- Double computational cost
- Complex infrastructure
- Delayed new system adoption

**Implementation Effort:** HIGH (16-20 hours)

**Use When:** You have infrastructure capacity and zero-risk requirement.

---

### Option D: Hierarchical Fallback with Version Tracking (RECOMMENDED FOR PRODUCTION)

**Approach:** Use version tags to determine which multipliers are valid.

**Hierarchy:**
1. Team-level v2 multipliers (if available, sample_size >= 15)
2. League-level v2 multipliers (if available, sample_size >= 30)  
3. Neutral baseline (multiplier = 1.0)

**Pros:**
- Clean separation of old vs new
- Gradual improvement as data accumulates
- Falls back gracefully
- Production-ready

**Cons:**
- Requires version tracking in database
- More complex logic than Option A

**Implementation Effort:** MEDIUM (8-10 hours)

**Use When:** Production deployment requiring professional approach.

---

## Implementation Requirements

### CRITICAL: Add These Tasks to Phase 1

#### Task 1.6: Implement Version Tracking System
**Priority:** CRITICAL  
**Must Complete Before:** Phase 1 deployment  
**Estimated Time:** 6 hours

##### Checklist
- [ ] Add `architecture_version` field to team_parameters table
- [ ] Add `architecture_version` field to league_parameters table
- [ ] Add `architecture_version` field to game_fixtures table
- [ ] Create migration script to add version fields
- [ ] Update all parameter calculation functions to set version='2.0'
- [ ] Update all prediction functions to include version in metadata
- [ ] Create version validation function
- [ ] Write tests for version tracking
- [ ] Code review completed

##### Implementation

```python
# version_manager.py (NEW FILE)

CURRENT_ARCHITECTURE_VERSION = '2.0'

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
    }
}

def get_architecture_metadata():
    """Return metadata about current architecture version."""
    return {
        'version': CURRENT_ARCHITECTURE_VERSION,
        'features': ARCHITECTURE_FEATURES[CURRENT_ARCHITECTURE_VERSION],
        'deployment_date': '2025-10-15',  # Update with actual deployment date
        'compatible_versions': [CURRENT_ARCHITECTURE_VERSION]  # Only v2 compatible with v2
    }

def validate_multiplier_compatibility(multiplier_version, prediction_version):
    """
    Check if multipliers calculated against one version can be applied to predictions
    from another version.
    
    Args:
        multiplier_version: Version that multipliers were calculated against
        prediction_version: Version of current prediction
        
    Returns:
        tuple: (is_compatible: bool, reason: str)
    """
    if multiplier_version == prediction_version:
        return True, "Versions match"
    
    # v1 and v2 are NOT compatible
    if {multiplier_version, prediction_version} == {'1.0', '2.0'}:
        return False, "v1 and v2 use fundamentally different prediction methods"
    
    return False, f"Unknown version compatibility: {multiplier_version} vs {prediction_version}"

def should_use_neutral_baseline(params, current_version):
    """
    Determine if neutral baseline (multiplier=1.0) should be used.
    
    Args:
        params: Parameter dictionary with potential multipliers
        current_version: Current architecture version
        
    Returns:
        tuple: (use_neutral: bool, reason: str)
    """
    # No version specified - use neutral
    if 'architecture_version' not in params:
        return True, "No architecture version in parameters"
    
    # Version mismatch - use neutral
    param_version = params['architecture_version']
    compatible, reason = validate_multiplier_compatibility(param_version, current_version)
    if not compatible:
        return True, f"Version incompatibility: {reason}"
    
    # Insufficient sample size - use neutral
    sample_size = params.get('sample_size', 0)
    if sample_size < 15:
        return True, f"Insufficient v{current_version} predictions (n={sample_size} < 15)"
    
    # All checks passed - multipliers are valid
    return False, "Multipliers compatible and sufficient"
```

##### Modify team_params.py

```python
# team_params.py - add version tracking

from version_manager import CURRENT_ARCHITECTURE_VERSION, get_architecture_metadata

def lambda_handler(event, context):
    """Enhanced with architecture version tracking."""
    
    architecture_meta = get_architecture_metadata()
    print(f"Running parameter calculation with architecture {architecture_meta['version']}")
    
    for league in all_leagues_flat:
        # ... existing league processing ...
        
        for team in teams:
            # ... existing parameter calculation ...
            
            # NEW: Add architecture version and metadata
            team_dict['architecture_version'] = CURRENT_ARCHITECTURE_VERSION
            team_dict['architecture_features'] = architecture_meta['features']
            team_dict['calculation_timestamp'] = int(datetime.now().timestamp())
            team_dict['baseline_method'] = _get_baseline_method(team_dict)
            
            # ... rest of existing code ...

def _get_baseline_method(team_dict):
    """Document which features were actually used in calculation."""
    features_used = []
    
    if team_dict.get('segmented_params') is not None:
        features_used.append('opponent_segmentation')
    
    if team_dict.get('tactical_profile') and not team_dict['tactical_profile'].get('is_default'):
        features_used.append('tactical_features')
    
    return {
        'features': features_used,
        'description': f"Baseline uses: {', '.join(features_used) if features_used else 'league defaults'}"
    }
```

##### Modify predict_scores.py

```python
# predict_scores.py - add version to predictions

from version_manager import CURRENT_ARCHITECTURE_VERSION, get_architecture_metadata

def process_fixtures(fixtures):
    """Enhanced with architecture version tracking."""
    
    architecture_meta = get_architecture_metadata()
    
    for fixture in fixtures:
        # ... existing prediction logic ...
        
        # NEW: Add comprehensive version metadata
        aggregated_fixture_data['prediction_metadata'] = {
            'architecture_version': CURRENT_ARCHITECTURE_VERSION,
            'architecture_features': architecture_meta['features'],
            'prediction_timestamp': int(datetime.now().timestamp()),
            'baseline_components': {
                'segmentation_used': home_params_selected.get('using_segmented', False),
                'segmentation_tier': home_params_selected.get('segment_tier'),
                'form_adjustment_applied': form_metadata.get('form_adjustment_applied', False),
                'form_pattern': form_metadata.get('form_pattern'),
                'tactical_adjustment_applied': tactical_metadata.get('tactical_adjustment_applied', False)
            },
            'multipliers': {
                'home_source': home_multiplier_source,
                'away_source': away_multiplier_source,
                'home_multiplier': float(home_params['home_multiplier']),
                'away_multiplier': float(away_params['away_multiplier'])
            }
        }
        
        # ... rest of existing code ...
```

---

#### Task 1.7: Implement Transition Multiplier Logic
**Priority:** CRITICAL  
**Must Complete Before:** Phase 1 deployment  
**Estimated Time:** 4 hours

##### Checklist
- [ ] Create transition_manager.py module
- [ ] Implement get_transition_multipliers() function
- [ ] Integrate into prediction pipeline
- [ ] Add configuration for transition strategy
- [ ] Add logging for multiplier sources
- [ ] Write tests for all transition scenarios
- [ ] Code review completed

##### Implementation

```python
# transition_manager.py (NEW FILE)

from datetime import datetime, timedelta
import math
from decimal import Decimal
from version_manager import CURRENT_ARCHITECTURE_VERSION, should_use_neutral_baseline

# Configuration - adjust based on chosen strategy
TRANSITION_CONFIG = {
    'strategy': 'hierarchical_fallback',  # Options: 'clean_slate', 'confidence_decay', 'hierarchical_fallback'
    'v2_deployment_date': datetime(2025, 10, 15),  # Update with actual date
    'learning_period_days': 21,  # How long to use neutral baseline
    'min_team_sample_size': 15,  # Minimum v2 predictions needed for team multipliers
    'min_league_sample_size': 30,  # Minimum v2 predictions needed for league multipliers
    'decay_rate': 0.05  # For confidence_decay strategy
}

def get_effective_multipliers(team_params, league_params):
    """
    Central function to determine which multipliers to use during transition.
    Implements the configured transition strategy.
    
    Args:
        team_params: Team parameter dictionary
        league_params: League parameter dictionary
        
    Returns:
        dict: Multiplier values and metadata
    """
    strategy = TRANSITION_CONFIG['strategy']
    
    if strategy == 'clean_slate':
        return _clean_slate_strategy()
    elif strategy == 'confidence_decay':
        return _confidence_decay_strategy(team_params, league_params)
    elif strategy == 'hierarchical_fallback':
        return _hierarchical_fallback_strategy(team_params, league_params)
    else:
        raise ValueError(f"Unknown transition strategy: {strategy}")

def _clean_slate_strategy():
    """
    Strategy A: Use neutral baseline for learning period.
    After learning period, use v2 multipliers if available.
    """
    deployment_date = TRANSITION_CONFIG['v2_deployment_date']
    learning_days = TRANSITION_CONFIG['learning_period_days']
    days_since_deployment = (datetime.now() - deployment_date).days
    
    if days_since_deployment < learning_days:
        return {
            'home_multiplier': Decimal('1.0'),
            'away_multiplier': Decimal('1.0'),
            'total_multiplier': Decimal('1.0'),
            'confidence': Decimal('0.1'),
            'source': 'neutral_learning_period',
            'strategy': 'clean_slate',
            'days_remaining': learning_days - days_since_deployment
        }
    else:
        # Learning period complete - check for v2 multipliers
        # This will be populated by normal multiplier calculation
        return {
            'source': 'calculated_v2',
            'strategy': 'clean_slate',
            'learning_complete': True
        }

def _confidence_decay_strategy(team_params, league_params):
    """
    Strategy B: Gradually decay old multipliers while new ones develop.
    """
    deployment_date = TRANSITION_CONFIG['v2_deployment_date']
    decay_rate = TRANSITION_CONFIG['decay_rate']
    days_since_deployment = (datetime.now() - deployment_date).days
    
    # Check if we have v2 multipliers yet
    use_neutral, reason = should_use_neutral_baseline(team_params, CURRENT_ARCHITECTURE_VERSION)
    
    if not use_neutral:
        # We have valid v2 multipliers - use them
        return {
            'home_multiplier': team_params['home_multiplier'],
            'away_multiplier': team_params['away_multiplier'],
            'total_multiplier': team_params['total_multiplier'],
            'confidence': team_params['confidence'],
            'source': 'team_v2',
            'strategy': 'confidence_decay',
            'transition_complete': True
        }
    
    # No v2 multipliers yet - check for v1 multipliers to decay
    if team_params.get('architecture_version') == '1.0':
        # Apply decay to v1 multipliers
        decay_factor = math.exp(-decay_rate * days_since_deployment)
        
        old_home = float(team_params['home_multiplier'])
        old_away = float(team_params['away_multiplier'])
        
        # Pull toward 1.0
        decayed_home = 1.0 + (old_home - 1.0) * decay_factor
        decayed_away = 1.0 + (old_away - 1.0) * decay_factor
        
        return {
            'home_multiplier': Decimal(str(decayed_home)),
            'away_multiplier': Decimal(str(decayed_away)),
            'total_multiplier': Decimal(str((decayed_home + decayed_away) / 2)),
            'confidence': Decimal(str(float(team_params.get('confidence', 0.5)) * decay_factor)),
            'source': 'v1_decayed',
            'strategy': 'confidence_decay',
            'decay_factor': decay_factor,
            'days_until_neutral': int(-math.log(0.05) / decay_rate - days_since_deployment)
        }
    
    # No multipliers at all - use neutral
    return {
        'home_multiplier': Decimal('1.0'),
        'away_multiplier': Decimal('1.0'),
        'total_multiplier': Decimal('1.0'),
        'confidence': Decimal('0.1'),
        'source': 'neutral_no_multipliers',
        'strategy': 'confidence_decay'
    }

def _hierarchical_fallback_strategy(team_params, league_params):
    """
    Strategy D: Use hierarchy - team v2 → league v2 → neutral.
    Only use multipliers calculated against same architecture version.
    """
    current_version = CURRENT_ARCHITECTURE_VERSION
    
    # Level 1: Try team-level v2 multipliers
    if team_params.get('architecture_version') == current_version:
        sample_size = team_params.get('sample_size', 0)
        if sample_size >= TRANSITION_CONFIG['min_team_sample_size']:
            return {
                'home_multiplier': team_params['home_multiplier'],
                'away_multiplier': team_params['away_multiplier'],
                'total_multiplier': team_params['total_multiplier'],
                'confidence': team_params['confidence'],
                'source': 'team_v2',
                'strategy': 'hierarchical_fallback',
                'sample_size': sample_size
            }
    
    # Level 2: Try league-level v2 multipliers
    if league_params.get('architecture_version') == current_version:
        sample_size = league_params.get('sample_size', 0)
        if sample_size >= TRANSITION_CONFIG['min_league_sample_size']:
            return {
                'home_multiplier': league_params['home_multiplier'],
                'away_multiplier': league_params['away_multiplier'],
                'total_multiplier': league_params['total_multiplier'],
                'confidence': Decimal(str(float(league_params['confidence']) * 0.7)),  # Reduce confidence
                'source': 'league_v2',
                'strategy': 'hierarchical_fallback',
                'sample_size': sample_size
            }
    
    # Level 3: Fallback to neutral baseline
    deployment_date = TRANSITION_CONFIG['v2_deployment_date']
    days_since_deployment = (datetime.now() - deployment_date).days
    
    return {
        'home_multiplier': Decimal('1.0'),
        'away_multiplier': Decimal('1.0'),
        'total_multiplier': Decimal('1.0'),
        'confidence': Decimal('0.2'),
        'source': 'neutral_insufficient_v2_data',
        'strategy': 'hierarchical_fallback',
        'days_since_deployment': days_since_deployment,
        'team_sample_size': team_params.get('sample_size', 0),
        'league_sample_size': league_params.get('sample_size', 0)
    }

def get_neutral_multipliers():
    """Return neutral baseline multipliers."""
    return {
        'home_multiplier': Decimal('1.0'),
        'away_multiplier': Decimal('1.0'),
        'total_multiplier': Decimal('1.0'),
        'confidence': Decimal('0.1'),
        'source': 'neutral_baseline'
    }
```

##### Integrate into Prediction Pipeline

```python
# predict_scores.py - integrate transition manager

from transition_manager import get_effective_multipliers, TRANSITION_CONFIG

def process_fixtures(fixtures):
    """Modified to use transition-aware multipliers."""
    
    print(f"Running predictions with transition strategy: {TRANSITION_CONFIG['strategy']}")
    
    for fixture in fixtures:
        # ... existing setup code ...
        
        home_params = get_team_params_from_db(unique_home_id) or league_params
        away_params = get_team_params_from_db(unique_away_id) or league_params
        
        # NEW: Get transition-aware multipliers
        home_multipliers = get_effective_multipliers(home_params, league_params)
        away_multipliers = get_effective_multipliers(away_params, league_params)
        
        # Log multiplier sources for monitoring
        print(f"Home multipliers: {home_multipliers['source']} "
              f"(home={home_multipliers['home_multiplier']:.2f})")
        print(f"Away multipliers: {away_multipliers['source']} "
              f"(away={away_multipliers['away_multiplier']:.2f})")
        
        # Merge multipliers into params
        home_params.update(home_multipliers)
        away_params.update(away_multipliers)
        
        # Store multiplier source for metadata
        home_multiplier_source = home_multipliers['source']
        away_multiplier_source = away_multipliers['source']
        
        # ... continue with existing prediction logic ...
```

---

#### Task 1.8: Update Multiplier Calculation to Filter by Version
**Priority:** CRITICAL  
**Must Complete Before:** Phase 2 deployment  
**Estimated Time:** 3 hours

##### Checklist
- [ ] Modify calculate_team_multipliers() to filter by version
- [ ] Modify calculate_league_multipliers() to filter by version
- [ ] Add version validation
- [ ] Update minimum sample size logic
- [ ] Add logging for filtered counts
- [ ] Write tests
- [ ] Code review completed

##### Implementation

```python
# Modify calculate_team_multipliers in team_params.py

def calculate_team_multipliers(team_id, fixtures_data, min_sample_size=10):
    """
    Enhanced to only use predictions from current architecture version.
    """
    from version_manager import CURRENT_ARCHITECTURE_VERSION
    
    # Filter to only v2 predictions
    v2_fixtures = [
        f for f in fixtures_data
        if f.get('prediction_metadata', {}).get('architecture_version') == CURRENT_ARCHITECTURE_VERSION
    ]
    
    total_fixtures = len(fixtures_data)
    v2_fixtures_count = len(v2_fixtures)
    
    print(f"Filtering multiplier calculation: {v2_fixtures_count}/{total_fixtures} "
          f"fixtures are v{CURRENT_ARCHITECTURE_VERSION}")
    
    if v2_fixtures_count < min_sample_size:
        print(f"Insufficient v{CURRENT_ARCHITECTURE_VERSION} predictions "
              f"(n={v2_fixtures_count} < {min_sample_size})")
        return {
            'home_multiplier': Decimal('1.0'),
            'away_multiplier': Decimal('1.0'),
            'total_multiplier': Decimal('1.0'),
            'confidence': Decimal('0.1'),
            'sample_size': v2_fixtures_count,
            'architecture_version': CURRENT_ARCHITECTURE_VERSION,
            'insufficient_data': True,
            'timestamp': int(datetime.now().timestamp())
        }
    
    # Continue with existing logic using ONLY v2_fixtures
    home_goals_predicted = []
    home_goals_actual = []
    away_goals_predicted = []
    away_goals_actual = []
    
    # Process team as home team
    home_items = [
        item for item in v2_fixtures  # Use filtered fixtures
        if 'home' in item and 'team_id' in item['home'] 
        and int(item['home']['team_id']) == team_id
    ]
    
    # ... rest of existing logic unchanged ...
    
    # Add version to return
    result = {
        # ... existing multiplier calculations ...
        'architecture_version': CURRENT_ARCHITECTURE_VERSION,
        'sample_size': sample_size,
        'timestamp': int(datetime.now().timestamp())
    }
    
    return result
```

---

## Database Schema Updates

### Required New Fields

#### team_parameters table
```python
{
    'id': 'league_id-team_id',  # Existing
    # ... existing fields ...
    
    # NEW FIELDS
    'architecture_version': '2.0',  # Which architecture calculated these parameters
    'architecture_features': {      # What features were available
        'segmentation': True,
        'form_adjustment': True,
        'tactical_features': True
    },
    'baseline_method': {            # What was actually used
        'features': ['opponent_segmentation'],
        'description': 'Baseline uses: opponent_segmentation'
    },
    'calculation_timestamp': 1728000000  # When parameters were calculated
}
```

#### league_parameters table
```python
{
    'league_id': 123,  # Existing
    # ... existing fields ...
    
    # NEW FIELDS - same as team_parameters
    'architecture_version': '2.0',
    'architecture_features': { ... },
    'calculation_timestamp': 1728000000
}
```

#### game_fixtures table
```python
{
    'fixture_id': 456,  # Existing
    # ... existing fields ...
    
    # NEW FIELD
    'prediction_metadata': {
        'architecture_version': '2.0',
        'architecture_features': { ... },
        'prediction_timestamp': 1728000000,
        'baseline_components': {
            'segmentation_used': True,
            'segmentation_tier': 'weak',
            'form_adjustment_applied': False,
            'tactical_adjustment_applied': False
        },
        'multipliers': {
            'home_source': 'team_v2',
            'away_source': 'neutral_baseline',
            'home_multiplier': 1.15,
            'away_multiplier': 1.0
        }
    }
}
```

### Migration Script

```python
# migrate_add_version_fields.py

import boto3
from decimal import Decimal
from datetime import datetime

dynamodb = boto3.resource('dynamodb')

def migrate_team_parameters():
    """Add version fields to team_parameters table."""
    table = dynamodb.Table('team_parameters')
    
    response = table.scan()
    items = response['Items']
    
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response['Items'])
    
    print(f"Migrating {len(items)} team parameter records...")
    
    for i, item in enumerate(items):
        if 'architecture_version' not in item:
            table.update_item(
                Key={'id': item['id']},
                UpdateExpression='''
                    SET architecture_version = :version,
                        architecture_features = :features,
                        calculation_timestamp = :ts
                ''',
                ExpressionAttributeValues={
                    ':version': '1.0',  # Existing records are v1
                    ':features': {
                        'segmentation': False,
                        'form_adjustment': False,
                        'tactical_features': False
                    },
                    ':ts': int(datetime.now().timestamp())
                }
            )
            
            if (i + 1) % 100 == 0:
                print(f"Migrated {i + 1} records...")
    
    print("Team parameters migration complete.")

def migrate_league_parameters():
    """Add version fields to league_parameters table."""
    table = dynamodb.Table('league_parameters')
    
    # Similar logic as team_parameters
    # ... implementation omitted for brevity ...

def migrate_game_fixtures():
    """Add prediction_metadata to game_fixtures table."""
    table = dynamodb.Table('game_fixtures')
    
    response = table.scan()
    items = response['Items']
    
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response['Items'])
    
    print(f"Migrating {len(items)} fixture records...")
    
    for i, item in enumerate(items):
        if 'prediction_metadata' not in item:
            table.update_item(
                Key={'fixture_id': item['fixture_id']},
                UpdateExpression='SET prediction_metadata = :meta',
                ExpressionAttributeValues={
                    ':meta': {
                        'architecture_version': '1.0',  # Existing predictions are v1
                        'architecture_features': {
                            'segmentation': False,
                            'form_adjustment': False,
                            'tactical_features': False
                        },
                        'prediction_timestamp': item.get('timestamp', int(datetime.now().timestamp()))
                    }
                }
            )
            
            if (i + 1) % 100 == 0:
                print(f"Migrated {i + 1} records...")
    
    print("Game fixtures migration complete.")

if __name__ == "__main__":
    response = input("Migrate all tables? Type 'MIGRATE ALL' to continue: ")
    if response == "MIGRATE ALL":
        migrate_team_parameters()
        migrate_league_parameters()
        migrate_game_fixtures()
    else:
        print("Migration cancelled.")
```

---

## Monitoring During Transition

### Key Metrics to Track

```python
# monitoring_metrics.py (NEW FILE)

def calculate_transition_metrics():
    """
    Calculate and log metrics during transition period.
    Run this daily to monitor transition progress.
    """
    from transition_manager import TRANSITION_CONFIG
    from datetime import datetime, timedelta
    
    metrics = {}
    
    # 1. Multiplier source distribution
    fixtures_table = dynamodb.Table('game_fixtures')
    
    # Get recent predictions (last 7 days)
    cutoff = int((datetime.now() - timedelta(days=7)).timestamp())
    
    response = fixtures_table.scan(
        FilterExpression='#ts > :cutoff',
        ExpressionAttributeNames={'#ts': 'timestamp'},
        ExpressionAttributeValues={':cutoff': cutoff}
    )
    
    source_counts = {
        'team_v2': 0,
        'league_v2': 0,
        'neutral_baseline': 0,
        'v1_decayed': 0,
        'other': 0
    }
    
    for item in response['Items']:
        home_source = item.get('prediction_metadata', {}).get('multipliers', {}).get('home_source', 'other')
        away_source = item.get('prediction_metadata', {}).get('multipliers', {}).get('away_source', 'other')
        
        source_counts[home_source] = source_counts.get(home_source, 0) + 1
        source_counts[away_source] = source_counts.get(away_source, 0) + 1
    
    metrics['multiplier_sources'] = source_counts
    metrics['total_predictions'] = len(response['Items'])
    
    # 2. V2 prediction accumulation
    v2_count = sum(
        1 for item in response['Items']
        if item.get('prediction_metadata', {}).get('architecture_version') == '2.0'
    )
    
    metrics['v2_prediction_rate'] = v2_count / max(len(response['Items']), 1)
    
    # 3. Teams ready for v2 multipliers
    teams_table = dynamodb.Table('team_parameters')
    teams_response = teams_table.scan()
    
    v2_ready_teams = sum(
        1 for item in teams_response['Items']
        if item.get('architecture_version') == '2.0' and
           item.get('sample_size', 0) >= TRANSITION_CONFIG['min_team_sample_size']
    )
    
    metrics['v2_ready_teams'] = v2_ready_teams
    metrics['total_teams'] = len(teams_response['Items'])
    metrics['v2_ready_percentage'] = (v2_ready_teams / max(len(teams_response['Items']), 1)) * 100
    
    # 4. Days since deployment
    deployment_date = TRANSITION_CONFIG['v2_deployment_date']
    days_since = (datetime.now() - deployment_date).days
    metrics['days_since_v2_deployment'] = days_since
    
    # Print summary
    print("\n=== TRANSITION METRICS ===")
    print(f"Days since v2 deployment: {metrics['days_since_v2_deployment']}")
    print(f"V2 prediction rate: {metrics['v2_prediction_rate']*100:.1f}%")
    print(f"Teams with v2 multipliers: {metrics['v2_ready_teams']}/{metrics['total_teams']} "
          f"({metrics['v2_ready_percentage']:.1f}%)")
    print(f"\nMultiplier source distribution (last 7 days):")
    for source, count in metrics['multiplier_sources'].items():
        percentage = (count / (metrics['total_predictions'] * 2)) * 100  # *2 for home+away
        print(f"  {source}: {count} ({percentage:.1f}%)")
    
    return metrics

# Add CloudWatch logging
def log_to_cloudwatch(metrics):
    """Send metrics to CloudWatch for dashboard."""
    cloudwatch = boto3.client('cloudwatch')
    
    cloudwatch.put_metric_data(
        Namespace='PredictionModel/Transition',
        MetricData=[
            {
                'MetricName': 'V2PredictionRate',
                'Value': metrics['v2_prediction_rate'] * 100,
                'Unit': 'Percent'
            },
            {
                'MetricName': 'V2ReadyTeamsPercentage',
                'Value': metrics['v2_ready_percentage'],
                'Unit': 'Percent'
            },
            {
                'MetricName': 'DaysSinceDeployment',
                'Value': metrics['days_since_v2_deployment'],
                'Unit': 'Count'
            }
        ]
    )
```

### CloudWatch Dashboard

Create a dashboard to monitor transition:

```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "title": "V2 Prediction Adoption Rate",
        "metrics": [
          ["PredictionModel/Transition", "V2PredictionRate"]
        ],
        "period": 86400,
        "stat": "Average",
        "region": "eu-west-2",
        "yAxis": {
          "left": {
            "min": 0,
            "max": 100
          }
        }
      }
    },
    {
      "type": "metric",
      "properties": {
        "title": "Teams with V2 Multipliers",
        "metrics": [
          ["PredictionModel/Transition", "V2ReadyTeamsPercentage"]
        ],
        "period": 86400,
        "stat": "Average"
      }
    },
    {
      "type": "metric",
      "properties": {
        "title": "Multiplier Source Distribution",
        "metrics": [
          ["PredictionModel/Transition", "MultiplierSource", { "stat": "SampleCount", "dimensions": {"Source": "team_v2"} }],
          ["...", { "dimensions": {"Source": "league_v2"} }],
          ["...", { "dimensions": {"Source": "neutral_baseline"} }]
        ],
        "period": 86400
      }
    }
  ]
}
```

---

## Decision Matrix

Choose your transition strategy based on your constraints:

| Consideration | Clean Slate | Confidence Decay | Parallel Systems | Hierarchical Fallback |
|--------------|-------------|------------------|------------------|-----------------------|
| Implementation Effort | ⭐ LOW | ⭐⭐ MEDIUM | ⭐⭐⭐⭐ HIGH | ⭐⭐⭐ MEDIUM |
| Accuracy During Transition | ⚠️ Lower | ✅ Maintained | ✅✅ No Impact | ✅ Maintained |
| Clean Baseline | ✅✅ Perfect | ⚠️ Some contamination | ✅✅ Perfect | ✅ Clean |
| Production Ready | ⚠️ Requires stakeholder buy-in | ✅ Yes | ✅✅ Yes | ✅✅ Yes |
| Infrastructure Cost | ✅ No change | ✅ No change | ⚠️ Double | ✅ No change |
| Complexity | ⭐ Simple | ⭐⭐ Moderate | ⭐⭐⭐⭐ Complex | ⭐⭐⭐ Moderate |

**Recommendation:** Use **Hierarchical Fallback** for production deployment. It offers the best balance of clean baseline, maintained accuracy, and professional approach.

---

## Testing Transition Logic

```python
# test_transition.py

def test_clean_slate_learning_period():
    """Test that multipliers are neutral during learning period."""
    # Mock deployment date as 10 days ago
    from transition_manager import _clean_slate_strategy, TRANSITION_CONFIG
    TRANSITION_CONFIG['v2_deployment_date'] = datetime.now() - timedelta(days=10)
    TRANSITION_CONFIG['learning_period_days'] = 21
    
    multipliers = _clean_slate_strategy()
    
    assert multipliers['home_multiplier'] == Decimal('1.0')
    assert multipliers['away_multiplier'] == Decimal('1.0')
    assert multipliers['source'] == 'neutral_learning_period'
    assert multipliers['days_remaining'] == 11

def test_hierarchical_fallback_team_v2():
    """Test that team v2 multipliers are preferred."""
    team_params = {
        'architecture_version': '2.0',
        'sample_size': 20,
        'home_multiplier': Decimal('1.3'),
        'away_multiplier': Decimal('1.1'),
        'confidence': Decimal('0.7')
    }
    
    league_params = {
        'architecture_version': '2.0',
        'sample_size': 50,
        'home_multiplier': Decimal('1.2'),
        'away_multiplier': Decimal('1.15')
    }
    
    multipliers = _hierarchical_fallback_strategy(team_params, league_params)
    
    assert multipliers['source'] == 'team_v2'
    assert multipliers['home_multiplier'] == Decimal('1.3')

def test_hierarchical_fallback_league_v2():
    """Test fallback to league when team insufficient."""
    team_params = {
        'architecture_version': '2.0',
        'sample_size': 5,  # Too few
        'home_multiplier': Decimal('1.3')
    }
    
    league_params = {
        'architecture_version': '2.0',
        'sample_size': 50,
        'home_multiplier': Decimal('1.2'),
        'confidence': Decimal('0.6')
    }
    
    multipliers = _hierarchical_fallback_strategy(team_params, league_params)
    
    assert multipliers['source'] == 'league_v2'
    assert multipliers['home_multiplier'] == Decimal('1.2')
    assert multipliers['confidence'] == Decimal('0.42')  # Reduced by 0.7

def test_version_incompatibility():
    """Test that v1 multipliers are not used with v2 predictions."""
    team_params = {
        'architecture_version': '1.0',  # Old version
        'sample_size': 50,
        'home_multiplier': Decimal('2.0')
    }
    
    league_params = {
        'architecture_version': '1.0',
        'sample_size': 100
    }
    
    multipliers = _hierarchical_fallback_strategy(team_params, league_params)
    
    # Should fall back to neutral, not use v1 multipliers
    assert multipliers['source'] == 'neutral_insufficient_v2_data'
    assert multipliers['home_multiplier'] == Decimal('1.0')
```

---

## Summary Checklist

### Before Phase 1 Deployment

- [ ] Choose transition strategy (Recommended: Hierarchical Fallback)
- [ ] Update TRANSITION_CONFIG with deployment date
- [ ] Complete Task 1.6: Version tracking implementation
- [ ] Complete Task 1.7: Transition multiplier logic
- [ ] Complete Task 1.8: Filter multipliers by version
- [ ] Run database migration to add version fields
- [ ] Test all transition scenarios
- [ ] Set up CloudWatch monitoring
- [ ] Document transition plan for stakeholders
- [ ] Brief team on expected behavior during transition

### Week 1 After Deployment

- [ ] Monitor multiplier source distribution daily
- [ ] Verify all predictions tagged with v2
- [ ] Check for any v1 multipliers being applied
- [ ] Review error logs for version issues

### Week 3 After Deployment

- [ ] Calculate v2 prediction accumulation rate
- [ ] Identify first teams reaching min_sample_size
- [ ] Verify v2 multipliers being calculated correctly
- [ ] Compare early v2 predictions to actuals

### Week 6 After Deployment

- [ ] Measure percentage of teams with v2 multipliers
- [ ] Calculate improvement vs v1 architecture
- [ ] Review any remaining neutral baseline cases
- [ ] Document lessons learned

---

## Questions & Answers

**Q: What happens to old predictions in the database?**  
A: They remain unchanged but are tagged as v1. They won't be used for calculating new v2 multipliers.

**Q: Can we switch strategies mid-transition?**  
A: Yes, by updating TRANSITION_CONFIG, but not recommended after deployment.

**Q: How long until all teams have v2 multipliers?**  
A: Approximately 6-8 weeks with typical fixture schedules.

**Q: What if prediction accuracy drops initially?**  
A: Expected during learning period. Monitor closely; if drop exceeds 10%, investigate.

**Q: Can we manually override multipliers for specific teams?**  
A: Yes, but must tag them with correct architecture_version to prevent misuse.

---

## Contact

For questions about transition strategy:
- **Technical Lead:** [Name]
- **Architect:** [Name]
- **Channel:** #prediction-model-v2