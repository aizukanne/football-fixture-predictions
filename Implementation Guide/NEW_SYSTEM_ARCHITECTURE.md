# Complete Production Implementation Guide

**Status:** Updated 2025-10-03 | **Combined Document:** ✅ Complete
**Project Duration:** ~13 weeks (including Phase 0)
**Overall Readiness:** ~40% Complete (with critical Phase 0 additions)

## 🎯 Document Integration Confirmation

✅ **NEW_SYSTEM_ARCHITECTURE.md** and **ADDENDUM_BASELINE_DEFINITION_AND_TRANSITION.md** have been **successfully combined** into this single complete document.

✅ **All file name inconsistencies corrected** across both original documents.

✅ **Production-focused approach implemented** using Hierarchical Fallback with Version Tracking strategy.

✅ **Critical Phase 0 tasks added** as prerequisite to prevent circular error problems.

## Implementation Sequence: Modular Restructuring FIRST

**UPDATED APPROACH:** Complete modular restructuring before implementing new architecture phases.

## Post-Restructuring File References

| **Architecture Reference** | **Post-Modular Structure** | **Status** | **Module Type** |
|----------------------------|----------------------------|------------|-----------------|
| `team_params.py` | `src/parameters/team_calculator.py` | 🔄 **Refactored from computeTeamParameters.py** | Core |
| `predict_scores.py` | `src/prediction/prediction_engine.py` | 🔄 **Refactored from makeTeamRankings.py** | Core |
| `opponent_classifier.py` | `src/features/opponent_classifier.py` | ➕ **New Phase 1 module** | Feature |
| `version_manager.py` | `src/infrastructure/version_manager.py` | ➕ **New Phase 0 module** | Infrastructure |
| `transition_manager.py` | `src/infrastructure/transition_manager.py` | ➕ **New Phase 0 module** | Infrastructure |

## Reference Code vs Implementation

**Important:** [`genai-pundit.py`](genai-pundit.py:1) serves as **code sample and reference only** and should NOT be modified. The [`get_team_standing()`](genai-pundit.py:740) function provides an implementation pattern for creating the new `opponent_classifier.py` module.

## **CRITICAL:** Phase 0 Must Complete First

**New Timeline:** Phase 0 (1 week) + Phase 1 (2 weeks) = 3 weeks total for foundational deployment
**Key Addition:** Version tracking and baseline transition system to prevent multiplier contamination

---

## Progress Tracking

### Overall Phase Completion
- [ ] **Phase 0:** Baseline Transition & Version Tracking (Week 0 - CRITICAL)
- [ ] Phase 1: Opponent Strength Stratification (Weeks 1-2)
- [ ] Phase 2: Enhanced Prediction Error Tracking (Weeks 3-4)
- [ ] Phase 3: Multi-Timescale Form Integration (Weeks 5-6)
- [ ] Phase 4: Derived Tactical Style Features (Weeks 7-9)
- [ ] Phase 5: Team Classification & Adaptive Strategy (Weeks 10-11)
- [ ] Phase 6: Confidence Calibration & Reporting (Week 12)

---

## Phase 1: Opponent Strength Stratification

**CRITICAL ISSUE:** The current correction multiplier system was calibrated against predictions made with the OLD architecture (no segmentation, no form adjustments, no tactical features). Applying these old multipliers to NEW architecture predictions creates a circular error problem that will degrade prediction quality.

**SOLUTION:** Reset baseline definition and implement version-aware correction system during transition.

### The Baseline Correction Problem

#### What Went Wrong
The existing system calculates correction multipliers by comparing:
- **Predicted goals** (from old model without segmentation/form/tactical features)
- **Actual goals** (ground truth from matches)

These multipliers capture systematic biases in the OLD prediction methodology. When you deploy the NEW architecture with fundamentally different prediction methods, these old multipliers become invalid and potentially harmful.

#### Concrete Example
```python
# Old System:
Team A away prediction = 1.2 goals (using overall away average)
Team A actual away goals = 2.4 goals (against strong opponents)
Calculated multiplier = 2.4 / 1.2 = 2.0

# New System:
Team A away prediction = 2.1 goals (using segmented parameter vs strong opponents)
If we apply old multiplier: 2.1 × 2.0 = 4.2 goals ❌ WRONG
```

The new system ALREADY accounts for opponent strength through segmentation. Applying the old multiplier (which was compensating for lack of segmentation) double-corrects and produces inflated predictions.

### New Baseline Definition

**Baseline = Raw Enhanced Model Output (No Multipliers)**

In the new architecture, your baseline prediction is:
```python
baseline_lambda = (
    segmented_parameter[opponent_tier]  # Phase 1
    + form_adjustment                    # Phase 3
    + tactical_matchup_adjustment        # Phase 4
) × home_advantage_factor
```

**Multipliers are NOT part of the baseline.** They are corrections applied AFTER baseline calculation, and only using multipliers calculated against the SAME architecture version.

### Hierarchical Fallback with Version Tracking (PRODUCTION APPROACH)

**Hierarchy:**
1. Team-level v2 multipliers (if available, sample_size >= 15)
2. League-level v2 multipliers (if available, sample_size >= 30)  
3. Neutral baseline (multiplier = 1.0)

**Benefits:**
- Clean separation of old vs new architecture
- Gradual improvement as data accumulates  
- Falls back gracefully to neutral baseline
- Production-ready approach

### Task 0.1: Implement Version Tracking System
**Priority:** CRITICAL | **Must Complete Before:** Phase 1 deployment  
**Files:** `src/infrastructure/version_manager.py` (new), `src/parameters/team_calculator.py` (modify), `src/prediction/prediction_engine.py` (modify)
**Estimated Time:** 6 hours

#### Checklist
- [ ] Add `architecture_version` field to team_parameters table
- [ ] Add `architecture_version` field to league_parameters table  
- [ ] Add `architecture_version` field to game_fixtures table
- [ ] Create migration script to add version fields
- [ ] Update all parameter calculation functions to set version='2.0'
- [ ] Update all prediction functions to include version in metadata
- [ ] Create version validation function
- [ ] Write tests for version tracking
- [ ] Code review completed

#### Implementation

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
    """
    if multiplier_version == prediction_version:
        return True, "Versions match"
    
    # v1 and v2 are NOT compatible
    if {multiplier_version, prediction_version} == {'1.0', '2.0'}:
        return False, "v1 and v2 use fundamentally different prediction methods"
    
    return False, f"Unknown version compatibility: {multiplier_version} vs {prediction_version}"

def should_use_neutral_baseline(params, current_version):
    """Determine if neutral baseline (multiplier=1.0) should be used."""
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

### Task 0.2: Implement Transition Multiplier Logic
**Priority:** CRITICAL | **Must Complete Before:** Phase 1 deployment
**Files:** `src/infrastructure/transition_manager.py` (new), `src/prediction/prediction_engine.py` (modify)
**Estimated Time:** 4 hours

#### Checklist
- [ ] Create transition_manager.py module
- [ ] Implement get_transition_multipliers() function
- [ ] Integrate into prediction pipeline
- [ ] Add configuration for transition strategy
- [ ] Add logging for multiplier sources
- [ ] Write tests for all transition scenarios
- [ ] Code review completed

#### Implementation

```python
# src/infrastructure/transition_manager.py (NEW FILE)

from datetime import datetime, timedelta
import math
from decimal import Decimal
from src.infrastructure.version_manager import CURRENT_ARCHITECTURE_VERSION, should_use_neutral_baseline

# Configuration - adjust based on chosen strategy
TRANSITION_CONFIG = {
    'strategy': 'hierarchical_fallback',
    'v2_deployment_date': datetime(2025, 10, 15),  # Update with actual date
    'min_team_sample_size': 15,  # Minimum v2 predictions needed for team multipliers
    'min_league_sample_size': 30,  # Minimum v2 predictions needed for league multipliers
}

def get_effective_multipliers(team_params, league_params):
    """
    Central function to determine which multipliers to use during transition.
    Implements hierarchical fallback strategy.
    """
    return _hierarchical_fallback_strategy(team_params, league_params)

def _hierarchical_fallback_strategy(team_params, league_params):
    """
    Strategy: Use hierarchy - team v2 → league v2 → neutral.
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
```

### Task 0.3: Database Schema Migration
**Priority:** CRITICAL | **Must Complete Before:** Phase 1 deployment  
**Files:** `migrate_add_version_fields.py` (new)  
**Estimated Time:** 3 hours

#### Required New Fields

**team_parameters table:**
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
    'calculation_timestamp': 1728000000  # When parameters were calculated
}
```

**game_fixtures table:**
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

---

## Phase 1: Opponent Strength Stratification
**Priority:** Critical | **Effort:** Small | **Timeline:** Weeks 1-2

### Overview
Segment team performance by opponent quality to capture non-linear performance patterns. Teams often perform dramatically differently against strong vs weak opponents.

### Caching Strategy Benefits

#### **Why Cache League Standings?**

**1. API Efficiency & Cost Reduction:**
- Without cache: 20 teams in Premier League = 20 identical API calls per parameter calculation cycle
- With 24-hour cache: 20 teams = 1 API call per day per league
- Cost reduction: 95%+ fewer API requests for multi-team leagues
- API-Football charges per request - caching provides significant cost savings

**2. Performance Optimization:**
- Database cache retrieval: ~10-50ms
- API calls: 1-5 seconds each
- Parallel team calculations become feasible
- Total execution time: Hours → Minutes for league-wide calculations

**3. Rate Limiting Protection:**
- Prevents hitting API rate limits during bulk operations
- Allows processing multiple leagues simultaneously
- Eliminates API timeout cascading failures

#### **Usage Pattern for Opponent Classification:**

```python
# Current workflow (inefficient):
for team in premier_league_teams:  # 20 teams
    standings = get_team_standing(team_id)  # 20 separate API calls
    calculate_team_params()

# Enhanced workflow (efficient):
standings_dict = get_enhanced_league_standings(league_id)  # 1 cached API call
for team in teams:  # 20 teams
    opponent_tier = classify_opponent_strength(opponent_id, standings_dict)
    calculate_segmented_params(by_opponent_tier)
```

#### **Cache Duration Rationale:**
- **League Reality:** Standings change weekly after match rounds
- **Processing Frequency:** Team parameters calculated multiple times daily
- **24-Hour TTL:** Ensures fresh data without excessive API usage
- **Processing Pattern:** Multiple calculation cycles per day benefit from same cache

### Task 1.1: Create Opponent Classification Module
**Files:** `src/features/opponent_classifier.py` (new file) + `src/parameters/team_calculator.py` (import)
**Estimated Time:** 4 hours

#### Checklist
- [ ] Create new module `opponent_classifier.py`
- [ ] Implement `get_league_standings()` function (based on existing reference pattern)
- [ ] Implement `classify_team_by_position()` function
- [ ] Add caching for league standings (24-hour TTL)
- [ ] Create `league_standings_cache` DynamoDB table
- [ ] Import new functions in `src/parameters/team_calculator.py`
- [ ] Write unit tests
- [ ] Code review completed

#### Important Note
**`genai-pundit.py` is a code sample/reference only and should NOT be modified.** The [`get_team_standing()`](genai-pundit.py:740) function serves as an implementation pattern for creating the new `get_league_standings()` function in the dedicated `opponent_classifier.py` module.

#### Rationale
A dedicated module provides better separation of concerns and avoids modifying existing working code in `genai-pundit.py`. The existing function provides a solid reference pattern for API integration and response handling.

#### Implementation

```python
# opponent_classifier.py
import boto3
import requests
import time
from datetime import datetime, timedelta
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
standings_cache_table = dynamodb.Table('league_standings_cache')

TIER_THRESHOLDS = {
    'small_league': {  # 12-14 teams
        'strong': 0.30,    # Top 30%
        'weak': 0.70       # Bottom 30%
    },
    'medium_league': {  # 16-18 teams
        'strong': 0.30,
        'weak': 0.70
    },
    'large_league': {  # 20+ teams
        'strong': 0.30,
        'weak': 0.70
    }
}

def get_league_size_category(total_teams):
    """Determine league size category."""
    if total_teams <= 14:
        return 'small_league'
    elif total_teams <= 18:
        return 'medium_league'
    else:
        return 'large_league'

def classify_team_by_position(league_position, total_teams):
    """
    Classify a team into strength tier based on league position.
    
    Args:
        league_position (int): Current position in league (1 = first place)
        total_teams (int): Total number of teams in league
        
    Returns:
        str: 'strong', 'average', or 'weak'
    """
    if not league_position or not total_teams or league_position > total_teams:
        return 'average'  # Default fallback
    
    league_category = get_league_size_category(total_teams)
    thresholds = TIER_THRESHOLDS[league_category]
    
    position_percentile = league_position / total_teams
    
    if position_percentile <= thresholds['strong']:
        return 'strong'
    elif position_percentile >= thresholds['weak']:
        return 'weak'
    else:
        return 'average'

def get_league_standings(league_id, season, rapidapi_key, use_cache=True):
    """
    Fetch current league standings with 24-hour caching.
    
    Args:
        league_id (int): League ID
        season (str): Season year
        rapidapi_key (str): API key
        use_cache (bool): Whether to use cached data
        
    Returns:
        dict: Mapping of team_id to league_position and total_teams
    """
    cache_key = f"{league_id}-{season}"
    
    # Try cache first
    if use_cache:
        try:
            response = standings_cache_table.get_item(Key={'cache_key': cache_key})
            if 'Item' in response:
                cached_time = response['Item']['timestamp']
                cache_age = datetime.now().timestamp() - cached_time
                
                # Cache valid for 24 hours
                if cache_age < 86400:
                    print(f"Using cached standings for league {league_id}")
                    return response['Item']['standings_data']
        except Exception as e:
            print(f"Cache read failed: {e}, fetching from API")
    
    # Fetch from API
    url = "https://api-football-v1.p.rapidapi.com/v3/standings"
    querystring = {"league": str(league_id), "season": str(season)}
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('response') or not data['response'][0].get('league'):
            return {}
        
        standings = data['response'][0]['league']['standings'][0]
        total_teams = len(standings)
        
        # Build lookup dictionary
        standings_dict = {}
        for standing in standings:
            team_id = standing['team']['id']
            position = standing['rank']
            standings_dict[team_id] = {
                'position': position,
                'total_teams': total_teams,
                'tier': classify_team_by_position(position, total_teams)
            }
        
        # Cache the result
        try:
            standings_cache_table.put_item(
                Item={
                    'cache_key': cache_key,
                    'timestamp': int(datetime.now().timestamp()),
                    'standings_data': standings_dict,
                    'ttl': int((datetime.now() + timedelta(days=1)).timestamp())
                }
            )
        except Exception as e:
            print(f"Failed to cache standings: {e}")
        
        return standings_dict
        
    except Exception as e:
        print(f"Error fetching standings for league {league_id}: {e}")
        return {}

def get_opponent_tier_from_match(match_data, team_id, standings_dict):
    """
    Determine opponent tier for a specific match.
    
    Args:
        match_data: Match data dictionary with home_team_id and away_team_id
        team_id: The team we're analyzing
        standings_dict: Output from get_league_standings()
        
    Returns:
        str: 'strong', 'average', 'weak', or None if undetermined
    """
    # Determine opponent
    if match_data.get('home_team_id') == team_id:
        opponent_id = match_data.get('away_team_id')
    else:
        opponent_id = match_data.get('home_team_id')
    
    if opponent_id in standings_dict:
        return standings_dict[opponent_id]['tier']
    
    return None
```

#### Testing
```python
# test_opponent_classifier.py
def test_classify_team_by_position():
    # Small league (12 teams)
    assert classify_team_by_position(1, 12) == 'strong'
    assert classify_team_by_position(4, 12) == 'average'
    assert classify_team_by_position(10, 12) == 'weak'
    
    # Large league (20 teams)
    assert classify_team_by_position(3, 20) == 'strong'
    assert classify_team_by_position(10, 20) == 'average'
    assert classify_team_by_position(18, 20) == 'weak'

def test_standings_cache():
    # Test that standings are cached correctly
    # Test that stale cache (>24h) triggers refresh
    pass
```

---
### Task 0.4: Update Multiplier Calculation to Filter by Version
**Priority:** CRITICAL | **Must Complete Before:** Phase 2 deployment
**Files:** `src/parameters/multiplier_calculator.py` (modify existing)
**Estimated Time:** 3 hours

#### Checklist
- [ ] Modify calculate_team_multipliers() to filter by version
- [ ] Modify calculate_league_multipliers() to filter by version
- [ ] Add version validation
- [ ] Update minimum sample size logic
- [ ] Add logging for filtered counts
- [ ] Write tests
- [ ] Code review completed

#### Implementation

```python
# Modify calculate_team_multipliers in src/parameters/multiplier_calculator.py

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
    # Add version to return
    result = {
        # ... existing multiplier calculations ...
        'architecture_version': CURRENT_ARCHITECTURE_VERSION,
        'sample_size': v2_fixtures_count,
        'timestamp': int(datetime.now().timestamp())
    }
    
    return result
```

#### File Reference Corrections from Addendum

**CRITICAL:** The addendum contained incorrect file references. Here are the corrections:

| **Addendum Reference** | **Actual File** | **Status** |
|------------------------|----------------|------------|
| `team_params.py` | `computeTeamParameters.py` | ✅ **Use existing** |
| `predict_scores.py` | `src/prediction/prediction_engine.py` | ✅ **Use existing** |

**Integration Points:**
- Modify `src/parameters/team_calculator.py` - add version tracking to [`fit_team_params()`](src/parameters/team_calculator.py:446)
- Modify `src/prediction/prediction_engine.py` - add version metadata to [`process_fixtures()`](src/prediction/prediction_engine.py:41)
- Modify `src/parameters/multiplier_calculator.py` - update [`calculate_team_multipliers()`](src/parameters/multiplier_calculator.py:843) to filter by version

---


### Task 1.2: Modify Team Parameter Calculation
**Files:** `src/parameters/team_calculator.py` (modify existing)
**Estimated Time:** 6 hours

#### Checklist
- [ ] Import enhanced standings function from existing reference
- [ ] Modify `fit_team_params()` to accept standings_dict
- [ ] Segment home/away matches by opponent tier
- [ ] Calculate mu, variance for each segment
- [ ] Implement graceful fallback for small samples
- [ ] Update return structure with segmented parameters
- [ ] Update `lambda_handler()` to fetch standings once per league
- [ ] Test with real team data
- [ ] Code review completed

#### Implementation

```python
# src/parameters/team_calculator.py (modifications)
from opponent_classifier import get_league_standings, get_opponent_tier_from_match

def fit_team_params(df, team_id, league_id, standings_dict=None):
    """
    Calculate team-specific parameters with opponent segmentation.
    Enhanced to compute separate statistics for strong/average/weak opponents.
    
    Parameters:
    - df: DataFrame containing match data with team IDs
    - team_id: ID of the team to analyze
    - league_id: ID of the league this team belongs to
    - standings_dict: Dictionary mapping team_id to position/tier (optional)
    
    Returns:
    - Dictionary of team parameters including segmented values
    """
    MIN_HOME_MATCHES = 5
    MIN_AWAY_MATCHES = 5
    MIN_SEGMENT_MATCHES = 3  # Minimum matches per opponent tier
    
    league_params = fetch_league_parameters(league_id)
    
    # Early exit for insufficient data
    if df.empty or len(df) < 10:
        return _get_league_fallback_params(league_params, league_id, team_id)
    
    # Split into home and away matches
    home_matches = df[df['home_team_id'] == team_id].copy()
    away_matches = df[df['away_team_id'] == team_id].copy()
    
    # Initialize result dictionary
    result = {
        'league_id': league_id,
        'team_id': team_id,
    }
    
    # If standings available, add opponent tier classification
    if standings_dict:
        home_matches['opponent_tier'] = home_matches.apply(
            lambda row: get_opponent_tier_from_match(row, team_id, standings_dict),
            axis=1
        )
        away_matches['opponent_tier'] = away_matches.apply(
            lambda row: get_opponent_tier_from_match(row, team_id, standings_dict),
            axis=1
        )
    
    # Calculate overall parameters (existing logic)
    result.update(_calculate_overall_params(
        home_matches, away_matches, team_id, league_params
    ))
    
    # Calculate segmented parameters if we have standings
    if standings_dict and 'opponent_tier' in home_matches.columns:
        segmented = _calculate_segmented_params(
            home_matches, away_matches, team_id, league_params, MIN_SEGMENT_MATCHES
        )
        result['segmented_params'] = segmented
    else:
        result['segmented_params'] = None
    
    return result

def _calculate_segmented_params(home_matches, away_matches, team_id, league_params, min_matches):
    """
    Calculate performance metrics segmented by opponent tier.
    
    Returns nested dictionary:
    {
        'home': {
            'strong': {'mu': X, 'variance': Y, 'n_matches': Z},
            'average': {...},
            'weak': {...}
        },
        'away': {...}
    }
    """
    segmented = {
        'home': {},
        'away': {}
    }
    
    tiers = ['strong', 'average', 'weak']
    
    # Home segmentation
    for tier in tiers:
        tier_matches = home_matches[home_matches['opponent_tier'] == tier]
        
        if len(tier_matches) >= min_matches:
            goals = tier_matches['home_goals']
            segmented['home'][tier] = {
                'mu': float(goals.mean()),
                'variance': float(goals.var()) if len(goals) > 1 else league_params.get('variance_home', 1.65),
                'n_matches': len(tier_matches),
                'p_score': float((goals > 0).mean())
            }
        else:
            # Insufficient data - use overall home parameters
            segmented['home'][tier] = None
    
    # Away segmentation
    for tier in tiers:
        tier_matches = away_matches[away_matches['opponent_tier'] == tier]
        
        if len(tier_matches) >= min_matches:
            goals = tier_matches['away_goals']
            segmented['away'][tier] = {
                'mu': float(goals.mean()),
                'variance': float(goals.var()) if len(goals) > 1 else league_params.get('variance_away', 1.3),
                'n_matches': len(tier_matches),
                'p_score': float((goals > 0).mean())
            }
        else:
            segmented['away'][tier] = None
    
    return segmented

def _calculate_overall_params(home_matches, away_matches, team_id, league_params):
    """
    Calculate overall venue parameters (existing logic, unchanged).
    This is your current implementation - keep it as-is.
    """
    # Your existing fit_team_params logic goes here
    # Just extracted into a helper function for clarity
    pass

def _get_league_fallback_params(league_params, league_id, team_id):
    """Return league parameters when team data insufficient."""
    if league_params:
        return {
            'mu': league_params.get('mu', 1.35),
            'mu_home': league_params.get('mu_home', 1.5),
            'mu_away': league_params.get('mu_away', 1.2),
            'variance_home': league_params.get('variance_home', 1.65),
            'variance_away': league_params.get('variance_away', 1.3),
            'segmented_params': None,
            'using_league_params': True
        }
    else:
        return {
            'mu': 1.35,
            'mu_home': 1.5,
            'mu_away': 1.2,
            'variance_home': 1.65,
            'variance_away': 1.3,
            'segmented_params': None,
            'using_league_params': True
        }
```

#### Lambda Handler Update
```python
# src/parameters/team_calculator.py - lambda_handler modification
def lambda_handler(event, context):
    """Enhanced to fetch and use league standings."""
    # ... existing setup code ...
    
    for league in all_leagues_flat:
        league_id = league['id']
        season = get_league_start_date(league_id)[:4]
        
        # NEW: Fetch league standings once per league from new module
        standings_dict = get_league_standings(
            league_id,
            season,
            rapidapi_key,
            use_cache=True
        )
        print(f"Fetched standings for {len(standings_dict)} teams in league {league_id}")
        
        # ... existing team loop ...
        for team in teams:
            team_id = team['team_id']
            
            # ... existing data fetching ...
            
            # MODIFIED: Pass standings to fit_team_params
            team_dict = fit_team_params(
                team_scores_df,
                team_id,
                league_id,
                standings_dict=standings_dict  # NEW parameter
            )
            
            # ... rest of existing logic ...
```

---

### Task 1.3: Create Caching Infrastructure
**Files:** DynamoDB table creation only
**Estimated Time:** 1 hour

#### Checklist
- [ ] Create `league_standings_cache` DynamoDB table with TTL
- [ ] Configure table with appropriate partition key (`cache_key`)
- [ ] Set up TTL attribute for automatic cache expiration
- [ ] Test caching mechanism with sample data
- [ ] Verify cache read/write performance

#### Implementation

**DynamoDB Table Configuration:**
```bash
# Create league_standings_cache table
Table Name: league_standings_cache
Partition Key: cache_key (String)
TTL Attribute: ttl
```

**Cache Key Format:** `{league_id}-{season}` (e.g., "39-2024")

#### Rationale
**Migration script removed:** The `segmented_params` field will be populated naturally during regular team parameter calculation cycles. Existing records will get the new field structure when the enhanced `fit_team_params()` function runs, eliminating the need for manual database migration.

---

### Task 1.4: Update Prediction Engine
**Files:** `src/prediction/prediction_engine.py` (modify existing)
**Estimated Time:** 4 hours

#### Checklist
- [ ] Create `select_appropriate_parameters()` function
- [ ] Modify `calculate_to_score()` to use segmented params
- [ ] Add fallback logic when segments unavailable
- [ ] Add logging to indicate which segment used
- [ ] Test predictions with segmented vs non-segmented params
- [ ] Performance testing (ensure no significant latency increase)
- [ ] Code review completed

#### Implementation

#### Rationale
The prediction logic is implemented in `src/prediction/prediction_engine.py` (refactored from `makeTeamRankings.py`), not `predict_scores.py`. Time reduced from 6 to 4 hours due to existing sophisticated prediction infrastructure that can be enhanced rather than rebuilt.

```python
# src/prediction/prediction_engine.py (modifications)

def select_appropriate_parameters(team_params, opponent_tier, is_home):
    """
    Select the appropriate parameters based on opponent tier.
    Falls back to overall parameters if segmented data unavailable.
    
    Args:
        team_params: Full team parameter dictionary
        opponent_tier: 'strong', 'average', or 'weak'
        is_home: Boolean indicating if team is playing at home
        
    Returns:
        dict: Parameters to use for lambda calculation
    """
    venue = 'home' if is_home else 'away'
    
    # Check if segmented parameters exist and have data for this tier
    segmented = team_params.get('segmented_params')
    if segmented and segmented.get(venue) and segmented[venue].get(opponent_tier):
        segment_data = segmented[venue][opponent_tier]
        
        print(f"Using segmented parameters: {venue} vs {opponent_tier} "
              f"(n={segment_data['n_matches']})")
        
        # Build parameter dict with segmented values
        params = team_params.copy()
        params[f'mu_{venue}'] = segment_data['mu']
        params[f'variance_{venue}'] = segment_data['variance']
        params[f'p_score_{venue}'] = segment_data['p_score']
        params['using_segmented'] = True
        params['segment_tier'] = opponent_tier
        params['segment_n_matches'] = segment_data['n_matches']
        
        return params
    else:
        # Fallback to overall parameters
        print(f"Using overall {venue} parameters (segmented data unavailable for {opponent_tier})")
        params = team_params.copy()
        params['using_segmented'] = False
        params['segment_tier'] = None
        return params

def process_fixtures(fixtures):
    """Modified to determine opponent tiers and use segmented parameters."""
    
    for fixture in fixtures:
        try:
            # ... existing setup code ...
            
            home_team_id = fixture['home_id']
            away_team_id = fixture['away_id']
            league_id = fixture['league_id']
            season = fixture['season']
            
            # NEW: Fetch standings to determine opponent tiers
            standings_dict = get_league_standings(
                league_id, 
                season, 
                rapidapi_key,
                use_cache=True
            )
            
            # Determine opponent tiers
            home_opponent_tier = standings_dict.get(away_team_id, {}).get('tier', 'average')
            away_opponent_tier = standings_dict.get(home_team_id, {}).get('tier', 'average')
            
            print(f"Home team facing {home_opponent_tier} opponent")
            print(f"Away team facing {away_opponent_tier} opponent")
            
            # ... existing parameter fetching ...
            home_params = get_team_params_from_db(unique_home_id) or league_params
            away_params = get_team_params_from_db(unique_away_id) or league_params
            
            # NEW: Select appropriate segmented parameters
            home_params_selected = select_appropriate_parameters(
                home_params, 
                away_opponent_tier,
                is_home=True
            )
            away_params_selected = select_appropriate_parameters(
                away_params,
                home_opponent_tier,
                is_home=False
            )
            
            # MODIFIED: Use selected parameters for predictions
            home_score, home_goals, home_likelihood, home_probs = calculate_to_score(
                home_team_parameters,
                away_team_parameters,
                home_params_selected,  # Using segmented params
                is_home=True,
                league_id=league_id
            )
            
            # ... rest of existing prediction logic ...
            
            # NEW: Add segmentation metadata to output
            aggregated_fixture_data['prediction_metadata'] = {
                'home_using_segmented': home_params_selected.get('using_segmented', False),
                'home_opponent_tier': home_opponent_tier,
                'away_using_segmented': away_params_selected.get('using_segmented', False),
                'away_opponent_tier': away_opponent_tier
            }
            
        except Exception as e:
            print(f"Error processing fixture {fixture.get('fixture_id')}: {e}")
            continue
```

---

### Task 1.5: Testing & Validation
**Estimated Time:** 4 hours

#### Checklist
- [ ] Unit tests for opponent classification
- [ ] Integration test: full pipeline with segmented params
- [ ] Compare predictions with/without segmentation
- [ ] Validate improvements on historical data
- [ ] Performance benchmarks (API calls, processing time)
- [ ] Documentation updated

#### Test Plan

```python
# test_phase1_integration.py

def test_full_segmentation_pipeline():
    """
    End-to-end test of segmented parameter pipeline.
    """
    # 1. Fetch standings
    standings = get_league_standings(39, "2024", test_api_key, use_cache=False)
    assert len(standings) > 0
    
    # 2. Load test matches
    test_matches = load_test_fixture_data()
    
    # 3. Calculate segmented parameters
    team_params = fit_team_params(
        test_matches, 
        team_id=33,  # Example: Manchester United
        league_id=39,
        standings_dict=standings
    )
    
    # 4. Verify segmentation exists
    assert team_params['segmented_params'] is not None
    assert 'strong' in team_params['segmented_params']['home']
    
    # 5. Make prediction using segmented params
    opponent_tier = 'weak'
    params_selected = select_appropriate_parameters(
        team_params,
        opponent_tier,
        is_home=True
    )
    
    assert params_selected['using_segmented'] == True
    assert params_selected['segment_tier'] == opponent_tier

def test_prediction_improvement():
    """
    Compare prediction accuracy with and without segmentation.
    Uses historical matches from past season.
    """
    # Load last season's completed matches
    historical_matches = load_completed_matches(league_id=39, season="2023")
    
    errors_without_segmentation = []
    errors_with_segmentation = []
    
    for match in historical_matches:
        # Predict without segmentation
        pred_without = predict_match(match, use_segmentation=False)
        error_without = abs(pred_without - match['actual_home_goals'])
        errors_without_segmentation.append(error_without)
        
        # Predict with segmentation
        pred_with = predict_match(match, use_segmentation=True)
        error_with = abs(pred_with - match['actual_home_goals'])
        errors_with_segmentation.append(error_with)
    
    # Calculate mean absolute errors
    mae_without = sum(errors_without_segmentation) / len(errors_without_segmentation)
    mae_with = sum(errors_with_segmentation) / len(errors_with_segmentation)
    
    print(f"MAE without segmentation: {mae_without:.3f}")
    print(f"MAE with segmentation: {mae_with:.3f}")
    print(f"Improvement: {((mae_without - mae_with) / mae_without * 100):.1f}%")
    
    # Expect at least 5% improvement
    assert mae_with < mae_without * 0.95
```

---

## Phase 2: Enhanced Prediction Error Tracking

**Priority:** Critical | **Effort:** Medium | **Timeline:** Weeks 3-4

### Overview
Track prediction errors in detail to identify teams where the model fails and why. Implement fallback strategies for problematic teams.

### Task 2.1: Implement Error Profile Calculation
**File:** `error_profiler.py` (new file)  
**Estimated Time:** 8 hours

#### Checklist
- [ ] Create `error_profiler.py` module
- [ ] Implement `calculate_error_profile()` function
- [ ] Segment errors by opponent tier
- [ ] Segment errors by time window
- [ ] Calculate inadequacy score
- [ ] Write unit tests
- [ ] Code review completed

#### Implementation

```python
# error_profiler.py
import numpy as np
import math
from datetime import datetime, timedelta
from decimal import Decimal

def calculate_error_profile(fixtures_data, team_id, variance_home, variance_away):
    """
    Calculate detailed error profile for a team based on historical predictions.
    
    Args:
        fixtures_data: List of fixture dictionaries from DynamoDB
        team_id: Team to analyze
        variance_home: Team's actual performance variance at home
        variance_away: Team's actual performance variance away
        
    Returns:
        dict: Comprehensive error profile
    """
    home_fixtures = []
    away_fixtures = []
    
    # Separate into home and away fixtures
    for fixture in fixtures_data:
        if 'home' in fixture and 'team_id' in fixture['home']:
            if int(fixture['home']['team_id']) == team_id:
                home_fixtures.append(fixture)
        if 'away' in fixture and 'team_id' in fixture['away']:
            if int(fixture['away']['team_id']) == team_id:
                away_fixtures.append(fixture)
    
    # Calculate home errors
    home_profile = _calculate_venue_error_profile(
        home_fixtures, 
        'home',
        variance_home
    )
    
    # Calculate away errors
    away_profile = _calculate_venue_error_profile(
        away_fixtures,
        'away',
        variance_away
    )
    
    # Determine primary error mode
    classification = _classify_error_pattern(
        home_profile, 
        away_profile,
        variance_home,
        variance_away
    )
    
    return {
        'home': home_profile,
        'away': away_profile,
        'classification': classification,
        'last_updated': int(datetime.now().timestamp())
    }

def _calculate_venue_error_profile(fixtures, venue, variance):
    """Calculate error metrics for one venue (home or away)."""
    if not fixtures:
        return {
            'total_matches': 0,
            'std_dev_overall': 0,
            'by_opponent_tier': {},
            'by_time_window': {},
            'inadequacy_score': 0
        }
    
    # Extract prediction errors
    errors = []
    errors_by_tier = {'strong': [], 'average': [], 'weak': []}
    
    for fixture in fixtures:
        try:
            predicted = float(fixture[venue]['predicted_goals'])
            actual = float(fixture['goals'][venue])
            error = actual - predicted
            
            errors.append(error)
            
            # Categorize by opponent tier if available
            if 'prediction_metadata' in fixture:
                tier_key = f'{venue}_opponent_tier'
                opponent_tier = fixture['prediction_metadata'].get(tier_key, 'average')
                if opponent_tier in errors_by_tier:
                    errors_by_tier[opponent_tier].append(error)
                    
        except (KeyError, ValueError, TypeError):
            continue
    
    if not errors:
        return {
            'total_matches': 0,
            'std_dev_overall': 0,
            'by_opponent_tier': {},
            'by_time_window': {},
            'inadequacy_score': 0
        }
    
    # Calculate overall standard deviation
    std_dev_overall = float(np.std(errors))
    
    # Calculate by opponent tier
    std_by_tier = {}
    for tier, tier_errors in errors_by_tier.items():
        if len(tier_errors) >= 3:
            std_by_tier[tier] = {
                'std_dev': float(np.std(tier_errors)),
                'mean_error': float(np.mean(tier_errors)),
                'n_matches': len(tier_errors)
            }
    
    # Calculate by time window
    now = datetime.now()
    errors_30d = _filter_by_time_window(fixtures, venue, now, 30)
    errors_60d = _filter_by_time_window(fixtures, venue, now, 60)
    
    std_by_window = {
        '30_days': float(np.std(errors_30d)) if len(errors_30d) >= 5 else None,
        '60_days': float(np.std(errors_60d)) if len(errors_60d) >= 10 else None,
        'full_window': std_dev_overall
    }
    
    # Calculate inadequacy score: std_dev / sqrt(variance)
    inadequacy_score = std_dev_overall / math.sqrt(max(variance, 0.1))
    
    return {
        'total_matches': len(errors),
        'std_dev_overall': std_dev_overall,
        'mean_error': float(np.mean(errors)),
        'by_opponent_tier': std_by_tier,
        'by_time_window': std_by_window,
        'inadequacy_score': inadequacy_score
    }

def _filter_by_time_window(fixtures, venue, now, days):
    """Extract errors from matches within time window."""
    cutoff = now - timedelta(days=days)
    cutoff_timestamp = int(cutoff.timestamp())
    
    errors = []
    for fixture in fixtures:
        if fixture.get('timestamp', 0) >= cutoff_timestamp:
            try:
                predicted = float(fixture[venue]['predicted_goals'])
                actual = float(fixture['goals'][venue])
                errors.append(actual - predicted)
            except (KeyError, ValueError, TypeError):
                continue
    
    return errors

def _classify_error_pattern(home_profile, away_profile, var_home, var_away):
    """
    Classify team into error pattern category.
    
    Categories:
    - well_modeled: Low variance, low prediction errors
    - inherently_chaotic: High variance, proportionally high errors
    - model_inadequacy: Low variance, disproportionately high errors
    - insufficient_data: Not enough matches to classify
    """
    total_matches = home_profile['total_matches'] + away_profile['total_matches']
    
    if total_matches < 15:
        return {
            'category': 'insufficient_data',
            'confidence': 0.1,
            'reason': f'Only {total_matches} matches available'
        }
    
    # Use weighted average of home and away metrics
    avg_variance = (var_home + var_away) / 2
    avg_std_dev = (
        home_profile['std_dev_overall'] + away_profile['std_dev_overall']
    ) / 2
    avg_inadequacy = (
        home_profile['inadequacy_score'] + away_profile['inadequacy_score']
    ) / 2
    
    # Classification thresholds
    if avg_variance < 2.5 and avg_std_dev < 2.0:
        return {
            'category': 'well_modeled',
            'confidence': 0.8,
            'reason': 'Low variance and low prediction errors'
        }
    elif avg_variance > 4.0 and avg_inadequacy < 1.5:
        return {
            'category': 'inherently_chaotic',
            'confidence': 0.7,
            'reason': 'High variance, but errors proportional to unpredictability'
        }
    elif avg_variance < 2.5 and avg_std_dev > 4.0:
        return {
            'category': 'model_inadequacy',
            'confidence': 0.85,
            'reason': 'Team is consistent but model predictions are erratic'
        }
    else:
        return {
            'category': 'needs_more_data',
            'confidence': 0.5,
            'reason': 'Pattern unclear, needs more matches or falls between categories'
        }
```

---

### Task 2.2: Integrate Error Profiling into Parameter Calculation
**Files:** `team_params.py` (modify)  
**Estimated Time:** 4 hours

#### Checklist
- [ ] Import error_profiler module
- [ ] Fetch historical fixtures during parameter calculation
- [ ] Call `calculate_error_profile()` for each team
- [ ] Store error profile in team parameters
- [ ] Handle teams with no historical predictions yet
- [ ] Test integration
- [ ] Code review completed

#### Implementation

```python
# team_params.py - lambda_handler modification

from error_profiler import calculate_error_profile

def lambda_handler(event, context):
    """Enhanced to calculate and store error profiles."""
    
    for league in all_leagues_flat:
        # ... existing league setup ...
        
        # Fetch historical fixtures for error profiling
        end_time = int((datetime.now() - timedelta(days=1)).timestamp())
        start_time = int((datetime.now() - timedelta(days=180)).timestamp())
        league_fixtures = fetch_league_fixtures(country, league_name, start_time, end_time)
        
        for team in teams:
            team_id = team['team_id']
            
            # ... existing parameter calculation ...
            team_dict = fit_team_params(...)
            
            # NEW: Calculate error profile
            error_profile = calculate_error_profile(
                league_fixtures,
                team_id,
                team_dict.get('variance_home', 1.65),
                team_dict.get('variance_away', 1.3)
            )
            
            team_dict['error_profile'] = error_profile
            
            # Log if model inadequacy detected
            classification = error_profile['classification']['category']
            if classification == 'model_inadequacy':
                print(f"WARNING: Model inadequacy detected for team {team_name}")
                print(f"  Home std_dev: {error_profile['home']['std_dev_overall']:.2f}")
                print(f"  Away std_dev: {error_profile['away']['std_dev_overall']:.2f}")
                print(f"  Variance: {team_dict['variance_home']:.2f} / {team_dict['variance_away']:.2f}")
            
            # ... continue with existing logic ...
```

---

### Task 2.3: Implement Fallback Prediction Strategy
**File:** `fallback_strategy.py` (new file)  
**Estimated Time:** 6 hours

#### Checklist
- [ ] Create `fallback_strategy.py` module
- [ ] Implement `simple_form_based_prediction()` function
- [ ] Handle edge cases (very few recent matches)
- [ ] Add logging for fallback usage
- [ ] Write unit tests
- [ ] Code review completed

#### Implementation

```python
# fallback_strategy.py

import numpy as np
from decimal import Decimal

def simple_form_based_prediction(team_matches, venue, league_mu, min_matches=5):
    """
    Simple fallback prediction based purely on recent form.
    Used when complex model shows high inadequacy score.
    
    Args:
        team_matches: Recent match data for the team
        venue: 'home' or 'away'
        league_mu: League average for this venue (fallback)
        min_matches: Minimum matches to use this strategy
        
    Returns:
        dict: Simple prediction parameters
    """
    # Filter to relevant venue
    venue_matches = [
        m for m in team_matches 
        if (venue == 'home' and m.get('is_home')) or 
           (venue == 'away' and not m.get('is_home'))
    ]
    
    # Take last 10 matches at this venue
    recent_matches = sorted(
        venue_matches, 
        key=lambda x: x.get('match_date', ''), 
        reverse=True
    )[:10]
    
    if len(recent_matches) < min_matches:
        print(f"Insufficient recent matches ({len(recent_matches)}), using league average")
        return {
            'lambda': float(league_mu),
            'strategy': 'league_average',
            'n_matches': len(recent_matches),
            'confidence': 0.3
        }
    
    # Extract goals scored
    goals = []
    for match in recent_matches:
        if venue == 'home':
            goals.append(match.get('home_goals', 0))
        else:
            goals.append(match.get('away_goals', 0))
    
    # Use median (robust to outliers)
    median_goals = np.median(goals)
    
    # Apply minimal Bayesian smoothing
    prior_weight = 2  # Very light smoothing
    sample_size = len(goals)
    
    smoothed_lambda = (
        league_mu * prior_weight + median_goals * sample_size
    ) / (prior_weight + sample_size)
    
    # Calculate confidence based on consistency
    std_dev = np.std(goals)
    consistency_factor = 1.0 / (1.0 + std_dev)
    sample_factor = min(sample_size / 10.0, 1.0)
    confidence = consistency_factor * sample_factor
    
    return {
        'lambda': float(smoothed_lambda),
        'strategy': 'simple_form_based',
        'n_matches': sample_size,
        'median_goals': float(median_goals),
        'std_dev': float(std_dev),
        'confidence': confidence
    }

def should_use_fallback(error_profile, venue):
    """
    Determine if fallback strategy should be used.
    
    Args:
        error_profile: Error profile dict from error_profiler
        venue: 'home' or 'away'
        
    Returns:
        bool: True if fallback should be used
    """
    if not error_profile:
        return False
    
    classification = error_profile.get('classification', {})
    
    # Use fallback for model inadequacy cases
    if classification.get('category') == 'model_inadequacy':
        if classification.get('confidence', 0) >= 0.7:
            return True
    
    # Also use fallback if venue-specific errors are very high
    venue_profile = error_profile.get(venue, {})
    std_dev = venue_profile.get('std_dev_overall', 0)
    inadequacy = venue_profile.get('inadequacy_score', 0)
    
    if std_dev > 5.0 and inadequacy > 2.5:
        print(f"Fallback triggered: {venue} std_dev={std_dev:.2f}, inadequacy={inadequacy:.2f}")
        return True
    
    return False
```

---

### Task 2.4: Integrate Fallback into Prediction Pipeline
**Files:** `predict_scores.py` (modify)  
**Estimated Time:** 6 hours

#### Checklist
- [ ] Import fallback_strategy module
- [ ] Check error profile before prediction
- [ ] Route to fallback when appropriate
- [ ] Ensure fallback results compatible with existing code
- [ ] Add metadata to track fallback usage
- [ ] Test with known problematic teams
- [ ] Monitor fallback usage rates
- [ ] Code review completed

#### Implementation

```python
# predict_scores.py (modifications)

from fallback_strategy import simple_form_based_prediction, should_use_fallback

def calculate_to_score(team1_stats, team2_stats, params, is_home=True, league_id=None, opponent_lambda=None):
    """
    Modified to check for fallback strategy before complex calculation.
    """
    venue = 'home' if is_home else 'away'
    
    # NEW: Check if we should use fallback strategy
    error_profile = params.get('error_profile')
    if error_profile and should_use_fallback(error_profile, venue):
        print(f"Using fallback strategy for {venue} team")
        
        # Get recent match data
        team_matches = params.get('recent_matches', [])
        league_mu = params.get(f'mu_{venue}', 1.35)
        
        # Use simple form-based prediction
        fallback_result = simple_form_based_prediction(
            team_matches,
            venue,
            league_mu
        )
        
        lambda_final = fallback_result['lambda']
        
        # Use league alpha for probability calculations
        alpha_nb = params.get(f'alpha_{venue}', 0.3)
        alpha_team = max(alpha_nb, 0.05)
        
        # Calculate probabilities with fallback lambda
        score = 1 - math.exp(-lambda_final)
        most_likely_goals, goal_probability, probabilities = calculate_goal_probabilities(
            lambda_final, 
            alpha_team
        )
        
        # Add fallback metadata
        probabilities['_metadata'] = {
            'fallback_used': True,
            'fallback_reason': error_profile['classification']['category'],
            'fallback_confidence': fallback_result['confidence'],
            'fallback_n_matches': fallback_result['n_matches']
        }
        
        return score, most_likely_goals, goal_probability, probabilities
    
    # Otherwise, proceed with standard complex calculation
    # ... existing calculate_to_score logic ...
```

---

### Task 2.5: Testing & Validation
**Estimated Time:** 6 hours

#### Checklist
- [ ] Unit tests for error profiler
- [ ] Unit tests for fallback strategy
- [ ] Integration test: full pipeline with error detection
- [ ] Validate on historical problem teams
- [ ] Compare fallback vs standard predictions
- [ ] Performance benchmarks
- [ ] Documentation updated

#### Test Cases

```python
# test_phase2_integration.py

def test_error_profile_calculation():
    """Test error profile accurately identifies problematic teams."""
    # Load fixtures for team with known high std_dev
    fixtures = load_test_fixtures(team_id=2191)  # Penybont example
    
    error_profile = calculate_error_profile(
        fixtures,
        team_id=2191,
        variance_home=1.4,
        variance_away=1.4
    )
    
    # Should be classified as model inadequacy
    assert error_profile['classification']['category'] == 'model_inadequacy'
    assert error_profile['away']['std_dev_overall'] > 4.0
    assert error_profile['away']['inadequacy_score'] > 2.0

def test_fallback_improves_predictions():
    """Verify fallback strategy reduces errors for problematic teams."""
    problem_teams = identify_high_stddev_teams()
    
    improvements = []
    for team_id in problem_teams:
        # Get historical matches
        matches = load_team_matches(team_id)
        
        # Predict using standard method
        standard_errors = []
        for match in matches:
            pred_standard = predict_with_standard_method(match)
            error = abs(pred_standard - match['actual_goals'])
            standard_errors.append(error)
        
        # Predict using fallback method
        fallback_errors = []
        for match in matches:
            pred_fallback = predict_with_fallback_method(match)
            error = abs(pred_fallback - match['actual_goals'])
            fallback_errors.append(error)
        
        mae_standard = np.mean(standard_errors)
        mae_fallback = np.mean(fallback_errors)
        improvement = (mae_standard - mae_fallback) / mae_standard
        
        improvements.append(improvement)
        print(f"Team {team_id}: {improvement*100:.1f}% improvement")
    
    # Expect fallback to improve predictions on average
    avg_improvement = np.mean(improvements)
    assert avg_improvement > 0, "Fallback should improve predictions for problem teams"
```

---

## Phase 3: Multi-Timescale Form Integration

**Priority:** High | **Effort:** Medium | **Timeline:** Weeks 5-6

### Overview
Detect and respond to teams in unusual performance states (hot streaks, slumps) that deviate from season-long baselines.

### Task 3.1: Implement Form Deviation Detection
**File:** `form_analyzer.py` (new file)  
**Estimated Time:** 8 hours

#### Checklist
- [ ] Create `form_analyzer.py` module
- [ ] Implement `detect_form_pattern()` function
- [ ] Calculate baseline vs recent performance
- [ ] Identify consistent deviation patterns
- [ ] Write unit tests
- [ ] Code review completed

#### Implementation

```python
# form_analyzer.py

import numpy as np
from datetime import datetime, timedelta
from collections import deque

def detect_form_pattern(team_matches, venue, baseline_lambda, window_size=8):
    """
    Detect if team is in hot streak, slump, or baseline form.
    
    Args:
        team_matches: List of recent matches for the team
        venue: 'home' or 'away'
        baseline_lambda: Season-long expected goals for this venue
        window_size: Number of recent matches to analyze
        
    Returns:
        dict: Form analysis results
    """
    # Filter to relevant venue
    venue_matches = [
        m for m in team_matches
        if (venue == 'home' and m.get('is_home')) or
           (venue == 'away' and not m.get('is_home'))
    ]
    
    # Sort by date, most recent first
    recent_matches = sorted(
        venue_matches,
        key=lambda x: x.get('match_date', ''),
        reverse=True
    )[:window_size]
    
    if len(recent_matches) < 5:
        return {
            'pattern': 'insufficient_data',
            'adjustment_factor': 0.0,
            'confidence': 0.0,
            'n_matches': len(recent_matches)
        }
    
    # Calculate deviations from baseline
    deviations = []
    actual_goals = []
    
    for match in recent_matches:
        if venue == 'home':
            actual = match.get('home_goals', 0)
        else:
            actual = match.get('away_goals', 0)
        
        actual_goals.append(actual)
        deviation = actual - baseline_lambda
        deviations.append(deviation)
    
    # Analyze pattern
    positive_count = sum(1 for d in deviations if d > 0.3)
    negative_count = sum(1 for d in deviations if d < -0.3)
    total_count = len(deviations)
    
    avg_deviation = np.mean(deviations)
    deviation_consistency = positive_count / total_count if positive_count > negative_count else negative_count / total_count
    
    # Determine pattern
    if positive_count >= total_count * 0.75 and avg_deviation > 0.5:
        pattern = 'hot_streak'
        base_adjustment = avg_deviation
    elif negative_count >= total_count * 0.75 and avg_deviation < -0.5:
        pattern = 'slump'
        base_adjustment = avg_deviation
    else:
        pattern = 'baseline'
        base_adjustment = 0.0
    
    # Calculate confidence based on consistency and recency
    confidence = deviation_consistency * min(total_count / window_size, 1.0)
    
    # Scale adjustment by confidence
    adjustment_factor = base_adjustment * confidence
    
    return {
        'pattern': pattern,
        'adjustment_factor': adjustment_factor,
        'confidence': confidence,
        'n_matches': total_count,
        'avg_deviation': avg_deviation,
        'recent_goals_avg': np.mean(actual_goals),
        'baseline_lambda': baseline_lambda
    }

def check_personnel_correlation(form_changes, injury_events):
    """
    Check if form changes correlate with key player injuries/returns.
    
    Args:
        form_changes: List of dates when form pattern changed
        injury_events: List of injury/return events with dates
        
    Returns:
        list: Correlated events within 2-match window
    """
    correlations = []
    
    for form_change in form_changes:
        form_date = datetime.strptime(form_change['date'], '%Y-%m-%d')
        
        for event in injury_events:
            event_date = datetime.strptime(event['date'], '%Y-%m-%d')
            days_diff = abs((event_date - form_date).days)
            
            # Consider events within 14 days (roughly 2 matches)
            if days_diff <= 14:
                correlations.append({
                    'form_change_date': form_change['date'],
                    'form_change_type': form_change['pattern'],
                    'injury_event_date': event['date'],
                    'injury_event_type': event['type'],  # 'injury' or 'return'
                    'player_name': event['player_name'],
                    'player_impact_score': event.get('impact_score', 0),
                    'days_difference': days_diff
                })
    
    return correlations
```

---

### Task 3.2: Apply Form Adjustments in Predictions
**Files:** `predict_scores.py` (modify)  
**Estimated Time:** 6 hours

#### Checklist
- [ ] Import form_analyzer module
- [ ] Fetch recent match history during prediction
- [ ] Detect form pattern before lambda calculation
- [ ] Apply adjustment factor to lambda
- [ ] Add form metadata to predictions
- [ ] Test with teams in known hot streaks/slumps
- [ ] Code review completed

#### Implementation

```python
# predict_scores.py (modifications)

from form_analyzer import detect_form_pattern

def calculate_to_score_with_form(team1_stats, team2_stats, params, is_home=True, league_id=None, opponent_lambda=None):
    """
    Enhanced calculate_to_score with form adjustment.
    """
    venue = 'home' if is_home else 'away'
    
    # ... existing lambda calculation up to corrections ...
    lmbda = calculate_base_lambda(team1_stats, team2_stats, params, is_home)
    
    # Apply multiplier corrections
    lmbda, correction_info = apply_smart_correction(...)
    
    # NEW: Detect and apply form adjustment
    recent_matches = params.get('recent_matches', [])
    if len(recent_matches) >= 5:
        form_analysis = detect_form_pattern(
            recent_matches,
            venue,
            baseline_lambda=params.get(f'mu_{venue}', lmbda),
            window_size=8
        )
        
        if form_analysis['pattern'] != 'baseline':
            adjustment = form_analysis['adjustment_factor']
            
            # Scale adjustment based on confidence
            scaled_adjustment = adjustment * 0.25  # Max 25% adjustment
            
            print(f"Form adjustment: {form_analysis['pattern']} "
                  f"(factor: {adjustment:.2f}, scaled: {scaled_adjustment:.2f})")
            
            lmbda_before_form = lmbda
            lmbda = lmbda + scaled_adjustment
            lmbda = max(0.1, min(lmbda, 5.0))  # Keep within bounds
            
            form_metadata = {
                'form_adjustment_applied': True,
                'form_pattern': form_analysis['pattern'],
                'form_confidence': form_analysis['confidence'],
                'adjustment_factor': scaled_adjustment,
                'lambda_before': lmbda_before_form,
                'lambda_after': lmbda
            }
        else:
            form_metadata = {
                'form_adjustment_applied': False,
                'form_pattern': 'baseline'
            }
    else:
        form_metadata = {
            'form_adjustment_applied': False,
            'form_pattern': 'insufficient_data'
        }
    
    # Continue with ceiling and probability calculations
    # ...
    
    # Add form metadata to probabilities
    probabilities['_form_metadata'] = form_metadata
    
    return score, most_likely_goals, goal_probability, probabilities
```

---

### Task 3.3: Track Personnel Impact on Form
**File:** `personnel_tracker.py` (new file)  
**Estimated Time:** 6 hours

#### Checklist
- [ ] Create `personnel_tracker.py` module
- [ ] Calculate player impact scores
- [ ] Track injury/return dates
- [ ] Correlate with form changes
- [ ] Store in form_context
- [ ] Write unit tests
- [ ] Code review completed

#### Implementation

```python
# personnel_tracker.py

def calculate_player_impact_score(player_stats):
    """
    Calculate how impactful a player is to team performance.
    
    Args:
        player_stats: Dictionary with player statistics
        
    Returns:
        float: Impact score from 0-10
    """
    # Extract key metrics
    minutes = player_stats.get('minutes', 0)
    rating = player_stats.get('rating', 0)
    goal_involvement = player_stats.get('goal_involvement', 0)
    total_games = player_stats.get('total_games_played', 1)
    
    # Minutes component (0-3 points)
    minutes_per_game = minutes / max(total_games, 1)
    minutes_score = min(minutes_per_game / 30, 3.0)  # Max 3 for 90+ min/game
    
    # Rating component (0-4 points)
    rating_score = max((rating - 6.0) / 1.0, 0) * 2  # Scale 6-8 rating to 0-4
    rating_score = min(rating_score, 4.0)
    
    # Goal involvement component (0-3 points)
    involvement_per_game = goal_involvement / max(total_games, 1)
    involvement_score = min(involvement_per_game / 0.5, 3.0)  # Max 3 for 0.5+ per game
    
    total_score = minutes_score + rating_score + involvement_score
    return min(total_score, 10.0)

def track_injury_events(team_id, season, start_date, end_date):
    """
    Track injury and return events for a team in a date range.
    
    Returns:
        list: Injury events with impact scores
    """
    # This would integrate with your existing injury tracking
    # For now, placeholder structure
    events = []
    
    # Fetch injuries from your existing system
    injuries = get_fixture_injuries_for_period(team_id, season, start_date, end_date)
    
    for injury in injuries:
        player_stats = injury.get('player_stats', {})
        impact_score = calculate_player_impact_score(player_stats)
        
        events.append({
            'date': injury['date'],
            'type': 'injury',
            'player_name': injury['player_name'],
            'player_id': injury['player_id'],
            'impact_score': impact_score,
            'expected_return': injury.get('expected_return'),
            'injury_type': injury.get('injury_type')
        })
    
    return events
```

---

### Task 3.4: Testing & Validation
**Estimated Time:** 6 hours

#### Test Cases

```python
# test_phase3_integration.py

def test_form_detection_hot_streak():
    """Test detection of genuine hot streak."""
    # Create synthetic data: team averaging 1.5 goals, now scoring 2.5+
    matches = [
        {'match_date': '2024-10-01', 'is_home': True, 'home_goals': 3},
        {'match_date': '2024-09-24', 'is_home': True, 'home_goals': 2},
        {'match_date': '2024-09-17', 'is_home': True, 'home_goals': 3},
        {'match_date': '2024-09-10', 'is_home': True, 'home_goals': 2},
        {'match_date': '2024-09-03', 'is_home': True, 'home_goals': 3},
        {'match_date': '2024-08-27', 'is_home': True, 'home_goals': 2},
    ]
    
    form = detect_form_pattern(matches, 'home', baseline_lambda=1.5)
    
    assert form['pattern'] == 'hot_streak'
    assert form['adjustment_factor'] > 0.3
    assert form['confidence'] > 0.7

def test_form_detection_baseline():
    """Test that normal performance isn't flagged as pattern."""
    matches = [
        {'match_date': '2024-10-01', 'is_home': True, 'home_goals': 2},
        {'match_date': '2024-09-24', 'is_home': True, 'home_goals': 1},
        {'match_date': '2024-09-17', 'is_home': True, 'home_goals': 2},
        {'match_date': '2024-09-10', 'is_home': True, 'home_goals': 1},
        {'match_date': '2024-09-03', 'is_home': True, 'home_goals': 2},
    ]
    
    form = detect_form_pattern(matches, 'home', baseline_lambda=1.5)
    
    assert form['pattern'] == 'baseline'
    assert abs(form['adjustment_factor']) < 0.2
```

---

## Phase 4: Derived Tactical Style Features

**Priority:** Medium | **Effort:** Large | **Timeline:** Weeks 7-9

### Overview
Derive tactical style metrics from available statistics and apply matchup-based adjustments.

### Task 4.1: Calculate Tactical Style Scores
**File:** `tactical_analyzer.py` (new file)  
**Estimated Time:** 10 hours

#### Checklist
- [ ] Create `tactical_analyzer.py` module
- [ ] Implement attacking intensity calculation
- [ ] Implement defensive solidity calculation
- [ ] Implement counter-attacking efficiency calculation
- [ ] Normalize scores across league
- [ ] Write unit tests
- [ ] Code review completed

#### Implementation

```python
# tactical_analyzer.py

import numpy as np
from scipy import stats as scipy_stats

def calculate_tactical_profile(team_matches, league_context):
    """
    Calculate tactical style scores from match statistics.
    
    Args:
        team_matches: List of match data for the team
        league_context: League-wide statistics for normalization
        
    Returns:
        dict: Tactical profile with normalized scores
    """
    if not team_matches or len(team_matches) < 8:
        return get_default_tactical_profile()
    
    # Calculate raw metrics
    attacking_intensity = _calculate_attacking_intensity(team_matches)
    defensive_solidity = _calculate_defensive_solidity(team_matches)
    counter_efficiency = _calculate_counter_efficiency(team_matches)
    possession_style = _estimate_possession_style(team_matches)
    
    # Normalize to 0-10 scale using league context
    profile = {
        'attacking_intensity': _normalize_score(
            attacking_intensity,
            league_context['attacking_intensity_range']
        ),
        'defensive_solidity': _normalize_score(
            defensive_solidity,
            league_context['defensive_solidity_range']
        ),
        'counter_efficiency': _normalize_score(
            counter_efficiency,
            league_context['counter_efficiency_range']
        ),
        'possession_style': _normalize_score(
            possession_style,
            league_context['possession_style_range']
        ),
        'n_matches': len(team_matches),
        'last_updated': int(datetime.now().timestamp())
    }
    
    return profile

def _calculate_attacking_intensity(matches):
    """
    Attacking intensity: ratio of goals scored to goals conceded,
    adjusted for opponent quality.
    """
    total_scored = 0
    total_conceded = 0
    quality_weights = []
    
    for match in matches:
        is_home = match.get('is_home', False)
        scored = match.get('home_goals' if is_home else 'away_goals', 0)
        conceded = match.get('away_goals' if is_home else 'home_goals', 0)
        
        # Opponent quality adjustment (if available)
        opponent_strength = match.get('opponent_strength', 1.0)
        weight = 1.0 / opponent_strength
        
        total_scored += scored * weight
        total_conceded += conceded * weight
        quality_weights.append(weight)
    
    avg_weight = np.mean(quality_weights)
    weighted_scored = total_scored / (len(matches) * avg_weight)
    weighted_conceded = total_conceded / (len(matches) * avg_weight)
    
    # Ratio with floor to avoid division by zero
    intensity = weighted_scored / max(weighted_conceded, 0.3)
    
    return intensity

def _calculate_defensive_solidity(matches):
    """
    Defensive solidity: combination of clean sheet rate and goals conceded.
    """
    clean_sheets = 0
    total_conceded = 0
    
    for match in matches:
        is_home = match.get('is_home', False)
        conceded = match.get('away_goals' if is_home else 'home_goals', 0)
        
        total_conceded += conceded
        if conceded == 0:
            clean_sheets += 1
    
    clean_sheet_rate = clean_sheets / len(matches)
    goals_conceded_per_game = total_conceded / len(matches)
    
    # Solidity score: high clean sheet rate AND low concession rate
    # Scale so low concession is good
    concession_score = 1.0 / (1.0 + goals_conceded_per_game)
    
    solidity = (clean_sheet_rate * 0.6 + concession_score * 0.4)
    
    return solidity

def _calculate_counter_efficiency(matches):
    """
    Counter-attacking efficiency: goals per shot on target.
    High efficiency with fewer total shots suggests counter-attacking.
    """
    total_goals = 0
    total_shots_on_target = 0
    
    for match in matches:
        is_home = match.get('is_home', False)
        goals = match.get('home_goals' if is_home else 'away_goals', 0)
        shots_on_target = match.get('home_shots_on_target' if is_home else 'away_shots_on_target', 0)
        
        total_goals += goals
        total_shots_on_target += shots_on_target
    
    if total_shots_on_target == 0:
        return 0.2  # Default low efficiency
    
    efficiency = total_goals / total_shots_on_target
    
    return efficiency

def _estimate_possession_style(matches):
    """
    Estimate possession style from passing and territorial metrics.
    Since we don't have direct possession %, use proxy metrics.
    """
    # This is a placeholder - enhance based on available data
    # Could use: pass completion rate, shots per game, territorial advantage
    
    total_passes = 0
    completed_passes = 0
    
    for match in matches:
        # If pass data available
        passes = match.get('passes', {})
        total_passes += passes.get('total', 0)
        completed_passes += passes.get('accurate', 0)
    
    if total_passes == 0:
        return 0.5  # Default neutral
    
    pass_completion = completed_passes / total_passes
    
    # Higher pass completion suggests possession-based play
    return pass_completion

def _normalize_score(value, league_range):
    """
    Normalize a value to 0-10 scale using league context.
    
    Args:
        value: Raw metric value
        league_range: (min, max, mean, std) from league
        
    Returns:
        float: Score from 0-10
    """
    league_min, league_max, league_mean, league_std = league_range
    
    # Z-score normalization
    if league_std > 0:
        z_score = (value - league_mean) / league_std
        # Map z-scores to 0-10 (z of -2 = 0, z of +2 = 10)
        normalized = 5 + (z_score * 2.5)
        normalized = max(0, min(10, normalized))
    else:
        # Fallback if no variance in league
        normalized = 5.0
    
    return normalized

def calculate_league_tactical_context(all_team_profiles):
    """
    Calculate league-wide statistics for normalization.
    Run this once per league after calculating all team profiles.
    """
    # Extract raw values
    attacking_values = [p['attacking_intensity_raw'] for p in all_team_profiles]
    defensive_values = [p['defensive_solidity_raw'] for p in all_team_profiles]
    counter_values = [p['counter_efficiency_raw'] for p in all_team_profiles]
    possession_values = [p['possession_style_raw'] for p in all_team_profiles]
    
    context = {
        'attacking_intensity_range': (
            min(attacking_values),
            max(attacking_values),
            np.mean(attacking_values),
            np.std(attacking_values)
        ),
        'defensive_solidity_range': (
            min(defensive_values),
            max(defensive_values),
            np.mean(defensive_values),
            np.std(defensive_values)
        ),
        'counter_efficiency_range': (
            min(counter_values),
            max(counter_values),
            np.mean(counter_values),
            np.std(counter_values)
        ),
        'possession_style_range': (
            min(possession_values),
            max(possession_values),
            np.mean(possession_values),
            np.std(possession_values)
        )
    }
    
    return context

def get_default_tactical_profile():
    """Default profile when insufficient data."""
    return {
        'attacking_intensity': 5.0,
        'defensive_solidity': 5.0,
        'counter_efficiency': 5.0,
        'possession_style': 5.0,
        'n_matches': 0,
        'is_default': True
    }
```

---

### Task 4.2: Implement Tactical Matchup Adjustments
**Files:** `predict_scores.py` (modify)  
**Estimated Time:** 6 hours

#### Checklist
- [ ] Import tactical_analyzer module
- [ ] Fetch tactical profiles for both teams
- [ ] Calculate matchup compatibility
- [ ] Apply lambda adjustments
- [ ] Add tactical metadata
- [ ] Test with known stylistic matchups
- [ ] Code review completed

#### Implementation

```python
# predict_scores.py (modifications)

from tactical_analyzer import calculate_tactical_profile

def apply_tactical_matchup_adjustment(home_lambda, away_lambda, home_tactical, away_tactical):
    """
    Adjust lambdas based on tactical style matchup.
    
    Args:
        home_lambda: Home team base lambda
        away_lambda: Away team base lambda
        home_tactical: Home team tactical profile
        away_tactical: Away team tactical profile
        
    Returns:
        tuple: (adjusted_home_lambda, adjusted_away_lambda, adjustment_metadata)
    """
    adjustments = []
    home_adjustment = 0.0
    away_adjustment = 0.0
    
    # Rule 1: Counter-attacking home vs attacking away
    if (home_tactical['counter_efficiency'] > 7.0 and 
        away_tactical['attacking_intensity'] > 7.0):
        home_adjustment += 0.08  # +8% to home
        adjustments.append({
            'rule': 'counter_vs_attack',
            'effect': '+8% home lambda',
            'reason': 'Counter-attacking home team vs aggressive away team creates space'
        })
    
    # Rule 2: Both teams highly defensive
    if (home_tactical['defensive_solidity'] > 7.0 and 
        away_tactical['defensive_solidity'] > 7.0):
        home_adjustment -= 0.10  # -10% to both
        away_adjustment -= 0.10
        adjustments.append({
            'rule': 'defensive_stalemate',
            'effect': '-10% both lambdas',
            'reason': 'Two defensive teams likely produce low-scoring match'
        })
    
    # Rule 3: Both teams highly offensive
    if (home_tactical['attacking_intensity'] > 7.0 and 
        away_tactical['attacking_intensity'] > 7.0):
        home_adjustment += 0.10  # +10% to both
        away_adjustment += 0.10
        adjustments.append({
            'rule': 'offensive_clash',
            'effect': '+10% both lambdas',
            'reason': 'Two attacking teams likely produce high-scoring match'
        })
    
    # Rule 4: Possession mismatch
    possession_gap = abs(home_tactical['possession_style'] - away_tactical['possession_style'])
    if possession_gap > 4.0:
        # Team with higher possession style gets slight boost at home
        if home_tactical['possession_style'] > away_tactical['possession_style']:
            home_adjustment += 0.05
            adjustments.append({
                'rule': 'possession_dominance',
                'effect': '+5% home lambda',
                'reason': 'Possession-dominant team at home with large style gap'
            })
    
    # Apply adjustments
    home_lambda_adjusted = home_lambda * (1.0 + home_adjustment)
    away_lambda_adjusted = away_lambda * (1.0 + away_adjustment)
    
    # Keep within reasonable bounds
    home_lambda_adjusted = max(0.1, min(home_lambda_adjusted, 5.0))
    away_lambda_adjusted = max(0.1, min(away_lambda_adjusted, 5.0))
    
    metadata = {
        'tactical_adjustment_applied': len(adjustments) > 0,
        'home_adjustment_pct': home_adjustment * 100,
        'away_adjustment_pct': away_adjustment * 100,
        'rules_triggered': adjustments,
        'home_lambda_before': home_lambda,
        'away_lambda_before': away_lambda,
        'home_lambda_after': home_lambda_adjusted,
        'away_lambda_after': away_lambda_adjusted
    }
    
    return home_lambda_adjusted, away_lambda_adjusted, metadata

def calculate_coordinated_predictions_with_tactical(
    home_team_parameters, away_team_parameters, 
    home_params, away_params, 
    league_id
):
    """
    Enhanced prediction function with tactical adjustments.
    """
    # Calculate base lambdas
    home_lambda_base = calculate_base_lambda(
        home_team_parameters, away_team_parameters, home_params, is_home=True
    )
    away_lambda_base = calculate_base_lambda(
        home_team_parameters, away_team_parameters, away_params, is_home=False
    )
    
    # Apply tactical matchup adjustments
    home_tactical = home_params.get('tactical_profile', {})
    away_tactical = away_params.get('tactical_profile', {})
    
    if home_tactical and away_tactical and not home_tactical.get('is_default'):
        home_lambda_tactical, away_lambda_tactical, tactical_metadata = apply_tactical_matchup_adjustment(
            home_lambda_base,
            away_lambda_base,
            home_tactical,
            away_tactical
        )
        
        print(f"Tactical adjustment: Home {tactical_metadata['home_adjustment_pct']:.1f}%, "
              f"Away {tactical_metadata['away_adjustment_pct']:.1f}%")
    else:
        home_lambda_tactical = home_lambda_base
        away_lambda_tactical = away_lambda_base
        tactical_metadata = {'tactical_adjustment_applied': False}
    
    # Continue with coordinated corrections
    home_lambda_final, away_lambda_final, coordination_info = apply_coordinated_correction(
        home_lambda_tactical, away_lambda_tactical, 
        home_params, away_params,
        home_params, away_params
    )
    
    # Add tactical metadata to coordination info
    coordination_info['tactical_adjustments'] = tactical_metadata
    
    # Generate final predictions
    # ... rest of prediction logic ...
    
    return (home_score, home_goals, home_likelihood, home_probs,
            away_score, away_goals, away_likelihood, away_probs,
            coordination_info)
```

---

### Task 4.3: Integrate into Parameter Calculation
**Files:** `team_params.py` (modify)  
**Estimated Time:** 6 hours

#### Checklist
- [ ] Calculate tactical profile during team parameter calculation
- [ ] Calculate league-wide context for normalization
- [ ] Store tactical profiles in DynamoDB
- [ ] Update every 5 matches
- [ ] Test profile accuracy
- [ ] Code review completed

---

### Task 4.4: Testing & Validation
**Estimated Time:** 6 hours

#### Test Cases

```python
# test_phase4_integration.py

def test_tactical_profile_calculation():
    """Test tactical profile accurately characterizes teams."""
    # Load known defensive team
    defensive_team_matches = load_team_matches(team_id=123)
    profile = calculate_tactical_profile(defensive_team_matches, league_context)
    
    assert profile['defensive_solidity'] > 7.0
    assert profile['attacking_intensity'] < 5.0

def test_tactical_matchup_adjustments():
    """Test matchup adjustments apply correctly."""
    home_tactical = {
        'counter_efficiency': 8.0,
        'attacking_intensity': 5.0,
        'defensive_solidity': 7.0,
        'possession_style': 4.0
    }
    away_tactical = {
        'counter_efficiency': 4.0,
        'attacking_intensity': 8.0,
        'defensive_solidity': 5.0,
        'possession_style': 7.0
    }
    
    home_adj, away_adj, metadata = apply_tactical_matchup_adjustment(
        1.5, 1.2, home_tactical, away_tactical
    )
    
    # Home should get counter-attacking boost
    assert home_adj > 1.5
    assert metadata['tactical_adjustment_applied'] == True
```

---

## Phase 5: Team Classification & Adaptive Strategy

**Priority:** High | **Effort:** Medium | **Timeline:** Weeks 10-11

### Overview
Classify teams by predictability and route to appropriate prediction strategies.

### Task 5.1: Implement Team Classification System
**File:** `team_classifier.py` (new file)  
**Estimated Time:** 6 hours

#### Checklist
- [ ] Create `team_classifier.py` module
- [ ] Implement classification logic
- [ ] Define classification thresholds
- [ ] Write unit tests
- [ ] Code review completed

#### Implementation

```python
# team_classifier.py

from datetime import datetime

CLASSIFICATION_THRESHOLDS = {
    'well_modeled': {
        'max_variance': 2.0,
        'max_std_dev': 2.0,
        'min_sample_size': 15
    },
    'inherently_chaotic': {
        'min_variance': 4.0,
        'max_inadequacy_ratio': 1.5,
        'min_sample_size': 15
    },
    'model_inadequacy': {
        'max_variance': 2.5,
        'min_std_dev': 4.0,
        'min_inadequacy_ratio': 2.0,
        'min_sample_size': 10
    }
}

def classify_team_predictability(team_params, error_profile):
    """
    Classify team into predictability category.
    
    Args:
        team_params: Full team parameter dictionary
        error_profile: Error profile from error_profiler
        
    Returns:
        dict: Classification with confidence and reasoning
    """
    # Extract key metrics
    variance_home = team_params.get('variance_home', 0)
    variance_away = team_params.get('variance_away', 0)
    avg_variance = (variance_home + variance_away) / 2
    
    if not error_profile or not error_profile.get('home') or not error_profile.get('away'):
        return {
            'category': 'insufficient_data',
            'confidence': 0.0,
            'reason': 'No error profile available',
            'timestamp': int(datetime.now().timestamp())
        }
    
    std_dev_home = error_profile['home'].get('std_dev_overall', 0)
    std_dev_away = error_profile['away'].get('std_dev_overall', 0)
    avg_std_dev = (std_dev_home + std_dev_away) / 2
    
    sample_size = (
        error_profile['home'].get('total_matches', 0) +
        error_profile['away'].get('total_matches', 0)
    )
    
    inadequacy_home = error_profile['home'].get('inadequacy_score', 0)
    inadequacy_away = error_profile['away'].get('inadequacy_score', 0)
    avg_inadequacy = (inadequacy_home + inadequacy_away) / 2
    
    # Check well_modeled
    if (avg_variance < CLASSIFICATION_THRESHOLDS['well_modeled']['max_variance'] and
        avg_std_dev < CLASSIFICATION_THRESHOLDS['well_modeled']['max_std_dev'] and
        sample_size >= CLASSIFICATION_THRESHOLDS['well_modeled']['min_sample_size']):
        
        return {
            'category': 'well_modeled',
            'confidence': 0.8,
            'reason': f'Low variance ({avg_variance:.2f}) and low prediction errors ({avg_std_dev:.2f})',
            'metrics': {
                'variance': avg_variance,
                'std_dev': avg_std_dev,
                'inadequacy': avg_inadequacy,
                'sample_size': sample_size
            },
            'timestamp': int(datetime.now().timestamp())
        }
    
    # Check model_inadequacy
    if (avg_variance < CLASSIFICATION_THRESHOLDS['model_inadequacy']['max_variance'] and
        avg_std_dev > CLASSIFICATION_THRESHOLDS['model_inadequacy']['min_std_dev'] and
        avg_inadequacy > CLASSIFICATION_THRESHOLDS['model_inadequacy']['min_inadequacy_ratio'] and
        sample_size >= CLASSIFICATION_THRESHOLDS['model_inadequacy']['min_sample_size']):
        
        return {
            'category': 'model_inadequacy',
            'confidence': 0.85,
            'reason': f'Team is consistent (variance {avg_variance:.2f}) but predictions erratic (std_dev {avg_std_dev:.2f})',
            'metrics': {
                'variance': avg_variance,
                'std_dev': avg_std_dev,
                'inadequacy': avg_inadequacy,
                'sample_size': sample_size
            },
            'timestamp': int(datetime.now().timestamp())
        }
    
    # Check inherently_chaotic
    if (avg_variance > CLASSIFICATION_THRESHOLDS['inherently_chaotic']['min_variance'] and
        avg_inadequacy < CLASSIFICATION_THRESHOLDS['inherently_chaotic']['max_inadequacy_ratio'] and
        sample_size >= CLASSIFICATION_THRESHOLDS['inherently_chaotic']['min_sample_size']):
        
        return {
            'category': 'inherently_chaotic',
            'confidence': 0.7,
            'reason': f'High variance ({avg_variance:.2f}) but errors proportional to unpredictability',
            'metrics': {
                'variance': avg_variance,
                'std_dev': avg_std_dev,
                'inadequacy': avg_inadequacy,
                'sample_size': sample_size
            },
            'timestamp': int(datetime.now().timestamp())
        }
    
    # Default category
    return {
        'category': 'needs_more_data',
        'confidence': 0.4,
        'reason': f'Pattern unclear with {sample_size} matches. Falls between categories.',
        'metrics': {
            'variance': avg_variance,
            'std_dev': avg_std_dev,
            'inadequacy': avg_inadequacy,
            'sample_size': sample_size
        },
        'timestamp': int(datetime.now().timestamp())
    }
```

---

### Task 5.2: Implement Strategy Router
**File:** `strategy_router.py` (new file)  
**Estimated Time:** 6 hours

#### Checklist
- [ ] Create `strategy_router.py` module
- [ ] Implement routing logic
- [ ] Define confidence interval adjustments
- [ ] Write unit tests
- [ ] Code review completed

#### Implementation

```python
# strategy_router.py

def select_prediction_strategy(team_classification, venue):
    """
    Select appropriate prediction strategy based on team classification.
    
    Args:
        team_classification: Classification dict from team_classifier
        venue: 'home' or 'away'
        
    Returns:
        dict: Strategy configuration
    """
    category = team_classification.get('category', 'needs_more_data')
    confidence = team_classification.get('confidence', 0.5)
    
    strategies = {
        'well_modeled': {
            'method': 'standard_full',
            'use_segmentation': True,
            'use_form_adjustment': True,
            'use_tactical_adjustment': True,
            'confidence_interval_multiplier': 1.0,
            'description': 'Full standard pipeline with all enhancements'
        },
        'inherently_chaotic': {
            'method': 'standard_wide_intervals',
            'use_segmentation': True,
            'use_form_adjustment': True,
            'use_tactical_adjustment': True,
            'confidence_interval_multiplier': 1.5,
            'description': 'Standard pipeline with wider confidence intervals'
        },
        'model_inadequacy': {
            'method': 'fallback',
            'use_segmentation': False,
            'use_form_adjustment': False,
            'use_tactical_adjustment': False,
            'confidence_interval_multiplier': 1.3,
            'description': 'Simple form-based fallback strategy'
        },
        'needs_more_data': {
            'method': 'standard_moderate',
            'use_segmentation': True,
            'use_form_adjustment': True,
            'use_tactical_adjustment': False,
            'confidence_interval_multiplier': 1.2,
            'description': 'Standard pipeline with moderate confidence'
        },
        'insufficient_data': {
            'method': 'league_based',
            'use_segmentation': False,
            'use_form_adjustment': False,
            'use_tactical_adjustment': False,
            'confidence_interval_multiplier': 1.5,
            'description': 'League parameters with wide intervals'
        }
    }
    
    strategy = strategies.get(category, strategies['needs_more_data']).copy()
    strategy['classification'] = category
    strategy['classification_confidence'] = confidence
    strategy['venue'] = venue
    
    return strategy

def adjust_probabilities_for_strategy(probabilities, strategy):
    """
    Adjust probability distributions based on strategy configuration.
    Wider confidence intervals = flatter probability distribution.
    
    Args:
        probabilities: Dict mapping goals (0-10) to probabilities
        strategy: Strategy dict from select_prediction_strategy
        
    Returns:
        dict: Adjusted probabilities
    """
    multiplier = strategy.get('confidence_interval_multiplier', 1.0)
    
    if multiplier == 1.0:
        return probabilities  # No adjustment needed
    
    # Flatten distribution by moving probability mass toward mean
    adjusted = {}
    mean_goals = sum(g * p for g, p in probabilities.items())
    
    for goals, prob in probabilities.items():
        # Move probability toward uniform distribution
        uniform_prob = 1.0 / len(probabilities)
        adjustment_factor = (multiplier - 1.0) * 0.3  # Scale adjustment
        
        adjusted_prob = prob * (1 - adjustment_factor) + uniform_prob * adjustment_factor
        adjusted[goals] = adjusted_prob
    
    # Renormalize
    total_prob = sum(adjusted.values())
    for goals in adjusted:
        adjusted[goals] /= total_prob
    
    return adjusted
```

---

### Task 5.3: Integrate Strategy Router into Prediction Pipeline
**Files:** `predict_scores.py` (modify)  
**Estimated Time:** 6 hours

#### Checklist
- [ ] Import strategy_router module
- [ ] Check classification before prediction
- [ ] Route to appropriate strategy
- [ ] Apply confidence adjustments
- [ ] Add routing metadata
- [ ] Test all strategy paths
- [ ] Code review completed

---

### Task 5.4: Testing & Validation
**Estimated Time:** 4 hours

---

## Phase 6: Confidence Calibration & Reporting

**Priority:** Medium | **Effort:** Medium | **Timeline:** Week 12

### Overview
Track probability calibration and provide monitoring dashboards.

### Task 6.1: Implement Calibration Tracking
**File:** `calibration_tracker.py` (new file)  
**Estimated Time:** 8 hours

### Task 6.2: Build Monitoring Dashboard
**Tool:** CloudWatch Dashboards  
**Estimated Time:** 8 hours

### Task 6.3: Implement Automated Alerts
**Tool:** CloudWatch Alarms  
**Estimated Time:** 4 hours

---

## Cross-Cutting Tasks

### Database Schema Migration
**Estimated Time:** 8 hours across all phases

### Monitoring & Logging
**Estimated Time:** 6 hours across all phases

### Documentation
**Estimated Time:** 12 hours across all phases

---

## Deployment & Rollout Strategy

### Week 12: Production Deployment

#### Phase 1 Deployment
- [ ] Deploy to development environment
- [ ] Run validation tests
- [ ] Deploy to production with feature flag OFF
- [ ] Enable for one small league (testing)
- [ ] Monitor for 3 days
- [ ] Enable for 25% of leagues
- [ ] Monitor for 1 week
- [ ] Full rollout

#### Phase 2-6 Deployments
- Follow same gradual rollout pattern
- Monitor error rates, prediction accuracy, latency
- Maintain rollback capability

---

## Success Metrics

Track these metrics throughout implementation:

- **Prediction Accuracy**: Mean Absolute Error (MAE) reduction
- **Calibration**: Brier score, calibration plots
- **Coverage**: % of teams with each strategy
- **Performance**: Latency impact, API call efficiency
- **Reliability**: Error rates, fallback usage frequency

---

## Notes for Developers

1. **Code Style**: Follow existing patterns in codebase
2. **Testing**: Unit tests required for all new functions
3. **Error Handling**: Graceful degradation, never crash
4. **Logging**: Structured logging with context
5. **Documentation**: Docstrings for all public functions

---

## Contact & Support

**Project Lead**: [Name]  
**Technical Architect**: [Name]  
**Dev Team Channel**: [Slack/Teams Channel]

For questions or issues during implementation, reach out in team channel.
# Implementation Readiness Assessment

**Status:** Updated 2025-10-03  
**Overall Readiness:** ~60% Complete (revised from initial assessment)

## Corrected File References

| **Implementation Guide Reference** | **Actual File** | **Status** |
|-----------------------------------|----------------|------------|
| `team_params.py` | `computeTeamParameters.py` | ✅ **Use existing** |
| `predict_scores.py` | `src/prediction/prediction_engine.py` | ✅ **Use existing** |
| `opponent_classifier.py` | `src/features/opponent_classifier.py` | ➕ **New module created** |
| `migrate_team_params_schema.py` | **Not needed** | ❌ **Removed from plan** |

## Existing Infrastructure Strengths

✅ **League Standings Integration:** [`get_team_standing()`](genai-pundit.py:740) provides API-Football standings access  
✅ **Parameter Calculation Framework:** [`fit_team_params()`](src/parameters/team_calculator.py:446) in place
✅ **Prediction Engine:** Sophisticated coordinated predictions in [`src/prediction/prediction_engine.py`](src/prediction/prediction_engine.py:493)
✅ **DynamoDB Architecture:** Tables and Lambda handlers operational  

## Phase 1 Implementation Approach

**Strategy:** Enhance existing functions rather than create new modules  
**Timeline:** 1-2 weeks (reduced from 2-3 weeks)  
**Key Changes:** Add caching + opponent classification to existing infrastructure  

---

# Implementation Readiness Assessment

**Status:** Updated 2025-10-03  
**Overall Readiness:** ~50% Complete (revised assessment)

## Corrected File References

| **Implementation Guide Reference** | **Actual File** | **Status** |
|-----------------------------------|----------------|------------|
| `team_params.py` | `src/parameters/team_calculator.py` | ✅ **Use existing** |
| `predict_scores.py` | `src/prediction/prediction_engine.py` | ✅ **Use existing** |
| `opponent_classifier.py` | **Create new module** | ➕ **New implementation required** |
| `migrate_team_params_schema.py` | **Not needed** | ❌ **Removed from plan** |

## Reference Code vs Implementation

**Important:** [`genai-pundit.py`](genai-pundit.py:1) serves as **code sample and reference only** and should NOT be modified. The [`get_team_standing()`](genai-pundit.py:740) function provides an implementation pattern for creating the new `opponent_classifier.py` module.

## Existing Infrastructure Strengths

✅ **League Standings Reference:** [`get_team_standing()`](genai-pundit.py:740) provides implementation pattern  
✅ **Parameter Calculation Framework:** [`fit_team_params()`](src/parameters/team_calculator.py:446) in place
✅ **Prediction Engine:** Sophisticated coordinated predictions in [`src/prediction/prediction_engine.py`](src/prediction/prediction_engine.py:493)
✅ **DynamoDB Architecture:** Tables and Lambda handlers operational  

## Phase 1 Implementation Approach

**Strategy:** Create new `opponent_classifier.py` module using existing code as reference  
**Timeline:** 2 weeks (original estimate restored)  
**Key Changes:** New module + caching + integration with existing parameter calculation  

---
