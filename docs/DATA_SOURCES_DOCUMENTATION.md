# Data Sources Documentation
**Football Fixture Prediction System - Version 6.0**

This document details all data sources used throughout the application for venue analysis, tactical/strategy analysis, and manager analysis.

---

## Overview

The system uses **API-Football (via RapidAPI)** as its primary external data source, with local caching in **AWS DynamoDB** for performance optimization.

### Primary Data Source
- **Service:** API-Football v3
- **Provider:** RapidAPI
- **Base URL:** `https://api-football-v1.p.rapidapi.com/v3`
- **Authentication:** RapidAPI Key (environment variable: `RAPIDAPI_KEY`)

---

## 1. Venue Analysis Data Sources

### 1.1 Venue Information
**Source:** API-Football `/teams` endpoint

**What is Collected:**
```json
{
  "venue_id": "Unique stadium identifier",
  "venue_name": "Stadium name (e.g., 'Old Trafford')",
  "venue_city": "City location",
  "venue_address": "Physical address",
  "venue_capacity": "Stadium capacity",
  "venue_surface": "Playing surface type (grass/artificial)"
}
```

**API Endpoint Used:**
```
GET /v3/teams
Parameters:
  - id: team_id
  - league: league_id
  - season: season_year
```

**Implementation Location:**
- `src/data/api_client.py` - `get_venue_id()` function (line 145-185)
- `src/features/venue_analyzer.py` - VenueAnalyzer class

**Caching:**
- **Primary Cache:** DynamoDB table `venue_cache`
- **TTL:** 7 days (venues rarely change)
- **Cache Key:** `venue_{venue_id}`

### 1.2 Stadium-Specific Performance
**Source:** Derived from match results at specific venues

**What is Analyzed:**
- Home team win rate at the stadium
- Average goals scored at venue
- Average goals conceded at venue
- Clean sheet percentage
- High-scoring game frequency

**Implementation:**
- `src/features/venue_analyzer.py` - `analyze_venue_factors()` (line 60-120)
- Calculates stadium advantage multipliers

### 1.3 Geographic/Travel Data
**Source:** Calculated from venue coordinates

**What is Collected:**
- Stadium coordinates (latitude/longitude) - from API-Football
- Distance calculations between venues
- Travel fatigue factors
- Timezone differences

**Implementation:**
- `src/utils/geographic.py` - Distance and travel impact calculations
- Uses Haversine formula for distance calculation
- Travel fatigue formula: `1 - (distance_km / 1000) * 0.05`

---

## 2. Tactical/Strategy Analysis Data Sources

### 2.1 Formation Data
**Source:** API-Football `/fixtures/lineups/{match_id}` endpoint

**What is Collected:**
```json
{
  "home_formation": "4-3-3",
  "away_formation": "4-4-2",
  "starting_xi": [{
    "player": "Player details",
    "position": "Position on field",
    "grid": "Position grid reference"
  }],
  "substitutes": ["Bench players"],
  "coach": "Manager/coach information"
}
```

**API Endpoint Used:**
```
GET /v3/fixtures/lineups/{match_id}
```

**Implementation Location:**
- `src/data/tactical_data_collector.py` - `collect_formation_data()` (line 65-100)
- `src/data/tactical_data_collector.py` - `_fetch_formation_from_api()` (line 181-211)

**Caching:**
- **Cache Table:** DynamoDB `tactical_analysis_cache`
- **TTL:** 48 hours
- **Cache Key:** `formation_{match_id}`

### 2.2 Formation Characteristics Database
**Source:** Built-in tactical knowledge base

**What is Defined:**
```python
FORMATION_CHARACTERISTICS = {
    '4-4-2': {
        'strengths': ['balanced', 'solid_midfield', 'wide_play'],
        'weaknesses': ['vulnerable_to_overloads', 'limited_creativity'],
        'ideal_against': ['4-3-3', '3-5-2'],
        'vulnerable_to': ['4-2-3-1', '4-5-1'],
        'attacking_weight': 0.6,
        'defensive_weight': 0.6,
        'tactical_flexibility': 0.7
    },
    # ... 8 formations total
}
```

**Implementation:**
- `src/features/formation_analyzer.py` - Formation characteristics database
- Contains 8 common formations: 4-4-2, 4-3-3, 4-2-3-1, 3-5-2, 3-4-3, 4-5-1, 5-3-2, 5-4-1

### 2.3 Tactical Statistics
**Source:** Derived from API-Football match statistics

**What is Calculated:**
- **Possession Stats:** Ball possession percentage, territory control
- **Passing Stats:** Pass completion, short/long pass ratio, progressive passes
- **Attacking Stats:** Shots on target, expected goals (xG), attacking third entries
- **Defensive Stats:** Tackles, interceptions, blocks, defensive actions
- **Set Piece Stats:** Corner efficiency, free kick success, aerial duels
- **Pressing Stats:** High press success, PPDA (passes per defensive action)
- **Transition Stats:** Counter-attack speed, turnover recovery

**API Endpoint Used:**
```
GET /v3/fixtures/statistics
Parameters:
  - fixture: match_id
```

**Implementation:**
- `src/data/tactical_data_collector.py` - Multiple `_calculate_*_stats()` methods (line 224-250)
- `src/features/tactical_analyzer.py` - `calculate_tactical_style_scores()` (line 100-180)

### 2.4 Tactical Style Scoring
**Source:** Derived from aggregated match statistics

**8 Tactical Dimensions Scored (0-10 scale):**
1. **Possession Style** - How much a team dominates the ball
2. **Attacking Intensity** - Aggression in attack, shot frequency
3. **Defensive Solidity** - Defensive organization and resilience
4. **Counter Efficiency** - Effectiveness on counter-attacks
5. **Pressing Intensity** - High press and defensive aggression
6. **Build-up Speed** - Tempo of build-up play
7. **Width Usage** - Use of flanks vs central play
8. **Aerial Preference** - Reliance on aerial play

**Implementation:**
- `src/features/tactical_analyzer.py` - `calculate_tactical_style_scores()` (line 100-180)
- Normalizes scores using league-wide percentiles

---

## 3. Manager/Coach Analysis Data Sources

### 3.1 Manager Information
**Source:** API-Football team data (embedded in lineup data)

**What is Available:**
```json
{
  "coach": {
    "id": "Manager ID",
    "name": "Manager name",
    "photo": "Manager photo URL"
  }
}
```

**Current Status:** ⚠️ **PARTIALLY IMPLEMENTED**
- Manager data extraction from lineups: ✅ Available
- Manager tactical profile analysis: ⚠️ Placeholder implementation
- Manager history tracking: ❌ Not implemented

**Implementation Location:**
- `src/features/tactical_analyzer.py` - `get_manager_tactical_profile()` (line 453-521)
- Currently returns default profile - **needs enhancement**

### 3.2 Manager Tactical Profile (Planned)
**What Could Be Analyzed:**
- Formation preferences over career
- Tactical flexibility score
- Home/away strategy differences
- Response to score situations
- Substitution patterns
- Adaptation to opponent strength

**Current Implementation:**
```python
def _get_team_manager_data(self, team_id: int, league_id: int, season: int):
    """Get manager-specific tactical data."""
    try:
        # This would fetch manager tactical preferences
        return []  # ⚠️ Currently returns empty
    except Exception as e:
        logger.error(f"Error fetching manager data: {e}")
        return []
```

**Location:** `src/features/tactical_analyzer.py` (line 606-613)

---

## 4. Data Flow Architecture

### Data Collection Flow
```
┌─────────────────────────────────────────────────┐
│          External Data Source                   │
│         API-Football (RapidAPI)                 │
│                                                 │
│  Endpoints Used:                                │
│  • /teams (venue info)                          │
│  • /fixtures/lineups (formations)               │
│  • /fixtures/statistics (match stats)           │
│  • /standings (league tables)                   │
│  • /fixtures (match results)                    │
└─────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────┐
│           API Client Layer                      │
│      src/data/api_client.py                     │
│                                                 │
│  • Rate limiting (429 retry logic)              │
│  • Error handling                               │
│  • Response parsing                             │
└─────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────┐
│           Caching Layer                         │
│         AWS DynamoDB Tables                     │
│                                                 │
│  • venue_cache (7 day TTL)                      │
│  • tactical_analysis_cache (48 hour TTL)        │
│  • league_standings_cache (24 hour TTL)         │
└─────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────┐
│      Feature Extractors & Analyzers            │
│                                                 │
│  • VenueAnalyzer (Phase 2)                      │
│  • TacticalAnalyzer (Phase 4)                   │
│  • FormationAnalyzer (Phase 4)                  │
│  • TacticalDataCollector (Phase 4)              │
└─────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────┐
│        Prediction Engine                        │
│   src/prediction/prediction_engine.py           │
│                                                 │
│  Uses all analyzed data for predictions         │
└─────────────────────────────────────────────────┘
```

---

## 5. Data Source Limitations & Gaps

### Current Limitations

#### 5.1 Manager Analysis
- ⚠️ **Gap:** Manager tactical profiles not fully implemented
- **Impact:** Missing manager influence on tactical decisions
- **Workaround:** Uses team-level tactical analysis instead
- **Enhancement Needed:** Full manager history and preference tracking

#### 5.2 Real-Time Tactical Data
- ⚠️ **Gap:** Limited in-game tactical changes tracking
- **Impact:** Cannot detect formation changes during matches
- **Workaround:** Uses starting formation only
- **Enhancement Needed:** Live match event tracking

#### 5.3 Player-Level Data
- ⚠️ **Gap:** Individual player tactical roles not tracked
- **Impact:** Cannot analyze player-specific tactical impact
- **Workaround:** Formation-level analysis only
- **Enhancement Needed:** Player position and role tracking

### API-Football Limitations

1. **Rate Limiting:**
   - Free tier: 100 requests/day
   - Paid tier: 3000+ requests/day
   - System implements retry logic for 429 errors

2. **Data Availability:**
   - Historical data limited to recent seasons
   - Some lower league data may be incomplete
   - Real-time data has ~2-3 minute delay

3. **Cost Considerations:**
   - API calls consume quota
   - Caching strategy critical for cost control
   - Current cache TTLs optimized for cost/freshness balance

---

## 6. Alternative Data Sources (Not Currently Used)

### Potential Additional Sources

1. **Opta Sports Data**
   - More detailed tactical metrics
   - Player-level tracking data
   - **Not used:** Higher cost, complex integration

2. **StatsBomb**
   - Advanced event-level data
   - xG models and shot quality
   - **Not used:** Limited API access, expensive

3. **WhoScored / SofaScore**
   - Player ratings and tactical maps
   - **Not used:** Web scraping required (against ToS)

4. **Official League APIs**
   - Premier League API, Bundesliga API, etc.
   - **Not used:** Multiple integrations needed, varying data formats

---

## 7. Database Migration Considerations

### If Migrating to MongoDB

**Current DynamoDB Tables to Migrate:**

1. **venue_cache**
   ```javascript
   // MongoDB Collection: venues
   {
     _id: ObjectId,
     venue_id: Number,
     venue_name: String,
     venue_city: String,
     capacity: Number,
     surface: String,
     coordinates: { lat: Number, lng: Number },
     cached_at: Date,
     ttl: Date  // For TTL index
   }
   ```

2. **tactical_analysis_cache**
   ```javascript
   // MongoDB Collection: tactical_data
   {
     _id: ObjectId,
     match_id: Number,
     formation_data: Object,
     tactical_stats: Object,
     cached_at: Date,
     ttl: Date
   }
   ```

3. **league_standings_cache**
   ```javascript
   // MongoDB Collection: league_standings
   {
     _id: ObjectId,
     league_id: Number,
     season: Number,
     standings: Array,
     updated_at: Date,
     ttl: Date
   }
   ```

**Migration Effort Estimate:**
- Database abstraction layer: 1-2 days
- Cache implementation changes: 1 day
- Testing and validation: 1 day
- **Total: ~3-4 days**

---

## 8. Data Quality & Reliability

### Data Validation
- ✅ All API responses validated for expected structure
- ✅ Fallback to default values when data unavailable
- ✅ Graceful degradation if external APIs fail
- ✅ Logging of all data quality issues

### Monitoring
- CloudWatch metrics for API call success/failure rates
- Cache hit/miss ratio tracking
- Data freshness monitoring
- Alert on API quota approaching limits

---

## 9. Summary

### Data Sources by Feature

| Feature | Primary Source | Backup/Fallback | Update Frequency |
|---------|---------------|-----------------|------------------|
| **Venue Info** | API-Football `/teams` | Default neutral values | 7 days (cached) |
| **Stadium Performance** | Calculated from match history | League averages | Per prediction |
| **Travel/Geography** | API-Football + calculations | Direct distance | Static |
| **Formations** | API-Football `/fixtures/lineups` | Default 4-4-2 | 48 hours (cached) |
| **Tactical Stats** | API-Football `/fixtures/statistics` | League averages | Per match |
| **Tactical Styles** | Derived from aggregated stats | Neutral 5.0 scores | Per season |
| **Manager Profile** | ⚠️ Placeholder (API-Football) | Default profile | Not implemented |

### Key Takeaways

1. ✅ **Single Primary Source:** API-Football via RapidAPI handles all external data
2. ✅ **Robust Caching:** DynamoDB caching minimizes API calls and costs
3. ✅ **Graceful Degradation:** System works even when external data unavailable
4. ⚠️ **Manager Analysis Gap:** Currently uses placeholder - needs enhancement
5. 💡 **MongoDB Migration:** Straightforward - 3-4 days effort with clear mappings

---

**Last Updated:** October 4, 2025
**System Version:** 6.0
**Documentation Status:** Complete