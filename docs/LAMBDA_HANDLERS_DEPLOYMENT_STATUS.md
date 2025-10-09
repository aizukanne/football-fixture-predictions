# Lambda Handlers Deployment Status

**Last Updated:** October 9, 2025

## Overview

This document tracks all Lambda handlers implemented in the system and their deployment status.

---

## Implemented Handlers

### ✅ Currently Deployed (7 handlers)

| # | Handler File | Lambda Function Name | Queue/Trigger | Status |
|---|--------------|---------------------|---------------|---------|
| 1 | [`api_service_handler.py`](../src/handlers/api_service_handler.py) | `football-api-service-prod` | API Gateway | ✅ Deployed |
| 2 | [`fixture_ingestion_handler.py`](../src/handlers/fixture_ingestion_handler.py) | `football-fixture-ingestion-prod` | Manual/Scheduled | ✅ Deployed |
| 3 | [`prediction_handler.py`](../src/handlers/prediction_handler.py) | `football-prediction-handler-prod` | `football-fixture-predictions` queue | ✅ Deployed |
| 4 | [`league_parameter_handler.py`](../src/handlers/league_parameter_handler.py) | `football-league-parameter-handler-prod` | `football-league-parameter-updates` queue | ✅ Deployed |
| 5 | [`team_parameter_handler.py`](../src/handlers/team_parameter_handler.py) | `football-team-parameter-handler-prod` | `football-team-parameter-updates` queue | ✅ Deployed |
| 6 | [`team_parameter_dispatcher.py`](../src/handlers/team_parameter_dispatcher.py) | `football-team-parameter-dispatcher-prod` | Manual | ✅ Deployed |
| 7 | [`best_bets_handler.py`](../src/handlers/best_bets_handler.py) | `football-best-bets-handler-prod` | `best-bets-analysis` queue | ✅ Deployed |

### 🔴 Previously Missing (Now Fixed)

| # | Handler File | Lambda Function Name | Queue/Trigger | Status |
|---|--------------|---------------------|---------------|---------|
| 8 | [`match_data_handler.py`](../src/handlers/match_data_handler.py) | `football-match-data-handler-prod` | `football-match-results` queue | ⚠️ **Added to deployment script** |

---

## Handler Details

### 1. API Service Handler
- **Purpose:** REST API endpoint for querying predictions
- **Trigger:** API Gateway
- **Timeout:** 30 seconds
- **Memory:** 1024 MB

### 2. Fixture Ingestion Handler
- **Purpose:** Fetch upcoming fixtures from API-Football
- **Trigger:** Manual invocation or CloudWatch Events
- **Timeout:** 300 seconds (5 minutes)
- **Memory:** 512 MB
- **Sends messages to:** `football-fixture-predictions` queue

### 3. Prediction Handler
- **Purpose:** Generate match predictions
- **Trigger:** SQS - `football-fixture-predictions` queue
- **Timeout:** 60 seconds
- **Memory:** 1024 MB
- **Batch Size:** 1 message

### 4. League Parameter Handler
- **Purpose:** Calculate league-wide statistical parameters
- **Trigger:** SQS - `football-league-parameter-updates` queue
- **Timeout:** 900 seconds (15 minutes)
- **Memory:** 512 MB
- **Batch Size:** 5 messages

### 5. Team Parameter Handler
- **Purpose:** Calculate team-specific parameters
- **Trigger:** SQS - `football-team-parameter-updates` queue
- **Timeout:** 1200 seconds (20 minutes)
- **Memory:** 512 MB
- **Batch Size:** 5 messages

### 6. Team Parameter Dispatcher
- **Purpose:** Orchestrate batch team parameter updates
- **Trigger:** Manual invocation
- **Timeout:** Default
- **Memory:** Default

### 7. Best Bets Handler
- **Purpose:** Analyze predictions and identify betting opportunities
- **Trigger:** SQS - `best-bets-analysis` queue
- **Timeout:** 60 seconds
- **Memory:** 512 MB
- **Batch Size:** 10 messages

### 8. Match Data Handler ⚠️ NEW
- **Purpose:** Collect post-match scores and statistics
- **Trigger:** SQS - `football-match-results` queue
- **Timeout:** 300 seconds (5 minutes)
- **Memory:** 512 MB
- **Batch Size:** 5 messages
- **Enhanced Features:**
  - Basic score collection (home/away goals)
  - Halftime scores
  - Match statistics (shots, possession, passes, etc.)
  - Validation and error handling

---

## Deployment

### Quick Deploy All Functions

```bash
./scripts/deploy_lambda_functions.sh prod
```

### Deploy Individual Handler

```bash
aws lambda create-function \
    --function-name "football-match-data-handler-prod" \
    --runtime python3.9 \
    --role "arn:aws:iam::985019772236:role/FootballPredictionLambdaRole" \
    --handler src.handlers.match_data_handler.lambda_handler \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --timeout 300 \
    --memory-size 512 \
    --environment "Variables={ENVIRONMENT=prod,TABLE_PREFIX=football_,TABLE_SUFFIX=_prod,RAPIDAPI_KEY=${RAPIDAPI_KEY}}" \
    --region eu-west-2
```

### Configure SQS Trigger

```bash
aws lambda create-event-source-mapping \
    --function-name "football-match-data-handler-prod" \
    --event-source-arn "arn:aws:sqs:eu-west-2:985019772236:football_football-match-results_prod" \
    --batch-size 5 \
    --region eu-west-2
```

---

## Queue Mappings

| Queue Name | Handler Function | Purpose |
|------------|------------------|---------|
| `football-fixture-predictions` | `prediction-handler` | Process fixture predictions |
| `football-league-parameter-updates` | `league-parameter-handler` | Update league parameters |
| `football-team-parameter-updates` | `team-parameter-handler` | Update team parameters |
| `best-bets-analysis` | `best-bets-handler` | Analyze betting opportunities |
| `football-match-results` | `match-data-handler` | Collect match scores/stats |
| `football-cache-updates` | ❌ No handler | Cache refresh (future) |

---

## Missing Handlers

### Cache Update Handler (Planned)
- **Queue:** `football-cache-updates`
- **Purpose:** Refresh cached data (standings, venues, etc.)
- **Status:** Not implemented yet

---

## Deployment History

### October 9, 2025
- ✅ Identified missing `match_data_handler` deployment
- ✅ Updated deployment script to include all 8 handlers
- ✅ Documented all handler configurations
- ⚠️ Match Data Handler needs to be deployed to production

---

## Next Steps

1. **Deploy Missing Handler:**
   ```bash
   ./scripts/deploy_lambda_functions.sh prod
   ```

2. **Verify Deployment:**
   ```bash
   aws lambda list-functions --region eu-west-2 | grep football
   ```

3. **Test Match Data Handler:**
   ```bash
   aws sqs send-message \
       --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-match-results_prod \
       --message-body '{"action": "check_scores", "time_range": {"start": 1759508423, "end": 1760026823}}' \
       --region eu-west-2
   ```

4. **Monitor Processing:**
   ```bash
   aws logs tail /aws/lambda/football-match-data-handler-prod --follow --region eu-west-2
   ```

---

## Notes

- All handlers use Python 3.9 runtime
- All handlers use the same IAM role: `FootballPredictionLambdaRole`
- Environment variables are automatically configured during deployment
- Table names follow pattern: `football_{table}_{environment}`

---

**Status:** 7/8 handlers deployed, 1 ready for deployment