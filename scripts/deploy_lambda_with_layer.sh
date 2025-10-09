#!/bin/bash

###############################################################################
# Lambda Functions Deployment with Layer
#
# This script deploys Lambda functions using Python 3.13 and a Lambda Layer
# for heavy dependencies (numpy, pandas, scipy, scikit-learn)
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

# Configuration
ENVIRONMENT=${1:-prod}
AWS_ACCOUNT_ID="985019772236"
AWS_REGION="eu-west-2"
IAM_ROLE="FootballPredictionLambdaRole"
IAM_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${IAM_ROLE}"
LAMBDA_LAYER_ARN="arn:aws:lambda:eu-west-2:985019772236:layer:scipy-layer:4"
PACKAGE_FILE="lambda_deployment/football_prediction_system_light.zip"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Lambda Functions Deployment with Layer${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Environment:${NC} $ENVIRONMENT"
echo -e "${GREEN}AWS Region:${NC} $AWS_REGION"
echo -e "${GREEN}Runtime:${NC} python3.13"
echo -e "${GREEN}Lambda Layer:${NC} $LAMBDA_LAYER_ARN"
echo ""

# Check if package exists
if [ ! -f "$PACKAGE_FILE" ]; then
    echo -e "${RED}❌ Package not found: $PACKAGE_FILE${NC}"
    echo ""
    echo "Please build the lightweight package first:"
    echo "  ./scripts/build_lambda_package_lightweight.sh"
    exit 1
fi

PACKAGE_SIZE=$(du -h "$PACKAGE_FILE" | cut -f1)
echo -e "${GREEN}Package Size:${NC} $PACKAGE_SIZE"
echo ""

# Check IAM role
echo -e "${YELLOW}Checking IAM role...${NC}"
aws iam get-role --role-name "$IAM_ROLE" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ IAM role not found: $IAM_ROLE${NC}"
    exit 1
fi
echo -e "${GREEN}✅ IAM role exists${NC}"
echo ""

# Confirm deployment
read -p "$(echo -e ${YELLOW}Deploy all Lambda functions? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo -e "${RED}Deployment cancelled${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Deploying Lambda Functions${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Deploy API Service Handler
echo -e "${YELLOW}[1/8] Deploying API Service Handler...${NC}"
aws lambda create-function \
    --function-name "football-api-service-${ENVIRONMENT}" \
    --runtime python3.13 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.api_service_handler.lambda_handler \
    --zip-file fileb://"$PACKAGE_FILE" \
    --timeout 30 \
    --memory-size 1024 \
    --layers "$LAMBDA_LAYER_ARN" \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT},RAPIDAPI_KEY=4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-api-service-${ENVIRONMENT}" \
    --zip-file fileb://"$PACKAGE_FILE" \
    --region "$AWS_REGION"

# Update configuration if function already exists
aws lambda update-function-configuration \
    --function-name "football-api-service-${ENVIRONMENT}" \
    --runtime python3.13 \
    --layers "$LAMBDA_LAYER_ARN" \
    --region "$AWS_REGION" \
    2>/dev/null || true

echo -e "${GREEN}✅ API Service Handler deployed${NC}"
echo ""

# Deploy Fixture Ingestion Handler
echo -e "${YELLOW}[2/8] Deploying Fixture Ingestion Handler...${NC}"
FIXTURES_QUEUE_URL="https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/football_football-fixture-predictions_${ENVIRONMENT}"

aws lambda create-function \
    --function-name "football-fixture-ingestion-${ENVIRONMENT}" \
    --runtime python3.13 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.fixture_ingestion_handler.lambda_handler \
    --zip-file fileb://"$PACKAGE_FILE" \
    --timeout 300 \
    --memory-size 512 \
    --layers "$LAMBDA_LAYER_ARN" \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},FIXTURES_QUEUE_URL=${FIXTURES_QUEUE_URL},RAPIDAPI_KEY=4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-fixture-ingestion-${ENVIRONMENT}" \
    --zip-file fileb://"$PACKAGE_FILE" \
    --region "$AWS_REGION"

aws lambda update-function-configuration \
    --function-name "football-fixture-ingestion-${ENVIRONMENT}" \
    --runtime python3.13 \
    --layers "$LAMBDA_LAYER_ARN" \
    --region "$AWS_REGION" \
    2>/dev/null || true

echo -e "${GREEN}✅ Fixture Ingestion Handler deployed${NC}"
echo ""

# Deploy Prediction Handler
echo -e "${YELLOW}[3/8] Deploying Prediction Handler...${NC}"
aws lambda create-function \
    --function-name "football-prediction-handler-${ENVIRONMENT}" \
    --runtime python3.13 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.prediction_handler.lambda_handler \
    --zip-file fileb://"$PACKAGE_FILE" \
    --timeout 60 \
    --memory-size 1024 \
    --layers "$LAMBDA_LAYER_ARN" \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-prediction-handler-${ENVIRONMENT}" \
    --zip-file fileb://"$PACKAGE_FILE" \
    --region "$AWS_REGION"

aws lambda update-function-configuration \
    --function-name "football-prediction-handler-${ENVIRONMENT}" \
    --runtime python3.13 \
    --layers "$LAMBDA_LAYER_ARN" \
    --region "$AWS_REGION" \
    2>/dev/null || true

# Add SQS trigger
echo -e "${YELLOW}  Configuring SQS trigger...${NC}"
PREDICTION_QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:football_football-fixture-predictions_${ENVIRONMENT}"
aws lambda create-event-source-mapping \
    --function-name "football-prediction-handler-${ENVIRONMENT}" \
    --event-source-arn "$PREDICTION_QUEUE_ARN" \
    --batch-size 1 \
    --region "$AWS_REGION" \
    2>/dev/null || echo "  (SQS trigger already exists)"

echo -e "${GREEN}✅ Prediction Handler deployed${NC}"
echo ""

# Deploy League Parameter Handler
echo -e "${YELLOW}[4/8] Deploying League Parameter Handler...${NC}"
aws lambda create-function \
    --function-name "football-league-parameter-handler-${ENVIRONMENT}" \
    --runtime python3.13 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.league_parameter_handler.lambda_handler \
    --zip-file fileb://"$PACKAGE_FILE" \
    --timeout 900 \
    --memory-size 512 \
    --layers "$LAMBDA_LAYER_ARN" \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-league-parameter-handler-${ENVIRONMENT}" \
    --zip-file fileb://"$PACKAGE_FILE" \
    --region "$AWS_REGION"

aws lambda update-function-configuration \
    --function-name "football-league-parameter-handler-${ENVIRONMENT}" \
    --runtime python3.13 \
    --layers "$LAMBDA_LAYER_ARN" \
    --region "$AWS_REGION" \
    2>/dev/null || true

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

# Deploy Best Bets Handler
echo -e "${YELLOW}[5/8] Deploying Best Bets Handler...${NC}"
BEST_BETS_QUEUE_URL="https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/football_best-bets-analysis_${ENVIRONMENT}"

aws lambda create-function \
    --function-name "football-best-bets-handler-${ENVIRONMENT}" \
    --runtime python3.13 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.best_bets_handler.lambda_handler \
    --zip-file fileb://"$PACKAGE_FILE" \
    --timeout 60 \
    --memory-size 512 \
    --layers "$LAMBDA_LAYER_ARN" \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-best-bets-handler-${ENVIRONMENT}" \
    --zip-file fileb://"$PACKAGE_FILE" \
    --region "$AWS_REGION"

aws lambda update-function-configuration \
    --function-name "football-best-bets-handler-${ENVIRONMENT}" \
    --runtime python3.13 \
    --layers "$LAMBDA_LAYER_ARN" \
    --region "$AWS_REGION" \
    2>/dev/null || true

# Add SQS trigger
echo -e "${YELLOW}  Configuring SQS trigger...${NC}"
BEST_BETS_QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:football_best-bets-analysis_${ENVIRONMENT}"
aws lambda create-event-source-mapping \
    --function-name "football-best-bets-handler-${ENVIRONMENT}" \
    --event-source-arn "$BEST_BETS_QUEUE_ARN" \
    --batch-size 10 \
    --region "$AWS_REGION" \
    2>/dev/null || echo "  (SQS trigger already exists)"

echo -e "${GREEN}✅ Best Bets Handler deployed${NC}"
echo ""

# Deploy Team Parameter Handler
echo -e "${YELLOW}[6/8] Deploying Team Parameter Handler...${NC}"
aws lambda create-function \
    --function-name "football-team-parameter-handler-${ENVIRONMENT}" \
    --runtime python3.13 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.team_parameter_handler.lambda_handler \
    --zip-file fileb://"$PACKAGE_FILE" \
    --timeout 1200 \
    --memory-size 512 \
    --layers "$LAMBDA_LAYER_ARN" \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-team-parameter-handler-${ENVIRONMENT}" \
    --zip-file fileb://"$PACKAGE_FILE" \
    --region "$AWS_REGION"

aws lambda update-function-configuration \
    --function-name "football-team-parameter-handler-${ENVIRONMENT}" \
    --runtime python3.13 \
    --layers "$LAMBDA_LAYER_ARN" \
    --region "$AWS_REGION" \
    2>/dev/null || true

# Add SQS trigger (batch size 1 = one league at a time)
echo -e "${YELLOW}  Configuring SQS trigger...${NC}"
TEAM_QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:football_football-team-parameter-updates_${ENVIRONMENT}"
aws lambda create-event-source-mapping \
    --function-name "football-team-parameter-handler-${ENVIRONMENT}" \
    --event-source-arn "$TEAM_QUEUE_ARN" \
    --batch-size 1 \
    --maximum-concurrency 10 \
    --region "$AWS_REGION" \
    2>/dev/null || echo "  (SQS trigger already exists)"

echo -e "${GREEN}✅ Team Parameter Handler deployed${NC}"
# Deploy Team Parameter Dispatcher
echo -e "${YELLOW}[7/8] Deploying Team Parameter Dispatcher...${NC}"
aws lambda create-function \
    --function-name "football-team-parameter-dispatcher-${ENVIRONMENT}" \
    --runtime python3.13 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.team_parameter_dispatcher.lambda_handler \
    --zip-file fileb://"$PACKAGE_FILE" \
    --timeout 60 \
    --memory-size 256 \
    --layers "$LAMBDA_LAYER_ARN" \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},AWS_REGION=${AWS_REGION},TEAM_PARAMETER_QUEUE_URL=https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/football_football-team-parameter-updates_${ENVIRONMENT}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-team-parameter-dispatcher-${ENVIRONMENT}" \
    --zip-file fileb://"$PACKAGE_FILE" \
    --region "$AWS_REGION"

aws lambda update-function-configuration \
    --function-name "football-team-parameter-dispatcher-${ENVIRONMENT}" \
    --runtime python3.13 \
    --layers "$LAMBDA_LAYER_ARN" \
    --region "$AWS_REGION" \
    2>/dev/null || true

echo -e "${GREEN}✅ Team Parameter Dispatcher deployed${NC}"
echo ""

# Deploy Match Data Handler
echo -e "${YELLOW}[8/8] Deploying Match Data Handler...${NC}"
aws lambda create-function \
    --function-name "football-match-data-handler-${ENVIRONMENT}" \
    --runtime python3.13 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.match_data_handler.lambda_handler \
    --zip-file fileb://"$PACKAGE_FILE" \
    --timeout 300 \
    --memory-size 512 \
    --layers "$LAMBDA_LAYER_ARN" \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT},RAPIDAPI_KEY=4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-match-data-handler-${ENVIRONMENT}" \
    --zip-file fileb://"$PACKAGE_FILE" \
    --region "$AWS_REGION"

aws lambda update-function-configuration \
    --function-name "football-match-data-handler-${ENVIRONMENT}" \
    --runtime python3.13 \
    --layers "$LAMBDA_LAYER_ARN" \
    --region "$AWS_REGION" \
    2>/dev/null || true

# Add SQS trigger
echo -e "${YELLOW}  Configuring SQS trigger...${NC}"
MATCH_RESULTS_QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:football_football-match-results_${ENVIRONMENT}"
aws lambda create-event-source-mapping \
    --function-name "football-match-data-handler-${ENVIRONMENT}" \
    --event-source-arn "$MATCH_RESULTS_QUEUE_ARN" \
    --batch-size 5 \
    --region "$AWS_REGION" \
    2>/dev/null || echo "  (SQS trigger already exists)"

echo -e "${GREEN}✅ Match Data Handler deployed${NC}"
echo ""

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Deployment Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${GREEN}✅ All Lambda functions deployed successfully${NC}"
echo ""
echo -e "${YELLOW}Deployed Functions:${NC}"
echo "  1. football-api-service-${ENVIRONMENT} (python3.13 + layer)"
echo "  2. football-fixture-ingestion-${ENVIRONMENT} (python3.13 + layer)"
echo "  3. football-prediction-handler-${ENVIRONMENT} (python3.13 + layer)"
echo "  4. football-league-parameter-handler-${ENVIRONMENT} (python3.13 + layer)"
echo "  5. football-best-bets-handler-${ENVIRONMENT} (python3.13 + layer)"
echo "  6. football-team-parameter-handler-${ENVIRONMENT} (python3.13 + layer)"
echo "  7. football-team-parameter-dispatcher-${ENVIRONMENT} (python3.13 + layer)"
echo "  8. football-match-data-handler-${ENVIRONMENT} (python3.13 + layer)"
echo ""

echo -e "${YELLOW}Verify Deployment:${NC}"
echo "  aws lambda list-functions --region ${AWS_REGION} --query \"Functions[?contains(FunctionName, 'football')].FunctionName\""
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Test a Lambda function:"
echo "     aws lambda invoke --function-name football-api-service-${ENVIRONMENT} --region ${AWS_REGION} response.json"
echo ""
echo "  2. Deploy API Gateway:"
echo "     ./scripts/deploy_api_service.sh ${ENVIRONMENT} arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:football-api-service-${ENVIRONMENT}"
echo ""

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"