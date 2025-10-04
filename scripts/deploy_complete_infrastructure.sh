#!/bin/bash

###############################################################################
# Complete Football Prediction System Infrastructure Deployment
#
# This script deploys the complete, independent infrastructure including:
# - DynamoDB tables (with environment-based naming)
# - SQS queues (all 5 queues + DLQs)
# - Configuration updates
#
# Usage:
#   ./scripts/deploy_complete_infrastructure.sh [environment]
#
# Examples:
#   ./scripts/deploy_complete_infrastructure.sh dev
#   ./scripts/deploy_complete_infrastructure.sh prod
#
# Environment Variables (optional):
#   TABLE_PREFIX - Prefix for table names (e.g., "myapp_")
#   TABLE_SUFFIX - Suffix for table names (e.g., "_prod")
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

# Default values
ENVIRONMENT=${1:-${ENVIRONMENT:-dev}}
AWS_REGION=${AWS_REGION:-eu-west-2}

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Football Prediction System - Complete Infrastructure Deployment${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Environment:${NC} $ENVIRONMENT"
echo -e "${GREEN}AWS Region:${NC} $AWS_REGION"
echo -e "${GREEN}Table Prefix:${NC} ${TABLE_PREFIX:-<none>}"
echo -e "${GREEN}Table Suffix:${NC} ${TABLE_SUFFIX:-<none>}"
echo ""

# Confirm deployment
read -p "$(echo -e ${YELLOW}Do you want to proceed with deployment? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo -e "${RED}Deployment cancelled${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Step 1: Deploying DynamoDB Tables${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Deploy DynamoDB tables
echo -e "${GREEN}Creating DynamoDB tables...${NC}"
python3 -m src.infrastructure.deploy_tables --no-interactive

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to create DynamoDB tables${NC}"
    exit 1
fi

echo -e "${GREEN}✅ DynamoDB tables created successfully${NC}"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Step 2: Creating SQS Queues${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Create SQS queues
echo -e "${GREEN}Creating SQS queues...${NC}"
python3 -m src.infrastructure.create_all_sqs_queues \
    --environment "$ENVIRONMENT" \
    --region "$AWS_REGION" \
    --export "queue_config_${ENVIRONMENT}.json" \
    --update-constants

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to create SQS queues${NC}"
    exit 1
fi

echo -e "${GREEN}✅ SQS queues created successfully${NC}"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Step 3: Verifying Infrastructure${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Verify table deployment
echo -e "${GREEN}Verifying DynamoDB tables...${NC}"
python3 -m src.infrastructure.deploy_tables --verify-only

# List created queues
echo ""
echo -e "${GREEN}Verifying SQS queues...${NC}"
aws sqs list-queues --region "$AWS_REGION" --queue-name-prefix "football-" 2>/dev/null || echo "Note: AWS CLI needed for queue verification"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Deployment Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${GREEN}✅ Infrastructure deployment completed successfully${NC}"
echo ""
echo -e "${YELLOW}Created Resources:${NC}"
echo "  📊 DynamoDB Tables:"
echo "     - game_fixtures"
echo "     - league_parameters"
echo "     - team_parameters"
echo "     - venue_cache"
echo "     - tactical_cache"
echo "     - league_standings_cache"
echo ""
echo "  📨 SQS Queues (+ DLQs):"
echo "     - football-fixture-predictions"
echo "     - football-league-parameter-updates"
echo "     - football-team-parameter-updates"
echo "     - football-cache-updates"
echo "     - football-match-results"
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Deploy Lambda functions:"
echo "     - Fixture Ingestion Handler"
echo "     - Prediction Handler"
echo "     - League Parameter Handler"
echo "     - Team Parameter Handler"
echo ""
echo "  2. Configure EventBridge rules:"
echo "     - Daily fixture ingestion (06:00 UTC)"
echo "     - Weekly parameter updates"
echo "     - Daily cache refresh"
echo ""
echo "  3. Set up IAM permissions:"
echo "     - Lambda execution roles"
echo "     - SQS access policies"
echo "     - DynamoDB access policies"
echo ""
echo "  4. Test the system:"
echo "     - Manual Lambda invocations"
echo "     - End-to-end workflow"
echo "     - Error handling"
echo ""

echo -e "${GREEN}Configuration files:${NC}"
echo "  - queue_config_${ENVIRONMENT}.json (Queue URLs and ARNs)"
echo "  - src/utils/constants.py (Updated with queue URL)"
echo ""

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
