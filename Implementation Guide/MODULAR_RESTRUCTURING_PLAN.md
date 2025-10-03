# Modular Restructuring Plan

**Status:** Draft for Review  
**Created:** 2025-10-03  
**Purpose:** Break down monolithic files into maintainable, testable modules aligned with new architecture

---

## Current Code Analysis

### File Size Assessment
- **`makeTeamRankings.py`**: 2,568 lines ⚠️ **CRITICAL - Too Large**
- **`computeTeamParameters.py`**: 1,040 lines ⚠️ **Large - Needs Refactoring**
- **`computeLeagueParameters.py`**: 648 lines ✅ **Moderate - Could Benefit from Modularization**
- **`checkScores.py`**: 315 lines ✅ **Small but Important - Score Update Service**

### Problems Identified

#### 1. **Mixed Responsibilities** 
**Issue:** Each file combines multiple concerns:
- Lambda orchestration + Business logic + Data access + Utilities
- **Impact:** Hard to test, maintain, and extend
- **Example:** `makeTeamRankings.py` contains prediction logic, API calls, database operations, and mathematical functions all mixed together

#### 2. **Code Duplication**
**Issue:** Similar functions repeated across files:
- Data conversion functions (`convert_floats_to_decimal`, `decimal_default`)
- API calling patterns with retry logic
- DynamoDB operations
- **Impact:** Maintenance nightmare, inconsistent behavior

#### 3. **Poor Testability**
**Issue:** Monolithic functions are hard to unit test:
- `process_fixtures()` is 285 lines doing everything
- Tight coupling between API calls and business logic
- **Impact:** Low test coverage, difficult debugging

#### 4. **Architecture Misalignment**
**Issue:** Current structure doesn't support new architecture concepts:
- No clear place for opponent classification
- No separation for form analysis
- No tactical feature modules
- **Impact:** New features will make files even larger

---

## Proposed Modular Structure

### **1. Core Business Logic Modules**

#### `src/prediction/`
**Purpose:** Pure prediction logic separated from data access
**Reason:** Enables testing with mock data, cleaner architecture

```
prediction/
├── __init__.py
├── prediction_engine.py      # Main orchestration
├── baseline_calculator.py    # Raw model calculations
├── probability_calculator.py # Convert lambda to probabilities
└── coordination_engine.py    # Coordinated predictions
```

**What moves here:**
- `calculate_coordinated_predictions()` from `makeTeamRankings.py`
- `calculate_to_score()` and related prediction functions
- `analyze_match_probabilities()`

**Reason:** Separates prediction logic from data fetching, making it easier to test different scenarios and modify prediction algorithms.

#### `src/parameters/`
**Purpose:** Parameter calculation logic for teams and leagues
**Reason:** Central location for all parameter-related calculations

```
parameters/
├── __init__.py
├── team_calculator.py        # fit_team_params logic
├── league_calculator.py      # fit_league_params logic
├── segmented_calculator.py   # NEW - opponent-based segmentation
└── multiplier_calculator.py  # Correction multiplier logic
```

**What moves here:**
- `fit_team_params()` from `computeTeamParameters.py`
- `fit_league_params()` from `computeLeagueParameters.py`
- `calculate_team_multipliers()` and `calculate_league_multipliers()`

**Reason:** Groups related parameter calculations, makes it easier to add segmented parameter logic in Phase 1.

#### `src/statistics/`
**Purpose:** Statistical and mathematical functions
**Reason:** Reusable statistical functions shouldn't be scattered across files

```
statistics/
├── __init__.py
├── distributions.py          # Poisson, Negative Binomial functions
├── smoothing.py             # Bayesian smoothing functions
├── optimization.py          # Grid search, weight tuning
└── validation.py            # Statistical validation functions
```

**What moves here:**
- `nb_pmf()`, `poisson_pmf()` from multiple files
- `bayesian_smooth_rate()`, `bayesian_smooth_binary()` from `makeTeamRankings.py`
- `tune_weights_grid()` from both parameter files
- `empirical_hist()`, `nb_probs()`

**Reason:** Centralizes mathematical functions for reuse, easier testing, and potential performance optimization.

### **2. Data Access Layer**

#### `src/data/`
**Purpose:** Clean separation between data access and business logic
**Reason:** Enables mocking for tests, easier to swap data sources

```
data/
├── __init__.py
├── api_client.py            # All API-Football calls
├── database_client.py       # All DynamoDB operations
├── cache_manager.py         # NEW - Caching logic
└── data_models.py           # Data validation and transformation
```

**What moves here:**
- All API calling functions from multiple files
- All DynamoDB operations
- Data conversion utilities
- Retry logic and error handling

**Reason:** Single responsibility for data access, easier to implement caching, better error handling consistency.

#### `src/data/api_client.py` Consolidation
**Functions to consolidate:**
- `get_league_teams()`, `get_football_match_scores()`, `get_league_start_date()`
- `get_team_statistics()`, `get_venue_id()`, `get_next_fixture()`
- `get_last_five_games()`, `get_head_to_head()`
- `get_injured_players()`, `get_player_statistics()`
- `get_fixtures_goals()` from `checkScores.py` - **Enhanced for comprehensive match data**

**Reason:** Single place for all external API calls with consistent retry logic, rate limiting, and error handling.

#### `src/data/match_data_collector.py` (NEW)
**Purpose:** Enhanced match data collection beyond basic scores
**Reason:** Support for Phase 4+ tactical features and comprehensive analysis

```
match_data_collector.py   # Comprehensive match statistics
├── collect_basic_scores()      # Current functionality from checkScores.py
├── collect_halftime_scores()   # NEW - Halftime score tracking
├── collect_match_statistics()  # NEW - Shots, possession, cards, etc.
├── collect_player_statistics() # NEW - Individual player performance
└── validate_match_data()       # NEW - Data quality validation
```

**Enhanced Data Structure:**
```python
match_data = {
    'fixture_id': 12345,
    'basic_scores': {
        'home_goals': 2,
        'away_goals': 1,
        'final_result': '2-1'
    },
    'halftime_scores': {          # NEW
        'home_halftime': 1,
        'away_halftime': 0,
        'halftime_result': '1-0'
    },
    'match_statistics': {         # NEW - Supporting Phase 4 tactical analysis
        'home_shots': 15,
        'away_shots': 8,
        'home_shots_on_target': 6,
        'away_shots_on_target': 3,
        'home_possession': 65,
        'away_possession': 35,
        'home_passes': 542,
        'away_passes': 298,
        'home_pass_accuracy': 87,
        'away_pass_accuracy': 82,
        'home_corners': 7,
        'away_corners': 3,
        'home_fouls': 12,
        'away_fouls': 16,
        'home_yellow_cards': 2,
        'away_yellow_cards': 3,
        'home_red_cards': 0,
        'away_red_cards': 1
    },
    'player_statistics': {        # NEW - Supporting tactical analysis
        'home_players': [...],
        'away_players': [...]
    }
}
```

**Reason:** The new architecture's Phase 4 tactical analysis requires comprehensive match statistics beyond basic scores. This structure supports shots, possession, and other metrics mentioned in the tactical feature calculations.

### **3. New Architecture Modules**

#### `src/features/` (NEW)
**Purpose:** Support new architecture features
**Reason:** Clean implementation space for Phase 1+ features

```
features/
├── __init__.py
├── opponent_classifier.py    # Phase 1 - opponent strength classification
├── form_analyzer.py          # Phase 3 - form deviation detection  
├── tactical_analyzer.py      # Phase 4 - tactical style features
└── team_classifier.py        # Phase 5 - team classification
```

**Reason:** Dedicated space for new features without polluting existing code, aligned with implementation phases.

#### `src/infrastructure/` (NEW)
**Purpose:** Version tracking and transition management
**Reason:** Critical for Phase 0 deployment

```
infrastructure/
├── __init__.py
├── version_manager.py        # Architecture version tracking
├── transition_manager.py     # Multiplier transition logic
└── monitoring.py            # Transition metrics and logging
```

**Reason:** Supports the critical Phase 0 requirements for preventing multiplier contamination.

### **4. Lambda Handlers (Simplified)**

#### `handlers/`
**Purpose:** Thin orchestration layer
**Reason:** Lambda handlers should only orchestrate, not contain business logic

```
handlers/
├── __init__.py
├── team_parameters_handler.py    # Simplified orchestration
├── league_parameters_handler.py  # Simplified orchestration
├── prediction_handler.py         # Simplified orchestration
└── match_data_handler.py          # Enhanced from checkScores.py
```

#### Enhanced Match Data Handler
**Current `checkScores.py` Analysis:**
- **Size:** 315 lines ✅ **Small but Important**
- **Purpose:** Updates fixture records with match outcomes
- **Structure:** Well-organized but limited to basic scores

**Restructuring `checkScores.py` → `match_data_handler.py`:**

**What stays in handler:**
- Event parsing and time range calculation
- Error handling and logging for match data updates
- Orchestration of data collection workflow

**What moves to modules:**
- `query_dynamodb_records()` → `src/data/database_client.py`
- `get_fixtures_goals()` → `src/data/api_client.py` (enhanced)
- `add_attribute_to_dynamodb_item()` → `src/data/database_client.py`
- `get_league_start_date()` → `src/data/api_client.py` (deduplicated)

**Enhanced Capabilities:**
```python
# match_data_handler.py (simplified orchestration)
def lambda_handler(event, context):
    """Enhanced match data collection orchestration."""
    time_range = parse_time_range(event)
    
    for league in all_leagues:
        # Basic score collection (existing functionality)
        basic_scores = collect_basic_scores(league, time_range)
        
        # NEW: Enhanced data collection
        halftime_scores = collect_halftime_scores(league, time_range)
        match_statistics = collect_match_statistics(league, time_range)
        
        # Update database with comprehensive data
        update_match_records(basic_scores, halftime_scores, match_statistics)
```

**Reason:** `checkScores.py` becomes the foundation for comprehensive match data collection, supporting Phase 4+ tactical analysis while maintaining clean separation of concerns.

### **5. Shared Utilities**

#### `src/utils/`
**Purpose:** Pure utility functions used across modules
**Reason:** Eliminates code duplication

```
utils/
├── __init__.py
├── converters.py            # Data type conversions
## 📊 Enhanced Match Data Architecture

### **Support for Halftime Scores & Match Statistics**

**YES** - The new architecture **DOES** include comprehensive match data collection beyond basic full-time scores:

#### **Phase 4 Tactical Analysis Requirements**
The implementation guide's **Phase 4: Derived Tactical Style Features** specifically mentions calculations that require enhanced match statistics:

```python
# From NEW_SYSTEM_ARCHITECTURE.md Phase 4
def calculate_counter_attacking_efficiency(team_matches, is_home):
    """
    Counter-attacking efficiency: goals per shot on target.
    High efficiency with fewer total shots suggests counter-attacking.
    """
    for match in team_matches:
        goals = match.get('home_goals' if is_home else 'away_goals', 0)
        shots_on_target = match.get('home_shots_on_target' if is_home else 'away_shots_on_target', 0)
```

**This requires collecting shot statistics that `checkScores.py` currently doesn't gather.**

#### **Data Architecture Enhancements**

**Current `checkScores.py` Limitation:**
- Only collects basic full-time scores (`goals.home`, `goals.away`)
- Missing halftime scores, shots, possession, and other tactical metrics

**Enhanced Data Collection Strategy:**

```python
# Enhanced match data structure supporting all phases
enhanced_match_data = {
    'fixture_id': 12345,
    'basic_scores': {
        'home_goals': 2,
        'away_goals': 1
    },
    'halftime_scores': {          # NEW - Phase 1+ requirement
        'home_halftime': 1,
        'away_halftime': 0
    },
    'match_statistics': {         # NEW - Phase 4 tactical analysis
        'home_shots': 15,
        'away_shots': 8,
        'home_shots_on_target': 6,
        'away_shots_on_target': 3,
        'home_possession': 65,
        'away_possession': 35,
        'home_passes': 542,
        'away_passes': 298,
        'home_pass_accuracy': 87,
        'away_pass_accuracy': 82,
        'home_corners': 7,
        'away_corners': 3,
        'home_fouls': 12,
        'away_fouls': 16,
        'home_yellow_cards': 2,
        'away_yellow_cards': 3
    }
}
```

#### **Implementation Phases**

**Phase 1 (Immediate):** Add halftime score collection
- **Reason:** Provides better form analysis and opponent strength context
- **API Endpoint:** API-Football `/fixtures` endpoint includes halftime scores
- **Storage:** Add `halftime_scores` field to `game_fixtures` table

**Phase 4 (Tactical Features):** Add comprehensive match statistics
- **Reason:** Required for tactical style calculations (counter-attacking efficiency, possession-based play)
- **API Endpoint:** API-Football `/fixtures/statistics` endpoint
- **Storage:** Add `match_statistics` field to `game_fixtures` table

#### **Database Schema Evolution**

```python
# game_fixtures table enhancement
{
    'fixture_id': 456,
    'timestamp': 1728000000,
    # ... existing fields ...
    
    # Phase 1 addition
    'halftime_scores': {
        'home': 1,
        'away': 0
    },
    
    # Phase 4 addition  
    'match_statistics': {
        'shots': {'home': 15, 'away': 8},
        'shots_on_target': {'home': 6, 'away': 3},
        'possession': {'home': 65, 'away': 35},
        'passes': {'home': 542, 'away': 298},
        'pass_accuracy': {'home': 87, 'away': 82},
        # ... additional stats as needed
    }
}
```

#### **Benefits of Enhanced Data Collection**

1. **Tactical Analysis Support:** Enables Phase 4 tactical style features
2. **Better Form Analysis:** Halftime patterns reveal team consistency  
3. **Improved Predictions:** More data points for model refinement
4. **Future-Proofing:** Infrastructure ready for advanced analytics

**Reason:** The modular restructuring creates the perfect foundation to enhance `checkScores.py` into a comprehensive match data collection system that supports all phases of the new architecture.
├── validators.py            # Input validation
├── formatters.py            # Output formatting
└── constants.py             # Shared constants
```

**What moves here:**
- `convert_floats_to_decimal()`, `convert_for_dynamodb()`
- `decimal_default()`, data validation functions
- Shared constants and configuration

**Reason:** Single source of truth for common operations, easier maintenance.

---

## Implementation Benefits

### **1. Testability** 
✅ **Pure functions:** Business logic separated from I/O  
✅ **Mockable dependencies:** Data layer can be mocked  
✅ **Focused tests:** Each module has specific test scope  

### **2. Maintainability**
✅ **Single responsibility:** Each module has one clear purpose  
✅ **Reduced coupling:** Clear interfaces between modules  
✅ **Code reuse:** Common functions in shared utilities  

### **3. Scalability**
✅ **Feature addition:** New architecture features have dedicated space  
✅ **Performance optimization:** Can optimize individual modules  
✅ **Team development:** Multiple developers can work on different modules  

### **4. Architecture Alignment**
✅ **Phase support:** Structure supports all 6 implementation phases  
✅ **Version compatibility:** Infrastructure modules handle transitions  
✅ **Production readiness:** Clean separation supports monitoring and debugging  

---

## Migration Strategy

### **Phase 0: Infrastructure Setup**
1. Create new directory structure
2. Move utility functions to shared modules
3. Implement version tracking modules
4. **Risk:** Low - mostly new code

### **Phase 1: Data Layer**
1. Extract API client functions
2. Extract database operations  
3. Update Lambda handlers to use new modules
4. **Risk:** Medium - requires testing API compatibility

### **Phase 2: Business Logic**
1. Extract parameter calculation logic
2. Extract prediction logic
3. Extract statistical functions
4. **Risk:** High - core business logic, requires extensive testing

### **Phase 3: Feature Integration**
1. Implement new architecture features in dedicated modules
2. Integrate with existing prediction pipeline
3. **Risk:** Medium - new features, but isolated modules

### **Total Effort Estimate: 3-4 weeks**
- Week 1: Infrastructure + Data layer
- Week 2: Business logic extraction
- Week 3: Integration testing + bug fixes
- Week 4: New feature module preparation

---

## Decision Rationale Summary

| **Decision** | **Reason** | **Benefit** |
|--------------|------------|-------------|
| **Separate data access** | Business logic mixed with API calls | Testable, mockable, maintainable |
| **Extract statistical functions** | Duplicated across files | Reusable, consistent, optimizable |
| **Thin Lambda handlers** | Too much logic in handlers | Easier deployment, testing, debugging |
| **Feature modules** | New architecture needs dedicated space | Clean implementation, phase alignment |
| **Infrastructure modules** | Phase 0 requirements critical | Version tracking, transition management |
| **Shared utilities** | Code duplication everywhere | DRY principle, consistency |

This modular structure will reduce the largest file (`makeTeamRankings.py`) from 2,568 lines to approximately:
- **Handler:** ~100 lines
- **Prediction modules:** ~300-400 lines each
- **Data modules:** ~200-300 lines each
- **Feature modules:** ~200-500 lines each

**Result:** Maximum file size ~500 lines, average ~250 lines, much more maintainable and testable.