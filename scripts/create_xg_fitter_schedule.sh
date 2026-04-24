#!/bin/bash

###############################################################################
# Create the EventBridge rule that invokes the V2 xG parameter fitter
# once a week on Wednesday at 05:00 UTC.
#
# Timing rationale:
#   02:00 UTC  V1 league params refit (existing, weekly Wed)
#   03:00 UTC  V1 team params refit   (existing, weekly Wed)
#   04:00 UTC  Daily match-results ingestion; on Wednesdays this writes
#              Tuesday's new rows into football_match_statistics_prod
#   05:00 UTC  V2 xG params refit (this rule) — runs AFTER daily
#              match-results is reliably done so the weekly fit always
#              includes through Tuesday's fixtures
#
# Usage: ./scripts/create_xg_fitter_schedule.sh [ENVIRONMENT]
#        ENVIRONMENT defaults to "prod"
###############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ENVIRONMENT="${1:-prod}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-985019772236}"
AWS_REGION="${AWS_REGION:-eu-west-2}"

FUNCTION_NAME="football-xg-parameter-fitter-${ENVIRONMENT}"
RULE_NAME="football-xg-parameter-weekly-${ENVIRONMENT}"
SCHEDULE="cron(0 5 ? * WED *)"   # Every Wednesday at 05:00 UTC
DESCRIPTION="Weekly refresh of V2 xG-based team and league parameters"

FUNCTION_ARN="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${FUNCTION_NAME}"
RULE_ARN="arn:aws:events:${AWS_REGION}:${AWS_ACCOUNT_ID}:rule/${RULE_NAME}"

echo -e "${GREEN}Rule:${NC}     ${RULE_NAME}"
echo -e "${GREEN}Schedule:${NC} ${SCHEDULE}"
echo -e "${GREEN}Target:${NC}   ${FUNCTION_ARN}"
echo ""

# 1. Create or update the rule.
aws events put-rule \
    --name "${RULE_NAME}" \
    --schedule-expression "${SCHEDULE}" \
    --description "${DESCRIPTION}" \
    --state ENABLED \
    --region "${AWS_REGION}" >/dev/null
echo -e "${GREEN}✅ Rule created/updated${NC}"

# 2. Wire the lambda as a target.
aws events put-targets \
    --rule "${RULE_NAME}" \
    --targets "Id=1,Arn=${FUNCTION_ARN}" \
    --region "${AWS_REGION}" >/dev/null
echo -e "${GREEN}✅ Target attached${NC}"

# 3. Allow EventBridge to invoke the lambda (idempotent; silently pass if
# the permission already exists).
if aws lambda add-permission \
    --function-name "${FUNCTION_NAME}" \
    --statement-id "AllowEventBridgeWeekly-${ENVIRONMENT}" \
    --action "lambda:InvokeFunction" \
    --principal "events.amazonaws.com" \
    --source-arn "${RULE_ARN}" \
    --region "${AWS_REGION}" \
    2>/dev/null; then
    echo -e "${GREEN}✅ Invoke permission added${NC}"
else
    echo -e "${YELLOW}(permission already exists, skipping)${NC}"
fi

echo ""
echo -e "${GREEN}Done.${NC} The xG fitter will run every Wednesday at 05:00 UTC."
echo "Next scheduled invocation:"
aws events list-targets-by-rule --rule "${RULE_NAME}" --region "${AWS_REGION}" --query 'Targets[].Arn' --output text
