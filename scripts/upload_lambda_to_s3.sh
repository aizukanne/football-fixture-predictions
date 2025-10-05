#!/bin/bash

###############################################################################
# Upload Lambda Package to S3
#
# This script uploads the Lambda deployment package to S3
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

# Configuration
BUCKET_NAME="football-prediction-lambda-deployment"
PACKAGE_FILE="lambda_deployment/football_prediction_system.zip"
S3_KEY="lambda-packages/football_prediction_system_$(date +%Y%m%d_%H%M%S).zip"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Uploading Lambda Package to S3${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Check if package exists
if [ ! -f "$PACKAGE_FILE" ]; then
    echo -e "${RED}❌ Package not found: $PACKAGE_FILE${NC}"
    echo ""
    echo "Please build the package first:"
    echo "  ./scripts/build_lambda_package.sh"
    exit 1
fi

# Create S3 bucket if it doesn't exist
echo -e "${YELLOW}Checking S3 bucket...${NC}"
if ! aws s3 ls "s3://${BUCKET_NAME}" 2>/dev/null; then
    echo -e "${YELLOW}Creating S3 bucket: ${BUCKET_NAME}${NC}"
    aws s3 mb "s3://${BUCKET_NAME}" --region eu-west-2
    
    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "${BUCKET_NAME}" \
        --versioning-configuration Status=Enabled \
        --region eu-west-2
    
    echo -e "${GREEN}✅ Bucket created${NC}"
else
    echo -e "${GREEN}✅ Bucket exists${NC}"
fi
echo ""

# Upload package
echo -e "${YELLOW}Uploading package to S3...${NC}"
aws s3 cp "$PACKAGE_FILE" "s3://${BUCKET_NAME}/${S3_KEY}" --region eu-west-2

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Package uploaded successfully${NC}"
    echo ""
    
    # Output S3 details
    echo -e "${GREEN}S3 Location:${NC}"
    echo "  Bucket: ${BUCKET_NAME}"
    echo "  Key: ${S3_KEY}"
    echo "  URL: s3://${BUCKET_NAME}/${S3_KEY}"
    echo ""
    
    # Export for use by other scripts
    echo "export LAMBDA_S3_BUCKET=${BUCKET_NAME}" > /tmp/lambda_s3_location.sh
    echo "export LAMBDA_S3_KEY=${S3_KEY}" >> /tmp/lambda_s3_location.sh
    
    echo -e "${GREEN}✅ Environment variables exported to: /tmp/lambda_s3_location.sh${NC}"
    echo ""
    echo -e "${YELLOW}Next Step:${NC}"
    echo "  Deploy Lambda functions using S3:"
    echo "  ./scripts/deploy_lambda_from_s3.sh prod"
else
    echo -e "${RED}❌ Upload failed${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"