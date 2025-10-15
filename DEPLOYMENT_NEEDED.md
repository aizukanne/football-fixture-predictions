# Deployment Required for Manager Analysis Integration

## Files Modified

### 1. API Client - Improved Rate Limiting
**File:** `src/data/api_client.py`
**Changes:**
- Enhanced 429 (rate limit) handling with exponential backoff
- Added Retry-After header support
- Added jitter to prevent thundering herd
- Better error handling for 5xx errors
- Timeout support

### 2. Manager Analyzer - Better Logging
**File:** `src/features/manager_analyzer.py`
**Changes:**
- Added print statements for coach data retrieval
- Better error logging with stack traces
- Visibility into manager profile fetching process

### 3. Team Calculator - Manager Profile Integration
**File:** `src/parameters/team_calculator.py`
**Changes:**
- Manager profile fields added to tactical_params
- Calls TacticalAnalyzer.get_manager_tactical_profile()
- Stores 9 manager fields with team parameters

### 4. Tactical Analyzer - Import Fix
**File:** `src/features/tactical_analyzer.py`
**Changes:**
- Fixed statistics module import conflict
- Changed from `from statistics import mean` to `import statistics as stats`

### 5. Prediction Handler - Manager Multipliers
**File:** `src/handlers/prediction_handler.py`
**Changes:**
- Imports manager multiplier utilities
- Applies manager adjustments to team parameters before predictions

### 6. Manager Multiplier Utilities - NEW
**File:** `src/utils/manager_multipliers.py`
**Changes:**
- NEW FILE - Manager multiplier calculation logic
- Gets multipliers from team params
- Applies adjustments to mu/p_score parameters

## Lambdas That Need Deployment

1. **football-team-parameter-handler-prod**
   - Needs: api_client.py, manager_analyzer.py, team_calculator.py, tactical_analyzer.py
   - Reason: Calculates and stores team parameters with manager data

2. **football-prediction-handler-prod** (if separate)
   - Needs: prediction_handler.py, manager_multipliers.py
   - Reason: Applies manager multipliers to predictions

## Deployment Commands

### Option 1: Deploy via script
```bash
./scripts/deploy_lambda_with_layer.sh team-parameter-handler
./scripts/deploy_lambda_with_layer.sh prediction-handler
```

### Option 2: Deploy manually
```bash
# Package code
cd /home/ubuntu/Projects/football-fixture-predictions
zip -r lambda_package.zip src/ -x "*.pyc" -x "*__pycache__*"

# Update team parameter handler
aws lambda update-function-code \
  --function-name football-team-parameter-handler-prod \
  --zip-file fileb://lambda_package.zip \
  --region eu-west-2

# Update prediction handler (if separate)
aws lambda update-function-code \
  --function-name football-prediction-handler-prod \
  --zip-file fileb://lambda_package.zip \
  --region eu-west-2
```

## After Deployment

1. **Trigger team parameter recalculation:**
   ```bash
   python3 invoke_team_param_dispatcher.py --test
   ```

2. **Monitor CloudWatch logs:**
   - Look for "Fetching coach data for team..." messages
   - Look for "✅ Coach data retrieved..." success messages
   - Check for any error messages

3. **Verify manager data in DynamoDB:**
   ```bash
   python3 check_manager_data.py
   ```
   - Should show real manager names (not "Unknown")
   - Should show manager_profile_available: True

## Expected Outcome

After deployment and recalculation:
- Team parameters will include real manager names
- Manager multipliers will be applied to predictions
- System will handle rate limits gracefully with exponential backoff
- Detailed logging will show manager data retrieval process

## Current Status

✅ Code changes complete
✅ Local testing successful (real manager data retrieved)
✅ Rate limit handling improved
⚠️  **Deployment pending**
⚠️  **Recalculation pending**
