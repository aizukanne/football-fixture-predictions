#!/bin/bash

###############################################################################
# Quick Lambda Code Update Script
# Updates the genai-pundit Lambda function code without full rebuild
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

ENVIRONMENT=${1:-prod}
FUNCTION_NAME="football-genai-pundit-${ENVIRONMENT}"
REGION="eu-west-2"

echo -e "${BLUE}Updating Lambda function: ${FUNCTION_NAME}${NC}"

# Create temporary deployment package
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Copy source files
cp -r /home/ubuntu/Projects/football-fixture-predictions/src .

# Create deployment package
zip -r function.zip src/ > /dev/null

echo -e "${GREEN}Updating Lambda function code...${NC}"
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://function.zip \
    --region "$REGION" \
    --no-cli-pager

echo -e "${GREEN}✓ Lambda function updated successfully${NC}"

# Cleanup
cd - > /dev/null
rm -rf "$TEMP_DIR"

echo -e "${BLUE}Function: $FUNCTION_NAME${NC}"
echo -e "${BLUE}Region: $REGION${NC}"