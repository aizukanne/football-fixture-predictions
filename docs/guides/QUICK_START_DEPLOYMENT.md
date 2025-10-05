# Quick Start Deployment Guide

**Football Fixture Prediction System v6.0**  
**5-Minute Deployment to AWS**

---

## 🎯 What's Already Done

✅ **Infrastructure (60% Complete)**
- 6 DynamoDB tables deployed to eu-west-2
- 10 SQS queues created (5 main + 5 DLQs)
- Environment configured for production
- All credentials verified and working
- Security measures implemented

---

## 🚀 Quick Deployment Steps

### Step 1: Create IAM Role (2 minutes)

```bash
./scripts/create_lambda_iam_role.sh
```

This creates the `FootballPredictionLambdaRole` with all necessary permissions.

### Step 2: Build Lambda Package (3-5 minutes)

```bash
./scripts/build_lambda_package.sh
```

This creates `lambda_deployment/football_prediction_system.zip` (~50-80 MB).

### Step 3: Deploy Lambda Functions (2 minutes)

```bash
./scripts/deploy_lambda_functions.sh prod
```

This deploys all 5 Lambda functions and configures SQS triggers.

### Step 4: Deploy API Gateway (1 minute)

```bash
./scripts/deploy_api_service.sh prod arn:aws:lambda:eu-west-2:985019772236:function:football-api-service-prod
```

This creates the HTTP API endpoint for predictions.

### Step 5: Test the System (1 minute)

```bash
# Test API endpoint
aws lambda invoke \
    --function-name football-api-service-prod \
    --payload '{"queryStringParameters": {"fixture_id": "123456"}}' \
    --region eu-west-2 \
    response.json

cat response.json
```

---

## 📋 Complete Deployment Commands

Copy and paste this entire block:

```bash
# Navigate to project
cd /home/ubuntu/Projects/football-fixture-predictions

# Load environment
source setup_deployment_env.sh

# Create IAM role
./scripts/create_lambda_iam_role.sh

# Build Lambda package
./scripts/build_lambda_package.sh

# Deploy Lambda functions
./scripts/deploy_lambda_functions.sh prod

# Get the API Service Lambda ARN
API_LAMBDA_ARN=$(aws lambda get-function --function-name football-api-service-prod --region eu-west-2 --query 'Configuration.FunctionArn' --output text)

# Deploy API Gateway
./scripts/deploy_api_service.sh prod "$API_LAMBDA_ARN"

# Test the deployment
aws lambda invoke \
    --function-name football-api-service-prod \
    --payload '{"queryStringParameters": {"fixture_id": "123456"}}' \
    --region eu-west-2 \
    response.json && cat response.json
```

---

## 🔍 Verify Deployment

### Check All Resources

```bash
# List Lambda functions
aws lambda list-functions --region eu-west-2 --query "Functions[?contains(FunctionName, 'football')].[FunctionName, Runtime, State]" --output table

# List DynamoDB tables
aws dynamodb list-tables --region eu-west-2 --query "TableNames[?contains(@, 'football_')]"

# List SQS queues
aws sqs list-queues --region eu-west-2 --queue-name-prefix "football_"

# Check API Gateway
aws apigatewayv2 get-apis --region eu-west-2 --query "Items[?contains(Name, 'football')].[Name, ApiEndpoint]" --output table
```

### Test Individual Functions

```bash
# Test Fixture Ingestion
aws lambda invoke \
    --function-name football-fixture-ingestion-prod \
    --payload '{"action": "test"}' \
    --region eu-west-2 \
    fixture_response.json

# Test Prediction Handler
aws lambda invoke \
    --function-name football-prediction-handler-prod \
    --payload '{"fixture_id": 123456}' \
    --region eu-west-2 \
    prediction_response.json
```

---

## 📊 Deployment Status

### ✅ Completed (60%)

| Resource | Count | Status |
|----------|-------|--------|
| DynamoDB Tables | 6/6 | ✅ DEPLOYED |
| SQS Queues | 10/10 | ✅ DEPLOYED |
| Environment Config | 1/1 | ✅ CONFIGURED |
| Credentials | 2/2 | ✅ VERIFIED |

### ⏳ Pending (40%)

| Resource | Count | Status |
|----------|-------|--------|
| IAM Role | 0/1 | ⏳ PENDING |
| Lambda Functions | 0/5 | ⏳ PENDING |
| API Gateway | 0/1 | ⏳ PENDING |
| EventBridge Rules | 0/3 | ⏳ PENDING |

---

## 🎯 Deployed Resources Summary

### DynamoDB Tables (eu-west-2)
1. `football_game_fixtures_prod`
2. `football_league_parameters_prod`
3. `football_team_parameters_prod`
4. `football_venue_cache_prod`
5. `football_tactical_cache_prod`
6. `football_league_standings_cache_prod`

### SQS Queues (eu-west-2)
1. `football_football-fixture-predictions_prod` + DLQ
2. `football_football-league-parameter-updates_prod` + DLQ
3. `football_football-team-parameter-updates_prod` + DLQ
4. `football_football-cache-updates_prod` + DLQ
5. `football_football-match-results_prod` + DLQ

### Lambda Functions (To Deploy)
1. `football-api-service-prod` - HTTP API endpoint
2. `football-fixture-ingestion-prod` - Daily fixture retrieval
3. `football-prediction-handler-prod` - Generate predictions
4. `football-league-parameter-handler-prod` - League parameters
5. `football-team-parameter-handler-prod` - Team parameters

---

## 🔐 Credentials

### AWS
- **Account ID:** 985019772236
- **IAM User:** terraform
- **Region:** eu-west-2 (Europe - London)
- **Status:** ✅ Verified

### API-Football
- **Key:** 4c37223ace... (working)
- **Plan:** Free tier (30 requests/day)
- **Status:** ✅ Validated
- **Endpoint:** https://api-football-v1.p.rapidapi.com

---

## 📝 Environment Configuration

### Current Settings (.env)
```bash
AWS_DEFAULT_REGION=eu-west-2
ENVIRONMENT=prod
TABLE_PREFIX=football_
TABLE_SUFFIX=_prod
```

### Lambda Environment Variables
All Lambda functions will have:
- `ENVIRONMENT=prod`
- `TABLE_PREFIX=football_`
- `TABLE_SUFFIX=_prod`
- `RAPIDAPI_KEY=<from constants>`

---

## ⚙️ EventBridge Configuration

### Daily Fixture Ingestion (06:00 UTC)
```bash
aws events put-rule \
    --name football-daily-fixture-ingestion-prod \
    --schedule-expression "cron(0 6 * * ? *)" \
    --state ENABLED \
    --region eu-west-2
```

### Weekly Parameter Updates (Sunday 02:00 UTC)
```bash
aws events put-rule \
    --name football-weekly-parameter-update-prod \
    --schedule-expression "cron(0 2 ? * SUN *)" \
    --state ENABLED \
    --region eu-west-2
```

### Daily Cache Refresh (04:00 UTC)
```bash
aws events put-rule \
    --name football-daily-cache-refresh-prod \
    --schedule-expression "cron(0 4 * * ? *)" \
    --state ENABLED \
    --region eu-west-2
```

---

## 🧪 Testing

### Manual Lambda Invocation
```bash
# Invoke API Service
aws lambda invoke \
    --function-name football-api-service-prod \
    --payload file://test_payload.json \
    --region eu-west-2 \
    response.json
```

### Send Test Message to SQS
```bash
aws sqs send-message \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-fixture-predictions_prod \
    --message-body '{"fixture_id": 123456, "test": true}' \
    --region eu-west-2
```

### Check CloudWatch Logs
```bash
aws logs tail /aws/lambda/football-api-service-prod --follow --region eu-west-2
```

---

## 📊 Monitoring

### CloudWatch Metrics
- Lambda invocations
- Lambda errors
- Lambda duration
- DynamoDB read/write capacity
- SQS queue depth
- API Gateway requests

### Set Up Alarms
```bash
# DLQ Alarm (any message indicates failure)
aws cloudwatch put-metric-alarm \
    --alarm-name football-prediction-dlq-alarm-prod \
    --alarm-description "Alert when messages arrive in prediction DLQ" \
    --metric-name ApproximateNumberOfMessagesVisible \
    --namespace AWS/SQS \
    --statistic Average \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 1 \
    --comparison-operator GreaterThanOrEqualToThreshold \
    --dimensions Name=QueueName,Value=football_football-prediction-dlq_prod \
    --region eu-west-2

# Lambda Error Alarm
aws cloudwatch put-metric-alarm \
    --alarm-name football-lambda-errors-prod \
    --alarm-description "Alert on Lambda function errors" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=FunctionName,Value=football-api-service-prod \
    --region eu-west-2
```

---

## 💰 Cost Estimate

### Monthly Costs (Approximate)

| Service | Usage | Cost |
|---------|-------|------|
| DynamoDB | On-demand, low traffic | $5-10 |
| Lambda | 50K invocations/month | $0.20 |
| SQS | 100K requests/month | $0.04 |
| API Gateway | 10K requests/month | $1.00 |
| CloudWatch | Logs + metrics | $2-5 |
| **Total** | | **$8-17/month** |

---

## 🔧 Troubleshooting

### Issue: Lambda Package Too Large
**Solution:** Use Lambda Layers or deploy as container image

### Issue: Lambda Timeout
**Solution:** Increase timeout in `deploy_lambda_functions.sh`

### Issue: DynamoDB Throttling
**Solution:** Switch from on-demand to provisioned capacity

### Issue: API Rate Limit (RapidAPI)
**Solution:** Upgrade to paid plan or implement caching

### Issue: IAM Permissions
**Solution:** Run `./scripts/create_lambda_iam_role.sh` again

---

## 📚 Related Documentation

- [Final Deployment Status Report](FINAL_DEPLOYMENT_STATUS_REPORT.md)
- [Complete Deployment Guide](COMPLETE_INDEPENDENT_DEPLOYMENT_GUIDE.md)
- [API Documentation](API_DOCUMENTATION.md)
- [Environment Configuration](ENVIRONMENT_CONFIGURATION.md)
- [Pre-Deployment Checklist](COMPREHENSIVE_PRE_DEPLOYMENT_CHECKLIST.md)

---

## ✅ Success Criteria

Your deployment is successful when:

1. ✅ All 5 Lambda functions are deployed and active
2. ✅ API Gateway returns valid responses
3. ✅ SQS queues are processing messages
4. ✅ DynamoDB tables are receiving writes
5. ✅ CloudWatch shows no errors
6. ✅ EventBridge rules are triggering on schedule

---

## 🎉 Next Steps After Deployment

1. **Test End-to-End Workflow**
   - Trigger fixture ingestion
   - Verify predictions generated
   - Check database for results

2. **Enable Monitoring**
   - Set up CloudWatch dashboards
   - Configure alarms
   - Enable X-Ray tracing

3. **Optimize Performance**
   - Review Lambda memory settings
   - Adjust timeout values
   - Enable reserved concurrency

4. **Upgrade API Plan**
   - Move from free tier to paid
   - Increase rate limits
   - Enable additional features

5. **Production Hardening**
   - Implement API authentication
   - Add request validation
   - Enable encryption at rest
   - Set up backup policies

---

*Last Updated: 2025-10-05 04:21 UTC*  
*Deployment Region: eu-west-2 (Europe - London)*  
*System Version: v6.0 - Production Ready*