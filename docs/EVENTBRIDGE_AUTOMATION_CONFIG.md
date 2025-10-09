# EventBridge Automation Configuration

**Last Updated:** October 9, 2025

## Overview

This document describes the automated EventBridge rules configured for the Football Prediction System.

---

## Configured Rules

### 1. Daily Match Results Check ✅ ACTIVE

**Rule:** `football-match-results-daily-prod`

**Purpose:** Automatically check and update match scores for completed fixtures

**Schedule:** Daily at 04:00 UTC  
**Expression:** `cron(0 4 * * ? *)`

**Target:** `football-match-data-handler-prod` Lambda function

**Configuration:**
```json
{
  "Name": "football-match-results-daily-prod",
  "Arn": "arn:aws:events:eu-west-2:985019772236:rule/football-match-results-daily-prod",
  "ScheduleExpression": "cron(0 4 * * ? *)",
  "State": "ENABLED",
  "Description": "Daily automatic score checking for completed matches at 04:00 UTC"
}
```

**What it does:**
- Triggers the match data handler Lambda function daily
- Checks all matches from the past 24 hours
- Updates fixture records with actual scores
- Collects enhanced match statistics (shots, possession, etc.)

**Created:** October 9, 2025

---

### 2. Daily Fixture Ingestion (Existing)

**Rule:** `football-daily-fixture-ingestion-prod`

**Purpose:** Fetch upcoming fixtures from API-Football

**Schedule:** Daily at 06:00 UTC  
**Expression:** `cron(0 6 * * ? *)`

**Target:** `football-fixture-ingestion-prod` Lambda function

---

### 3. Weekly Parameter Updates (Existing)

**Rule:** `football-weekly-parameter-update-prod`

**Purpose:** Update league and team parameters

**Schedule:** Weekly on Sundays at 02:00 UTC  
**Expression:** `cron(0 2 ? * SUN *)`

**Target:** `football-league-parameter-handler-prod` Lambda function

---

### 4. Daily Cache Refresh (Existing)

**Rule:** `football-daily-cache-refresh-prod`

**Purpose:** Refresh cached data (standings, venues)

**Schedule:** Daily at 01:00 UTC  
**Expression:** `cron(0 4 * * ? *)`

**Target:** Cache refresh handler (if deployed)

---

## Daily Automation Timeline

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  01:00 UTC - Cache Refresh                                  │
│              └─ Update standings cache                      │
│              └─ Refresh venue data                          │
│                                                             │
│  02:00 UTC - Weekly Parameter Update (Sundays only)         │
│              └─ Recalculate league parameters               │
│              └─ Update team strength ratings                │
│                                                             │
│  04:00 UTC - Match Results Check ⭐ NEW                     │
│              └─ Check completed matches                     │
│              └─ Update actual scores                        │
│              └─ Collect match statistics                    │
│                                                             │
│  06:00 UTC - Fixture Ingestion                              │
│              └─ Fetch today's fixtures                      │
│              └─ Queue for predictions                       │
│              └─ Automatic predictions generated             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Management Commands

### View All Rules

```bash
aws events list-rules --region eu-west-2 --query "Rules[?contains(Name, 'football')].{Name:Name,Schedule:ScheduleExpression,State:State}"
```

### View Rule Details

```bash
aws events describe-rule --name football-match-results-daily-prod --region eu-west-2
```

### View Rule Targets

```bash
aws events list-targets-by-rule --rule football-match-results-daily-prod --region eu-west-2
```

### Disable a Rule (Temporarily)

```bash
aws events disable-rule --name football-match-results-daily-prod --region eu-west-2
```

### Enable a Rule

```bash
aws events enable-rule --name football-match-results-daily-prod --region eu-west-2
```

### Update Schedule

```bash
aws events put-rule \
    --name football-match-results-daily-prod \
    --schedule-expression "cron(0 6 * * ? *)" \
    --region eu-west-2
```

### Delete Rule

```bash
# First remove targets
aws events remove-targets --rule football-match-results-daily-prod --ids 1 --region eu-west-2

# Then delete rule
aws events delete-rule --name football-match-results-daily-prod --region eu-west-2
```

---

## Monitoring

### Check Last Execution

```bash
aws logs tail /aws/lambda/football-match-data-handler-prod --since 1h --region eu-west-2
```

### View CloudWatch Metrics

```bash
aws cloudwatch get-metric-statistics \
    --namespace AWS/Events \
    --metric-name Invocations \
    --dimensions Name=RuleName,Value=football-match-results-daily-prod \
    --statistics Sum \
    --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 86400 \
    --region eu-west-2
```

### Check for Errors

```bash
aws logs filter-log-events \
    --log-group-name /aws/lambda/football-match-data-handler-prod \
    --filter-pattern "ERROR" \
    --start-time $(date -u -d '1 day ago' +%s)000 \
    --region eu-west-2
```

---

## Troubleshooting

### Rule Not Triggering

1. **Check rule state:**
   ```bash
   aws events describe-rule --name football-match-results-daily-prod --region eu-west-2
   ```
   Ensure `State` is `ENABLED`

2. **Verify targets:**
   ```bash
   aws events list-targets-by-rule --rule football-match-results-daily-prod --region eu-west-2
   ```
   Ensure Lambda ARN is correct

3. **Check Lambda permissions:**
   ```bash
   aws lambda get-policy --function-name football-match-data-handler-prod --region eu-west-2
   ```
   Should show EventBridge permission

### Lambda Errors

1. **Check recent logs:**
   ```bash
   aws logs tail /aws/lambda/football-match-data-handler-prod --follow --region eu-west-2
   ```

2. **View CloudWatch Logs:**
   - Go to CloudWatch Console
   - Navigate to Log Groups
   - Find `/aws/lambda/football-match-data-handler-prod`
   - Check recent log streams

### Permission Issues

If you see "User is not authorized to perform: events:PutTargets":

```bash
# Add EventBridge permissions to Lambda
aws lambda add-permission \
    --function-name football-match-data-handler-prod \
    --statement-id AllowEventBridgeInvoke \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:eu-west-2:985019772236:rule/football-match-results-daily-prod \
    --region eu-west-2
```

---

## Cost Optimization

### Current Configuration
- **Match Results Check:** Once daily = 30 invocations/month
- **Average Duration:** ~30 seconds per execution
- **Cost:** ~$0.01/month (negligible)

### Optimization Options

1. **Reduce Frequency:**
   - Change to every 2 days: `cron(0 4 */2 * ? *)`
   - Weekend only: `cron(0 4 ? * SAT,SUN *)`

2. **Conditional Execution:**
   - Add logic to skip if no matches expected
   - Check fixture count before processing

3. **Batch Processing:**
   - Process multiple days in single execution
   - Reduce invocation frequency

---

## Future Enhancements

### Planned Improvements

1. **Smart Scheduling:**
   - Trigger based on actual match times
   - Multiple checks on heavy match days

2. **Real-time Updates:**
   - WebSocket or polling for live scores
   - Update predictions during matches

3. **Failure Notifications:**
   - SNS alerts for failed checks
   - Slack/email notifications

4. **Performance Monitoring:**
   - Track processing duration
   - Alert on anomalies

---

## Configuration as Code

### Terraform Example

```hcl
resource "aws_cloudwatch_event_rule" "match_results_daily" {
  name                = "football-match-results-daily-prod"
  description         = "Daily automatic score checking"
  schedule_expression = "cron(0 4 * * ? *)"
  is_enabled          = true
}

resource "aws_cloudwatch_event_target" "match_results_lambda" {
  rule      = aws_cloudwatch_event_rule.match_results_daily.name
  target_id = "MatchDataHandler"
  arn       = aws_lambda_function.match_data_handler.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.match_data_handler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.match_results_daily.arn
}
```

---

## Deployment History

### October 9, 2025
- ✅ Created `football-match-results-daily-prod` rule
- ✅ Configured daily execution at 04:00 UTC
- ✅ Added Lambda target
- ✅ Granted EventBridge invoke permissions
- ✅ Tested configuration
- ✅ Documented automation

---

## Related Documentation

- [Lambda Handlers Deployment Status](LAMBDA_HANDLERS_DEPLOYMENT_STATUS.md)
- [Operational Workflow Guide](guides/OPERATIONAL_WORKFLOW_GUIDE.md)
- [Event-Driven Architecture](architecture/EVENT_DRIVEN_PREDICTION_SYSTEM_ARCHITECTURE.md)

---

**Status:** ✅ CONFIGURED AND ACTIVE