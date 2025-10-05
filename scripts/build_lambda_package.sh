#!/bin/bash

###############################################################################
# Lambda Package Builder
#
# This script creates a deployment package for Lambda functions
#
# Usage:
#   ./scripts/build_lambda_package.sh
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Building Lambda Deployment Package${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Create deployment directory
echo -e "${YELLOW}[1/6] Creating deployment directory...${NC}"
rm -rf lambda_deployment
mkdir -p lambda_deployment
cd lambda_deployment
echo -e "${GREEN}✅ Deployment directory created${NC}"
echo ""

# Copy source code
echo -e "${YELLOW}[2/6] Copying source code...${NC}"
cp -r ../src .
echo -e "${GREEN}✅ Source code copied${NC}"
echo ""

# Copy requirements
echo -e "${YELLOW}[3/6] Copying requirements...${NC}"
cp ../requirements.txt .
echo -e "${GREEN}✅ Requirements copied${NC}"
echo ""

# Install dependencies
echo -e "${YELLOW}[4/6] Installing dependencies (this may take a few minutes)...${NC}"
pip3 install -r requirements.txt -t . --quiet
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Clean up unnecessary files
echo -e "${YELLOW}[5/6] Cleaning up unnecessary files...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
echo -e "${GREEN}✅ Cleanup complete${NC}"
echo ""

# Create ZIP package
echo -e "${YELLOW}[6/6] Creating deployment package...${NC}"
zip -r football_prediction_system.zip . -q
PACKAGE_SIZE=$(du -h football_prediction_system.zip | cut -f1)
echo -e "${GREEN}✅ Package created: football_prediction_system.zip (${PACKAGE_SIZE})${NC}"
echo ""

cd ..

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Build Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${GREEN}✅ Deployment package ready${NC}"
echo ""
echo -e "${YELLOW}Package Location:${NC}"
echo "  lambda_deployment/football_prediction_system.zip"
echo ""
echo -e "${YELLOW}Package Size:${NC} ${PACKAGE_SIZE}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Create IAM role:"
echo "     ./scripts/create_lambda_iam_role.sh"
echo ""
echo "  2. Deploy Lambda functions:"
echo "     ./scripts/deploy_lambda_functions.sh prod"
echo ""

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"