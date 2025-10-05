# Operational Workflow Guide

**Football Fixture Prediction System v6.0**  
**How to Use the Deployed System**

---

## 🎯 Overview

This guide explains the correct order to initialize and operate the prediction system.

---

## 📋 System Initialization (First-Time Setup)

Before the system can generate predictions, it needs historical data to calculate statistical parameters.

### Phase 1: Calculate League Parameters (FIRST)

**Purpose:** Establish baseline statistics for each league (home advantage, goals per game, etc.)

**Function:** `football-league-parameter-handler-prod`

**How to Trigger:**

```bash
# Method 1: Direct Lambda invocation with league ID
aws lambda invoke \
    --function-name football-league-parameter-handler-prod \
    --payload '{"league_id": 39, "season": 2024}' \
    --region eu-west-2 \
    response.json

# Method 2: Send message to queue (for batch processing)
aws sqs send-message \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-league-parameter-updates_prod \
    --message-body '{"action": "update_league", "league_id": 39, "season": 2024}' \
    --region eu-west-2
```

**What it does:**
- Fetches recent match results for the league
- Calculates league-wide parameters: λ_home, λ_away, home advantage factor
- Stores results in `football_league_parameters_prod` table

**Required for:** All leagues you want to make predictions for

**Example leagues to initialize:**
```bash
# Premier League (England)
{"league_id": 39, "season": 2024}

# La Liga (Spain)
{"league_id": 140, "season": 2024}

# Bundesliga (Germany)
{"league_id": 78, "season": 2024}

# Serie A (Italy)
{"league_id": 135, "season": 2024}

# Ligue 1 (France)
{"league_id": 61, "season": 2024}
```

---

### Phase 2: Calculate Team Parameters (SECOND)

**Purpose:** Calculate team-specific strength ratings and form

**Function:** `football-team-parameter-handler-prod`

**How to Trigger:**

```bash
# Method 1: Direct Lambda invocation for specific team
aws lambda invoke \
    --function-name football-team-parameter-handler-prod \
    --payload '{"team_id": 33, "season": 2024}' \
    --region eu-west-2 \
    response.json

# Method 2: Send message to queue (for batch processing)
aws sqs send-message \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-team-parameter-updates_prod \
    --message-body '{"action": "update_team", "team_id": 33, "season": 2024}' \
    --region eu-west-2

# Method 3: Update all teams in a league
aws sqs send-message \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-team-parameter-updates_prod \
    --message-body '{"action": "update_league_teams", "league_id": 39, "season": 2024}' \
    --region eu-west-2
```

**What it does:**
- Fetches team's recent match history
- Calculates team parameters: α (attack strength), β (defense strength)
- Analyzes form, venue performance, opponent performance
- Stores results in `football_team_parameters_prod` table

**Required for:** All teams you want to predict

**Note:** Team parameters depend on league parameters, so league MUST be initialized first.

---

### Phase 3: Ingest Fixtures (THIRD)

**Purpose:** Retrieve upcoming fixtures from API-Football

**Function:** `football-fixture-ingestion-prod`

**How to Trigger:**

```bash
# Method 1: Direct Lambda invocation for today's fixtures
aws lambda invoke \
    --function-name football-fixture-ingestion-prod \
    --payload '{"action": "fetch_today"}' \
    --region eu-west-2 \
    response.json

# Method 2: For specific date range
aws lambda invoke \
    --function-name football-fixture-ingestion-prod \
    --payload '{"action": "fetch_range", "from": "2024-10-05", "to": "2024-10-12"}' \
    --region eu-west-2 \
    response.json

# Method 3: For specific league
aws lambda invoke \
    --function-name football-fixture-ingestion-prod \
    --payload '{"action": "fetch_league", "league_id": 39, "season": 2024}' \
    --region eu-west-2 \
    response.json
```

**What it does:**
- Calls API-Football to retrieve fixture data
- Sends each fixture to the prediction queue
- Triggers automatic prediction generation

**Note:** This automatically triggers Phase 4 (predictions) via SQS

---

### Phase 4: Generate Predictions (AUTOMATIC)

**Purpose:** Calculate match outcome probabilities

**Function:** `football-prediction-handler-prod`

**How it's triggered:**
- **Automatically** when fixture ingestion sends messages to SQS queue
- **Or manually** for specific fixtures

**Manual Trigger (if needed):**

```bash
# Direct prediction for a specific fixture
aws lambda invoke \
    --function-name football-prediction-handler-prod \
    --payload '{"fixture_id": 1234567}' \
    --region eu-west-2 \
    response.json

# Or via SQS queue
aws sqs send-message \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-fixture-predictions_prod \
    --message-body '{"fixture_id": 1234567}' \
    --region eu-west-2
```

**What it does:**
- Retrieves fixture details from database
- Looks up league and team parameters
- Applies all 6 phases of the prediction model:
  1. Core statistical engine (Poisson distribution)
  2. Opponent stratification (smart vs dumb teams)
  3. Venue analysis (home/away performance)
  4. Temporal evolution (recent form)
  5. Tactical intelligence (formations, managers)
  6. Adaptive strategy selection
  7. Confidence calibration
- Stores predictions in `football_game_fixtures_prod` table

---

## 🔄 Complete Initialization Workflow

### Step-by-Step First-Time Setup

```bash
# Step 1: Initialize League Parameters
# Do this for each league you want to support

echo "Initializing Premier League..."
aws lambda invoke \
    --function-name football-league-parameter-handler-prod \
    --payload '{"league_id": 39, "season": 2024}' \
    --region eu-west-2 \
    response_league.json

# Wait for completion (check logs)
aws logs tail /aws/lambda/football-league-parameter-handler-prod --region eu-west-2

# Step 2: Initialize Team Parameters
# This can be done for all teams in the league at once

echo "Initializing all Premier League teams..."
aws sqs send-message \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-team-parameter-updates_prod \
    --message-body '{"action": "update_league_teams", "league_id": 39, "season": 2024}' \
    --region eu-west-2

# Wait for processing (this may take 10-15 minutes for all teams)
# Monitor SQS queue depth
aws sqs get-queue-attributes \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-team-parameter-updates_prod \
    --attribute-names ApproximateNumberOfMessages \
    --region eu-west-2

# Step 3: Ingest Upcoming Fixtures

echo "Fetching this week's fixtures..."
aws lambda invoke \
    --function-name football-fixture-ingestion-prod \
    --payload '{"action": "fetch_range", "from": "2024-10-05", "to": "2024-10-12"}' \
    --region eu-west-2 \
    response_fixtures.json

# Step 4: Predictions are automatically generated!
# Check the prediction queue
aws sqs get-queue-attributes \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-fixture-predictions_prod \
    --attribute-names ApproximateNumberOfMessages \
    --region eu-west-2

# Step 5: Query predictions from database
aws dynamodb scan \
    --table-name football_game_fixtures_prod \
    --limit 10 \
    --region eu-west-2
```

---

## 📅 Ongoing Operations (After Initialization)

### Daily Operations

**1. Morning: Ingest Today's Fixtures (06:00 UTC recommended)**

```bash
aws lambda invoke \
    --function-name football-fixture-ingestion-prod \
    --payload '{"action": "fetch_today"}' \
    --region eu-west-2 \
    response.json
```

**2. Automatic: Predictions Generated**
- SQS automatically triggers prediction handler
- No manual intervention needed

**3. Query Predictions via API Service**

```bash
# Get predictions for specific fixture
aws lambda invoke \
    --function-name football-api-service-prod \
    --payload '{"queryStringParameters": {"fixture_id": "1234567"}}' \
    --region eu-west-2 \
    response.json

# Get predictions for specific date
aws lambda invoke \
    --function-name football-api-service-prod \
    --payload '{"queryStringParameters": {"date": "2024-10-05"}}' \
    --region eu-west-2 \
    response.json

# Get predictions for specific league
aws lambda invoke \
    --function-name football-api-service-prod \
    --payload '{"queryStringParameters": {"league_id": "39"}}' \
    --region eu-west-2 \
    response.json
```

### Weekly Operations

**Update Parameters (Sunday 02:00 UTC recommended)**

```bash
# Update league parameters (weekly)
aws sqs send-message \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-league-parameter-updates_prod \
    --message-body '{"action": "update_all_leagues"}' \
    --region eu-west-2

# Update team parameters (weekly)
aws sqs send-message \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-team-parameter-updates_prod \
    --message-body '{"action": "update_all_teams"}' \
    --region eu-west-2
```

---

## 🔧 Operational Sequence Diagram

```
INITIALIZATION (First Time)
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  1. League Parameter Handler                                │
│     ├─ Input: league_id, season                             │
│     └─ Output: League parameters → DynamoDB                 │
│                                                             │
│  2. Team Parameter Handler (depends on step 1)              │
│     ├─ Input: team_id OR league_id (all teams)             │
│     └─ Output: Team parameters → DynamoDB                   │
│                                                             │
│  3. Fixture Ingestion                                       │
│     ├─ Input: date range OR league_id                      │
│     ├─ Fetches fixtures from API-Football                   │
│     └─ Output: Fixtures → SQS Queue                         │
│                                                             │
│  4. Prediction Handler (triggered by SQS)                   │
│     ├─ Input: fixture_id (from SQS)                        │
│     ├─ Reads: League & Team parameters from DynamoDB       │
│     └─ Output: Predictions → DynamoDB                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘

ONGOING OPERATIONS
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  DAILY (06:00 UTC):                                         │
│    Fixture Ingestion → Predictions (automatic)              │
│                                                             │
│  WEEKLY (Sunday 02:00 UTC):                                 │
│    Update League Parameters                                 │
│    Update Team Parameters                                   │
│                                                             │
│  AS NEEDED:                                                 │
│    Query predictions via API Service                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Dependencies

```
football_league_parameters_prod
         ↓ (required by)
football_team_parameters_prod
         ↓ (required by)
football_game_fixtures_prod
         ↓ (used by)
football-prediction-handler
```

**Critical Rule:** You CANNOT generate predictions without:
1. League parameters for that league
2. Team parameters for both teams
3. Fixture data

---

## 🚨 Common Issues and Solutions

### Issue 1: Predictions Fail with "League Parameters Not Found"

**Cause:** League parameters haven't been initialized

**Solution:**
```bash
aws lambda invoke \
    --function-name football-league-parameter-handler-prod \
    --payload '{"league_id": 39, "season": 2024}' \
    --region eu-west-2 \
    response.json
```

### Issue 2: Predictions Fail with "Team Parameters Not Found"

**Cause:** Team parameters haven't been calculated

**Solution:**
```bash
aws lambda invoke \
    --function-name football-team-parameter-handler-prod \
    --payload '{"team_id": 33, "season": 2024}' \
    --region eu-west-2 \
    response.json
```

### Issue 3: No Fixtures to Predict

**Cause:** Fixture ingestion hasn't been run

**Solution:**
```bash
aws lambda invoke \
    --function-name football-fixture-ingestion-prod \
    --payload '{"action": "fetch_today"}' \
    --region eu-west-2 \
    response.json
```

### Issue 4: API Rate Limit Exceeded

**Cause:** Free tier limited to 30 requests/day

**Solution:** Upgrade API-Football plan or space out requests

---

## 📈 Recommended Operational Schedule

### Initial Setup (One Time)
```
Hour 0:00 - Initialize 5 major leagues (5 API calls)
Hour 0:30 - Initialize all teams in those leagues (batch processing)
Hour 2:00 - First fixture ingestion (1-5 API calls depending on fixtures)
Hour 2:30 - First predictions generated (automatic, no API calls)
```

### Daily Operations
```
06:00 UTC - Daily fixture ingestion (1-5 API calls)
06:15 UTC - Predictions automatically generated
```

### Weekly Operations
```
Sunday 02:00 UTC - Update league parameters (5 API calls)
Sunday 02:30 UTC - Update team parameters (batch, no API calls to external)
```

**Total API Calls:**
- Daily: 1-5 calls
- Weekly: 5 calls
- Monthly: ~50-70 calls (well within free tier's 30/day = 900/month)

---

## 🔍 Monitoring Operations

### Check System Health

```bash
# Check Lambda function states
aws lambda list-functions \
    --region eu-west-2 \
    --query "Functions[?contains(FunctionName, 'football')].{Name:FunctionName, State:State}"

# Check SQS queue depths
aws sqs get-queue-attributes \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-fixture-predictions_prod \
    --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible \
    --region eu-west-2

# Check DLQ for errors
aws sqs get-queue-attributes \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-prediction-dlq_prod \
    --attribute-names ApproximateNumberOfMessages \
    --region eu-west-2

# View recent logs
aws logs tail /aws/lambda/football-prediction-handler-prod --follow --region eu-west-2
```

### Check Data Status

```bash
# Count league parameters
aws dynamodb scan \
    --table-name football_league_parameters_prod \
    --select COUNT \
    --region eu-west-2

# Count team parameters
aws dynamodb scan \
    --table-name football_team_parameters_prod \
    --select COUNT \
    --region eu-west-2

# Count fixtures with predictions
aws dynamodb scan \
    --table-name football_game_fixtures_prod \
    --filter-expression "attribute_exists(predictions)" \
    --select COUNT \
    --region eu-west-2
```

---

## ✅ Quick Start Checklist

### First-Time Setup
- [ ] Initialize league parameters for each league (5-10 leagues)
- [ ] Initialize team parameters for each team (bulk operation per league)
- [ ] Verify parameters stored in DynamoDB
- [ ] Run first fixture ingestion
- [ ] Confirm predictions generated automatically
- [ ] Test API service to retrieve predictions

### Daily Operations
- [ ] Run fixture ingestion (automated via EventBridge recommended)
- [ ] Monitor CloudWatch logs for errors
- [ ] Check DLQ for failed messages

### Weekly Operations
- [ ] Update league parameters
- [ ] Update team parameters
- [ ] Review prediction accuracy (manual analysis)

---

## 🎯 Summary: Execution Order

**CRITICAL SEQUENCE:**

1. **League Parameters** → MUST BE FIRST
2. **Team Parameters** → MUST BE SECOND (depends on #1)
3. **Fixture Ingestion** → Can run anytime after #1 & #2
4. **Predictions** → Automatic (depends on #1, #2, #3)
5. **Query Results** → Via API Service (depends on #4)

**You cannot skip steps or change the order!**

---

*Guide Version: 1.0*  
*Last Updated: 2025-10-05*  
*System Version: v6.0*