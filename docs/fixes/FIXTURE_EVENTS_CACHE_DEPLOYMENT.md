# Deployment Guide: fixture_events_cache Table

## Overview

This guide covers deploying the `fixture_events_cache` table that was referenced in code but never created during initial deployment.

## Changes Made

### 1. Added Table Creation Method

**File**: `src/infrastructure/deploy_tables.py`

Added `create_fixture_events_cache_table()` method (lines 429-492):
- Primary key: `fixture_id` (String)
- Billing mode: Pay-per-request
- TTL enabled on `ttl` attribute (7 days)
- Tags: Project, Environment, Purpose, TTL

### 2. Added Table to Deployment List

**File**: `src/infrastructure/deploy_tables.py` (line 454)

Updated `deploy_all_tables()` to include:
```python
('fixture_events_cache', self.create_fixture_events_cache_table)
```

## Table Schema

**Note**: Actual table name will include configured prefix and suffix:
- Dev: `fixture_events_cache`
- Prod: `football_fixture_events_cache_prod`

```json
{
  "TableName": "football_fixture_events_cache_prod",
  "KeySchema": [
    {
      "AttributeName": "fixture_id",
      "KeyType": "HASH"
    }
  ],
  "AttributeDefinitions": [
    {
      "AttributeName": "fixture_id",
      "AttributeType": "S"
    }
  ],
  "BillingMode": "PAY_PER_REQUEST"
}
```

### Item Structure

```json
{
  "fixture_id": "1386571",
  "events": [...],
  "ttl": 1729900800,
  "cached_at": 1729641600
}
```

## IAM Permissions

### Current Setup

The existing IAM role (`FootballPredictionLambdaRole`) already has wildcard permissions for DynamoDB tables:

```json
{
  "Resource": [
    "arn:aws:dynamodb:eu-west-2:985019772236:table/football_*"
  ]
}
```

**✅ No IAM changes needed** - The new table will be named `football_fixture_events_cache_prod` (with configured prefix/suffix), so it's already covered by the wildcard permission `football_*`.

## Deployment Steps

### Step 1: Deploy the Table

```bash
cd /home/ubuntu/Projects/football-fixture-predictions

# Run the table deployment script
python3 -m src.infrastructure.deploy_tables
```

This will create all tables including the new `fixture_events_cache` table.

### Step 2: Verify Table Creation

```bash
# List all DynamoDB tables
aws dynamodb list-tables --region eu-west-2 | grep fixture_events_cache

# Get table details (use actual table name with prefix/suffix)
aws dynamodb describe-table \
  --table-name football_fixture_events_cache_prod \
  --region eu-west-2
```

### Step 3: Verify TTL is Enabled

```bash
aws dynamodb describe-time-to-live \
  --table-name football_fixture_events_cache_prod \
  --region eu-west-2
```

Expected output:
```json
{
  "TimeToLiveDescription": {
    "AttributeName": "ttl",
    "TimeToLiveStatus": "ENABLED"
  }
}
```

### Step 4: Test Cache Access

After deployment, the Lambda functions will automatically start using the cache. Monitor logs for:

**Success indicators:**
```
Cache hit for fixture 1386571
Cached events for fixture 1386571
```

**No more error messages:**
```
Cache table not available: AccessDeniedException
Failed to cache events: AccessDeniedException
```

## Usage in Code

The cache is used in [`database_client.py:989`](../../src/data/database_client.py:989):

```python
def get_cached_fixture_events(fixture_id, dynamodb=None):
    """Get fixture events with caching (7-day TTL)"""
    cache_table_name = 'fixture_events_cache'
    
    # Try cache first
    response = cache_table.get_item(Key={'fixture_id': str(fixture_id)})
    if 'Item' in response:
        return response['Item'].get('events')
    
    # Fetch from API if not cached
    events = get_fixture_events(fixture_id)
    
    # Cache for 7 days
    cache_table.put_item(Item={
        'fixture_id': str(fixture_id),
        'events': events,
        'ttl': int((datetime.now() + timedelta(days=7)).timestamp())
    })
    
    return events
```

## Benefits

### Before Fix
- ❌ Every fixture event request hits the API
- ❌ High API usage and costs
- ❌ Slower response times
- ❌ Error messages in logs

### After Fix
- ✅ Events cached for 7 days
- ✅ Reduced API usage (cached data reused)
- ✅ Faster response times
- ✅ Clean logs without errors

## Monitoring

### CloudWatch Metrics to Watch

1. **DynamoDB Metrics** (`football_fixture_events_cache_prod`):
   - `ConsumedReadCapacityUnits`
   - `ConsumedWriteCapacityUnits`
   - `UserErrors` (should be 0)

2. **Lambda Logs**:
   - Cache hit rate
   - API fallback frequency

### Expected Behavior

- **First request for a fixture**: API call + cache write
- **Subsequent requests (within 7 days)**: Cache hit
- **After 7 days**: TTL expires, next request fetches from API again

## Rollback Plan

If issues occur, the cache can be disabled without breaking functionality:

```python
# In database_client.py, the code already handles missing table:
try:
    cache_table = dynamodb.Table(cache_table_name)
    response = cache_table.get_item(...)
except Exception as e:
    print(f"Cache not available, fetching from API")
    # Falls back to API call
```

To completely disable:
1. Delete the table
2. System continues working (with API fallback)
3. No code changes needed

## Cost Estimate

**DynamoDB Costs** (Pay-per-request):
- Write: $1.25 per million writes
- Read: $0.25 per million reads

**Example scenario**:
- 100 fixtures cached/day = 3,000/month writes
- 10 reads per cached fixture = 30,000/month reads
- **Cost**: ~$0.01/month (negligible)

**API Cost Savings**:
- Reduced API calls = Fewer rate limit issues
- Better performance = Happier users

## Related Files

- **Table Creation**: `src/infrastructure/deploy_tables.py`
- **Cache Usage**: `src/data/database_client.py`
- **IAM Permissions**: `scripts/create_lambda_iam_role.sh`

## Completion Checklist

- [x] Table creation method added
- [x] Table added to deployment list
- [x] Documentation created
- [ ] Table deployed to AWS
- [ ] TTL verified as enabled
- [ ] Lambda logs show successful caching
- [ ] No more AccessDenied errors