#!/bin/bash

###############################################################################
# GenAI Pundit API Gateway Deployment Script
#
# This script deploys the API Gateway endpoint for GenAI Pundit
# It creates a /analysis POST endpoint on the existing API Gateway
#
# Usage:
#   ./scripts/deploy_genai_pundit_gateway.sh [environment]
#
# Examples:
#   ./scripts/deploy_genai_pundit_gateway.sh prod
#   ./scripts/deploy_genai_pundit_gateway.sh dev
#
# Environment Variables (optional):
#   ENVIRONMENT  - Environment identifier (dev, staging, prod)
#   AWS_REGION   - AWS region (default: eu-west-2)
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
ENVIRONMENT=${1:-${ENVIRONMENT:-prod}}
AWS_REGION=${AWS_REGION:-eu-west-2}

# Lambda function name
LAMBDA_FUNCTION_NAME="football-genai-pundit-${ENVIRONMENT}"
LAMBDA_ARN="arn:aws:lambda:${AWS_REGION}:985019772236:function:${LAMBDA_FUNCTION_NAME}"

# API Gateway details (using existing API)
API_NAME="football-predictions-api-${ENVIRONMENT}"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   GenAI Pundit API Gateway Deployment${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Environment:${NC} $ENVIRONMENT"
echo -e "${GREEN}AWS Region:${NC} $AWS_REGION"
echo -e "${GREEN}Lambda Function:${NC} $LAMBDA_FUNCTION_NAME"
echo ""

# Confirm deployment
read -p "$(echo -e ${YELLOW}Deploy API Gateway /analysis endpoint? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo -e "${RED}Deployment cancelled${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Deploying API Gateway${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${GREEN}[1/6] Finding existing API Gateway...${NC}"
API_ID=$(aws apigateway get-rest-apis --region $AWS_REGION --query "items[?name=='$API_NAME'].id" --output text)

if [ -z "$API_ID" ]; then
    echo -e "${RED}Error: API Gateway '$API_NAME' not found${NC}"
    echo "Please ensure the main API Gateway is deployed first"
    exit 1
fi

echo -e "${GREEN}Found API Gateway: $API_ID${NC}"
echo ""

echo -e "${GREEN}[2/6] Getting root resource...${NC}"
ROOT_RESOURCE_ID=$(aws apigateway get-resources --rest-api-id $API_ID --region $AWS_REGION --query 'items[?path==`/`].id' --output text)
echo -e "${GREEN}Root resource ID: $ROOT_RESOURCE_ID${NC}"
echo ""

echo -e "${GREEN}[3/6] Creating /analysis resource...${NC}"
# Check if /analysis resource already exists
ANALYSIS_RESOURCE_ID=$(aws apigateway get-resources --rest-api-id $API_ID --region $AWS_REGION --query 'items[?pathPart==`analysis`].id' --output text 2>/dev/null || echo "")

if [ -z "$ANALYSIS_RESOURCE_ID" ]; then
    ANALYSIS_RESOURCE_ID=$(aws apigateway create-resource \
        --rest-api-id $API_ID \
        --parent-id $ROOT_RESOURCE_ID \
        --path-part analysis \
        --region $AWS_REGION \
        --query 'id' \
        --output text)
    echo -e "${GREEN}Created /analysis resource: $ANALYSIS_RESOURCE_ID${NC}"
else
    echo -e "${YELLOW}Resource /analysis already exists: $ANALYSIS_RESOURCE_ID${NC}"
fi
echo ""

echo -e "${GREEN}[4/6] Setting up HTTP methods and Lambda integration...${NC}"

# Array of HTTP methods to configure
METHODS=("GET" "POST" "PUT" "DELETE")

for METHOD in "${METHODS[@]}"; do
    echo -e "${BLUE}  Configuring $METHOD method...${NC}"
    
    # Create method (no API key required - auth in Lambda code)
    aws apigateway put-method \
        --rest-api-id $API_ID \
        --resource-id $ANALYSIS_RESOURCE_ID \
        --http-method $METHOD \
        --authorization-type NONE \
        --no-api-key-required \
        --region $AWS_REGION \
        --no-cli-pager > /dev/null 2>&1
    
    # Create Lambda integration (AWS_PROXY)
    aws apigateway put-integration \
        --rest-api-id $API_ID \
        --resource-id $ANALYSIS_RESOURCE_ID \
        --http-method $METHOD \
        --type AWS_PROXY \
        --integration-http-method POST \
        --uri "arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations" \
        --region $AWS_REGION \
        --no-cli-pager > /dev/null 2>&1
    
    # Create method response
    aws apigateway put-method-response \
        --rest-api-id $API_ID \
        --resource-id $ANALYSIS_RESOURCE_ID \
        --http-method $METHOD \
        --status-code 200 \
        --region $AWS_REGION \
        --no-cli-pager > /dev/null 2>&1
    
    echo -e "${GREEN}  ✓ $METHOD method configured${NC}"
done

echo -e "${GREEN}POST method configured${NC}"
echo ""

echo -e "${GREEN}[5/6] Setting up CORS (OPTIONS method)...${NC}"

# Create OPTIONS method for CORS
aws apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $ANALYSIS_RESOURCE_ID \
    --http-method OPTIONS \
    --authorization-type NONE \
    --no-api-key-required \
    --region $AWS_REGION \
    --no-cli-pager > /dev/null 2>&1

# Create MOCK integration for OPTIONS
aws apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $ANALYSIS_RESOURCE_ID \
    --http-method OPTIONS \
    --type MOCK \
    --request-templates '{"application/json": "{\"statusCode\": 200}"}' \
    --region $AWS_REGION \
    --no-cli-pager > /dev/null 2>&1

# Create OPTIONS method response with CORS headers
aws apigateway put-method-response \
    --rest-api-id $API_ID \
    --resource-id $ANALYSIS_RESOURCE_ID \
    --http-method OPTIONS \
    --status-code 200 \
    --response-parameters '{"method.response.header.Access-Control-Allow-Headers": false, "method.response.header.Access-Control-Allow-Methods": false, "method.response.header.Access-Control-Allow-Origin": false}' \
    --region $AWS_REGION \
    --no-cli-pager > /dev/null 2>&1

# Create OPTIONS integration response with CORS values
aws apigateway put-integration-response \
    --rest-api-id $API_ID \
    --resource-id $ANALYSIS_RESOURCE_ID \
    --http-method OPTIONS \
    --status-code 200 \
    --response-parameters '{"method.response.header.Access-Control-Allow-Headers": "'"'"'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,x-api-key'"'"'", "method.response.header.Access-Control-Allow-Methods": "'"'"'GET,POST,PUT,DELETE,OPTIONS'"'"'", "method.response.header.Access-Control-Allow-Origin": "'"'"'*'"'"'"}' \
    --region $AWS_REGION \
    --no-cli-pager > /dev/null 2>&1

echo -e "${GREEN}✓ CORS configured (all methods: GET, POST, PUT, DELETE)${NC}"
echo ""

echo -e "${GREEN}[6/6] Granting Lambda permissions and deploying...${NC}"

# Grant API Gateway permission to invoke Lambda for all methods
aws lambda add-permission \
    --function-name $LAMBDA_FUNCTION_NAME \
    --statement-id apigateway-genai-pundit-all-${ENVIRONMENT} \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${AWS_REGION}:985019772236:${API_ID}/*/*/analysis" \
    --region $AWS_REGION \
    2>/dev/null || echo -e "${YELLOW}  Lambda permission may already exist${NC}"

# Deploy API
DEPLOYMENT_ID=$(aws apigateway create-deployment \
    --rest-api-id $API_ID \
    --stage-name prod \
    --description "GenAI Pundit /analysis endpoint deployment" \
    --region $AWS_REGION \
    --query 'id' \
    --output text)

echo -e "${GREEN}Deployed to stage 'prod': $DEPLOYMENT_ID${NC}"
echo ""

# Get API key (assumes it was created with the main API)
API_KEY_ID=$(aws apigateway get-api-keys --region $AWS_REGION --include-values --query 'items[0].id' --output text 2>/dev/null || echo "")

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Deployment Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${YELLOW}API Endpoint:${NC}"
echo "  https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/analysis"
echo ""

echo -e "${YELLOW}Authentication:${NC}"
echo "  API key authentication is handled in the Lambda function code"
echo "  Include x-api-key header in your requests"
echo ""

echo -e "${YELLOW}Test the endpoint:${NC}"
echo "  # POST request"
echo "  curl -X POST \\"
echo "    https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/analysis \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H 'x-api-key: q9fsNSUn2X0k6nLMchKu+hRnWLsRvkzqxsodnLack8U=' \\"
echo "    -d '{\"fixture_id\": 1374235}'"
echo ""
echo "  # GET request"
echo "  curl -X GET \\"
echo "    'https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/analysis?fixture_id=1374235' \\"
echo "    -H 'x-api-key: q9fsNSUn2X0k6nLMchKu+hRnWLsRvkzqxsodnLack8U='"
echo ""

echo -e "${YELLOW}Configuration saved to:${NC}"
echo "  genai_pundit_gateway_config_${ENVIRONMENT}.json"
echo ""

# Save configuration
cat > genai_pundit_gateway_config_${ENVIRONMENT}.json <<EOF
{
  "environment": "$ENVIRONMENT",
  "region": "$AWS_REGION",
  "api_id": "$API_ID",
  "endpoint_url": "https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod",
  "analysis_endpoint": "https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/analysis",
  "resource_id": "$ANALYSIS_RESOURCE_ID",
  "lambda_function_arn": "$LAMBDA_ARN",
  "stage_name": "prod",
  "deployment_id": "$DEPLOYMENT_ID"
}
EOF

echo -e "${GREEN}✅ GenAI Pundit API Gateway endpoint deployed successfully!${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"