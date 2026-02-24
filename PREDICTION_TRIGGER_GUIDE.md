# Manual Prediction Trigger Guide

## Summary

Successfully created and tested a manual trigger script for match predictions. The script retrieves fixtures from RapidAPI and sends them to the prediction processing queue.

## Diagnostic Findings

### System Architecture Analysis

The prediction system follows this workflow:

1. **Fixture Ingestion** → Retrieves fixtures from RapidAPI
2. **Queue Population** → Sends fixtures to SQS queue (`football_football-fixture-predictions_prod`)
3. **Prediction Processing** → Lambda handler processes queued fixtures
4. **Results Storage** → Predictions stored in DynamoDB

### Issues Identified

1. **RAPIDAPI_KEY Environment Variable**
   - The `FixtureRetriever` class requires `RAPIDAPI_KEY` to be set as an environment variable
   - Fallback value exists in `constants.py` but must be explicitly exported

2. **FIXTURES_QUEUE_URL Configuration**
   - Default value in `constants.py` contains placeholder `{account_id}`
   - Must be set to actual production queue URL

### Solution Provided

Created [`trigger_predictions_manual.py`](trigger_predictions_manual.py) with:

- ✅ **Environment diagnostic checks** - Validates configuration before execution
- ✅ **Comprehensive error handling** - Catches and reports issues at each stage
- ✅ **Dry-run mode** - Test without sending to queue
- ✅ **Detailed logging** - Shows retrieved fixtures and execution summary
- ✅ **Flexible date ranges** - Works for any league and date range

## Test Results (Dry Run)

**Test Command:**
```bash
export RAPIDAPI_KEY="4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4"
export FIXTURES_QUEUE_URL="https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-fixture-predictions_prod"
python3 trigger_predictions_manual.py --league-id 39 --start-date 2026-02-20 --end-date 2026-02-23 --dry-run
```

**Results:**
- ✅ Retrieved 10 fixtures from Premier League (League ID 39)
- ✅ All fixtures successfully formatted
- ✅ Ready to send to production queue

**Fixtures Found (Feb 20-23, 2026):**

1. Chelsea vs Burnley - Feb 21, 15:00
2. Brentford vs Brighton - Feb 21, 15:00
3. Aston Villa vs Leeds - Feb 21, 15:00
4. West Ham vs Bournemouth - Feb 21, 17:30
5. Manchester City vs Newcastle - Feb 21, 20:00
6. Crystal Palace vs Wolves - Feb 22, 14:00
7. Nottingham Forest vs Liverpool - Feb 22, 14:00
8. Sunderland vs Fulham - Feb 22, 14:00
9. Tottenham vs Arsenal - Feb 22, 16:30
10. Everton vs Manchester United - Feb 23, 20:00

## Usage Instructions

### 1. Environment Setup

Set required environment variables:

```bash
# Required: RapidAPI Key
export RAPIDAPI_KEY="your_rapidapi_key_here"

# Required: Production Queue URL
export FIXTURES_QUEUE_URL="https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-fixture-predictions_prod"
```

### 2. Check Environment

Verify configuration before running:

```bash
python3 trigger_predictions_manual.py --check-env
```

**Expected Output:**
```
✅ RAPIDAPI_KEY: ********************46a4 (from environment)
✅ FIXTURES_QUEUE_URL: https://sqs.eu-west-2.amazonaws.com/...
✅ AWS Account: 985019772236
✅ AWS ARN: arn:aws:iam::985019772236:user/terraform
✅ Architecture Version: 6.0
```

### 3. Dry Run (Recommended First)

Test without actually sending to queue:

```bash
python3 trigger_predictions_manual.py \
  --league-id 39 \
  --start-date 2026-02-20 \
  --end-date 2026-02-23 \
  --dry-run
```

### 4. Live Execution

**⚠️ WARNING: This will trigger actual predictions and consume API credits**

Remove `--dry-run` flag to execute:

```bash
python3 trigger_predictions_manual.py \
  --league-id 39 \
  --start-date 2026-02-20 \
  --end-date 2026-02-23
```

## Script Features

### Diagnostic Checks

The script performs comprehensive checks before execution:

1. ✅ RAPIDAPI_KEY availability
2. ✅ FIXTURES_QUEUE_URL configuration
3. ✅ AWS credentials and permissions
4. ✅ Architecture version compatibility

### Error Handling

Detailed error reporting at each stage:

- **API Errors** - RapidAPI connection/rate limit issues
- **Formatting Errors** - Invalid fixture data
- **Queue Errors** - SQS send failures

### Execution Summary

Provides detailed statistics:

- Fixtures retrieved from API
- Fixtures successfully formatted
- Fixtures sent to queue
- Any warnings or errors encountered

## Common Issues and Solutions

### Issue 1: RAPIDAPI_KEY Not Found

**Error:**
```
❌ RAPIDAPI_KEY environment variable not set
```

**Solution:**
```bash
export RAPIDAPI_KEY="4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4"
```

### Issue 2: Queue URL Not Configured

**Error:**
```
❌ FIXTURES_QUEUE_URL not properly configured
```

**Solution:**
```bash
export FIXTURES_QUEUE_URL="https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-fixture-predictions_prod"
```

### Issue 3: No Fixtures Found

**Warning:**
```
⚠️ No fixtures found for league 39 between 2026-02-20 and 2026-02-23
```

**Possible Causes:**
- Date range outside current season
- No matches scheduled for that period
- API returning empty results

**Solution:**
- Verify date range is correct
- Check league schedule
- Try different date range

### Issue 4: AWS Permissions

**Error:**
```
❌ AWS credentials error: Unable to locate credentials
```

**Solution:**
```bash
# Configure AWS credentials
aws configure

# Or use environment variables
export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
export AWS_DEFAULT_REGION="eu-west-2"
```

## Command Reference

### Basic Usage

```bash
python3 trigger_predictions_manual.py \
  --league-id <LEAGUE_ID> \
  --start-date <YYYY-MM-DD> \
  --end-date <YYYY-MM-DD>
```

### Options

- `--league-id` - League identifier (e.g., 39 for Premier League)
- `--start-date` - Start date in YYYY-MM-DD format
- `--end-date` - End date in YYYY-MM-DD format
- `--dry-run` - Test mode, don't send to queue
- `--check-env` - Only check environment configuration

### Examples

**Premier League (League ID 39):**
```bash
python3 trigger_predictions_manual.py \
  --league-id 39 \
  --start-date 2026-02-20 \
  --end-date 2026-02-23 \
  --dry-run
```

**La Liga (League ID 140):**
```bash
python3 trigger_predictions_manual.py \
  --league-id 140 \
  --start-date 2026-02-20 \
  --end-date 2026-02-23 \
  --dry-run
```

**Multiple Leagues:**
```bash
# Run for each league separately
for league_id in 39 140 78 135 61; do
  python3 trigger_predictions_manual.py \
    --league-id $league_id \
    --start-date 2026-02-20 \
    --end-date 2026-02-23 \
    --dry-run
done
```

## League ID Reference

Common league IDs:

- **39** - Premier League (England)
- **140** - La Liga (Spain)
- **78** - Bundesliga (Germany)
- **135** - Serie A (Italy)
- **61** - Ligue 1 (France)

For complete list, see [`leagues.py`](leagues.py)

## Next Steps After Triggering

1. **Monitor SQS Queue**
   - Check message count in queue
   - Verify messages are being processed

2. **Check Lambda Execution**
   - Review CloudWatch logs for prediction handler
   - Verify predictions are being generated

3. **Verify Results in DynamoDB**
   - Check `football_game_fixtures_prod` table
   - Confirm fixture records contain predictions

## Monitoring Commands

```bash
# Check SQS queue depth
aws sqs get-queue-attributes \
  --queue-url "https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-fixture-predictions_prod" \
  --attribute-names ApproximateNumberOfMessages

# Check recent Lambda executions
aws logs tail /aws/lambda/makeTeamRankings --follow

# Query DynamoDB for recent predictions
aws dynamodb scan \
  --table-name football_game_fixtures_prod \
  --filter-expression "league_id = :lid" \
  --expression-attribute-values '{":lid":{"N":"39"}}' \
  --max-items 5
```

## Troubleshooting

If predictions don't appear:

1. **Check Queue Processing**
   - Verify Lambda is triggered by SQS
   - Check Lambda execution logs

2. **Verify Parameters Exist**
   - League parameters for league 39, season 2025
   - Team parameters for participating teams

3. **Check API Rate Limits**
   - RapidAPI may throttle requests
   - Wait and retry if needed

## Additional Resources

- [Prediction Computation Guide](docs/guides/PREDICTION_COMPUTATION_GUIDE.md)
- [Operational Workflow Guide](docs/guides/OPERATIONAL_WORKFLOW_GUIDE.md)
- [System Architecture](docs/architecture/NEW_SYSTEM_ARCHITECTURE.md)

---

**Created:** 2026-02-17  
**Author:** Debug Mode - Football Fixture Prediction System  
**Status:** ✅ Tested and Validated
