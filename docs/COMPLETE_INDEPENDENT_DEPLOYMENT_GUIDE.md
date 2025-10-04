# Complete Independent Deployment Guide

**Football Fixture Prediction System - Standalone AWS Deployment**

## Overview

This guide explains how to deploy the complete Football Fixture Prediction System as a **fully independent, self-contained AWS application** with zero dependencies on existing resources.

### Key Features
- ✅ **Complete Independence** - No reliance on existing tables or queues
- ✅ **Environment Isolation** - Support for dev, staging, prod environments
- ✅ **Multi-Tenant Ready** - Deploy multiple instances in same AWS account
- ✅ **One-Command Deployment** - Automated infrastructure setup
- ✅ **Zero Manual Configuration** - Automatic constant updates

---

## Architecture

### Complete Infrastructure Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPLETE INDEPENDENT SYSTEM                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  DynamoDB Tables (6):                                           │
│  ├─ game_fixtures              - Store fixture predictions     │
│  ├─ league_parameters          - League-level stats            │
│  ├─ team_parameters            - Team-level stats              │
│  ├─ venue_cache                - Venue information cache       │
│  ├─ tactical_cache             - Tactical data cache           │
│  └─ league_standings_cache     - League standings cache        │
│                                                                 │
│  SQS Queues (5 + 5 DLQs = 10):                                 │
│  ├─ football-fixture-predictions       + DLQ                   │
│  ├─ football-league-parameter-updates  + DLQ                   │
│  ├─ football-team-parameter-updates    + DLQ                   │
│  ├─ football-cache-updates             + DLQ                   │
│  └─ football-match-results             + DLQ                   │
│                                                                 │
│  Lambda Functions (4):                                          │
│  ├─ Fixture Ingestion Handler  - Daily fixture retrieval       │
│  ├─ Prediction Handler         - Generate predictions          │
│  ├─ League Parameter Handler   - Compute league parameters     │
│  └─ Team Parameter Handler     - Compute team parameters       │
│                                                                 │
│  EventBridge Rules (3):                                         │
│  ├─ Daily Fixture Ingestion    - 06:00 UTC                     │
│  ├─ Weekly Parameter Updates   - Sunday 02:00 UTC              │
│  └─ Daily Cache Refresh        - 04:00 UTC                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### Required
1. **AWS Account** with programmatic access
2. **AWS CLI** configured with credentials
3. **Python 3.8+** installed
4. **Boto3** installed (`pip install boto3`)
5. **Required Permissions**:
   - DynamoDB: CreateTable, DescribeTable, ListTables
   - SQS: CreateQueue, GetQueueUrl, GetQueueAttributes, TagQueue
   - IAM: CreateRole, AttachRolePolicy (for Lambda deployment)
   - Lambda: CreateFunction, UpdateFunctionConfiguration
   - EventBridge: PutRule, PutTargets

### Optional
- Git (for version control)
- Docker (for Lambda container deployment)
- SAM CLI (alternative deployment method)

---

## Quick Start (5 Minutes)

### Step 1: Clone and Setup
```bash
cd /path/to/football-fixture-predictions
```

### Step 2: Set Environment Variables (Optional)
```bash
# For dev environment (default)
export ENVIRONMENT=dev
export AWS_REGION=eu-west-2

# For production environment
export ENVIRONMENT=prod
export TABLE_PREFIX=mycompany_
export TABLE_SUFFIX=_production
```

### Step 3: Deploy Complete Infrastructure
```bash
./scripts/deploy_complete_infrastructure.sh dev
```

That's it! The script will:
1. ✅ Create all 6 DynamoDB tables
2. ✅ Create all 10 SQS queues (5 main + 5 DLQs)
3. ✅ Update `src/utils/constants.py` with queue URLs
4. ✅ Export configuration to `queue_config_dev.json`
5. ✅ Verify all resources created successfully

---

## Detailed Deployment Instructions

### Option 1: Automated Deployment (Recommended)

#### Development Environment
```bash
./scripts/deploy_complete_infrastructure.sh dev
```

#### Production Environment
```bash
export TABLE_PREFIX=prod_
export ENVIRONMENT=prod
./scripts/deploy_complete_infrastructure.sh prod
```

#### Custom Environment
```bash
export TABLE_PREFIX=client1_
export TABLE_SUFFIX=_europe
export ENVIRONMENT=staging
export AWS_REGION=eu-west-1
./scripts/deploy_complete_infrastructure.sh staging
```

### Option 2: Manual Step-by-Step Deployment

#### Step 1: Deploy DynamoDB Tables
```bash
# Interactive mode (default)
python3 -m src.infrastructure.deploy_tables

# Non-interactive (for CI/CD)
export ENVIRONMENT=dev
python3 -m src.infrastructure.deploy_tables --no-interactive

# Dry run (preview without creating)
python3 -m src.infrastructure.deploy_tables --dry-run

# Verify existing tables
python3 -m src.infrastructure.deploy_tables --verify-only
```

#### Step 2: Create SQS Queues
```bash
# Create all queues and update constants
python3 -m src.infrastructure.create_all_sqs_queues \
    --environment dev \
    --region eu-west-2 \
    --export queue_config_dev.json \
    --update-constants

# Production deployment
python3 -m src.infrastructure.create_all_sqs_queues \
    --environment prod \
    --region eu-west-2 \
    --export queue_config_prod.json \
    --update-constants
```

#### Step 3: Verify Infrastructure
```bash
# List DynamoDB tables
aws dynamodb list-tables --region eu-west-2

# List SQS queues
aws sqs list-queues --region eu-west-2 --queue-name-prefix football-

# Check table details
aws dynamodb describe-table --table-name game_fixtures --region eu-west-2
```

---

## Environment-Based Naming

### How It Works

The system uses environment variables to generate unique resource names:

```python
# Environment Variables
TABLE_PREFIX = os.getenv('TABLE_PREFIX', '')      # e.g., "myapp_"
TABLE_SUFFIX = os.getenv('TABLE_SUFFIX', '')      # e.g., "_prod"
ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')     # e.g., "dev", "staging", "prod"

# Naming Logic
def _get_table_name(base_name: str) -> str:
    parts = []
    if TABLE_PREFIX:
        parts.append(TABLE_PREFIX.rstrip('_'))
    parts.append(base_name)
    if TABLE_SUFFIX:
        parts.append(TABLE_SUFFIX.lstrip('_'))
    elif ENVIRONMENT and ENVIRONMENT != 'prod':
        parts.append(ENVIRONMENT)
    return '_'.join(parts)
```

### Examples

| Base Name | Prefix | Suffix | Environment | Result |
|-----------|--------|--------|-------------|---------|
| game_fixtures | - | - | dev | game_fixtures_dev |
| game_fixtures | - | - | prod | game_fixtures |
| game_fixtures | myapp_ | - | dev | myapp_game_fixtures_dev |
| game_fixtures | - | _production | prod | game_fixtures_production |
| game_fixtures | client1_ | _eu | staging | client1_game_fixtures_eu |

### Use Cases

**Development Environment**
```bash
export ENVIRONMENT=dev
# Tables: game_fixtures_dev, league_parameters_dev, etc.
# Queues: football-fixture-predictions_dev, etc.
```

**Production Environment**
```bash
export ENVIRONMENT=prod
# Tables: game_fixtures, league_parameters, etc.
# Queues: football-fixture-predictions, etc.
```

**Multi-Tenant Deployment**
```bash
export TABLE_PREFIX=client_acme_
export ENVIRONMENT=prod
# Tables: client_acme_game_fixtures, client_acme_league_parameters, etc.
```

**Regional Isolation**
```bash
export TABLE_SUFFIX=_us_east
export ENVIRONMENT=prod
# Tables: game_fixtures_us_east, league_parameters_us_east, etc.
```

---

## Configuration Files

### Generated Configuration Files

After deployment, the following files are created:

#### 1. `queue_config_{environment}.json`
Contains all queue URLs and ARNs:

```json
{
  "environment": "dev",
  "region": "eu-west-2",
  "queues": {
    "fixture_predictions": {
      "queue_name": "football-fixture-predictions_dev",
      "queue_url": "https://sqs.eu-west-2.amazonaws.com/123456789012/football-fixture-predictions_dev",
      "queue_arn": "arn:aws:sqs:eu-west-2:123456789012:football-fixture-predictions_dev",
      "dlq_name": "football-prediction-dlq_dev",
      "dlq_url": "https://sqs.eu-west-2.amazonaws.com/123456789012/football-prediction-dlq_dev",
      "dlq_arn": "arn:aws:sqs:eu-west-2:123456789012:football-prediction-dlq_dev"
    },
    "league_parameters": { ... },
    "team_parameters": { ... },
    "cache_updates": { ... },
    "match_results": { ... }
  }
}
```

#### 2. `src/utils/constants.py`
Automatically updated with queue URL:

```python
FIXTURES_QUEUE_URL = os.getenv(
    'FIXTURES_QUEUE_URL',
    'https://sqs.eu-west-2.amazonaws.com/123456789012/football-fixture-predictions_dev'
)
```

---

## Queue Configuration Details

### Queue Specifications

| Queue Name | Purpose | Visibility Timeout | Max Receive | Message Retention |
|------------|---------|-------------------|-------------|-------------------|
| football-fixture-predictions | Main fixture processing | 5 minutes | 2 | 14 days |
| football-league-parameter-updates | League parameter computation | 15 minutes | 3 | 14 days |
| football-team-parameter-updates | Team parameter computation | 20 minutes | 3 | 14 days |
| football-cache-updates | Cache refresh operations | 2 minutes | 2 | 14 days |
| football-match-results | Match result processing | 1 minute | 3 | 14 days |

### Dead Letter Queue Behavior

Each main queue has a corresponding DLQ:
- **Max Receive Count**: Messages that fail processing N times move to DLQ
- **Retention**: DLQ messages retained for 14 days for debugging
- **Monitoring**: Set CloudWatch alarms on DLQ depth

---

## Table Schema Details

### 1. game_fixtures
**Purpose**: Store all fixture predictions

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| fixture_id | Number | HASH | Unique fixture ID from API |
| timestamp | Number | RANGE | Match timestamp (Unix) |
| date | String | - | Match date (YYYY-MM-DD) |
| home_team | String | - | Home team name |
| away_team | String | - | Away team name |
| home_id | Number | - | Home team ID |
| away_id | Number | - | Away team ID |
| league_id | Number | - | League ID |
| season | Number | - | Season year |
| predictions | Map | - | Predicted probabilities |
| processed | Boolean | - | Processing status |

**GSI**: date-index (HASH: date, RANGE: timestamp)

### 2. league_parameters
**Purpose**: Store league-level statistical parameters

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| league_id | Number | HASH | Unique league ID |
| season | Number | RANGE | Season year |
| parameters | Map | - | League parameters (λ_home, λ_away, etc.) |
| last_updated | Number | - | Last update timestamp |
| match_count | Number | - | Matches in calculation |

### 3. team_parameters
**Purpose**: Store team-level statistical parameters

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| team_id | Number | HASH | Unique team ID |
| season | Number | RANGE | Season year |
| parameters | Map | - | Team parameters (α_home, β_away, etc.) |
| last_updated | Number | - | Last update timestamp |
| match_count | Number | - | Matches in calculation |

### 4. venue_cache
**Purpose**: Cache venue information

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| venue_id | Number | HASH | Unique venue ID |
| name | String | - | Venue name |
| city | String | - | City |
| capacity | Number | - | Seating capacity |
| surface | String | - | Playing surface type |

### 5. tactical_cache
**Purpose**: Cache tactical data

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| team_id | Number | HASH | Team ID |
| season | Number | RANGE | Season year |
| formation | String | - | Primary formation |
| tactics | Map | - | Tactical statistics |

### 6. league_standings_cache
**Purpose**: Cache league standings

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| league_id | Number | HASH | League ID |
| season | Number | RANGE | Season year |
| standings | List | - | Team standings |
| last_updated | Number | - | Cache timestamp |

---

## Next Steps After Infrastructure Deployment

### 1. Deploy Lambda Functions

Each Lambda function needs to be packaged and deployed:

#### Package Dependencies
```bash
# Create deployment package
mkdir -p lambda_packages/fixture_ingestion
cd lambda_packages/fixture_ingestion

# Copy handler
cp ../../src/handlers/fixture_ingestion_handler.py .

# Copy dependencies
cp -r ../../src/data .
cp -r ../../src/utils .
cp -r ../../src/config .

# Install Python dependencies
pip install -r ../../requirements.txt -t .

# Create ZIP
zip -r fixture_ingestion.zip .
```

#### Deploy to AWS Lambda
```bash
# Create Lambda function
aws lambda create-function \
    --function-name fixture-ingestion-handler-dev \
    --runtime python3.9 \
    --role arn:aws:iam::ACCOUNT_ID:role/lambda-execution-role \
    --handler fixture_ingestion_handler.lambda_handler \
    --zip-file fileb://fixture_ingestion.zip \
    --timeout 300 \
    --memory-size 512 \
    --environment Variables="{
        ENVIRONMENT=dev,
        FIXTURES_QUEUE_URL=<queue_url_from_config>,
        RAPIDAPI_KEY=<your_key>
    }"
```

### 2. Configure EventBridge Rules

#### Daily Fixture Ingestion (06:00 UTC)
```bash
# Create EventBridge rule
aws events put-rule \
    --name daily-fixture-ingestion-dev \
    --schedule-expression "cron(0 6 * * ? *)" \
    --state ENABLED

# Add Lambda target
aws events put-targets \
    --rule daily-fixture-ingestion-dev \
    --targets "Id"="1","Arn"="arn:aws:lambda:REGION:ACCOUNT:function:fixture-ingestion-handler-dev"

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
    --function-name fixture-ingestion-handler-dev \
    --statement-id AllowEventBridgeInvoke \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:REGION:ACCOUNT:rule/daily-fixture-ingestion-dev
```

### 3. Set Up IAM Permissions

Create Lambda execution role with necessary permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/game_fixtures*",
        "arn:aws:dynamodb:*:*:table/league_parameters*",
        "arn:aws:dynamodb:*:*:table/team_parameters*",
        "arn:aws:dynamodb:*:*:table/*cache*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:*:*:football-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

### 4. Testing the System

#### Test 1: Manual Lambda Invocation
```bash
# Test fixture ingestion
aws lambda invoke \
    --function-name fixture-ingestion-handler-dev \
    --payload '{}' \
    response.json

# Check response
cat response.json
```

#### Test 2: Check Queue Messages
```bash
# Get queue URL from config
QUEUE_URL=$(jq -r '.queues.fixture_predictions.queue_url' queue_config_dev.json)

# Check queue depth
aws sqs get-queue-attributes \
    --queue-url $QUEUE_URL \
    --attribute-names ApproximateNumberOfMessages

# Receive a message (for testing)
aws sqs receive-message \
    --queue-url $QUEUE_URL \
    --max-number-of-messages 1
```

#### Test 3: Verify DynamoDB Data
```bash
# Scan game_fixtures table
aws dynamodb scan \
    --table-name game_fixtures_dev \
    --limit 10

# Query specific fixture
aws dynamodb get-item \
    --table-name game_fixtures_dev \
    --key '{"fixture_id": {"N": "12345"}, "timestamp": {"N": "1234567890"}}'
```

#### Test 4: End-to-End Workflow
```python
# test_e2e.py
import boto3
import json

# 1. Trigger fixture ingestion
lambda_client = boto3.client('lambda')
response = lambda_client.invoke(
    FunctionName='fixture-ingestion-handler-dev',
    InvocationType='RequestResponse'
)
print(f"Ingestion Status: {response['StatusCode']}")

# 2. Check SQS queue
sqs = boto3.client('sqs')
messages = sqs.receive_message(
    QueueUrl='<your_queue_url>',
    MaxNumberOfMessages=10
)
print(f"Messages in queue: {len(messages.get('Messages', []))}")

# 3. Verify DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('game_fixtures_dev')
fixtures = table.scan(Limit=10)
print(f"Fixtures in DB: {fixtures['Count']}")
```

---

## Multi-Environment Strategy

### Recommended Approach

```
Development:    ENVIRONMENT=dev     → game_fixtures_dev, football-*_dev
Staging:        ENVIRONMENT=staging → game_fixtures_staging, football-*_staging
Production:     ENVIRONMENT=prod    → game_fixtures, football-*
```

### Deployment Pipeline

```bash
# Development (automatic)
./scripts/deploy_complete_infrastructure.sh dev

# Staging (automatic)
./scripts/deploy_complete_infrastructure.sh staging

# Production (manual approval)
export ENVIRONMENT=prod
./scripts/deploy_complete_infrastructure.sh prod
```

---

## Troubleshooting

### Issue 1: Table Already Exists
```
Error: ResourceInUseException: Table already exists
```
**Solution**: Tables were previously created. Options:
- Delete existing tables: `aws dynamodb delete-table --table-name <table_name>`
- Use verify mode: `python3 -m src.infrastructure.deploy_tables --verify-only`
- Change environment: `export ENVIRONMENT=dev2`

### Issue 2: Queue Already Exists
```
Error: QueueAlreadyExists
```
**Solution**: The script handles this gracefully - it will use existing queue. If you need fresh queues:
```bash
# Delete queue
aws sqs delete-queue --queue-url <queue_url>

# Wait 60 seconds (AWS requirement)
sleep 60

# Re-run script
./scripts/deploy_complete_infrastructure.sh dev
```

### Issue 3: Insufficient Permissions
```
Error: AccessDenied
```
**Solution**: Ensure IAM user/role has required permissions (see Prerequisites)

### Issue 4: Queue URL Not Updated in constants.py
```
Error: Queue URL still shows placeholder
```
**Solution**: Run queue creation with update flag:
```bash
python3 -m src.infrastructure.create_all_sqs_queues --update-constants
```

### Issue 5: Wrong AWS Region
```
Error: Table not found
```
**Solution**: Ensure AWS_REGION matches deployment region:
```bash
export AWS_REGION=eu-west-2
aws configure set region eu-west-2
```

---

## Cost Estimation

### DynamoDB Tables (On-Demand Pricing)
- **Free Tier**: 25 GB storage, 25 WCU, 25 RCU
- **Estimated Cost**: $0-5/month (low traffic)
- **Production**: ~$20-50/month (moderate traffic)

### SQS Queues
- **Free Tier**: 1M requests/month
- **Estimated Cost**: $0-2/month (low traffic)
- **Production**: ~$5-10/month (moderate traffic)

### Lambda Functions
- **Free Tier**: 1M requests, 400,000 GB-seconds
- **Estimated Cost**: $0-5/month (daily runs)
- **Production**: ~$10-30/month (hourly runs)

### Total Monthly Cost
- **Development**: ~$0-10/month (within free tier)
- **Production**: ~$35-90/month (moderate traffic)

---

## Monitoring and Maintenance

### CloudWatch Dashboards

Create dashboard to monitor:
- Lambda invocations and errors
- SQS queue depth and age
- DynamoDB read/write capacity
- DLQ message count

### Recommended Alarms

```bash
# DLQ alarm (any message indicates failure)
aws cloudwatch put-metric-alarm \
    --alarm-name football-prediction-dlq-alarm \
    --alarm-description "Alert when messages in DLQ" \
    --metric-name ApproximateNumberOfMessagesVisible \
    --namespace AWS/SQS \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 1 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=QueueName,Value=football-prediction-dlq_dev

# Lambda error alarm
aws cloudwatch put-metric-alarm \
    --alarm-name fixture-ingestion-errors \
    --alarm-description "Alert on Lambda errors" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 1 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=FunctionName,Value=fixture-ingestion-handler-dev
```

### Maintenance Tasks

**Daily**
- ✅ Check CloudWatch logs for errors
- ✅ Monitor DLQ depth

**Weekly**
- ✅ Review Lambda execution times
- ✅ Check DynamoDB capacity utilization
- ✅ Verify data freshness

**Monthly**
- ✅ Review AWS costs
- ✅ Update dependencies
- ✅ Clean up old fixtures (>90 days)

---

## Security Best Practices

### 1. IAM Least Privilege
- Create separate roles for each Lambda function
- Grant only required permissions
- Use resource-level permissions (specific table/queue ARNs)

### 2. Encryption
- Enable DynamoDB encryption at rest (default KMS)
- Enable SQS encryption (optional, adds latency)

### 3. Network Security
- Deploy Lambda in VPC for database access
- Use VPC endpoints for AWS services
- Enable VPC flow logs

### 4. API Key Protection
```bash
# Store RapidAPI key in Secrets Manager
aws secretsmanager create-secret \
    --name football-rapidapi-key-dev \
    --secret-string '{"api_key":"your_key_here"}'

# Update Lambda to retrieve from Secrets Manager
```

### 5. Audit Logging
- Enable CloudTrail for all API calls
- Log all DynamoDB data access
- Monitor access patterns

---

## Cleanup/Teardown

### Delete All Resources

```bash
# Delete Lambda functions
aws lambda delete-function --function-name fixture-ingestion-handler-dev

# Delete EventBridge rules
aws events remove-targets --rule daily-fixture-ingestion-dev --ids 1
aws events delete-rule --name daily-fixture-ingestion-dev

# Delete SQS queues (including DLQs)
for queue in $(aws sqs list-queues --queue-name-prefix football- --query 'QueueUrls[]' --output text); do
    aws sqs delete-queue --queue-url $queue
done

# Delete DynamoDB tables
for table in game_fixtures_dev league_parameters_dev team_parameters_dev venue_cache_dev tactical_cache_dev league_standings_cache_dev; do
    aws dynamodb delete-table --table-name $table
done

# Delete CloudWatch log groups
for log_group in $(aws logs describe-log-groups --log-group-name-prefix /aws/lambda/fixture --query 'logGroups[].logGroupName' --output text); do
    aws logs delete-log-group --log-group-name $log_group
done
```

---

## Support and Resources

### Documentation
- [Main README](../README.md)
- [Fixture Ingestion Guide](FIXTURE_INGESTION_IMPLEMENTATION_GUIDE.md)
- [Environment Configuration](ENVIRONMENT_CONFIGURATION.md)
- [System Architecture](EVENT_DRIVEN_PREDICTION_SYSTEM_ARCHITECTURE.md)

### Scripts
- [deploy_complete_infrastructure.sh](../scripts/deploy_complete_infrastructure.sh)
- [deploy_tables.py](../src/infrastructure/deploy_tables.py)
- [create_all_sqs_queues.py](../src/infrastructure/create_all_sqs_queues.py)

### AWS Documentation
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [SQS Best Practices](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-best-practices.html)
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)

---

## Appendix

### A. Complete Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| ENVIRONMENT | No | dev | Environment identifier (dev/staging/prod) |
| AWS_REGION | No | eu-west-2 | AWS region for all resources |
| TABLE_PREFIX | No | '' | Prefix for all table names |
| TABLE_SUFFIX | No | '' | Suffix for all table names |
| FIXTURES_QUEUE_URL | No | Auto | SQS queue URL (auto-updated) |
| RAPIDAPI_KEY | Yes | - | RapidAPI Football API key |

### B. Resource Naming Conventions

**Tables**: `{PREFIX}{base_name}{SUFFIX|ENVIRONMENT}`
- Examples: game_fixtures_dev, myapp_league_parameters, team_parameters_prod

**Queues**: `{PREFIX}{base_name}{SUFFIX|ENVIRONMENT}`
- Examples: football-fixture-predictions_dev, client1_football-cache-updates

**Lambda Functions**: `{base_name}-{ENVIRONMENT}`
- Examples: fixture-ingestion-handler-dev, prediction-handler-prod

### C. API Rate Limits

**RapidAPI Football API**
- Free Tier: 100 requests/day
- Pro Plan: 10,000 requests/day
- Ultra Plan: 100,000 requests/day

**Recommendation**: Pro Plan for production (67 leagues × 2 requests = ~134 requests/day minimum)

### D. Sample Configuration Export

```json
{
  "environment": "dev",
  "region": "eu-west-2",
  "tables": {
    "game_fixtures": "game_fixtures_dev",
    "league_parameters": "league_parameters_dev",
    "team_parameters": "team_parameters_dev",
    "venue_cache": "venue_cache_dev",
    "tactical_cache": "tactical_cache_dev",
    "league_standings_cache": "league_standings_cache_dev"
  },
  "queues": {
    "fixture_predictions": {
      "queue_name": "football-fixture-predictions_dev",
      "queue_url": "https://sqs.eu-west-2.amazonaws.com/123456789012/football-fixture-predictions_dev",
      "queue_arn": "arn:aws:sqs:eu-west-2:123456789012:football-fixture-predictions_dev",
      "dlq_name": "football-prediction-dlq_dev",
      "dlq_url": "https://sqs.eu-west-2.amazonaws.com/123456789012/football-prediction-dlq_dev",
      "dlq_arn": "arn:aws:sqs:eu-west-2:123456789012:football-prediction-dlq_dev"
    }
  },
  "lambda_functions": {
    "fixture_ingestion": "fixture-ingestion-handler-dev"
  }
}
```

---

**Last Updated**: October 2025
**Version**: 1.0
**Status**: ✅ Complete Independent Solution
