# GenAI Pundit v2.0 - Deployment Guide

**Version:** 2.0 | **Status:** Production Ready | **Date:** October 11, 2025

---

## Overview

This guide provides step-by-step instructions for deploying GenAI Pundit v2.0 to AWS, including Lambda function deployment, API Gateway configuration, and API key management.

---

## Prerequisites

### Required AWS Resources

1. **IAM Role** for Lambda with permissions:
   - DynamoDB read/write
   - CloudWatch Logs
   - Lambda execution

2. **Lambda Layers** (already exist):
   - `scipy-layer:4` - ARN: `arn:aws:lambda:eu-west-2:985019772236:layer:scipy-layer:4`
   - `llm-layer:1` - ARN: `arn:aws:lambda:eu-west-2:985019772236:layer:llm-layer:1`

3. **DynamoDB Tables** (already exist):
   - `game_fixtures` - Fixture and prediction data
   - `team_parameters` - Team Phase 0-6 parameters
   - `league_parameters` - League conformance data
   - `game_analysis` - AI-generated analysis (will be created if needed)

### Required API Keys

You need to obtain API keys for:

1. **Google Gemini API**
   - Get from: https://aistudio.google.com/app/apikey
   - Create a new project or use existing
   - Enable Gemini API
   - Generate API key

2. **Anthropic Claude API**
   - Get from: https://console.anthropic.com/
   - Sign up or log in
   - Navigate to API Keys
   - Generate new API key

3. **OpenWeather API** (for weather forecasts)
   - Get from: https://openweathermap.org/api
   - Sign up for a free account
   - Navigate to API Keys
   - Generate API key (free tier includes 1,000 calls/day)
   - OneCall API 3.0 is used for hourly weather forecasts

4. **RapidAPI Key** (for team standings)
   - Get from: https://rapidapi.com/
   - Subscribe to API-Football (already used in the system)
   - Use existing RAPIDAPI_KEY from other handlers

5. **Mobile API Key** (for frontend authentication)
   - This is your existing mobile app API key
   - Used for authenticating requests from mobile/web apps

---

## Deployment Steps

### Step 1: Configure API Keys Locally

For local testing and development, create a `.env` file:

```bash
# Create .env file (never commit this!)
cat > .env << 'EOF'
# GenAI Pundit Configuration
ACTIVE_AI_PROVIDER=gemini

# AI Provider API Keys
GEMINI_API_KEY=your_gemini_api_key_here
ANTHROPIC_API_KEY=your_claude_api_key_here

# Weather and Standings API Keys
OPENWEATHER_KEY=your_openweather_api_key_here
RAPIDAPI_KEY=your_rapidapi_key_here

# Mobile/Web Authentication
VALID_MOBILE_API_KEY=your_existing_mobile_api_key

# DynamoDB Tables
GAME_FIXTURES_TABLE=game_fixtures
TEAM_PARAMETERS_TABLE=team_parameters
LEAGUE_PARAMETERS_TABLE=league_parameters
GAME_ANALYSIS_TABLE=game_analysis

# AWS Configuration
AWS_REGION=eu-west-2
ENVIRONMENT=prod
EOF

# Secure the file
chmod 600 .env
```

### Step 2: Build Deployment Package

```bash
# Build lightweight Lambda package (excludes dependencies in layers)
./scripts/build_lambda_package_lightweight.sh
```

This creates:
- `lambda_deployment/football_prediction_system_light.zip`
- Package size: ~5-10 MB (lightweight because dependencies are in layers)

### Step 3: Deploy Lambda Function

```bash
# Deploy all Lambda functions including GenAI Pundit (9 functions total)
./scripts/deploy_lambda_with_layer.sh prod
```

This automatically:
- ✅ Deploys GenAI Pundit as function #9 (Python 3.11)
- ✅ Attaches both `scipy-layer:4` and `llm-layer:1`
- ✅ Deploys 8 other functions (Python 3.13)
- ✅ Sets up basic environment variables
- ✅ Configures timeout (60s) and memory (512MB)

**Important**: The initial deployment sets placeholder environment variables. You need to update them with actual API keys in Step 4.

### Step 4: Configure Lambda Environment Variables

After deployment, update the Lambda function with your actual API keys:

```bash
# Set environment variables for production
aws lambda update-function-configuration \
    --function-name football-genai-pundit-prod \
    --environment Variables="{
        ENVIRONMENT=prod,
        ACTIVE_AI_PROVIDER=gemini,
        GAME_FIXTURES_TABLE=game_fixtures,
        TEAM_PARAMETERS_TABLE=team_parameters,
        LEAGUE_PARAMETERS_TABLE=league_parameters,
        GAME_ANALYSIS_TABLE=game_analysis,
        GEMINI_API_KEY=YOUR_ACTUAL_GEMINI_KEY,
        ANTHROPIC_API_KEY=YOUR_ACTUAL_CLAUDE_KEY,
        OPENWEATHER_KEY=YOUR_ACTUAL_OPENWEATHER_KEY,
        RAPIDAPI_KEY=YOUR_ACTUAL_RAPIDAPI_KEY,
        VALID_MOBILE_API_KEY=YOUR_ACTUAL_MOBILE_KEY
    }" \
    --region eu-west-2
```

**Security Note**: Never commit API keys to Git. Always set them directly in Lambda or use AWS Secrets Manager.

**Note**: The `RAPIDAPI_KEY` should be the same key used by other handlers (fixture ingestion, match data, etc.) that access the API-Football service.

### Step 5: Test Lambda Function Directly

Before setting up API Gateway, test the Lambda function directly:

```bash
# Test direct Lambda invocation
aws lambda invoke \
    --function-name football-genai-pundit-prod \
    --payload '{"fixture_id": 1035046}' \
    --region eu-west-2 \
    response.json

# Check response
cat response.json
```

Expected responses:
- **First call**: `{"message": "Analysis generation started..."}`
- **After 10-15 seconds**: Analysis will be in `game_analysis` DynamoDB table

### Step 6: Create game_analysis Table (if needed)

If the table doesn't exist, create it:

```bash
aws dynamodb create-table \
    --table-name game_analysis \
    --attribute-definitions \
        AttributeName=fixture_id,AttributeType=N \
        AttributeName=timestamp,AttributeType=N \
    --key-schema \
        AttributeName=fixture_id,KeyType=HASH \
        AttributeName=timestamp,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region eu-west-2
```

### Step 7: Deploy API Gateway (Optional)

If you want external API access (for mobile/web apps):

```bash
# Get Lambda function ARN
LAMBDA_ARN=$(aws lambda get-function \
    --function-name football-genai-pundit-prod \
    --query 'Configuration.FunctionArn' \
    --output text \
    --region eu-west-2)

# Deploy API Gateway
./scripts/deploy_api_service.sh prod $LAMBDA_ARN
```

This creates:
- API Gateway REST API
- `/analysis` endpoint (POST method)
- Usage plan with rate limiting
- API key for authentication
- CORS configuration

**Output**: Configuration saved to `api_gateway_config_prod.json`

---

## API Gateway Configuration Details

### Endpoint Structure

```
POST https://{api-id}.execute-api.eu-west-2.amazonaws.com/prod/analysis
```

### Request Format

```bash
curl -X POST \
  https://your-api-id.execute-api.eu-west-2.amazonaws.com/prod/analysis \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-api-gateway-key" \
  -d '{"fixture_id": 1035046}'
```

### Response Format

**First Request (202 Accepted)**:
```json
{
  "message": "Analysis generation started. Please retry in a few moments.",
  "fixture_id": 1035046,
  "status": "IN_PROGRESS"
}
```

**Subsequent Request (200 OK)**:
```json
{
  "fixture_id": 1035046,
  "timestamp": 1728662400,
  "analysis": "...(AI-generated match analysis)...",
  "provider": "gemini",
  "generated_at": 1728662415,
  "status": "COMPLETED"
}
```

### CORS Configuration

The API Gateway is configured with CORS to allow requests from:
- `https://footystats.abv.ng`
- `https://chacha-online.abv.ng`
- `http://10.197.182.36:3000` (local development)

To add more origins, update the `ALLOWED_ORIGINS` list in [`src/handlers/genai_pundit_handler.py`](../../src/handlers/genai_pundit_handler.py).

---

## Switching AI Providers

### Switch from Gemini to Claude

```bash
aws lambda update-function-configuration \
    --function-name football-genai-pundit-prod \
    --environment Variables="{
        ACTIVE_AI_PROVIDER=claude,
        ...(other environment variables unchanged)...
    }" \
    --region eu-west-2
```

### Switch from Claude to Gemini

```bash
aws lambda update-function-configuration \
    --function-name football-genai-pundit-prod \
    --environment Variables="{
        ACTIVE_AI_PROVIDER=gemini,
        ...(other environment variables unchanged)...
    }" \
    --region eu-west-2
```

**Note**: There is no automatic failover. If the active provider fails, the request will fail. Manual switching is required.

---

## Monitoring and Troubleshooting

### View Lambda Logs

```bash
# Get recent logs
aws logs tail /aws/lambda/football-genai-pundit-prod --follow --region eu-west-2
```

### Check DynamoDB Items

```bash
# Check if analysis was created
aws dynamodb query \
    --table-name game_analysis \
    --key-condition-expression "fixture_id = :fid" \
    --expression-attribute-values '{":fid": {"N": "1035046"}}' \
    --region eu-west-2
```

### Common Issues

#### 1. "Missing API Key" Error

**Cause**: Environment variables not set
**Solution**: Run Step 4 to configure environment variables

#### 2. "Analysis Generation Failed"

**Cause**: Invalid AI provider API key
**Solution**: Verify your GEMINI_API_KEY or ANTHROPIC_API_KEY is correct

#### 3. "403 Forbidden" from API Gateway

**Cause**: Invalid API key or origin not allowed
**Solution**: Check API key and CORS configuration

#### 4. "Timeout" Error

**Cause**: Lambda timeout (60s) exceeded
**Solution**: AI generation usually takes 15-30s. If timing out, check AI provider service status

---

## Cost Considerations

### Lambda Costs
- **Invocations**: $0.20 per 1M requests
- **Duration**: $0.0000166667 per GB-second
- **Estimate**: ~$0.001 per analysis generation

### AI Provider Costs

**Google Gemini (gemini-2.5-pro)**:
- Input: ~$1.25 per 1M tokens
- Output: ~$5.00 per 1M tokens
- **Estimate**: ~$0.02-0.05 per analysis (depending on length)

**Anthropic Claude (claude-4.5-sonnet)**:
- Input: ~$3.00 per 1M tokens
- Output: ~$15.00 per 1M tokens
- **Estimate**: ~$0.05-0.10 per analysis (depending on length)

### DynamoDB Costs
- **On-demand**: $1.25 per million write requests
- **Estimate**: Negligible for most use cases

**Total Cost Estimate**: $0.02-0.15 per match analysis

---

## Security Best Practices

### 1. Never Commit API Keys
- ✅ Use `.env` files locally (protected by `.gitignore`)
- ✅ Use Lambda environment variables in production
- ❌ Never hardcode keys in source code
- ❌ Never commit `.env` files to Git

### 2. Rotate API Keys Regularly
- Rotate Gemini and Claude API keys every 90 days
- Update Lambda environment variables after rotation

### 3. Monitor API Usage
- Set up CloudWatch alarms for:
  - Lambda errors
  - High invocation counts
  - Long execution times
- Monitor AI provider usage dashboards

### 4. Use API Key Authentication
- API Gateway requires `x-api-key` header
- Rotate API Gateway keys periodically
- Use separate keys for dev/prod environments

---

## Maintenance Tasks

### Weekly
- Check CloudWatch logs for errors
- Monitor AI provider costs
- Review DynamoDB usage

### Monthly
- Review and update CORS origins if needed
- Check for Lambda timeout issues
- Verify AI provider API key validity

### Quarterly
- Rotate AI provider API keys
- Review and optimize Lambda memory/timeout settings
- Update AI provider models if newer versions available

---

## Rollback Procedure

If issues arise after deployment:

```bash
# 1. Disable the function by updating environment variable
aws lambda update-function-configuration \
    --function-name football-genai-pundit-prod \
    --environment Variables="{ENVIRONMENT=maintenance}" \
    --region eu-west-2

# 2. Investigate logs
aws logs tail /aws/lambda/football-genai-pundit-prod --region eu-west-2

# 3. Redeploy previous version if needed
aws lambda update-function-code \
    --function-name football-genai-pundit-prod \
    --s3-bucket your-lambda-bucket \
    --s3-key previous-version.zip \
    --region eu-west-2
```

---

## Support and Resources

### Documentation
- [Implementation Guide](./GENAI_PUNDIT_V2_IMPLEMENTATION_GUIDE.md)
- [API Documentation](./API_DOCUMENTATION.md)
- [System Architecture](../architecture/NEW_SYSTEM_ARCHITECTURE.md)

### AI Provider Documentation
- [Google Gemini API](https://ai.google.dev/docs)
- [Anthropic Claude API](https://docs.anthropic.com/)

### AWS Documentation
- [Lambda Developer Guide](https://docs.aws.amazon.com/lambda/)
- [API Gateway Developer Guide](https://docs.aws.amazon.com/apigateway/)
- [DynamoDB Developer Guide](https://docs.aws.amazon.com/dynamodb/)

---

## Summary Checklist

- [ ] Obtain Gemini API key
- [ ] Obtain Claude API key
- [ ] Obtain OpenWeather API key
- [ ] Verify RapidAPI key (should already exist)
- [ ] Build lightweight Lambda package
- [ ] Deploy Lambda function
- [ ] Configure environment variables with all API keys
- [ ] Test Lambda function directly
- [ ] Create game_analysis table (if needed)
- [ ] Deploy API Gateway (optional)
- [ ] Test API Gateway endpoint
- [ ] Verify weather and standings data is being fetched
- [ ] Set up monitoring and alarms
- [ ] Document API endpoint for frontend teams

---

**Last Updated**: October 11, 2025  
**Maintainer**: Development Team  
**Status**: Production Ready