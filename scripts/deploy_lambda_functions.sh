#!/bin/bash

###############################################################################
# Lambda Functions Deployment Script
#
# This script deploys all Lambda functions for the Football Prediction System
#
# Prerequisites:
# 1. IAM role "FootballPredictionLambdaRole" must exist
# 2. DynamoDB tables must be deployed
# 3. SQS queues must be created
# 4. Lambda deployment package must be built
#
# Usage:
#   ./scripts/deploy_lambda_functions.sh [environment]
#
# Examples:
#   ./scripts/deploy_lambda_functions.sh prod
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment
source setup_deployment_env.sh

# Configuration
ENVIRONMENT=${1:-prod}
AWS_ACCOUNT_ID="985019772236"
AWS_REGION="eu-west-2"
IAM_ROLE="FootballPredictionLambdaRole"
IAM_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${IAM_ROLE}"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Lambda Functions Deployment${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Environment:${NC} $ENVIRONMENT"
echo -e "${GREEN}AWS Region:${NC} $AWS_REGION"
echo -e "${GREEN}AWS Account:${NC} $AWS_ACCOUNT_ID"
echo -e "${GREEN}IAM Role:${NC} $IAM_ROLE_ARN"
echo ""

# Check if deployment package exists
if [ ! -f "lambda_deployment/football_prediction_system.zip" ]; then
    echo -e "${RED}❌ Deployment package not found!${NC}"
    echo ""
    echo "Please create the deployment package first:"
    echo "  ./scripts/build_lambda_package.sh"
    exit 1
fi

# Check if IAM role exists
echo -e "${YELLOW}Checking IAM role...${NC}"
aws iam get-role --role-name "$IAM_ROLE" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ IAM role not found: $IAM_ROLE${NC}"
    echo ""
    echo "Please create the IAM role first:"
    echo "  ./scripts/create_lambda_iam_role.sh"
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
echo -e "${YELLOW}[1/7] Deploying API Service Handler...${NC}"
aws lambda create-function \
    --function-name "football-api-service-${ENVIRONMENT}" \
    --runtime python3.9 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.api_service_handler.lambda_handler \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --timeout 30 \
    --memory-size 1024 \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT},RAPIDAPI_KEY=${RAPIDAPI_KEY:-4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-api-service-${ENVIRONMENT}" \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --region "$AWS_REGION"

echo -e "${GREEN}✅ API Service Handler deployed${NC}"
echo ""

# Deploy Fixture Ingestion Handler
echo -e "${YELLOW}[2/7] Deploying Fixture Ingestion Handler...${NC}"
FIXTURES_QUEUE_URL="https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/football_football-fixture-predictions_${ENVIRONMENT}"

aws lambda create-function \
    --function-name "football-fixture-ingestion-${ENVIRONMENT}" \
    --runtime python3.9 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.fixture_ingestion_handler.lambda_handler \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --timeout 300 \
    --memory-size 512 \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},FIXTURES_QUEUE_URL=${FIXTURES_QUEUE_URL},RAPIDAPI_KEY=${RAPIDAPI_KEY:-4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-fixture-ingestion-${ENVIRONMENT}" \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --region "$AWS_REGION"

echo -e "${GREEN}✅ Fixture Ingestion Handler deployed${NC}"
echo ""

# Deploy Prediction Handler
echo -e "${YELLOW}[3/7] Deploying Prediction Handler...${NC}"
aws lambda create-function \
    --function-name "football-prediction-handler-${ENVIRONMENT}" \
    --runtime python3.9 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.prediction_handler.lambda_handler \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --timeout 60 \
    --memory-size 1024 \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-prediction-handler-${ENVIRONMENT}" \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --region "$AWS_REGION"

# Add SQS trigger
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
echo -e "${YELLOW}[4/7] Deploying League Parameter Handler...${NC}"
aws lambda create-function \
    --function-name "football-league-parameter-handler-${ENVIRONMENT}" \
    --runtime python3.9 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.league_parameter_handler.lambda_handler \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --timeout 900 \
    --memory-size 512 \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-league-parameter-handler-${ENVIRONMENT}" \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --region "$AWS_REGION"

# Add SQS trigger
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
echo -e "${YELLOW}[5/7] Deploying Best Bets Handler...${NC}"
BEST_BETS_QUEUE_URL="https://sqs.${AWS_REGION}.amazonaws.com/${AWS_ACCOUNT_ID}/football_best-bets-analysis_${ENVIRONMENT}"

aws lambda create-function \
    --function-name "football-best-bets-handler-${ENVIRONMENT}" \
    --runtime python3.9 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.best_bets_handler.lambda_handler \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --timeout 60 \
    --memory-size 512 \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-best-bets-handler-${ENVIRONMENT}" \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --region "$AWS_REGION"

# Add SQS trigger
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
echo -e "${YELLOW}[6/7] Deploying Team Parameter Handler...${NC}"
aws lambda create-function \
    --function-name "football-team-parameter-handler-${ENVIRONMENT}" \
    --runtime python3.9 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.team_parameter_handler.lambda_handler \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --timeout 1200 \
    --memory-size 512 \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-team-parameter-handler-${ENVIRONMENT}" \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --region "$AWS_REGION"

# Add SQS trigger
TEAM_QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:football_football-team-parameter-updates_${ENVIRONMENT}"
aws lambda create-event-source-mapping \
    --function-name "football-team-parameter-handler-${ENVIRONMENT}" \
    --event-source-arn "$TEAM_QUEUE_ARN" \
    --batch-size 5 \
    --region "$AWS_REGION" \
    2>/dev/null || echo "  (SQS trigger already exists)"

echo -e "${GREEN}✅ Team Parameter Handler deployed${NC}"
echo ""

# Deploy Match Data Handler
echo -e "${YELLOW}[7/8] Deploying Match Data Handler...${NC}"
aws lambda create-function \
    --function-name "football-match-data-handler-${ENVIRONMENT}" \
    --runtime python3.9 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.match_data_handler.lambda_handler \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --timeout 300 \
    --memory-size 512 \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},TABLE_PREFIX=football_,TABLE_SUFFIX=_${ENVIRONMENT},RAPIDAPI_KEY=${RAPIDAPI_KEY:-4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4}}" \
    --region "$AWS_REGION" \
    2>/dev/null || aws lambda update-function-code \
    --function-name "football-match-data-handler-${ENVIRONMENT}" \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --region "$AWS_REGION"

# Add SQS trigger
MATCH_RESULTS_QUEUE_ARN="arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:football_football-match-results_${ENVIRONMENT}"
aws lambda create-event-source-mapping \
    --function-name "football-match-data-handler-${ENVIRONMENT}" \
    --event-source-arn "$MATCH_RESULTS_QUEUE_ARN" \
    --batch-size 5 \
    --region "$AWS_REGION" \
    2>/dev/null || echo "  (SQS trigger already exists)"


# Deploy GenAI Pundit Handler
echo -e "${YELLOW}[8/8] Deploying GenAI Pundit Handler...${NC}"
LLM_LAYER_ARN="arn:aws:lambda:eu-west-2:985019772236:layer:llm-layer:1"

aws lambda create-function \
    --function-name "football-genai-pundit-${ENVIRONMENT}" \
    --runtime python3.11 \
    --role "$IAM_ROLE_ARN" \
    --handler src.handlers.genai_pundit_handler.lambda_handler \
    --zip-file fileb://lambda_deployment/football_prediction_system.zip \
    --timeout 60 \
    --memory-size 512 \
    --layers "$LLM_LAYER_ARN" \
    --environment "Variables={ENVIRONMENT=${ENVIRONMENT},ACTIVE_AI_PROVIDER=gemini,GAME_FIXTURES_TABLE=game_fixtures,TEAM_PARAMETERS_TABLE=team_parameters,LEAGUE_PARAMETERS_TABLE=league_parameters,GAME_ANALYSIS_TABLE=game_analysis,GEMINI_API_KEY=${GEMINI_API_KEY:-},ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-},VALID_MOBILE_API_KEY=${VALID_MOBILE_API_KEY:-}}" \
    --region "$AWS_REGION" \
    2>/dev/null || {
        # Update function code
        aws lambda update-function-code \
            --function-name "football-genai-pundit-${ENVIRONMENT}" \
            --zip-file fileb://lambda_deployment/football_prediction_system.zip \
            --region "$AWS_REGION"
        
        # Update layer configuration
        aws lambda update-function-configuration \
            --function-name "football-genai-pundit-${ENVIRONMENT}" \
            --layers "$LLM_LAYER_ARN" \
            --region "$AWS_REGION"
    }

echo -e "${GREEN}✅ GenAI Pundit Handler deployed with LLM layer${NC}"
echo -e "${YELLOW}  ℹ Using existing layer: llm-layer:1${NC}"
echo -e "${YELLOW}  ⚠ Note: Remember to set API keys (GEMINI_API_KEY, ANTHROPIC_API_KEY, VALID_MOBILE_API_KEY)${NC}"
echo ""
echo -e "${GREEN}✅ Match Data Handler deployed${NC}"
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
echo "  5. football-best-bets-handler-${ENVIRONMENT}"
echo "  6. football-team-parameter-handler-${ENVIRONMENT}"
echo "  7. football-match-data-handler-${ENVIRONMENT}"
echo "  8. football-genai-pundit-${ENVIRONMENT}"
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Deploy API Gateway:"
echo "     ./scripts/deploy_api_service.sh ${ENVIRONMENT} arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:football-api-service-${ENVIRONMENT}"
echo ""
echo "  2. Configure EventBridge rules:"
echo "     ./scripts/configure_eventbridge.sh ${ENVIRONMENT}"
echo ""
echo "  3. Test Lambda functions:"
echo "     aws lambda invoke --function-name football-api-service-${ENVIRONMENT} --region ${AWS_REGION} response.json"
echo ""

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"