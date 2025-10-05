#!/bin/bash
# Setup deployment environment variables for this project only
# Source: .env file in project root

# Load environment variables from .env file
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
    echo "✅ Environment variables loaded"
    echo ""
    echo "Configuration:"
    echo "  AWS_DEFAULT_REGION: ${AWS_DEFAULT_REGION}"
    echo "  ENVIRONMENT: ${ENVIRONMENT}"
    echo "  TABLE_PREFIX: ${TABLE_PREFIX}"
    echo "  TABLE_SUFFIX: ${TABLE_SUFFIX}"
    echo ""
    echo "Region set to eu-west-2 (Europe London) for this project"
else
    echo "❌ Error: .env file not found"
    exit 1
fi