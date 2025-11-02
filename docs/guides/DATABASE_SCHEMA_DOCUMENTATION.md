# Database Schema Documentation - game_fixtures Table

**Document Version:** 1.0
**Created:** October 4, 2025
**Table:** `game_fixtures`
**Purpose:** Store complete fixture predictions with team statistics, historical data, and prediction probabilities

---

## Overview

This document provides comprehensive documentation of the `game_fixtures` DynamoDB table schema, including all fields written by the prediction handler and exposed by the API service.

**Source Code Reference:** [src/handlers/prediction_handler.py](../src/handlers/prediction_handler.py) lines 283-316

---

## Table Schema

### Primary Key

| Attribute | Type | Description |
|-----------|------|-------------|
| `fixture_id` | Number | Unique fixture identifier from API-Football - **Partition Key** |

**Note**: This table uses a simple primary key with **no sort key**. The `timestamp` field is a regular attribute, not part of the primary key.

### Global Secondary Indexes (GSI)

| Index Name | Partition Key | Sort Key | Purpose |
|------------|---------------|----------|---------|
| `country-league-index` | `country` (String) | `league` (String) | Query fixtures by country and league |
| `country-timestamp-index` | `country` (String) | `timestamp` (Number) | Query fixtures by country and time range |

---

## Complete Record Structure

### Top-Level Fields

```json
{
  "fixture_id": Number,           // Unique fixture ID
  "timestamp": Number,            // Match timestamp (Unix epoch)
  "date": String,                 // ISO 8601 date/time (e.g., "2024-01-15T19:45:00+00:00")
  "country": String,              // Country name (e.g., "England")
  "league": String,               // League name (e.g., "Premier League")
  "league_id": Number,            // League ID
  "season": Number,               // Season year (e.g., 2024)
  "venue": Object,                // Venue information
  "home": Object,                 // Home team complete data
  "away": Object,                 // Away team complete data
  "h2h": Array,                   // Head-to-head match history
  "predictions": Object,          // Prediction probabilities (league params)
  "alternate_predictions": Object, // Prediction probabilities (team params)
  "coordination_info": Object     // Coordination metadata
}
```

---

## Detailed Field Specifications

### 1. Venue Object

```json
"venue": {
  "id": Number,                   // Venue ID
  "name": String,                 // Venue name (e.g., "Old Trafford")
  "city": String,                 // City name (e.g., "Manchester")
  "capacity": Number,             // Stadium capacity
  "surface": String               // Surface type (e.g., "grass")
}
```

### 2. Home Team Object

Complete home team data including statistics, predictions, and metadata:

```json
"home": {
  // Basic Team Information
  "team_id": Number,              // Team ID (e.g., 33)
  "team_name": String,            // Team name (e.g., "Manchester United")
  "team_logo": String,            // Team logo URL
  "Opponent": String,             // Opponent team name
  "date": String,                 // Match date (ISO 8601)

  // Prediction Results (League Parameters)
  "probability_to_score": Decimal, // Probability to score (0.0-1.0)
  "predicted_goals": Decimal,     // Expected goals (e.g., 1.5)
  "likelihood": Decimal,          // Prediction likelihood/confidence

  // Prediction Results (Team-Specific Parameters)
  "probability_to_score_alt": Decimal, // Alt probability to score
  "predicted_goals_alt": Decimal, // Alt expected goals
  "likelihood_alt": Decimal,      // Alt prediction likelihood

  // Team Performance Metrics
  "home_performance": Decimal,    // Home performance rating (0.0-1.0)
  "Wins": Number,                 // Total wins this season
  "Draws": Number,                // Total draws this season
  "Losses": Number,               // Total losses this season
  "Goals_For": Number,            // Total goals scored
  "Goals_Against": Number,        // Total goals conceded
  "Points": Number,               // Total points
  "Position": Number,             // League position
  "Form": String,                 // Recent form (e.g., "WWDLL")

  // Goal Statistics
  "team_goal_stats": {
    "home": {
      "average": Decimal,         // Average home goals per game
      "total": Number,            // Total home goals
      "minute": {
        "0-15": {"total": Number, "percentage": String},
        "16-30": {"total": Number, "percentage": String},
        "31-45": {"total": Number, "percentage": String},
        "46-60": {"total": Number, "percentage": String},
        "61-75": {"total": Number, "percentage": String},
        "76-90": {"total": Number, "percentage": String},
        "91-105": {"total": Number, "percentage": String},
        "106-120": {"total": Number, "percentage": String}
      }
    },
    "away": {
      "average": Decimal,
      "total": Number,
      "minute": { /* same structure as home */ }
    },
    "all": {
      "average": Decimal,
      "total": Number,
      "minute": { /* same structure as home */ }
    }
  },

  // Next Fixture Information
  "next_fixture": {
    "fixture_id": Number,
    "date": String,
    "opponent": String,
    "venue": String              // "home" or "away"
  },

  // Past Fixtures (Last 5 Games)
  "past_fixtures": [
    {
      "fixture_id": Number,
      "date": String,
      "opponent": String,
      "result": String,          // "W", "D", or "L"
      "score": String,           // e.g., "2-1"
      "venue": String            // "home" or "away"
    }
    // ... up to 5 fixtures
  ],

  // Injuries & Suspensions
  "injuries": [
    {
      "player_id": Number,
      "player_name": String,
      "type": String,            // "injury" or "suspension"
      "reason": String,          // Injury/suspension reason
      "expected_return": String  // Return date or "Unknown"
    }
  ]
}
```

### 3. Away Team Object

**Structure**: Identical to home team object, but with away-specific metrics

```json
"away": {
  // Same structure as home team
  "team_id": Number,
  "team_name": String,
  "team_logo": String,
  "Opponent": String,
  // ... (all same fields as home team)
  "away_performance": Decimal,   // Away performance rating (instead of home_performance)
  // ... (rest of fields identical)
}
```

### 4. Head-to-Head (h2h) Array

Historical matchups between the two teams:

```json
"h2h": [
  {
    "fixture_id": Number,
    "date": String,              // ISO 8601 date
    "home_team": String,         // Home team name
    "away_team": String,         // Away team name
    "home_score": Number,        // Home team score
    "away_score": Number,        // Away team score
    "winner": String,            // "home", "away", or "draw"
    "venue": String              // Venue name
  }
  // ... historical matches (typically 10-20 most recent)
]
```

### 5. Predictions Object (League Parameters)

Prediction probabilities calculated using league-wide parameters:

```json
"predictions": {
  // Match Outcome Probabilities
  "home_win": Decimal,           // Probability of home win (0.0-1.0)
  "draw": Decimal,               // Probability of draw (0.0-1.0)
  "away_win": Decimal,           // Probability of away win (0.0-1.0)

  // Goals Probabilities
  "both_teams_to_score": Decimal, // BTTS probability
  "over_1_5": Decimal,           // Over 1.5 goals probability
  "over_2_5": Decimal,           // Over 2.5 goals probability
  "over_3_5": Decimal,           // Over 3.5 goals probability
  "under_1_5": Decimal,          // Under 1.5 goals probability
  "under_2_5": Decimal,          // Under 2.5 goals probability
  "under_3_5": Decimal,          // Under 3.5 goals probability

  // Exact Score Probabilities (Top Likelihoods)
  "exact_score": {
    "0-0": Decimal,
    "1-0": Decimal,
    "0-1": Decimal,
    "1-1": Decimal,
    "2-0": Decimal,
    "0-2": Decimal,
    "2-1": Decimal,
    "1-2": Decimal,
    "2-2": Decimal,
    "3-0": Decimal,
    "0-3": Decimal,
    "3-1": Decimal,
    "1-3": Decimal,
    "3-2": Decimal,
    "2-3": Decimal
    // ... additional scores up to 5-5
  },

  // Confidence & Best Bet
  "confidence": Decimal,         // Overall prediction confidence (0.0-1.0)
  "best_bet": Array,             // Best betting recommendations (e.g., ["Over 2.5", "Home Win"])
  "value_bets": Array            // Value betting opportunities
}
```

### 6. Alternate Predictions Object (Team Parameters)

Prediction probabilities calculated using team-specific parameters:

```json
"alternate_predictions": {
  // Same structure as predictions object
  "home_win": Decimal,
  "draw": Decimal,
  "away_win": Decimal,
  "both_teams_to_score": Decimal,
  "over_2_5": Decimal,
  // ... (same fields as predictions)
}
```

### 7. Coordination Info Object

Metadata about prediction calculation coordination:

```json
"coordination_info": {
  "league_coordination": {
    "coordination_applied": Boolean,  // Was coordination successful?
    "home_lambda_original": Decimal,  // Original home lambda
    "away_lambda_original": Decimal,  // Original away lambda
    "home_lambda_adjusted": Decimal,  // Adjusted home lambda
    "away_lambda_adjusted": Decimal,  // Adjusted away lambda
    "adjustment_factor": Decimal,     // Coordination adjustment factor
    "fallback_reason": String         // Reason if fallback used (optional)
  },
  "team_coordination": {
    // Same structure as league_coordination
    "coordination_applied": Boolean,
    "home_lambda_original": Decimal,
    "away_lambda_original": Decimal,
    "home_lambda_adjusted": Decimal,
    "away_lambda_adjusted": Decimal,
    "adjustment_factor": Decimal,
    "fallback_reason": String
  }
}
```

---

## Complete Sample JSON Record

```json
{
  "fixture_id": 1035047,
  "timestamp": 1704477600,
  "date": "2024-01-05T20:00:00+00:00",
  "country": "England",
  "league": "Premier League",
  "league_id": 39,
  "season": 2024,

  "venue": {
    "id": 556,
    "name": "Old Trafford",
    "city": "Manchester",
    "capacity": 76212,
    "surface": "grass"
  },

  "home": {
    "team_id": 33,
    "team_name": "Manchester United",
    "team_logo": "https://media.api-sports.io/football/teams/33.png",
    "Opponent": "Tottenham Hotspur",
    "date": "2024-01-05T20:00:00+00:00",

    "probability_to_score": 0.72,
    "predicted_goals": 1.8,
    "likelihood": 0.85,

    "probability_to_score_alt": 0.75,
    "predicted_goals_alt": 1.9,
    "likelihood_alt": 0.87,

    "home_performance": 0.68,
    "Wins": 12,
    "Draws": 5,
    "Losses": 3,
    "Goals_For": 38,
    "Goals_Against": 22,
    "Points": 41,
    "Position": 3,
    "Form": "WWDLW",

    "team_goal_stats": {
      "home": {
        "average": 2.1,
        "total": 21,
        "minute": {
          "0-15": {"total": 3, "percentage": "14.3%"},
          "16-30": {"total": 5, "percentage": "23.8%"},
          "31-45": {"total": 4, "percentage": "19.0%"},
          "46-60": {"total": 3, "percentage": "14.3%"},
          "61-75": {"total": 4, "percentage": "19.0%"},
          "76-90": {"total": 2, "percentage": "9.5%"},
          "91-105": {"total": 0, "percentage": "0.0%"},
          "106-120": {"total": 0, "percentage": "0.0%"}
        }
      },
      "away": {
        "average": 1.7,
        "total": 17,
        "minute": {
          "0-15": {"total": 2, "percentage": "11.8%"},
          "16-30": {"total": 3, "percentage": "17.6%"},
          "31-45": {"total": 4, "percentage": "23.5%"},
          "46-60": {"total": 3, "percentage": "17.6%"},
          "61-75": {"total": 3, "percentage": "17.6%"},
          "76-90": {"total": 2, "percentage": "11.8%"},
          "91-105": {"total": 0, "percentage": "0.0%"},
          "106-120": {"total": 0, "percentage": "0.0%"}
        }
      },
      "all": {
        "average": 1.9,
        "total": 38,
        "minute": {
          "0-15": {"total": 5, "percentage": "13.2%"},
          "16-30": {"total": 8, "percentage": "21.1%"},
          "31-45": {"total": 8, "percentage": "21.1%"},
          "46-60": {"total": 6, "percentage": "15.8%"},
          "61-75": {"total": 7, "percentage": "18.4%"},
          "76-90": {"total": 4, "percentage": "10.5%"},
          "91-105": {"total": 0, "percentage": "0.0%"},
          "106-120": {"total": 0, "percentage": "0.0%"}
        }
      }
    },

    "next_fixture": {
      "fixture_id": 1035055,
      "date": "2024-01-12T15:00:00+00:00",
      "opponent": "Liverpool",
      "venue": "away"
    },

    "past_fixtures": [
      {
        "fixture_id": 1035040,
        "date": "2024-01-02T20:00:00+00:00",
        "opponent": "Nottingham Forest",
        "result": "W",
        "score": "3-0",
        "venue": "home"
      },
      {
        "fixture_id": 1035033,
        "date": "2023-12-26T17:30:00+00:00",
        "opponent": "Aston Villa",
        "result": "W",
        "score": "2-1",
        "venue": "away"
      },
      {
        "fixture_id": 1035028,
        "date": "2023-12-23T15:00:00+00:00",
        "opponent": "West Ham United",
        "result": "D",
        "score": "1-1",
        "venue": "home"
      },
      {
        "fixture_id": 1035021,
        "date": "2023-12-16T20:00:00+00:00",
        "opponent": "Liverpool",
        "result": "L",
        "score": "0-2",
        "venue": "away"
      },
      {
        "fixture_id": 1035015,
        "date": "2023-12-10T15:00:00+00:00",
        "opponent": "Chelsea",
        "result": "W",
        "score": "2-1",
        "venue": "home"
      }
    ],

    "injuries": [
      {
        "player_id": 18950,
        "player_name": "Lisandro Martinez",
        "type": "injury",
        "reason": "Muscle Injury",
        "expected_return": "2024-01-20"
      },
      {
        "player_id": 19188,
        "player_name": "Mason Mount",
        "type": "injury",
        "reason": "Calf Injury",
        "expected_return": "2024-01-15"
      }
    ]
  },

  "away": {
    "team_id": 47,
    "team_name": "Tottenham Hotspur",
    "team_logo": "https://media.api-sports.io/football/teams/47.png",
    "Opponent": "Manchester United",
    "date": "2024-01-05T20:00:00+00:00",

    "probability_to_score": 0.68,
    "predicted_goals": 1.5,
    "likelihood": 0.82,

    "probability_to_score_alt": 0.70,
    "predicted_goals_alt": 1.6,
    "likelihood_alt": 0.84,

    "away_performance": 0.62,
    "Wins": 11,
    "Draws": 4,
    "Losses": 5,
    "Goals_For": 35,
    "Goals_Against": 25,
    "Points": 37,
    "Position": 5,
    "Form": "WLDWL",

    "team_goal_stats": {
      "home": {
        "average": 1.9,
        "total": 19,
        "minute": { /* ... */ }
      },
      "away": {
        "average": 1.6,
        "total": 16,
        "minute": { /* ... */ }
      },
      "all": {
        "average": 1.75,
        "total": 35,
        "minute": { /* ... */ }
      }
    },

    "next_fixture": {
      "fixture_id": 1035056,
      "date": "2024-01-13T17:30:00+00:00",
      "opponent": "Manchester City",
      "venue": "home"
    },

    "past_fixtures": [
      /* ... similar structure to home team */
    ],

    "injuries": [
      {
        "player_id": 19765,
        "player_name": "James Maddison",
        "type": "injury",
        "reason": "Ankle Injury",
        "expected_return": "2024-01-10"
      }
    ]
  },

  "h2h": [
    {
      "fixture_id": 1003456,
      "date": "2023-08-26T12:30:00+00:00",
      "home_team": "Tottenham Hotspur",
      "away_team": "Manchester United",
      "home_score": 2,
      "away_score": 0,
      "winner": "home",
      "venue": "Tottenham Hotspur Stadium"
    },
    {
      "fixture_id": 987654,
      "date": "2023-04-27T20:00:00+00:00",
      "home_team": "Manchester United",
      "away_team": "Tottenham Hotspur",
      "home_score": 2,
      "away_score": 2,
      "winner": "draw",
      "venue": "Old Trafford"
    },
    {
      "fixture_id": 954321,
      "date": "2022-10-19T20:00:00+00:00",
      "home_team": "Tottenham Hotspur",
      "away_team": "Manchester United",
      "home_score": 2,
      "away_score": 0,
      "winner": "home",
      "venue": "Tottenham Hotspur Stadium"
    }
  ],

  "predictions": {
    "home_win": 0.48,
    "draw": 0.27,
    "away_win": 0.25,

    "both_teams_to_score": 0.72,
    "over_1_5": 0.85,
    "over_2_5": 0.62,
    "over_3_5": 0.32,
    "under_1_5": 0.15,
    "under_2_5": 0.38,
    "under_3_5": 0.68,

    "exact_score": {
      "0-0": 0.05,
      "1-0": 0.12,
      "0-1": 0.08,
      "1-1": 0.15,
      "2-0": 0.13,
      "0-2": 0.06,
      "2-1": 0.18,
      "1-2": 0.10,
      "2-2": 0.08,
      "3-0": 0.03,
      "0-3": 0.02
    },

    "confidence": 0.75,
    "best_bet": ["Over 2.5", "Both Teams To Score"],
    "value_bets": ["Home Win", "Over 1.5"]
  },

  "alternate_predictions": {
    "home_win": 0.52,
    "draw": 0.25,
    "away_win": 0.23,

    "both_teams_to_score": 0.75,
    "over_2_5": 0.65,
    "over_3_5": 0.35,

    "exact_score": {
      "2-1": 0.20,
      "1-1": 0.14,
      "2-0": 0.15,
      "1-0": 0.11,
      "3-1": 0.08
    },

    "confidence": 0.78,
    "best_bet": ["Over 2.5", "Home Win"],
    "value_bets": ["Home Win", "BTTS"]
  },

  "coordination_info": {
    "league_coordination": {
      "coordination_applied": true,
      "home_lambda_original": 1.75,
      "away_lambda_original": 1.42,
      "home_lambda_adjusted": 1.80,
      "away_lambda_adjusted": 1.50,
      "adjustment_factor": 1.03
    },
    "team_coordination": {
      "coordination_applied": true,
      "home_lambda_original": 1.82,
      "away_lambda_original": 1.51,
      "home_lambda_adjusted": 1.90,
      "away_lambda_adjusted": 1.60,
      "adjustment_factor": 1.04
    }
  }
}
```

---

## API Response Alignment

### Fields Exposed by API Service

The API service ([src/services/data_formatter.py](../src/services/data_formatter.py)) formats and exposes the following fields:

```json
{
  "fixture_id": Number,
  "timestamp": Number,
  "date": String,
  "has_best_bet": Boolean,      // Computed from predictions.best_bet
  "league": String,              // Optional, if present in DB
  "country": String,             // Optional, if present in DB
  "prediction_confidence": Decimal, // Optional, from predictions.confidence

  "home": {
    "team_id": Number,
    "team_name": String,
    "team_logo": String,
    "predicted_goals": Number,
    "predicted_goals_alt": Number,
    "home_performance": Number
  },

  "away": {
    "team_id": Number,
    "team_name": String,
    "team_logo": String,
    "predicted_goals": Number,
    "predicted_goals_alt": Number,
    "away_performance": Number
  },

  "best_bet": Array             // If has_best_bet is true
}
```

### What API Exposes vs What's in Database

| Category | In Database | Exposed by API | Notes |
|----------|-------------|----------------|-------|
| **Core Identity** | ✅ All fields | ✅ All fields | Full exposure |
| **Team Basic Info** | ✅ Full team objects | ✅ Filtered subset | API returns only essential fields |
| **Predictions** | ✅ Complete probabilities | ❌ Not exposed | Not currently in API response |
| **Performance Metrics** | ✅ Wins/Draws/Losses/Position | ❌ Not exposed | Rich data available for expansion |
| **Goal Statistics** | ✅ Detailed minute-by-minute | ❌ Not exposed | Valuable for web UI |
| **Past Fixtures** | ✅ Last 5 games | ❌ Not exposed | Great for match preview |
| **Head-to-Head** | ✅ Historical matches | ❌ Not exposed | Essential for context |
| **Injuries** | ✅ Current injuries/suspensions | ❌ Not exposed | Critical for predictions |
| **Next Fixture** | ✅ Next match info | ❌ Not exposed | Useful for scheduling |

---

## Recommendations for Web Development

### 1. Fields Currently Available (Not Exposed by API)

The following rich data is **already in the database** but **not currently exposed** by the API. These can be added to enhance the web interface:

#### High Priority for Web UI

```json
{
  // Match Context
  "predictions": {
    "home_win": 0.48,          // Display as percentage bars
    "draw": 0.27,
    "away_win": 0.25,
    "over_2_5": 0.62,          // Popular betting market
    "both_teams_to_score": 0.72,
    "exact_score": {           // Top score predictions
      "2-1": 0.18,
      "1-1": 0.15,
      "2-0": 0.13
    }
  },

  // Team Form & Stats
  "home": {
    "Form": "WWDLW",           // Visual form indicator
    "Position": 3,             // League standing
    "Points": 41,
    "Goals_For": 38,
    "Goals_Against": 22,
    "Wins": 12,
    "Draws": 5,
    "Losses": 3
  },

  // Match History
  "h2h": [                     // Recent head-to-head
    {
      "date": "2023-08-26",
      "home_score": 2,
      "away_score": 0,
      "winner": "home"
    }
  ],

  // Recent Form
  "past_fixtures": [           // Last 5 games
    {
      "opponent": "Nottingham Forest",
      "result": "W",
      "score": "3-0"
    }
  ],

  // Team News
  "injuries": [                // Injury list
    {
      "player_name": "Lisandro Martinez",
      "reason": "Muscle Injury",
      "expected_return": "2024-01-20"
    }
  ]
}
```

#### Medium Priority for Web UI

```json
{
  // Goal Timing Analysis
  "team_goal_stats": {
    "home": {
      "minute": {
        "0-15": {"percentage": "14.3%"},
        "16-30": {"percentage": "23.8%"},
        // ... useful for "when do they score" visualization
      }
    }
  },

  // Venue Information
  "venue": {
    "name": "Old Trafford",
    "city": "Manchester",
    "capacity": 76212
  }
}
```

### 2. Suggested Web UI Components

Based on available data, you can build:

1. **Match Prediction Card**
   - Win/Draw/Away probability bars
   - Best bet highlights
   - Confidence indicator

2. **Team Comparison Panel**
   - Side-by-side stats (Goals, Points, Position)
   - Form indicators (WWDLW vs WLDWL)
   - Performance ratings

3. **Head-to-Head Section**
   - Recent match results
   - Historical win/loss record

4. **Recent Form Timeline**
   - Last 5 games for each team
   - Visual result indicators

5. **Goal Statistics Dashboard**
   - When teams score (minute breakdown)
   - Average goals per game
   - Home vs Away performance

6. **Team News Panel**
   - Injuries and suspensions
   - Expected return dates

7. **Betting Markets Preview**
   - Over/Under probabilities
   - BTTS probability
   - Exact score predictions

### 3. API Enhancement Recommendations

To expose this data, update [src/services/data_formatter.py](../src/services/data_formatter.py) `_format_single_fixture()` method to include:

```python
formatted_fixture = {
    # ... existing fields ...

    # Add predictions
    'predictions': item.get('predictions'),
    'alternate_predictions': item.get('alternate_predictions'),

    # Add team stats
    'home_stats': {
        'form': item['home'].get('Form'),
        'position': item['home'].get('Position'),
        'points': item['home'].get('Points'),
        'record': {
            'wins': item['home'].get('Wins'),
            'draws': item['home'].get('Draws'),
            'losses': item['home'].get('Losses')
        },
        'goals': {
            'for': item['home'].get('Goals_For'),
            'against': item['home'].get('Goals_Against')
        }
    },

    # Add context
    'head_to_head': item.get('h2h'),
    'past_fixtures': {
        'home': item['home'].get('past_fixtures'),
        'away': item['away'].get('past_fixtures')
    },
    'injuries': {
        'home': item['home'].get('injuries'),
        'away': item['away'].get('injuries')
    }
}
```

---

## Summary

### Database Contains (Complete)

✅ **44+ fields per team** (88 total for both teams)
✅ **Prediction probabilities** (20+ markets)
✅ **Historical data** (h2h, past 5 games)
✅ **Real-time team news** (injuries, suspensions)
✅ **Goal statistics** (minute-by-minute breakdown)
✅ **Performance metrics** (form, position, points)
✅ **Venue information** (stadium details)
✅ **Coordination metadata** (prediction quality indicators)

### API Currently Exposes (Basic)

✅ **Core identifiers** (fixture_id, date, timestamp)
✅ **Team basics** (id, name, logo)
✅ **Predictions** (predicted goals)
✅ **Performance** (home/away performance ratings)
❌ **Most rich data** is available but not exposed

### Action Items

1. **For Web Development**: Use this documentation to design UI components around available data
2. **For API Enhancement**: Extend API response to include predictions, stats, and context
3. **For Frontend Integration**: Prioritize displaying predictions, form, and head-to-head data

---

**Last Updated**: October 4, 2025
**Status**: ✅ Complete and Verified
**Source**: [src/handlers/prediction_handler.py](../src/handlers/prediction_handler.py) lines 283-316
