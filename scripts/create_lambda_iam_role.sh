#!/bin/bash

###############################################################################
# Lambda IAM Role Creator
#
# This script creates the IAM role and policies for Lambda functions
#
# Usage:
#   ./scripts/create_lambda_iam_role.sh
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

AWS_ACCOUNT_ID="985019772236"
AWS_REGION="eu-west-2"
ROLE_NAME="FootballPredictionLambdaRole"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Creating Lambda IAM Role${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}AWS Account:${NC} $AWS_ACCOUNT_ID"
echo -e "${GREEN}Region:${NC} $AWS_REGION"
echo -e "${GREEN}Role Name:${NC} $ROLE_NAME"
echo ""

# Check if role already exists
echo -e "${YELLOW}Checking if role already exists...${NC}"
if aws iam get-role --role-name "$ROLE_NAME" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Role already exists: $ROLE_NAME${NC}"
    echo ""
    read -p "$(echo -e ${YELLOW}Update existing role? [y/N]: ${NC})" -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Operation cancelled${NC}"
        exit 1
    fi
    UPDATE_MODE=true
else
    UPDATE_MODE=false
fi

# Create trust policy
echo -e "${YELLOW}[1/3] Creating trust policy...${NC}"
cat > /tmp/lambda_trust_policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
echo -e "${GREEN}✅ Trust policy created${NC}"
echo ""

# Create execution policy
echo -e "${YELLOW}[2/3] Creating execution policy...${NC}"
cat > /tmp/lambda_execution_policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:BatchWriteItem",
        "dynamodb:BatchGetItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/football_*"
      ]
    },
    {
      "Sid": "SQSAccess",
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl"
      ],
      "Resource": [
        "arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:football_*"
      ]
    },
    {
      "Sid": "CloudWatchLogsAccess",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${AWS_REGION}:${AWS_ACCOUNT_ID}:log-group:/aws/lambda/*"
    }
  ]
}
EOF
echo -e "${GREEN}✅ Execution policy created${NC}"
echo ""

# Create or update role
echo -e "${YELLOW}[3/3] Creating IAM role...${NC}"
if [ "$UPDATE_MODE" = false ]; then
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///tmp/lambda_trust_policy.json \
        --description "Execution role for Football Prediction Lambda functions" \
        --region "$AWS_REGION"
    echo -e "${GREEN}✅ IAM role created${NC}"
else
    echo -e "${YELLOW}  Updating existing role...${NC}"
    aws iam update-assume-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-document file:///tmp/lambda_trust_policy.json \
        --region "$AWS_REGION"
    echo -e "${GREEN}✅ IAM role updated${NC}"
fi
echo ""

# Attach inline policy
echo -e "${YELLOW}Attaching execution policy...${NC}"
aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name "FootballPredictionExecutionPolicy" \
    --policy-document file:///tmp/lambda_execution_policy.json \
    --region "$AWS_REGION"
echo -e "${GREEN}✅ Execution policy attached${NC}"
echo ""

# Cleanup temporary files
rm -f /tmp/lambda_trust_policy.json
rm -f /tmp/lambda_execution_policy.json

# Wait for role to be available
echo -e "${YELLOW}Waiting for role to be available (10 seconds)...${NC}"
sleep 10
echo -e "${GREEN}✅ Role ready${NC}"
echo ""

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   IAM Role Created!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${GREEN}✅ IAM role setup complete${NC}"
echo ""
echo -e "${YELLOW}Role Details:${NC}"
echo "  Name: $ROLE_NAME"
echo "  ARN:  arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"
echo ""
echo -e "${YELLOW}Permissions:${NC}"
echo "  ✅ DynamoDB: Read/Write access to football_* tables"
echo "  ✅ SQS: Send/Receive/Delete messages in football_* queues"
echo "  ✅ CloudWatch Logs: Create log groups and streams"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Build Lambda deployment package:"
echo "     ./scripts/build_lambda_package.sh"
echo ""
echo "  2. Deploy Lambda functions:"
echo "     ./scripts/deploy_lambda_functions.sh prod"
echo ""

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"