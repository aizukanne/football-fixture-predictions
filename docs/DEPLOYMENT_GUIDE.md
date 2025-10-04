# Deployment Guide
**Football Fixture Prediction System - Production Deployment**

Version: 6.0 | Last Updated: October 4, 2025

---

## Table of Contents

1. [Deployment Overview](#deployment-overview)
2. [AWS Lambda Deployment](#aws-lambda-deployment)
3. [Environment-Based Table Isolation](#environment-based-table-isolation)
4. [Alternative Deployments](#alternative-deployments)
5. [Environment Configuration](#environment-configuration)
6. [Database Setup](#database-setup)
7. [Monitoring & Logging](#monitoring--logging)
8. [Security](#security)
9. [Performance Tuning](#performance-tuning)
10. [Troubleshooting](#troubleshooting)

---

## Deployment Overview

### Supported Deployment Options

1. **AWS Lambda + DynamoDB** (Recommended)
   - Serverless, auto-scaling
   - Pay-per-use pricing
   - Production-ready out of the box

2. **Docker Container**
   - Portable, consistent environments
   - Can run on any cloud or on-premises

3. **Traditional Server**
   - Full control
   - Suitable for high-volume use cases

4. **Home Network (LXD + MongoDB)**
   - Cost-effective for personal use
   - Full data control

---

## AWS Lambda Deployment

### Prerequisites

- AWS Account
- AWS CLI configured
- RapidAPI account with API-Football access
- Python 3.8+

### Step 1: Prepare the Package

```bash
# Create deployment directory
mkdir deployment
cd deployment

# Copy source code
cp -r ../src .
cp -r ../requirements.txt .

# Install dependencies to deployment directory
pip install -r requirements.txt -t .

# Create deployment package
zip -r ../deployment-package.zip .
cd ..
```

### Step 2: Create Lambda Function

**Option A: Using AWS CLI**

```bash
# Create Lambda function
aws lambda create-function \
    --function-name football-predictions \
    --runtime python3.9 \
    --role arn:aws:iam::YOUR_ACCOUNT_ID:role/lambda-execution-role \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://deployment-package.zip \
    --timeout 60 \
    --memory-size 512 \
    --environment Variables="{
        RAPIDAPI_KEY=your_key,
        TABLE_PREFIX=myapp_,
        TABLE_SUFFIX=_prod,
        ENVIRONMENT=prod
    }"
```

> **Note**: With environment-based table naming, you no longer need to specify individual table names. The system automatically generates them based on `TABLE_PREFIX`, `TABLE_SUFFIX`, and `ENVIRONMENT`. See [Environment-Based Table Isolation](#environment-based-table-isolation) for details.


**Option B: Using AWS Console**

1. Go to AWS Lambda Console
2. Click "Create function"
3. Choose "Author from scratch"
4. Function name: `football-predictions`
5. Runtime: Python 3.9
6. Upload `deployment-package.zip`
7. Set environment variables (see [Environment Configuration](#environment-configuration))
8. Configure timeout: 60 seconds
9. Configure memory: 512 MB

### Step 3: Create Lambda Handler

Create `lambda_function.py` in the root:

```python
import json
from src.prediction.prediction_engine import generate_prediction_with_reporting

def lambda_handler(event, context):
    """
    Lambda handler for football predictions.

    Expected event format:
    {
        "home_team_id": 33,
        "away_team_id": 40,
        "league_id": 39,
        "season": 2024,
        "venue_id": 556,  # Optional
        "include_insights": true  # Optional
    }
    """
    try:
        # Extract parameters
        home_team_id = event.get('home_team_id')
        away_team_id = event.get('away_team_id')
        league_id = event.get('league_id')
        season = event.get('season')
        venue_id = event.get('venue_id')
        include_insights = event.get('include_insights', True)

        # Validate required parameters
        if not all([home_team_id, away_team_id, league_id, season]):
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required parameters',
                    'required': ['home_team_id', 'away_team_id', 'league_id', 'season']
                })
            }

        # Generate prediction
        prediction = generate_prediction_with_reporting(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            league_id=league_id,
            season=season,
            venue_id=venue_id,
            include_insights=include_insights
        )

        return {
            'statusCode': 200,
            'body': json.dumps(prediction, default=str),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Prediction generation failed'
            })
        }
```

### Step 4: Configure API Gateway (Optional)

To expose Lambda as REST API:

```bash
# Create REST API
aws apigateway create-rest-api \
    --name football-predictions-api \
    --description "Football Prediction API"

# Create resource
aws apigateway create-resource \
    --rest-api-id YOUR_API_ID \
    --parent-id ROOT_RESOURCE_ID \
    --path-part predict

# Create POST method
aws apigateway put-method \
    --rest-api-id YOUR_API_ID \
    --resource-id RESOURCE_ID \
    --http-method POST \
    --authorization-type NONE

# Integrate with Lambda
aws apigateway put-integration \
    --rest-api-id YOUR_API_ID \
    --resource-id RESOURCE_ID \
    --http-method POST \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri arn:aws:apigateway:REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:REGION:ACCOUNT_ID:function:football-predictions/invocations

# Deploy API
aws apigateway create-deployment \
    --rest-api-id YOUR_API_ID \
    --stage-name prod
```

### Step 5: Set Up CloudWatch Monitoring

```bash
# Create log group
aws logs create-log-group \
    --log-group-name /aws/lambda/football-predictions

# Create metric filter for errors
aws logs put-metric-filter \
    --log-group-name /aws/lambda/football-predictions \
    --filter-name ErrorCount \
    --filter-pattern "ERROR" \
    --metric-transformations \
        metricName=Errors,metricNamespace=FootballPredictions,metricValue=1

# Create alarm
aws cloudwatch put-metric-alarm \
    --alarm-name football-predictions-errors \
    --alarm-description "Alert on prediction errors" \
    --metric-name Errors \
    --namespace FootballPredictions \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --alarm-actions arn:aws:sns:REGION:ACCOUNT_ID:alerts
```

---

## Environment-Based Table Isolation

### Overview

The system supports environment-based table naming, allowing multiple independent deployments in the same AWS account. This is essential for:

- **Multi-environment deployments** (dev, staging, prod)
- **Multi-tenant applications** (isolated data per customer)
- **CI/CD pipelines** (temporary test environments)
- **Developer sandboxes** (personal development environments)

### Quick Start

**1. Deploy tables with environment-specific names:**

```bash
# Set environment variables
export TABLE_PREFIX="myapp_"
export TABLE_SUFFIX="_prod"
export ENVIRONMENT="prod"

# Deploy all DynamoDB tables
python3 -m src.infrastructure.deploy_tables
```

**2. Configure Lambda function:**

```bash
aws lambda update-function-configuration \
  --function-name football-predictions \
  --environment Variables="{
    RAPIDAPI_KEY=your_key,
    TABLE_PREFIX=myapp_,
    TABLE_SUFFIX=_prod,
    ENVIRONMENT=prod
  }"
```

### Table Naming Convention

Tables are named using the pattern: `{TABLE_PREFIX}{base_name}{TABLE_SUFFIX}`

**Examples:**

| Configuration | Result |
|---------------|--------|
| No prefix/suffix | `game_fixtures` |
| Prefix: `myapp_` | `myapp_game_fixtures` |
| Suffix: `_prod` | `game_fixtures_prod` |
| Both: `myapp_` + `_prod` | `myapp_game_fixtures_prod` |

### Deployment Scenarios

**Development:**
```bash
# Single developer
python3 -m src.infrastructure.deploy_tables

# Multiple developers (isolated sandboxes)
export TABLE_PREFIX="dev_john_"
python3 -m src.infrastructure.deploy_tables
```

**Staging:**
```bash
export TABLE_PREFIX="myapp_"
export TABLE_SUFFIX="_staging"
export ENVIRONMENT="staging"
python3 -m src.infrastructure.deploy_tables --no-interactive
```

**Production:**
```bash
export TABLE_PREFIX="myapp_"
export TABLE_SUFFIX="_prod"
export ENVIRONMENT="prod"
python3 -m src.infrastructure.deploy_tables --no-interactive
```

**Multi-Tenant:**
```bash
# Customer 1
export TABLE_PREFIX="customer1_"
export TABLE_SUFFIX="_prod"
python3 -m src.infrastructure.deploy_tables --no-interactive

# Customer 2
export TABLE_PREFIX="customer2_"
export TABLE_SUFFIX="_prod"
python3 -m src.infrastructure.deploy_tables --no-interactive
```

### Deployment Script Features

**Interactive mode (default):**
```bash
python3 -m src.infrastructure.deploy_tables
# Prompts for environment configuration
```

**Automated mode:**
```bash
TABLE_PREFIX=myapp_ TABLE_SUFFIX=_prod python3 -m src.infrastructure.deploy_tables --no-interactive
```

**Dry-run mode (test configuration):**
```bash
python3 -m src.infrastructure.deploy_tables --dry-run
```

**Verify existing tables:**
```bash
python3 -m src.infrastructure.deploy_tables --verify-only
```

### IAM Permissions

Update IAM role to allow access to environment-specific tables:

**Option 1: Wildcard (Flexible)**
```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:PutItem",
    "dynamodb:GetItem",
    "dynamodb:UpdateItem",
    "dynamodb:Query",
    "dynamodb:Scan"
  ],
  "Resource": [
    "arn:aws:dynamodb:*:*:table/*game_fixtures*",
    "arn:aws:dynamodb:*:*:table/*league_parameters*",
    "arn:aws:dynamodb:*:*:table/*team_parameters*",
    "arn:aws:dynamodb:*:*:table/*venue_cache*",
    "arn:aws:dynamodb:*:*:table/*tactical_cache*",
    "arn:aws:dynamodb:*:*:table/*league_standings_cache*"
  ]
}
```

**Option 2: Explicit (Most Secure)**
```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:PutItem",
    "dynamodb:GetItem",
    "dynamodb:UpdateItem",
    "dynamodb:Query",
    "dynamodb:Scan"
  ],
  "Resource": [
    "arn:aws:dynamodb:eu-west-2:123456789012:table/myapp_game_fixtures_prod",
    "arn:aws:dynamodb:eu-west-2:123456789012:table/myapp_league_parameters_prod",
    "arn:aws:dynamodb:eu-west-2:123456789012:table/myapp_team_parameters_prod",
    "arn:aws:dynamodb:eu-west-2:123456789012:table/myapp_venue_cache_prod",
    "arn:aws:dynamodb:eu-west-2:123456789012:table/myapp_tactical_cache_prod",
    "arn:aws:dynamodb:eu-west-2:123456789012:table/myapp_league_standings_cache_prod"
  ]
}
```

### Verification

**Check table configuration:**
```python
from src.utils.constants import get_table_config

config = get_table_config()
print(f"Environment: {config['environment']}")
print(f"Tables: {config['tables']}")
```

**List deployed tables:**
```bash
aws dynamodb list-tables --query "TableNames[?contains(@, 'myapp_')]"
```

### Complete Documentation

For complete details on environment configuration, multi-tenant setup, migration, and troubleshooting, see:

**[Environment Configuration Guide](ENVIRONMENT_CONFIGURATION.md)**

---

## Alternative Deployments

### Docker Deployment

**Dockerfile:**

```dockerfile
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY lambda_function.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Run application
CMD ["python", "-m", "awslambdaric", "lambda_function.lambda_handler"]
```

**Build and Run:**

```bash
# Build image
docker build -t football-predictions:latest .

# Run container
docker run -p 8080:8080 \
    -e RAPIDAPI_KEY=your_key \
    -e AWS_ACCESS_KEY_ID=your_access_key \
    -e AWS_SECRET_ACCESS_KEY=your_secret_key \
    -e AWS_DEFAULT_REGION=eu-west-2 \
    football-predictions:latest
```

### Kubernetes Deployment

**deployment.yaml:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: football-predictions
spec:
  replicas: 3
  selector:
    matchLabels:
      app: football-predictions
  template:
    metadata:
      labels:
        app: football-predictions
    spec:
      containers:
      - name: football-predictions
        image: football-predictions:latest
        ports:
        - containerPort: 8080
        env:
        - name: RAPIDAPI_KEY
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: rapidapi-key
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: aws-secrets
              key: access-key-id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: aws-secrets
              key: secret-access-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: football-predictions-service
spec:
  selector:
    app: football-predictions
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
  type: LoadBalancer
```

### Home Network (LXD + MongoDB)

**Prerequisites:**
- LXD installed
- MongoDB installed
- Python 3.8+

**1. Create LXD Container:**

```bash
# Create container
lxc launch ubuntu:20.04 football-predictions

# Access container
lxc exec football-predictions -- bash

# Inside container - install Python
apt update
apt install -y python3.9 python3-pip git

# Clone repository
git clone https://github.com/yourusername/football-fixture-predictions.git
cd football-fixture-predictions

# Install dependencies
pip3 install -r requirements.txt
```

**2. Install MongoDB:**

```bash
# Install MongoDB
apt install -y mongodb

# Start MongoDB
systemctl start mongodb
systemctl enable mongodb
```

**3. Adapt Code for MongoDB:**

Create `src/data/mongodb_client.py`:

```python
from pymongo import MongoClient
from datetime import datetime, timedelta

class MongoDBClient:
    def __init__(self, connection_string="mongodb://localhost:27017/"):
        self.client = MongoClient(connection_string)
        self.db = self.client.football_predictions

        # Create indexes
        self.db.venue_cache.create_index("venue_id")
        self.db.tactical_cache.create_index("match_id")
        self.db.league_standings.create_index([("league_id", 1), ("season", 1)])

        # TTL indexes
        self.db.venue_cache.create_index("ttl", expireAfterSeconds=0)
        self.db.tactical_cache.create_index("ttl", expireAfterSeconds=0)

    def cache_venue(self, venue_id, data):
        """Cache venue data."""
        self.db.venue_cache.update_one(
            {"venue_id": venue_id},
            {"$set": {
                "data": data,
                "cached_at": datetime.now(),
                "ttl": datetime.now() + timedelta(days=7)
            }},
            upsert=True
        )

    def get_cached_venue(self, venue_id):
        """Get cached venue data."""
        result = self.db.venue_cache.find_one({"venue_id": venue_id})
        if result and result.get("ttl") > datetime.now():
            return result.get("data")
        return None
```

**4. Run Application:**

```bash
# Set environment variables
export RAPIDAPI_KEY=your_key
export DB_TYPE=mongodb
export MONGODB_URI=mongodb://localhost:27017/

# Run application
python3 api_server.py
```

---

## Environment Configuration

### Required Environment Variables

```bash
# API Keys
RAPIDAPI_KEY=your_rapidapi_key

# AWS Configuration (for DynamoDB)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=eu-west-2

# DynamoDB Tables
GAME_FIXTURES_TABLE=game_fixtures
TEAM_PARAMETERS_TABLE=team_parameters
LEAGUE_PARAMETERS_TABLE=league_parameters

# Optional Configuration
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
CACHE_ENABLED=true
MAX_RETRIES=5
PREDICTION_TIMEOUT=60
```

### Using .env File (Development)

Create `.env` file:

```bash
RAPIDAPI_KEY=your_key_here
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=eu-west-2
LOG_LEVEL=DEBUG
```

Load with python-dotenv:

```python
from dotenv import load_dotenv
load_dotenv()
```

---

## Database Setup

### DynamoDB Tables

**Create Tables:**

```bash
# Team Parameters Table
aws dynamodb create-table \
    --table-name team_parameters \
    --attribute-definitions \
        AttributeName=team_id,AttributeType=N \
        AttributeName=season,AttributeType=N \
    --key-schema \
        AttributeName=team_id,KeyType=HASH \
        AttributeName=season,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST

# League Parameters Table
aws dynamodb create-table \
    --table-name league_parameters \
    --attribute-definitions \
        AttributeName=league_id,AttributeType=N \
        AttributeName=season,AttributeType=N \
    --key-schema \
        AttributeName=league_id,KeyType=HASH \
        AttributeName=season,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST

# Venue Cache Table
aws dynamodb create-table \
    --table-name venue_cache \
    --attribute-definitions \
        AttributeName=venue_id,AttributeType=N \
    --key-schema \
        AttributeName=venue_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --time-to-live-specification Enabled=true,AttributeName=ttl
```

### MongoDB Collections

```javascript
// Venue cache
db.createCollection("venue_cache");
db.venue_cache.createIndex({ "venue_id": 1 }, { unique: true });
db.venue_cache.createIndex({ "ttl": 1 }, { expireAfterSeconds: 0 });

// Tactical cache
db.createCollection("tactical_cache");
db.tactical_cache.createIndex({ "match_id": 1 }, { unique: true });
db.tactical_cache.createIndex({ "ttl": 1 }, { expireAfterSeconds: 0 });

// League standings
db.createCollection("league_standings");
db.league_standings.createIndex({ "league_id": 1, "season": 1 }, { unique: true });
```

---

## Monitoring & Logging

### CloudWatch Metrics

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

def log_prediction_metric(prediction_time, confidence, success):
    """Log prediction metrics to CloudWatch."""
    cloudwatch.put_metric_data(
        Namespace='FootballPredictions',
        MetricData=[
            {
                'MetricName': 'PredictionTime',
                'Value': prediction_time,
                'Unit': 'Milliseconds'
            },
            {
                'MetricName': 'PredictionConfidence',
                'Value': confidence,
                'Unit': 'None'
            },
            {
                'MetricName': 'SuccessfulPredictions',
                'Value': 1 if success else 0,
                'Unit': 'Count'
            }
        ]
    )
```

### Logging Configuration

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('predictions.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

---

## Security

### API Key Management

```bash
# Store in AWS Secrets Manager
aws secretsmanager create-secret \
    --name football-predictions/rapidapi-key \
    --secret-string "your_api_key_here"

# Retrieve in Lambda
import boto3
secrets = boto3.client('secretsmanager')
response = secrets.get_secret_value(SecretId='football-predictions/rapidapi-key')
api_key = response['SecretString']
```

### IAM Role Permissions

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
                "dynamodb:Query"
            ],
            "Resource": [
                "arn:aws:dynamodb:*:*:table/team_parameters",
                "arn:aws:dynamodb:*:*:table/league_parameters",
                "arn:aws:dynamodb:*:*:table/venue_cache"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": "arn:aws:secretsmanager:*:*:secret:football-predictions/*"
        }
    ]
}
```

---

## Performance Tuning

### Lambda Configuration

```bash
# Increase memory for better CPU
aws lambda update-function-configuration \
    --function-name football-predictions \
    --memory-size 1024 \
    --timeout 120

# Enable reserved concurrency
aws lambda put-function-concurrency \
    --function-name football-predictions \
    --reserved-concurrent-executions 10
```

### Caching Optimization

```python
# Adjust cache TTLs in constants.py
VENUE_CACHE_TTL = 7 * 24 * 60 * 60      # 7 days
TACTICAL_CACHE_TTL = 48 * 60 * 60       # 48 hours
STANDINGS_CACHE_TTL = 24 * 60 * 60      # 24 hours
```

---

## Troubleshooting

### Common Issues

**Issue:** Lambda timeout
```
Solution: Increase timeout to 120 seconds or optimize queries
```

**Issue:** API rate limiting
```
Solution: Implement request throttling and increase cache TTL
```

**Issue:** High costs
```
Solution: Enable caching, reduce log verbosity, use reserved concurrency
```

**Issue:** Cold starts
```
Solution: Use Lambda provisioned concurrency or keep function warm
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with verbose output
python3 -m pdb lambda_function.py
```

---

## Cost Estimation

### AWS Costs (Monthly)

- **Lambda:** $0-5 (free tier covers most use)
- **DynamoDB:** $5-25 (on-demand pricing)
- **API Gateway:** $3-10 (if used)
- **CloudWatch:** $1-5 (logs and metrics)
- **Total:** $9-45/month (moderate usage)

### Optimization Tips

1. Use DynamoDB on-demand for variable workloads
2. Enable caching to reduce API calls
3. Monitor and optimize Lambda memory
4. Use CloudWatch Insights instead of full logs

---

**Deployment Status:** Production Ready ✅
**Last Updated:** October 4, 2025
**Version:** 6.0
