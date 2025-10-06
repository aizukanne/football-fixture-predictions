# Team Parameter Lambda Timeout - Implementation Summary

**Document Version:** 1.0  
**Implementation Date:** 2025-10-06  
**Status:** ✅ Implemented - Ready for Deployment

## 🎯 Problem Solved

**Original Issue:** Team parameter Lambda function timing out after 900 seconds when processing all 60+ leagues sequentially.

**Solution Implemented:** Dispatcher pattern that sends one SQS message per league, enabling parallel processing of up to 10 leagues simultaneously.

---

## 📦 What Was Implemented

### 1. New Component: Team Parameter Dispatcher (`src/handlers/team_parameter_dispatcher.py`)

**Purpose:** Lightweight Lambda function that dispatches team parameter computation jobs

**Features:**
- Reads all leagues from `leagues.py`
- Sends one SQS message per league
- Supports league filtering by country or ID
- Dry-run mode for testing
- Completes in <10 seconds

**Handler:** `src.handlers.team_parameter_dispatcher.lambda_handler`

### 2. Modified Component: Team Parameter Handler (`src/handlers/team_parameter_handler.py`)

**Changes:**
- ✅ Detects SQS event format (`if 'Records' in event`)
- ✅ Processes single league from SQS message
- ✅ Maintains backward compatibility (direct invocation still works)
- ✅ Returns detailed processing status
- ✅ Improved error handling

**Modes:**
1. **SQS Mode (NEW):** Process single league from message
2. **Direct Mode (LEGACY):** Process all leagues (backward compatible)

### 3. Updated Deployment Script (`scripts/deploy_lambda_with_layer.sh`)

**Changes:**
- ✅ Added dispatcher Lambda deployment (function #7)
- ✅ Configured SQS trigger with batch_size=1 and max_concurrency=10
- ✅ Set appropriate timeouts and memory
- ✅ Environment variables configured

---

## 🚀 Deployment Instructions

### Prerequisites

1. **AWS CLI configured** with appropriate credentials
2. **Queue already exists**: `football_football-team-parameter-updates_prod` ✅
3. **IAM role exists** with Lambda and SQS permissions

### Step 1: Build Lambda Package

```bash
cd /home/ubuntu/Projects/football-fixture-predictions

# Build the Lambda package with layer
./scripts/build_lambda_package_lightweight.sh
```

### Step 2: Deploy Lambda Functions

```bash
# Deploy all functions including the new dispatcher
./scripts/deploy_lambda_with_layer.sh prod
```

This will deploy:
- ✅ `football-team-parameter-dispatcher-prod` (NEW)
- ✅ `football-team-parameter-handler-prod` (MODIFIED)

### Step 3: Verify Deployment

```bash
# Check if dispatcher was deployed
aws lambda get-function \
  --function-name football-team-parameter-dispatcher-prod \
  --region eu-west-2

# Check if handler SQS trigger is configured
aws lambda list-event-source-mappings \
  --function-name football-team-parameter-handler-prod \
  --region eu-west-2
```

Expected output for SQS trigger:
```json
{
  "EventSourceMappings": [
    {
      "FunctionArn": "arn:aws:lambda:eu-west-2:...:function:football-team-parameter-handler-prod",
      "EventSourceArn": "arn:aws:sqs:eu-west-2:...:football_football-team-parameter-updates_prod",
      "State": "Enabled",
      "BatchSize": 1,
      "MaximumConcurrency": 10
    }
  ]
}
```

---

## 🧪 Testing Instructions

### Test 1: Dry Run (Recommended First Test)

Test the dispatcher without actually sending messages:

```bash
aws lambda invoke \
  --function-name football-team-parameter-dispatcher-prod \
  --payload '{"trigger_type": "manual", "dry_run": true}' \
  --region eu-west-2 \
  response.json

# Check the response
cat response.json | jq '.'
```

Expected output:
```json
{
  "statusCode": 200,
  "body": {
    "messages_sent": 0,
    "total_leagues": 60,
    "dry_run": true,
    "execution_time_ms": 150,
    "leagues_processed": [...]
  }
}
```

### Test 2: Single League Test

Test with just one league (Premier League):

```bash
aws lambda invoke \
  --function-name football-team-parameter-dispatcher-prod \
  --payload '{
    "trigger_type": "manual",
    "league_filter": {"league_ids": [39]},
    "dry_run": false
  }' \
  --region eu-west-2 \
  response.json

cat response.json | jq '.'
```

### Test 3: Monitor Processing

Check SQS queue and CloudWatch logs:

```bash
# Check queue depth
aws sqs get-queue-attributes \
  --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-team-parameter-updates_prod \
  --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible \
  --region eu-west-2

# Watch CloudWatch logs for team parameter handler
aws logs tail /aws/lambda/football-team-parameter-handler-prod \
  --follow \
  --region eu-west-2
```

### Test 4: Small Batch Test

Test with a few leagues:

```bash
aws lambda invoke \
  --function-name football-team-parameter-dispatcher-prod \
  --payload '{
    "trigger_type": "manual",
    "league_filter": {"countries": ["England"]},
    "dry_run": false
  }' \
  --region eu-west-2 \
  response.json
```

This will process England leagues (Premier League, Championship, League One, League Two).

### Test 5: Full Production Run

Process all leagues:

```bash
aws lambda invoke \
  --function-name football-team-parameter-dispatcher-prod \
  --payload '{"trigger_type": "manual"}' \
  --region eu-west-2 \
  response.json
```

⏱️ **Expected Duration:** ~12-15 minutes for all 60+ leagues (with 10 parallel executions)

---

## 📊 Monitoring

### CloudWatch Dashboards

Monitor the system using CloudWatch:

```bash
# View dispatcher logs
aws logs tail /aws/lambda/football-team-parameter-dispatcher-prod --follow --region eu-west-2

# View handler logs
aws logs tail /aws/lambda/football-team-parameter-handler-prod --follow --region eu-west-2
```

### Key Metrics to Monitor

1. **Dispatcher Metrics:**
   - Execution time (should be <10s)
   - Messages sent count
   - Error rate

2. **Handler Metrics:**
   - Execution time per league (should be 60-120s)
   - Success rate
   - DLQ message count

3. **SQS Queue Metrics:**
   - `ApproximateNumberOfMessagesVisible` (pending)
   - `ApproximateNumberOfMessagesNotVisible` (processing)
   - Age of oldest message

### Check for Failures

```bash
# Check Dead Letter Queue
aws sqs get-queue-attributes \
  --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-team-dlq_prod \
  --attribute-names ApproximateNumberOfMessages \
  --region eu-west-2

# If DLQ has messages, receive them to see what failed
aws sqs receive-message \
  --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-team-dlq_prod \
  --max-number-of-messages 10 \
  --region eu-west-2
```

---

## 🔧 Configuration

### Environment Variables

**Dispatcher Lambda:**
```bash
ENVIRONMENT=prod
AWS_REGION=eu-west-2
TEAM_PARAMETER_QUEUE_URL=https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-team-parameter-updates_prod
```

**Handler Lambda:**
```bash
ENVIRONMENT=prod
TABLE_PREFIX=football_
TABLE_SUFFIX=_prod
```

### SQS Configuration

**Queue:** `football_football-team-parameter-updates_prod`
- Visibility Timeout: 1200s (20 minutes)
- Max Receive Count: 3
- Batch Size: 1 (one league at a time)
- Max Concurrency: 10 (up to 10 parallel Lambda instances)

---

## 🚨 Troubleshooting

### Issue: Dispatcher times out

**Cause:** Too many leagues or SQS sending taking too long  
**Solution:** Use league filtering or increase timeout to 120s

### Issue: Handler still times out

**Cause:** Individual league has too many teams or slow API responses  
**Solution:** 
1. Check CloudWatch logs for specific league
2. Increase handler timeout to 1800s (30 minutes)
3. Investigate API-Football rate limiting

### Issue: Messages stuck in queue

**Cause:** Lambda not consuming messages or handler errors  
**Solution:**
1. Check if SQS trigger is enabled
2. Review CloudWatch logs for errors
3. Check DLQ for failed messages

### Issue: DLQ has messages

**Cause:** Repeated failures after 3 retry attempts  
**Solution:**
1. Review DLQ messages to identify problem leagues
2. Check if league parameters exist
3. Manually re-send to main queue after fixing issue

### Issue: "No league parameters found"

**Cause:** League parameters haven't been computed yet  
**Solution:**
1. Run league parameter handler first
2. Skip affected leagues or compute league params
3. Re-trigger team parameters after league params exist

---

## 📈 Performance Expectations

| Metric | Expected Value | Notes |
|--------|---------------|-------|
| **Dispatcher Duration** | <10 seconds | Sends 60 messages |
| **Handler Duration (per league)** | 60-120 seconds | Processes 20-30 teams |
| **Total Time (all leagues)** | 12-15 minutes | With 10 parallel executions |
| **Success Rate** | >95% | With retries |
| **Cost per Run** | ~$0.09 | 60 handler executions + 1 dispatcher |

---

## 🔄 Rollback Procedure

If issues arise, you can rollback to direct invocation:

```bash
# Disable SQS trigger
aws lambda update-event-source-mapping \
  --uuid <mapping-uuid> \
  --enabled false \
  --region eu-west-2

# Invoke handler directly (legacy mode)
aws lambda invoke \
  --function-name football-team-parameter-handler-prod \
  --payload '{}' \
  --region eu-west-2 \
  response.json
```

**Note:** Direct invocation will likely still timeout, but provides fallback option.

---

## 📋 Next Steps

### Optional Enhancements

1. **EventBridge Schedule** (automated triggers)
   ```bash
   # Create EventBridge rule to run every 3 days
   aws events put-rule \
     --name team-parameter-scheduled \
     --schedule-expression "cron(0 4 */3 * ? *)" \
     --region eu-west-2
   
   # Add dispatcher as target
   aws events put-targets \
     --rule team-parameter-scheduled \
     --targets "Id"="1","Arn"="arn:aws:lambda:eu-west-2:...:function:football-team-parameter-dispatcher-prod" \
     --region eu-west-2
   ```

2. **Integration with League Parameter Handler**
   - Modify league handler to trigger team dispatcher after completion
   - Implement dependency checking

3. **Advanced Monitoring**
   - Create CloudWatch dashboard
   - Set up SNS alerts for DLQ messages
   - Track per-league success metrics

---

## ✅ Verification Checklist

Before considering implementation complete:

- [ ] Dispatcher Lambda deployed successfully
- [ ] Handler Lambda updated successfully
- [ ] SQS trigger configured (batch size 1, concurrency 10)
- [ ] Dry-run test passes
- [ ] Single league test succeeds
- [ ] Small batch test succeeds (4-5 leagues)
- [ ] Full production run completes successfully
- [ ] Parameters stored correctly in DynamoDB
- [ ] No messages in DLQ
- [ ] CloudWatch logs show expected behavior
- [ ] Execution times within expected ranges
- [ ] Documentation updated

---

## 📚 Related Documentation

- **Architecture Design:** [`TEAM_PARAMETER_LAMBDA_TIMEOUT_SOLUTION.md`](./TEAM_PARAMETER_LAMBDA_TIMEOUT_SOLUTION.md)
- **System Architecture:** [`EVENT_DRIVEN_PREDICTION_SYSTEM_ARCHITECTURE.md`](./EVENT_DRIVEN_PREDICTION_SYSTEM_ARCHITECTURE.md)
- **Deployment Guide:** [`../../README.md`](../../README.md)

---

## 🆘 Support

For issues or questions:
1. Check CloudWatch logs for error messages
2. Review DLQ messages for failed leagues
3. Verify league parameters exist before running
4. Ensure API-Football rate limits not exceeded

---

**Document Status:** Ready for Production Deployment  
**Last Updated:** 2025-10-06  
**Implementation by:** Roo (Code Mode)