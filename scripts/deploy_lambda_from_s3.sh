#!/bin/bash

###############################################################################
# Lambda Functions Deployment from S3
#
# This script deploys Lambda functions using a package stored in S3
# Required for packages larger than 50MB
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Load environment
source setup_deployment_env.sh

# Load S3 location if available
if [ -f /tmp/lambda_s3_location.sh ]; then
    source /tmp/lambda_s3_location.sh
fi

# Configuration
ENVIRONMENT=${1:-prod}
AWS_ACCOUNT_ID="985019772236"
AWS_REGION="eu-west-2"
IAM_ROLE="FootballPredictionLambdaRole"
IAM_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${IAM_ROLE}"

# Check if S3 location is set
if [ -z "$LAMBDA_S3_BUCKET" ] || [ -z "$LAMBDA_S3_KEY" ]; then
    echo -e "${RED}❌ S3 location not set${NC}"
    echo ""
    echo "Please upload the package to S3 first:"
    echo "  ./scripts/upload_lambda_to_s3.sh"
    exit 1
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Lambda Functions Deployment from S3${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Environment:${NC} $ENVIRONMENT"
echo -e "${GREEN}AWS Region:${NC} $AWS_REGION"
echo -e "${GREEN}S3 Bucket:${NC} $LAMBDA_S3_BUCKET"
echo -e "${GREEN}S3 Key:${NC} $LAMBDA_S3_KEY"
echo ""

# Deploy API Service Handler
echo -e "${YELLOW}[1/5] Deploying API Service Handler...${NC}"
aws lambda create-function \
    --function-name "football-api-service-${ENVIRONMENT}" \
    --runtime python3.9 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.api_service_handler.lambda_handler \
    --code S3Bucket="$LAMBDA_S3_BUCKET",S3Key="$LAMBDA_S3_KEY" \
    --timeout 30 \
    --memory-size 1024 \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT},RAPIDAPI_KEY=4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-api-service-${ENVIRONMENT}" \
    --s3-bucket "$LAMBDA_S3_BUCKET" \
    --s3-key "$LAMBDA_S3_KEY" \
    --region "$AWS_REGION"

echo -e "${GREEN}✅ API Service Handler deployed${NC}"
echo ""

# Deploy Fixture Ingestion Handler
echo -e "${YELLOW}[2/5] Deploying Fixture Ingestion Handler...${NC}"
FIXTURES_QUEUE_URL="https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/football_football-fixture-predictions_${ENVIRONMENT}"

aws lambda create-function \
    --function-name "football-fixture-ingestion-${ENVIRONMENT}" \
    --runtime python3.9 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.fixture_ingestion_handler.lambda_handler \
    --code S3Bucket="$LAMBDA_S3_BUCKET",S3Key="$LAMBDA_S3_KEY" \
    --timeout 300 \
    --memory-size 512 \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},FIXTURES_QUEUE_URL=${FIXTURES_QUEUE_URL},RAPIDAPI_KEY=4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-fixture-ingestion-${ENVIRONMENT}" \
    --s3-bucket "$LAMBDA_S3_BUCKET" \
    --s3-key "$LAMBDA_S3_KEY" \
    --region "$AWS_REGION"

echo -e "${GREEN}✅ Fixture Ingestion Handler deployed${NC}"
echo ""

# Deploy Prediction Handler
echo -e "${YELLOW}[3/5] Deploying Prediction Handler...${NC}"
aws lambda create-function \
    --function-name "football-prediction-handler-${ENVIRONMENT}" \
    --runtime python3.9 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.prediction_handler.lambda_handler \
    --code S3Bucket="$LAMBDA_S3_BUCKET",S3Key="$LAMBDA_S3_KEY" \
    --timeout 60 \
    --memory-size 1024 \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-prediction-handler-${ENVIRONMENT}" \
    --s3-bucket "$LAMBDA_S3_BUCKET" \
    --s3-key "$LAMBDA_S3_KEY" \
    --region "$AWS_REGION"

# Add SQS trigger
echo -e "${YELLOW}  Configuring SQS trigger...${NC}"
PREDICTION_QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:football_football-fixture-predictions_${ENVIRONMENT}"
aws lambda create-event-source-mapping \
    --function-name "football-prediction-handler-${ENVIRONMENT}" \
    --event-source-arn "$PREDICTION_QUEUE_ARN" \
    --batch-size 10 \
    --region "$AWS_REGION" \
    2>/dev/null || echo "  (SQS trigger already exists)"

echo -e "${GREEN}✅ Prediction Handler deployed${NC}"
echo ""

# Deploy League Parameter Handler
echo -e "${YELLOW}[4/5] Deploying League Parameter Handler...${NC}"
aws lambda create-function \
    --function-name "football-league-parameter-handler-${ENVIRONMENT}" \
    --runtime python3.9 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.league_parameter_handler.lambda_handler \
    --code S3Bucket="$LAMBDA_S3_BUCKET",S3Key="$LAMBDA_S3_KEY" \
    --timeout 900 \
    --memory-size 512 \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-league-parameter-handler-${ENVIRONMENT}" \
    --s3-bucket "$LAMBDA_S3_BUCKET" \
    --s3-key "$LAMBDA_S3_KEY" \
    --region "$AWS_REGION"

# Add SQS trigger
echo -e "${YELLOW}  Configuring SQS trigger...${NC}"
LEAGUE_QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:football_football-league-parameter-updates_${ENVIRONMENT}"
aws lambda create-event-source-mapping \
    --function-name "football-league-parameter-handler-${ENVIRONMENT}" \
    --event-source-arn "$LEAGUE_QUEUE_ARN" \
    --batch-size 5 \
    --region "$AWS_REGION" \
    2>/dev/null || echo "  (SQS trigger already exists)"

echo -e "${GREEN}✅ League Parameter Handler deployed${NC}"
echo ""

# Deploy Team Parameter Handler
echo -e "${YELLOW}[5/5] Deploying Team Parameter Handler...${NC}"
aws lambda create-function \
    --function-name "football-team-parameter-handler-${ENVIRONMENT}" \
    --runtime python3.9 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.team_parameter_handler.lambda_handler \
    --code S3Bucket="$LAMBDA_S3_BUCKET",S3Key="$LAMBDA_S3_KEY" \
    --timeout 1200 \
    --memory-size 512 \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-team-parameter-handler-${ENVIRONMENT}" \
    --s3-bucket "$LAMBDA_S3_BUCKET" \
    --s3-key "$LAMBDA_S3_KEY" \
    --region "$AWS_REGION"

# Add SQS trigger
echo -e "${YELLOW}  Configuring SQS trigger...${NC}"
TEAM_QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:football_football-team-parameter-updates_${ENVIRONMENT}"
aws lambda create-event-source-mapping \
    --function-name "football-team-parameter-handler-${ENVIRONMENT}" \
    --event-source-arn "$TEAM_QUEUE_ARN" \
    --batch-size 5 \
    --region "$AWS_REGION" \
    2>/dev/null || echo "  (SQS trigger already exists)"

echo -e "${GREEN}✅ Team Parameter Handler deployed${NC}"
echo ""

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Deployment Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${GREEN}✅ All Lambda functions deployed successfully${NC}"
echo ""
echo -e "${YELLOW}Deployed Functions:${NC}"
echo "  1. football-api-service-${ENVIRONMENT}"
echo "  2. football-fixture-ingestion-${ENVIRONMENT}"
echo "  3. football-prediction-handler-${ENVIRONMENT}"
echo "  4. football-league-parameter-handler-${ENVIRONMENT}"
echo "  5. football-team-parameter-handler-${ENVIRONMENT}"
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Test Lambda functions:"
echo "     aws lambda invoke --function-name football-api-service-${ENVIRONMENT} --region ${AWS_REGION} response.json"
echo ""
echo "  2. Deploy API Gateway:"
echo "     ./scripts/deploy_api_service.sh ${ENVIRONMENT} arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:football-api-service-${ENVIRONMENT}"
echo ""

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"