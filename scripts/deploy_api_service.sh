#!/bin/bash

###############################################################################
# API Service Deployment Script
#
# This script deploys the API Service Lambda function and API Gateway
#
# Usage:
#   ./scripts/deploy_api_service.sh [environment] [lambda-arn]
#
# Examples:
#   ./scripts/deploy_api_service.sh dev arn:aws:lambda:eu-west-2:123:function:api-service-dev
#   ./scripts/deploy_api_service.sh prod arn:aws:lambda:eu-west-2:123:function:api-service-prod
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
ENVIRONMENT=${1:-${ENVIRONMENT:-dev}}
LAMBDA_ARN=${2:-""}
AWS_REGION=${AWS_REGION:-eu-west-2}

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   API Service Deployment${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Environment:${NC} $ENVIRONMENT"
echo -e "${GREEN}AWS Region:${NC} $AWS_REGION"
echo ""

# Check if Lambda ARN is provided
if [ -z "$LAMBDA_ARN" ]; then
    echo -e "${RED}Error: Lambda function ARN is required${NC}"
    echo ""
    echo "Usage: $0 [environment] [lambda-arn]"
    echo ""
    echo "Example:"
    echo "  $0 dev arn:aws:lambda:eu-west-2:123456789012:function:api-service-dev"
    echo ""
    exit 1
fi

echo -e "${GREEN}Lambda Function ARN:${NC} $LAMBDA_ARN"
echo ""

# Confirm deployment
read -p "$(echo -e ${YELLOW}Deploy API Gateway with this configuration? [y/N]: ${NC})" -n 1 -r
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

# Deploy API Gateway
echo -e "${GREEN}Creating API Gateway configuration...${NC}"
python3 -m src.infrastructure.deploy_api_gateway \
    --lambda-arn "$LAMBDA_ARN" \
    --region "$AWS_REGION" \
    --environment "$ENVIRONMENT" \
    --stage "prod"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to deploy API Gateway${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ API Gateway deployed successfully${NC}"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Deployment Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${YELLOW}Configuration:${NC}"
echo "  📝 API Gateway configuration saved to:"
echo "     api_gateway_config_${ENVIRONMENT}.json"
echo ""
echo "  🔑 API Key and endpoint URL can be found in the configuration file"
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Test the API endpoint:"
echo "     curl -H 'X-API-Key: <your-api-key>' \\"
echo "          'https://<api-id>.execute-api.${AWS_REGION}.amazonaws.com/prod/predictions?fixture_id=123456'"
echo ""
echo "  2. Test league query:"
echo "     curl -H 'X-API-Key: <your-api-key>' \\"
echo "          'https://<api-id>.execute-api.${AWS_REGION}.amazonaws.com/prod/predictions?country=England&league=Premier%20League'"
echo ""
echo "  3. Update frontend applications with:"
echo "     - API endpoint URL"
echo "     - API key for authentication"
echo ""
echo "  4. Set up monitoring:"
echo "     - CloudWatch dashboards"
echo "     - API Gateway metrics"
echo "     - Lambda error alerts"
echo ""

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
