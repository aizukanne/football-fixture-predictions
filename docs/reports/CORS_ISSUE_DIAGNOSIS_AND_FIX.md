# CORS Configuration Issue - Root Cause Analysis and Fix

## Date: 2025-10-16

## Problem Statement
The `/predictions` endpoint returns 500 errors on OPTIONS (preflight) requests from web browsers, blocking CORS access. The `/analysis` endpoint has the same requirement. The API works correctly from mobile apps which don't send preflight requests.

## Root Cause Analysis

### Investigation Process
1. Examined deployment scripts for CORS configuration
2. Queried actual AWS API Gateway configuration
3. Tested endpoints with curl to verify behavior

### Verified Configuration State

#### `/predictions` Endpoint (Resource ID: xooseg)
```json
{
  "httpMethod": "OPTIONS",
  "authorizationType": "NONE",
  "methodResponses": {
    "200": {
      "statusCode": "200",
      "responseParameters": {
        "method.response.header.Access-Control-Allow-Headers": true,
        "method.response.header.Access-Control-Allow-Methods": true,
        "method.response.header.Access-Control-Allow-Origin": true
      }
    }
  },
  "methodIntegration": {
    "type": "MOCK",
    "requestTemplates": {
      "application/json": "{\"statusCode\": 200}"
    }
    // ❌ MISSING: integrationResponses section
  }
}
```

**Test Result:**
```bash
$ curl -i -X OPTIONS https://esqyjhhc4e.execute-api.eu-west-2.amazonaws.com/prod/predictions
HTTP/2 500
{"message": "Internal server error"}
```

#### `/analysis` Endpoint (Resource ID: lhmoik) 
```json
{
  "httpMethod": "OPTIONS",
  "authorizationType": "NONE",
  "methodResponses": {
    "200": {
      "statusCode": "200",
      "responseParameters": {
        "method.response.header.Access-Control-Allow-Headers": false,
        "method.response.header.Access-Control-Allow-Methods": false,
        "method.response.header.Access-Control-Allow-Origin": false
      }
    }
  },
  "methodIntegration": {
    "type": "MOCK",
    "requestTemplates": {
      "application/json": "{\"statusCode\": 200}"
    },
    // ✅ PRESENT: integrationResponses section
    "integrationResponses": {
      "200": {
        "statusCode": "200",
        "responseParameters": {
          "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,x-api-key'",
          "method.response.header.Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
          "method.response.header.Access-Control-Allow-Origin": "'*'"
        }
      }
    }
  }
}
```

**Test Result:**
```bash
$ curl -i -X OPTIONS https://esqyjhhc4e.execute-api.eu-west-2.amazonaws.com/prod/analysis
HTTP/2 200
access-control-allow-origin: *
access-control-allow-headers: Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,x-api-key
access-control-allow-methods: GET,POST,PUT,DELETE,OPTIONS
```

## Root Cause

**The `/predictions` OPTIONS method is missing the `integrationResponses` configuration.**

When API Gateway receives an OPTIONS request:
1. The MOCK integration is invoked
2. The integration returns `{"statusCode": 200}`
3. ❌ API Gateway looks for an integration response mapping - **NONE EXISTS**
4. ❌ Without a mapping, API Gateway returns 500 Internal Server Error

The `/analysis` endpoint works because it has the integration response properly configured.

## Solution

### Fix Requirements
1. Add `integrationResponses` to `/predictions` OPTIONS method
2. Configure CORS headers as specified:
   - `Access-Control-Allow-Origin: *`
   - `Access-Control-Allow-Methods: GET,POST,OPTIONS`
   - `Access-Control-Allow-Headers: Content-Type,X-Api-Key`
3. Update `/analysis` headers to match requirements (currently too permissive)
4. Redeploy API Gateway stage

### Implementation

#### For `/predictions` endpoint:
```bash
aws apigateway put-integration-response \
  --rest-api-id esqyjhhc4e \
  --resource-id xooseg \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters '{
    "method.response.header.Access-Control-Allow-Origin": "'"'"'*'"'"'",
    "method.response.header.Access-Control-Allow-Methods": "'"'"'GET,POST,OPTIONS'"'"'",
    "method.response.header.Access-Control-Allow-Headers": "'"'"'Content-Type,X-Api-Key'"'"'"
  }' \
  --region eu-west-2
```

#### For `/analysis` endpoint (update headers):
```bash
aws apigateway put-integration-response \
  --rest-api-id esqyjhhc4e \
  --resource-id lhmoik \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters '{
    "method.response.header.Access-Control-Allow-Origin": "'"'"'*'"'"'",
    "method.response.header.Access-Control-Allow-Methods": "'"'"'GET,POST,OPTIONS'"'"'",
    "method.response.header.Access-Control-Allow-Headers": "'"'"'Content-Type,X-Api-Key'"'"'"
  }' \
  --region eu-west-2
```

#### Redeploy:
```bash
aws apigateway create-deployment \
  --rest-api-id esqyjhhc4e \
  --stage-name prod \
  --description "Fix CORS configuration for /predictions and /analysis endpoints" \
  --region eu-west-2
```

## Verification Tests

After applying the fix:

```bash
# Test /predictions OPTIONS
curl -i -X OPTIONS https://esqyjhhc4e.execute-api.eu-west-2.amazonaws.com/prod/predictions
# Expected: HTTP/2 200 with CORS headers

# Test /analysis OPTIONS
curl -i -X OPTIONS https://esqyjhhc4e.execute-api.eu-west-2.amazonaws.com/prod/analysis
# Expected: HTTP/2 200 with updated CORS headers

# Test from browser console
fetch('https://esqyjhhc4e.execute-api.eu-west-2.amazonaws.com/prod/predictions?country=England&league=Premier%20League', {
  headers: { 'X-Api-Key': 'YOUR_KEY' }
})
.then(r => r.json())
.then(console.log)
.catch(console.error)
```

## Prevention

### Update Deployment Scripts

#### deploy_api_gateway.py
Lines 184-194 need to ensure integration response is created:
```python
self.apigateway.put_integration_response(
    restApiId=api_id,
    resourceId=predictions_resource_id,
    httpMethod='OPTIONS',
    statusCode='200',
    responseParameters={
        'method.response.header.Access-Control-Allow-Origin': "'*'",
        'method.response.header.Access-Control-Allow-Headers': "'Content-Type,X-Api-Key'",
        'method.response.header.Access-Control-Allow-Methods': "'GET,POST,OPTIONS'"
    }
)
```

#### deploy_genai_pundit_gateway.sh
Lines 176-184 should use the simplified headers:
```bash
aws apigateway put-integration-response \
  --rest-api-id $API_ID \
  --resource-id $ANALYSIS_RESOURCE_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Headers": "'"'"'Content-Type,X-Api-Key'"'"'", "method.response.header.Access-Control-Allow-Methods": "'"'"'GET,POST,OPTIONS'"'"'", "method.response.header.Access-Control-Allow-Origin": "'"'"'*'"'"'"}' \
  --region $AWS_REGION
```

## Impact Assessment
- **Risk**: Low - Only affects CORS preflight responses
- **Downtime**: None - Change is additive
- **Mobile Apps**: No impact - mobile apps don't send OPTIONS
- **Browser Access**: Will enable browser access after fix

## References
- AWS API Gateway: esqyjhhc4e
- Region: eu-west-2
- Stage: prod
- `/predictions` Resource ID: xooseg
- `/analysis` Resource ID: lhmoik