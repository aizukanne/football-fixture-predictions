#!/bin/bash

###############################################################################
# CORS Configuration Fix Script
#
# This script fixes the CORS configuration for /predictions and /analysis
# endpoints by adding/updating the OPTIONS method integration responses.
#
# Root Cause: /predictions OPTIONS method was missing integrationResponses,
# causing 500 errors on browser preflight requests.
#
# Usage:
#   ./scripts/fix_cors_configuration.sh [environment]
#
# Examples:
#   ./scripts/fix_cors_configuration.sh prod
#   ./scripts/fix_cors_configuration.sh dev
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

# API Gateway configuration
API_ID="esqyjhhc4e"
PREDICTIONS_RESOURCE_ID="xooseg"
ANALYSIS_RESOURCE_ID="lhmoik"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   CORS Configuration Fix${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Environment:${NC} $ENVIRONMENT"
echo -e "${GREEN}AWS Region:${NC} $AWS_REGION"
echo -e "${GREEN}API Gateway ID:${NC} $API_ID"
echo ""
echo -e "${YELLOW}This will fix CORS for:${NC}"
echo "  • /predictions endpoint (add missing integration response)"
echo "  • /analysis endpoint (update headers to match requirements)"
echo ""

# Confirm execution
read -p "$(echo -e ${YELLOW}Proceed with CORS fix? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo -e "${RED}Fix cancelled${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Applying CORS Fix${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Step 1: Fix /predictions endpoint
echo -e "${GREEN}[1/4] Fixing /predictions OPTIONS integration response...${NC}"
aws apigateway put-integration-response \
    --rest-api-id $API_ID \
    --resource-id $PREDICTIONS_RESOURCE_ID \
    --http-method OPTIONS \
    --status-code 200 \
    --response-parameters '{"method.response.header.Access-Control-Allow-Origin": "'"'"'*'"'"'", "method.response.header.Access-Control-Allow-Methods": "'"'"'GET,POST,OPTIONS'"'"'", "method.response.header.Access-Control-Allow-Headers": "'"'"'Content-Type,X-Api-Key'"'"'"}' \
    --region $AWS_REGION \
    --no-cli-pager > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ /predictions OPTIONS integration response configured${NC}"
else
    echo -e "${RED}✗ Failed to configure /predictions OPTIONS integration response${NC}"
    exit 1
fi
echo ""

# Step 2: Update /analysis endpoint
echo -e "${GREEN}[2/4] Updating /analysis OPTIONS integration response...${NC}"
aws apigateway put-integration-response \
    --rest-api-id $API_ID \
    --resource-id $ANALYSIS_RESOURCE_ID \
    --http-method OPTIONS \
    --status-code 200 \
    --response-parameters '{"method.response.header.Access-Control-Allow-Origin": "'"'"'*'"'"'", "method.response.header.Access-Control-Allow-Methods": "'"'"'GET,POST,OPTIONS'"'"'", "method.response.header.Access-Control-Allow-Headers": "'"'"'Content-Type,X-Api-Key'"'"'"}' \
    --region $AWS_REGION \
    --no-cli-pager > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ /analysis OPTIONS integration response updated${NC}"
else
    echo -e "${RED}✗ Failed to update /analysis OPTIONS integration response${NC}"
    exit 1
fi
echo ""

# Step 3: Deploy changes
echo -e "${GREEN}[3/4] Deploying changes to API Gateway...${NC}"
DEPLOYMENT_ID=$(aws apigateway create-deployment \
    --rest-api-id $API_ID \
    --stage-name prod \
    --description "Fix CORS configuration - add missing integration responses" \
    --region $AWS_REGION \
    --query 'id' \
    --output text)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Deployment created: $DEPLOYMENT_ID${NC}"
else
    echo -e "${RED}✗ Failed to deploy changes${NC}"
    exit 1
fi
echo ""

# Step 4: Verify the fix
echo -e "${GREEN}[4/4] Verifying CORS configuration...${NC}"
echo ""

echo -e "${BLUE}Testing /predictions OPTIONS:${NC}"
PREDICTIONS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS \
    https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/predictions)

if [ "$PREDICTIONS_RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓ /predictions returns 200 OK${NC}"
    curl -i -X OPTIONS https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/predictions 2>&1 | grep -i "access-control"
else
    echo -e "${RED}✗ /predictions returns $PREDICTIONS_RESPONSE (expected 200)${NC}"
fi
echo ""

echo -e "${BLUE}Testing /analysis OPTIONS:${NC}"
ANALYSIS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS \
    https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/analysis)

if [ "$ANALYSIS_RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓ /analysis returns 200 OK${NC}"
    curl -i -X OPTIONS https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/analysis 2>&1 | grep -i "access-control"
else
    echo -e "${RED}✗ /analysis returns $ANALYSIS_RESPONSE (expected 200)${NC}"
fi
echo ""

# Summary
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Fix Complete${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

if [ "$PREDICTIONS_RESPONSE" = "200" ] && [ "$ANALYSIS_RESPONSE" = "200" ]; then
    echo -e "${GREEN}✅ CORS configuration fixed successfully!${NC}"
    echo ""
    echo -e "${YELLOW}CORS Headers Configured:${NC}"
    echo "  • Access-Control-Allow-Origin: *"
    echo "  • Access-Control-Allow-Methods: GET,POST,OPTIONS"
    echo "  • Access-Control-Allow-Headers: Content-Type,X-Api-Key"
    echo ""
    echo -e "${YELLOW}Test from browser console:${NC}"
    echo "  fetch('https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/predictions?country=England&league=Premier%20League', {"
    echo "    headers: { 'X-Api-Key': 'YOUR_API_KEY' }"
    echo "  })"
    echo "  .then(r => r.json())"
    echo "  .then(console.log)"
    echo ""
    exit 0
else
    echo -e "${RED}⚠️  CORS fix applied but verification failed${NC}"
    echo "Please check the API Gateway configuration manually"
    echo ""
    exit 1
fi