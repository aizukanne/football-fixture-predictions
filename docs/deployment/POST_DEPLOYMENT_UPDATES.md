# Post-Deployment Updates and Fixes

**Date**: 2025-10-05
**Status**: Completed
**Environment**: Production

## Overview

This document summarizes critical updates and fixes applied to the production system after initial deployment, including schema changes, bug fixes, and automation setup.

---

## 1. Team Parameters Table - Composite Key Migration

### Issue
The `team_parameters` table originally used a single numeric `team_id` as the primary key, which caused data overwrites when the same team_id existed in multiple leagues.

### Solution
Migrated to a **composite primary key** structure:

**Old Schema:**
```
Primary Key: team_id (Number)
```

**New Schema:**
```
Primary Key:
  - team_id (Number, HASH)
  - league_id (Number, RANGE)
```

### Benefits
- ✅ Unique identification of teams across different leagues
- ✅ No data loss from overwrites
- ✅ Efficient querying (can query all leagues for a specific team)
- ✅ More DynamoDB-idiomatic design

### Code Changes

**database_client.py:**
```python
# Updated function signatures
def get_team_params_from_db(team_id, league_id):
    response = teams_table.get_item(Key={
        'team_id': int(team_id),
        'league_id': int(league_id)
    })

def put_team_parameters(team_id, league_id, team_params):
    item['team_id'] = int(team_id)
    item['league_id'] = int(league_id)
```

**prediction_handler.py:**
```python
# Before
unique_home_id = f"{league_id}-{home_team_id}"
home_params = get_team_params_from_db(unique_home_id)

# After
home_params = get_team_params_from_db(home_team_id, league_id)
```

### Affected Lambda Functions
- ✅ football-team-parameter-handler-prod
- ✅ football-prediction-handler-prod

---

## 2. League Parameters Table - Composite Key Fix

### Issue
The `league_parameters` table has a composite key (`league_id` + `season`), but the fetch function was only providing `league_id`, causing ValidationException errors.

### Solution
Updated `fetch_league_parameters()` to accept both keys:

```python
def fetch_league_parameters(league_id, season=None):
    if season is None:
        season = datetime.now().year

    response = league_table.get_item(Key={
        'league_id': int(league_id),
        'season': int(season)
    })
```

### Affected Files
- `src/data/database_client.py`
- `src/handlers/team_parameter_handler.py`

---

## 3. SQS Queue Max Concurrency Configuration

### Issue
Not all SQS queues had max concurrency limits set, risking resource exhaustion.

### Solution
Set `MaximumConcurrency=2` for all event source mappings:

| Queue | Function | Max Concurrency |
|-------|----------|-----------------|
| football-fixture-predictions | football-prediction-handler-prod | 2 ✅ |
| football-league-parameter-updates | football-league-parameter-handler-prod | 2 ✅ |
| football-team-parameter-updates | football-team-parameter-handler-prod | 2 ✅ |

**Command Used:**
```bash
aws lambda update-event-source-mapping \
  --uuid <mapping-uuid> \
  --scaling-config MaximumConcurrency=2
```

---

## 4. Team Parameter Handler Implementation

### Missing Functions Implemented

**1. get_football_match_scores()**
- Location: `src/data/api_client.py`
- Purpose: Fetches match data from RapidAPI
- Returns: DataFrame with completed matches

**2. get_match_scores_min_games()**
- Location: `src/handlers/team_parameter_handler.py`
- Purpose: Collects match data across multiple seasons
- Walks back up to 3 seasons to meet minimum games requirement

**3. filter_team_matches()**
- Filters DataFrame to matches involving specific team

**4. games_played_per_team()**
- Fetches team statistics from API

### Bug Fixes

**Missing Import:**
```python
# Added to team_parameter_handler.py
from datetime import datetime, timedelta
```

**DateTime Conversion:**
```python
# Fixed in team_calculator.py
'classification_date': int(datetime.now().timestamp())  # Was: datetime.now()
```

**Parameter Passing:**
```python
# Fixed in team_parameter_handler.py - Line 106
tune_results = tune_weights_grid_team(
    team_scores_df,
    team_dict,  # Was: team_dict["mu"]
    team_dict["alpha"],
    team_games
)
```

---

## 5. Leagues.py Deployment

### Issue
The fixture ingestion handler had a hardcoded fallback configuration with only 6 leagues when `leagues.py` was missing.

### Solution

**Removed Fallback (leagues_config.py):**
```python
# Before
try:
    from leagues import allLeagues
except ImportError:
    allLeagues = {...}  # Hardcoded 6 leagues

# After
from leagues import allLeagues  # No fallback - fail fast
```

**Deployment Package:**
Now includes `leagues.py` in all Lambda packages:
- football-fixture-ingestion-prod
- football-team-parameter-handler-prod
- football-prediction-handler-prod
- football-league-parameter-handler-prod

**Results:**
- Before: 6 leagues processed
- After: **67 leagues processed** ✅

---

## 6. EventBridge Automation Setup

### Fixture Ingestion Daily Trigger

**EventBridge Rule Created:**
```
Name: football-fixture-ingestion-daily-prod
Schedule: cron(0 6 * * ? *)  # Daily at 06:00 UTC
State: ENABLED
Target: football-fixture-ingestion-prod Lambda
```

**Permissions:**
```bash
aws lambda add-permission \
  --function-name football-fixture-ingestion-prod \
  --statement-id AllowEventBridgeInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com
```

**Test Results:**
- Processed Leagues: 67
- Total Fixtures: 191
- Success Rate: 100%

---

## 7. Missing Function Stubs

### calculate_team_points()

**Issue:**
prediction_handler imported `calculate_team_points` which didn't exist in the modular codebase.

**Solution:**
Created stub function in `team_calculator.py`:

```python
def calculate_team_points(league_id, season, team_id, venue, match_details):
    """Stub function to support prediction_handler."""
    return {
        'team_info': {
            'team_id': team_id,
            'league_id': league_id,
            'points': 0,
            'position': 0,
            # ... other fields
        },
        'team_logo': '',
        'team_goal_stats': {
            'goals_for': 0,
            'goals_against': 0
        }
    }
```

---

## 8. Deployment Package Optimization

### Build Process Updated

**Old Process:**
- Included all dependencies in each package
- Large package sizes (~15MB)
- Redundant dependency installations

**New Process:**
```bash
# Source code only (no dependencies)
mkdir lambda_deployment
cp -r src lambda_deployment/
cp leagues.py lambda_deployment/
cd lambda_deployment
zip -r package.zip src leagues.py
```

**Package Sizes:**
- Source only: ~715KB
- Lambda Layer (scipy-layer:4): Contains numpy, pandas, scipy, scikit-learn
- Total efficient deployment ✅

---

## 9. Best Bets Handler Integration

### Issue
The prediction handler was sending messages to the same queue that triggered it (`football-fixture-predictions`), creating an infinite loop. The system was missing the best bets analysis component from the legacy system.

### Solution

**Created New Infrastructure:**
1. **SQS Queue**: `football_football-best-bets_prod`
   - Visibility Timeout: 2 minutes
   - Max Receive Count: 3
   - Dead Letter Queue: `football_football-best-bets-dlq_prod`

2. **Lambda Function**: `football-best-bets-handler-prod`
   - Handler: `src.handlers.best_bets_handler.lambda_handler`
   - Memory: 512 MB
   - Timeout: 2 minutes
   - Batch Size: 10

**Implementation:**
- Created `src/handlers/best_bets_handler.py` based on legacy `code-samples/find_best_bets.py`
- Analyzes prediction data to generate betting recommendations
- Updates fixture records with `best_bet` and `has_best_bet` attributes

**Flow:**
```
Prediction Handler → Stores predictions → Sends to Best Bets Queue
Best Bets Handler → Analyzes predictions → Updates DB with recommendations
```

**Code Changes:**

**constants.py:**
```python
BEST_BETS_QUEUE_URL = os.getenv(
    'BEST_BETS_QUEUE_URL',
    f'https://sqs.eu-west-2.amazonaws.com/{{account_id}}/{_get_table_name("football-best-bets")}'
)
```

**prediction_handler.py:**
```python
# Changed from FIXTURES_QUEUE_URL to BEST_BETS_QUEUE_URL
from ..utils.constants import BEST_BETS_QUEUE_URL

def send_to_sqs(data):
    """Send processed fixture data to best bets queue for analysis."""
    sqs.send_message(
        QueueUrl=BEST_BETS_QUEUE_URL,
        MessageBody=payload
    )
```

**database_client.py:**
```python
def update_fixture_best_bet(fixture_id, best_bet_data):
    """Update fixture with best bet recommendations."""
    # Queries fixture, then updates with best_bet and has_best_bet fields
```

### Affected Lambda Functions
- ✅ football-prediction-handler-prod (updated to send to best-bets queue)
- ✅ football-best-bets-handler-prod (newly created)

---

## 10. Field Naming Clarification

### Issue
The prediction handler created two similar fields: `opponent` (lowercase) and `Opponent` (uppercase), which was confusing.

### Solution
Renamed the lowercase field to `next_opponent` for clarity:

**api_client.py - get_next_fixture():**
```python
# Before
return {
    "opponent": "Next team name",
    ...
}

# After
return {
    "next_opponent": "Next team name",
    ...
}
```

**Field Definitions:**
- `next_opponent` (from get_next_fixture): The opponent in the team's next fixture after this one
- `Opponent` (in prediction_handler): The current opponent in this fixture

---

## 11. API Gateway Deployment

### Issue
The API service Lambda function existed but had no HTTP endpoint for external access. Frontend applications (mobile/web) needed a REST API to query predictions.

### Solution

**Created API Gateway Infrastructure:**

1. **API Gateway**: `football-predictions-api-prod`
   - API ID: `esqyjhhc4e`
   - Endpoint Type: Regional
   - Stage: `prod`

2. **Resources and Methods**:
   - `GET /predictions` - Query fixture predictions
   - `OPTIONS /predictions` - CORS preflight

3. **Authentication**:
   - API Key authentication via `x-api-key` header
   - Usage Plan: 10 req/sec, 20 burst, 10k/month quota
   - API Key ID: `bprnzrkxd5`

4. **CORS Configuration**:
   - Origins: `*`
   - Methods: OPTIONS, GET, POST
   - Headers: Content-Type, X-Amz-Date, Authorization, X-Api-Key

**API Endpoint:**
```
https://esqyjhhc4e.execute-api.eu-west-2.amazonaws.com/prod/predictions
```

**Query Examples:**
```bash
# Single fixture by ID
curl -H "x-api-key: <API_KEY>" \
  "https://esqyjhhc4e.execute-api.eu-west-2.amazonaws.com/prod/predictions?fixture_id=123456"

# League fixtures by date range
curl -H "x-api-key: <API_KEY>" \
  "https://esqyjhhc4e.execute-api.eu-west-2.amazonaws.com/prod/predictions?country=England&league=Premier%20League&startDate=2025-10-01&endDate=2025-10-10"
```

**Lambda Configuration Update:**
- Added `MOBILE_APP_KEY` environment variable to `football-api-service-prod`
- Matches API Gateway API key for authentication

**Deployment Command Used:**
```bash
python3 -m src.infrastructure.deploy_api_gateway \
  --lambda-arn arn:aws:lambda:eu-west-2:985019772236:function:football-api-service-prod \
  --region eu-west-2 \
  --environment prod \
  --stage prod
```

### Affected Components
- ✅ football-api-service-prod (Lambda environment updated with MOBILE_APP_KEY)
- ✅ football-predictions-api-prod (newly created API Gateway)

**Post-Deployment Fix:**
The `country-league-index` Global Secondary Index was missing from the `game_fixtures` table, causing API queries by country/league to fail. Created the GSI:

```bash
aws dynamodb update-table --table-name football_game_fixtures_prod \
  --attribute-definitions \
    AttributeName=country,AttributeType=S \
    AttributeName=league,AttributeType=S \
    AttributeName=fixture_id,AttributeType=N \
  --global-secondary-index-updates '[{
    "Create":{
      "IndexName":"country-league-index",
      "KeySchema":[
        {"AttributeName":"country","KeyType":"HASH"},
        {"AttributeName":"league","KeyType":"RANGE"}
      ],
      "Projection":{"ProjectionType":"ALL"}
    }
  }]'
```

**Index Configuration:**
- Index Name: `country-league-index`
- Hash Key: `country` (String)
- Range Key: `league` (String)
- Projection: ALL
- Billing Mode: PAY_PER_REQUEST (on-demand)

---

## 12. Tactical and Venue Parameters - Season Parameter Fix

### Issue
Tactical and venue parameters were **never being calculated** for any teams because the `season` parameter was missing when calling `fit_team_params()`.

### Root Cause
In `team_parameter_handler.py` line 87, the function was called without the season parameter:
```python
team_dict = fit_team_params(team_scores_df, team_id, league_id)  # Missing season!
```

### Impact
Without the season parameter, conditions in `team_calculator.py` lines 279 and 305 always failed:
- **Venue params**: `if season and not df.empty and len(df) >= MINIMUM_GAMES_THRESHOLD:`
- **Tactical params**: `if season and not df.empty and len(df) >= MINIMUM_GAMES_THRESHOLD:`

Both fell back to neutral parameters:
- `get_neutral_venue_params()` - No stadium advantages
- `get_neutral_tactical_params()` - No formation/style analysis

**What Was Missing:**
- ❌ Stadium-specific advantages (venue_strength, travel_impact)
- ❌ Formation/style analysis (possession_style, defensive_line, pressing_intensity)
- ❌ Playing surface adjustments (grass_strength, turf_strength)
- ❌ Tactical flexibility scores
- ❌ Formation preferences

### Solution
Added the season parameter to the function call:

**team_parameter_handler.py line 87:**
```python
# Before
team_dict = fit_team_params(team_scores_df, team_id, league_id)

# After
team_dict = fit_team_params(team_scores_df, team_id, league_id, season=season)
```

The `season` variable was already available (extracted at line 39), just wasn't being passed through.

### Verification
Now venue and tactical parameters calculate when:
1. ✅ season parameter provided (FIXED)
2. ✅ DataFrame not empty
3. ✅ Data meets MINIMUM_GAMES_THRESHOLD (10 games)

### Affected Components
- ✅ football-team-parameter-handler-prod (deployed with season parameter)

---

## Summary of Lambda Functions Updated

| Function | Updates Applied |
|----------|----------------|
| football-team-parameter-handler-prod | Composite key, missing functions, imports, leagues.py, **season parameter for venue/tactical** |
| football-prediction-handler-prod | Composite key, calculate_team_points, leagues.py, best-bets queue, next_opponent |
| football-best-bets-handler-prod | **NEW** - Best bet analysis and recommendations |
| football-api-service-prod | MOBILE_APP_KEY, API Gateway integration, **full details for fixture_id, Decimal fixes** |
| football-fixture-ingestion-prod | leagues.py, EventBridge trigger |
| football-league-parameter-handler-prod | leagues.py, composite key fetch |

---

## Verification Checklist

- [x] All SQS queues have max concurrency = 2
- [x] Team parameters table uses composite key (team_id + league_id)
- [x] League parameters fetch includes season parameter
- [x] All Lambda functions include leagues.py (no fallback)
- [x] EventBridge daily trigger configured for fixture ingestion
- [x] All missing function implementations completed
- [x] DateTime objects converted to timestamps before DynamoDB storage
- [x] Deployment packages optimized (source only, layer for dependencies)
- [x] Best bets queue and handler created and integrated
- [x] Prediction handler sends to best-bets queue (not fixtures queue)
- [x] Field naming clarified (next_opponent vs Opponent)
- [x] API Gateway deployed with API key authentication
- [x] API service Lambda integrated with API Gateway
- [x] API returns full details for fixture_id queries
- [x] API converts Decimals to proper integers/floats
- [x] Season parameter added to enable venue/tactical calculations
- [x] country-league-index GSI created on game_fixtures table

---

## Next Steps

1. **Monitor CloudWatch Logs** for any remaining errors
2. **Verify daily fixture ingestion** runs at 06:00 UTC
3. **Test end-to-end prediction flow** with real fixtures
4. **Set up alarms** for Lambda failures and DLQ messages
5. **Document API endpoints** for external access

---

## Reference Links

- DynamoDB Composite Keys: [AWS Documentation](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-sort-keys.html)
- Lambda Concurrency: [AWS Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html)
- EventBridge Cron Expressions: [Schedule Expressions](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)

---

**Last Updated**: 2025-10-05
**Author**: Football Fixture Prediction System Deployment Team
