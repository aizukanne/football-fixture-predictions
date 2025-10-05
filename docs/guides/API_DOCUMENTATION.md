# API Documentation
**Football Fixture Prediction System - Complete API Reference**

Version: 6.0 | Last Updated: October 4, 2025

---

## Table of Contents

1. [Core Prediction API](#core-prediction-api)
2. [Feature Extraction APIs](#feature-extraction-apis)
3. [Data Access APIs](#data-access-apis)
4. [Analysis APIs](#analysis-apis)
5. [Utility APIs](#utility-apis)
6. [Response Formats](#response-formats)
7. [Error Handling](#error-handling)
8. [Examples](#examples)

---

## Core Prediction API

### `generate_prediction_with_reporting()`

Generate a complete match prediction with all 6 phases of intelligence.

**Module:** `src.prediction.prediction_engine`

**Signature:**
```python
def generate_prediction_with_reporting(
    home_team_id: int,
    away_team_id: int,
    league_id: int,
    season: int,
    venue_id: Optional[int] = None,
    prediction_date: Optional[datetime] = None,
    include_insights: bool = True
) -> Dict
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `home_team_id` | int | Yes | API-Football team ID for home team |
| `away_team_id` | int | Yes | API-Football team ID for away team |
| `league_id` | int | Yes | API-Football league ID (e.g., 39 = Premier League) |
| `season` | int | Yes | Season year (e.g., 2024) |
| `venue_id` | int | No | Venue ID for stadium-specific analysis |
| `prediction_date` | datetime | No | Date for temporal analysis (defaults to now) |
| `include_insights` | bool | No | Include executive insights (default: True) |

**Returns:** `Dict`

```python
{
    'predictions': {
        'home_team': {
            'score_probability': float,        # Overall scoring probability (0-1)
            'most_likely_goals': int,          # Most probable number of goals
            'likelihood': float,               # Confidence in prediction (0-1)
            'goal_probabilities': {            # Probability distribution for goals
                0: float,
                1: float,
                2: float,
                # ... up to 10 goals
            }
        },
        'away_team': {
            # Same structure as home_team
        }
    },
    'confidence_analysis': {
        'calibration_method': str,             # e.g., 'isotonic_regression'
        'confidence_factors': {
            'archetype_predictability': float,
            'match_context': float,
            'data_quality': float,
            'historical_accuracy': float,
            'model_uncertainty': float
        },
        'uncertainty_sources': List[str],
        'reliability_assessment': float        # Overall reliability (0-1)
    },
    'metadata': {
        'architecture_version': str,           # e.g., '6.0'
        'features': List[str],                 # Enabled features
        'confidence_calibrated': bool,
        'final_confidence': float,
        'prediction_date': str,                # ISO format
        'venue_id': int,
        'league_id': int,
        'season': int
    },
    'prediction_metadata': {
        # Duplicate of metadata for backward compatibility
    },
    'insights': {                              # If include_insights=True
        'match_insights': List[str],
        'team_insights': Dict,
        'tactical_insights': Dict,
        'confidence_insights': Dict
    }
}
```

**Example:**
```python
from src.prediction.prediction_engine import generate_prediction_with_reporting

prediction = generate_prediction_with_reporting(
    home_team_id=33,      # Manchester United
    away_team_id=40,      # Liverpool
    league_id=39,         # Premier League
    season=2024,
    include_insights=True
)

print(f"Home Win Probability: {prediction['predictions']['home_team']['score_probability']:.2%}")
print(f"Confidence: {prediction['metadata']['final_confidence']:.2%}")
```

---

## Feature Extraction APIs

### Manager Analysis

#### `get_manager_profile()`

Get comprehensive manager tactical profile.

**Module:** `src.features.manager_analyzer`

**Signature:**
```python
def get_manager_profile(
    team_id: int,
    league_id: int,
    season: int
) -> Dict
```

**Returns:**
```python
{
    'manager_id': int,                    # API-Football coach ID
    'manager_name': str,                  # Full name
    'manager_age': int,
    'manager_nationality': str,
    'manager_photo': str,                 # URL to photo
    'experience_years': int,              # Total years as manager
    'teams_managed': int,                 # Number of teams
    'top_level_experience': bool,         # Top 5 leagues experience
    'preferred_formations': {
        'most_used': str,                 # e.g., '4-3-3'
        'usage_distribution': Dict[str, float],
        'formations_count': int
    },
    'tactical_flexibility': Decimal,      # 0-1 scale
    'formation_consistency': Decimal,
    'home_away_strategy_difference': {
        'home_formation': str,
        'away_formation': str,
        'strategy_difference': str,       # 'defensive_away', 'consistent', etc.
        'difference_score': Decimal
    },
    'opponent_adaptation': {
        'vs_top_teams': {
            'formation': str,
            'approach': str               # 'defensive', 'balanced', 'attacking'
        },
        'vs_mid_teams': {...},
        'vs_bottom_teams': {...},
        'adaptation_level': str           # 'high', 'medium', 'low'
    }
}
```

#### `get_manager_tactical_multiplier()`

Calculate manager-based prediction adjustment.

**Signature:**
```python
def get_manager_tactical_multiplier(
    team_id: int,
    league_id: int,
    season: int,
    opponent_tier: str,                   # 'top', 'middle', or 'bottom'
    venue: str                            # 'home' or 'away'
) -> Decimal
```

**Returns:** `Decimal` - Multiplier (e.g., 0.95 = 5% reduction, 1.08 = 8% boost)

---

### Team Classification

#### `classify_team_archetype()`

Classify team into tactical archetype.

**Module:** `src.features.team_classifier`

**Signature:**
```python
def classify_team_archetype(
    team_id: int,
    league_id: int,
    season: int
) -> str
```

**Returns:** One of:
- `'ELITE_CONSISTENT'` - Top teams with consistent performance
- `'TACTICAL_SPECIALISTS'` - Teams reliant on specific systems
- `'MOMENTUM_DEPENDENT'` - Performance varies with form
- `'HOME_FORTRESS'` - Extreme home/away differences
- `'BIG_GAME_SPECIALISTS'` - Perform differently vs strong teams
- `'UNPREDICTABLE_CHAOS'` - Highly variable performance

#### `get_team_performance_profile()`

Get detailed performance profile.

**Signature:**
```python
def get_team_performance_profile(
    team_id: int,
    league_id: int,
    season: int
) -> Dict
```

**Returns:**
```python
{
    'attacking_metrics': {
        'goals_per_game': float,
        'shots_per_game': float,
        'possession_avg': float,
        'attacking_third_entries': float
    },
    'defensive_metrics': {
        'goals_conceded_per_game': float,
        'clean_sheets_pct': float,
        'tackles_per_game': float,
        'defensive_stability': float
    },
    'form_metrics': {
        'recent_form': float,
        'home_form': float,
        'away_form': float,
        'momentum': float
    },
    'consistency_metrics': {
        'performance_variance': float,
        'result_predictability': float
    }
}
```

---

### Tactical Analysis

#### `TacticalAnalyzer`

Analyze team tactical preferences and styles.

**Module:** `src.features.tactical_analyzer`

**Methods:**

##### `analyze_team_formation_preferences()`
```python
def analyze_team_formation_preferences(
    team_id: int,
    league_id: int,
    season: int
) -> Dict
```

**Returns:**
```python
{
    'most_used_formation': str,           # e.g., '4-3-3'
    'formation_consistency': float,       # 0-1
    'formations_used': Dict[str, int],    # Formation: Count
    'tactical_consistency': float,
    'flexibility_score': float
}
```

##### `calculate_tactical_style_scores()`
```python
def calculate_tactical_style_scores(
    team_id: int,
    league_id: int,
    season: int
) -> Dict
```

**Returns:** 8 tactical dimensions (0-10 scale):
```python
{
    'possession_style': float,            # Ball dominance
    'attacking_intensity': float,         # Aggression in attack
    'defensive_solidity': float,          # Defensive organization
    'counter_efficiency': float,          # Counter-attack effectiveness
    'pressing_intensity': float,          # High press aggression
    'build_up_speed': float,              # Tempo of play
    'width_usage': float,                 # Flank vs central play
    'aerial_preference': float            # Aerial play reliance
}
```

---

### Venue Analysis

#### `VenueAnalyzer`

Analyze stadium advantages and travel impact.

**Module:** `src.features.venue_analyzer`

**Methods:**

##### `calculate_stadium_advantage()`
```python
def calculate_stadium_advantage(
    team_id: int,
    venue_id: int,
    league_id: int,
    season: int
) -> Decimal
```

**Returns:** Stadium advantage multiplier (e.g., 1.15 = 15% boost)

##### `calculate_travel_distance()`
```python
def calculate_travel_distance(
    home_venue_id: int,
    away_venue_id: int
) -> float
```

**Returns:** Distance in kilometers

---

### Form Analysis

#### `analyze_head_to_head_form()`

Analyze historical head-to-head matchups.

**Module:** `src.features.form_analyzer`

**Signature:**
```python
def analyze_head_to_head_form(
    home_team_id: int,
    away_team_id: int,
    limit: int = 10
) -> Dict
```

**Returns:**
```python
{
    'total_matches': int,
    'home_wins': int,
    'away_wins': int,
    'draws': int,
    'home_goals_avg': float,
    'away_goals_avg': float,
    'last_5_results': List[str],          # ['W', 'L', 'D', ...]
    'recent_trend': str,                  # 'home_dominant', 'even', etc.
    'h2h_multiplier': Decimal
}
```

---

## Data Access APIs

### API Client

#### `get_coach_by_team()`

**Module:** `src.data.api_client`

**Signature:**
```python
def get_coach_by_team(
    team_id: int,
    max_retries: int = 5
) -> Optional[Dict]
```

**Returns:**
```python
{
    'id': int,
    'name': str,
    'firstname': str,
    'lastname': str,
    'age': int,
    'birth': {
        'date': str,
        'place': str,
        'country': str
    },
    'nationality': str,
    'photo': str,
    'team': {
        'id': int,
        'name': str,
        'logo': str
    },
    'career': [
        {
            'start': str,                 # 'YYYY-MM-DD'
            'end': str,
            'team': {
                'id': int,
                'name': str,
                'logo': str
            }
        },
        # ... more positions
    ]
}
```

#### `get_fixture_lineups()`

Get match lineups including coach information.

**Signature:**
```python
def get_fixture_lineups(
    fixture_id: int,
    max_retries: int = 5
) -> Optional[Dict]
```

**Returns:**
```python
{
    'home': {
        'team': {...},
        'coach': {
            'id': int,
            'name': str,
            'photo': str
        },
        'formation': str,                 # e.g., '4-3-3'
        'startXI': [...],
        'substitutes': [...]
    },
    'away': {
        # Same structure as home
    }
}
```

---

## Analysis APIs

### Performance Dashboard

#### `generate_performance_summary()`

**Module:** `src.analytics.performance_dashboard`

**Signature:**
```python
def generate_performance_summary(
    league_id: int,
    season: int,
    date_range: Optional[Tuple[datetime, datetime]] = None
) -> Dict
```

**Returns:**
```python
{
    'overall_metrics': {
        'total_predictions': int,
        'accuracy_rate': float,
        'confidence_correlation': float,
        'avg_prediction_time': float
    },
    'by_competition': Dict[str, Dict],
    'by_team_archetype': Dict[str, Dict],
    'calibration_metrics': {
        'brier_score': float,
        'log_loss': float,
        'calibration_error': float
    },
    'top_performers': List[Dict],
    'improvement_areas': List[str]
}
```

---

### Confidence Calibrator

#### `calibrate_prediction_confidence()`

**Module:** `src.analytics.confidence_calibrator`

**Signature:**
```python
def calibrate_prediction_confidence(
    prediction: Dict,
    historical_accuracy: float,
    context_factors: Dict
) -> Decimal
```

**Returns:** Calibrated confidence score (0-1)

---

## Utility APIs

### Geographic Utils

#### `calculate_combined_travel_impact()`

**Module:** `src.utils.geographic`

**Signature:**
```python
def calculate_combined_travel_impact(
    distance_km: float,
    timezone_diff: int
) -> Decimal
```

**Returns:** Travel fatigue multiplier (0-1, where 1 = no impact)

---

## Response Formats

### Standard Response Structure

All prediction responses follow this structure:

```python
{
    'predictions': {...},          # Core predictions
    'confidence_analysis': {...},  # Confidence metrics
    'metadata': {...},             # System metadata
    'insights': {...}              # Optional insights
}
```

### Error Response Structure

```python
{
    'error': str,                  # Error message
    'error_type': str,             # Error classification
    'predictions': None,
    'metadata': {
        'architecture_version': str,
        'error': str
    }
}
```

---

## Error Handling

### Exception Types

- **`APIConnectionError`** - Failed to connect to external API
- **`DataUnavailableError`** - Required data not available
- **`ValidationError`** - Invalid input parameters
- **`CacheError`** - Database cache operation failed

### Retry Logic

All API calls include automatic retry with exponential backoff:
- **Max Retries:** 5
- **Wait Time:** 5-30 seconds
- **Status Codes:** Retries on 429 (rate limit)

### Fallback Mechanisms

System gracefully degrades when data unavailable:
- **Missing Coach Data:** Uses default neutral profile
- **Missing Tactical Data:** Uses league averages
- **API Failure:** Uses cached data or defaults

---

## Examples

### Example 1: Basic Prediction

```python
from src.prediction.prediction_engine import generate_prediction_with_reporting

# Predict Manchester United vs Liverpool
prediction = generate_prediction_with_reporting(
    home_team_id=33,
    away_team_id=40,
    league_id=39,
    season=2024
)

# Extract key metrics
home_prob = prediction['predictions']['home_team']['score_probability']
confidence = prediction['metadata']['final_confidence']

print(f"Home Team Scoring Probability: {home_prob:.1%}")
print(f"Prediction Confidence: {confidence:.1%}")
```

### Example 2: Manager Analysis

```python
from src.features.manager_analyzer import get_manager_profile, get_manager_tactical_multiplier

# Get manager profile
profile = get_manager_profile(
    team_id=33,
    league_id=39,
    season=2024
)

print(f"Manager: {profile['manager_name']}")
print(f"Experience: {profile['experience_years']} years")
print(f"Tactical Flexibility: {profile['tactical_flexibility']}")

# Get tactical multiplier for away match vs top team
multiplier = get_manager_tactical_multiplier(
    team_id=33,
    league_id=39,
    season=2024,
    opponent_tier='top',
    venue='away'
)

print(f"Tactical Adjustment: {float(multiplier-1)*100:+.1f}%")
```

### Example 3: Team Classification

```python
from src.features.team_classifier import classify_team_archetype, get_team_performance_profile

# Classify team
archetype = classify_team_archetype(
    team_id=33,
    league_id=39,
    season=2024
)

print(f"Team Archetype: {archetype}")

# Get performance profile
profile = get_team_performance_profile(
    team_id=33,
    league_id=39,
    season=2024
)

print(f"Goals/Game: {profile['attacking_metrics']['goals_per_game']:.2f}")
print(f"Clean Sheets: {profile['defensive_metrics']['clean_sheets_pct']:.1%}")
```

### Example 4: Tactical Analysis

```python
from src.features.tactical_analyzer import calculate_tactical_style_scores

# Get tactical style
tactical_scores = calculate_tactical_style_scores(
    team_id=33,
    league_id=39,
    season=2024
)

print("Tactical Profile (0-10 scale):")
for dimension, score in tactical_scores.items():
    print(f"  {dimension}: {score:.1f}")
```

### Example 5: Batch Predictions

```python
from src.prediction.prediction_engine import generate_prediction_with_reporting

fixtures = [
    (33, 40),  # Man Utd vs Liverpool
    (34, 35),  # Newcastle vs Tottenham
    (36, 37),  # Brighton vs Brentford
]

results = []
for home_id, away_id in fixtures:
    prediction = generate_prediction_with_reporting(
        home_team_id=home_id,
        away_team_id=away_id,
        league_id=39,
        season=2024,
        include_insights=False  # Faster without insights
    )
    results.append(prediction)

# Process results
for i, pred in enumerate(results):
    home_goals = pred['predictions']['home_team']['most_likely_goals']
    away_goals = pred['predictions']['away_team']['most_likely_goals']
    print(f"Fixture {i+1}: {home_goals}-{away_goals}")
```

---

## Rate Limiting

### API-Football Limits

- **Free Tier:** 100 requests/day
- **Basic Tier:** 3000 requests/day
- **Pro Tier:** 30000+ requests/day

### System Caching

To minimize API calls, the system caches:
- Venue data: 7 days
- Tactical data: 48 hours
- League standings: 24 hours
- Match results: Permanent

---

## Best Practices

1. **Use Caching:** Enable caching to reduce API calls and improve performance
2. **Batch Requests:** When predicting multiple matches, disable insights for faster processing
3. **Handle Errors:** Always wrap API calls in try-except blocks
4. **Respect Rate Limits:** Monitor your API usage to avoid hitting limits
5. **Validate Inputs:** Ensure team IDs and league IDs are valid before making calls

---

## Versioning

API follows semantic versioning: `MAJOR.MINOR.PATCH`

- **Current Version:** 6.0
- **Breaking Changes:** Major version increments
- **New Features:** Minor version increments
- **Bug Fixes:** Patch version increments

---

## Support

For API support:
- Documentation: This file
- Issues: GitHub Issues
- Email: support@example.com

---

**Last Updated:** October 4, 2025
**API Version:** 6.0
**Status:** Production Ready ✅
