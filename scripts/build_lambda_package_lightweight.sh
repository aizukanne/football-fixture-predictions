#!/bin/bash

###############################################################################
# Lightweight Lambda Package Builder
#
# This script creates a deployment package WITHOUT heavy dependencies
# Heavy dependencies (numpy, pandas, scipy, scikit-learn) are in Lambda Layer
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Building Lightweight Lambda Deployment Package${NC}"
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

# Create lightweight requirements (without heavy dependencies)
echo -e "${YELLOW}[3/6] Creating lightweight requirements...${NC}"
cat > requirements_light.txt << 'EOF'
# Lightweight dependencies only
# Heavy dependencies (numpy, pandas, scipy, scikit-learn) are in Lambda Layer

# AWS Services
boto3>=1.20.0,<2.0.0
botocore>=1.23.0,<2.0.0

# API & HTTP
requests>=2.26.0,<3.0.0

# Date & Time
python-dateutil>=2.8.2,<3.0.0

# Utilities
typing-extensions>=4.0.0
EOF
echo -e "${GREEN}✅ Lightweight requirements created${NC}"
echo ""

# Install lightweight dependencies
echo -e "${YELLOW}[4/6] Installing lightweight dependencies...${NC}"
pip3 install -r requirements_light.txt -t . --quiet
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
zip -r football_prediction_system_light.zip . -q
PACKAGE_SIZE=$(du -h football_prediction_system_light.zip | cut -f1)
echo -e "${GREEN}✅ Package created: football_prediction_system_light.zip (${PACKAGE_SIZE})${NC}"
echo ""

cd ..

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Build Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${GREEN}✅ Lightweight deployment package ready${NC}"
echo ""
echo -e "${YELLOW}Package Location:${NC}"
echo "  lambda_deployment/football_prediction_system_light.zip"
echo ""
echo -e "${YELLOW}Package Size:${NC} ${PACKAGE_SIZE}"
echo ""
echo -e "${YELLOW}Lambda Layer:${NC}"
echo "  ARN: arn:aws:lambda:eu-west-2:985019772236:layer:scipy-layer:4"
echo "  Contains: numpy, pandas, scipy, scikit-learn"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  Deploy Lambda functions with layer:"
echo "  ./scripts/deploy_lambda_with_layer.sh prod"
echo ""

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"