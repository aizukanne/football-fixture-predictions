# GSI Query Optimization - Database Client Update

## Overview
Updated database query functions to use the existing `country-league-index` Global Secondary Index (GSI) instead of expensive table scans.

## Problem Identified
The [`query_dynamodb_records()`](../../src/data/database_client.py:189) and [`fetch_league_fixtures()`](../../src/data/database_client.py:293) functions were using `scan()` operations that:
- Read the **entire table** before applying filters
- Consumed excessive read capacity
- Could timeout on large tables
- May have caused fixtures to be missed during score updates due to pagination limits

## GSI Structure Confirmed
**Table**: `football_game_fixtures_prod`
**GSI Name**: `country-league-index`

```json
{
  "IndexName": "country-league-index",
  "KeySchema": [
    {
      "AttributeName": "country",
      "KeyType": "HASH"
    },
    {
      "AttributeName": "league", 
      "KeyType": "RANGE"
    }
  ],
  "Projection": {
    "ProjectionType": "ALL"
  }
}
```

## Changes Made

### 1. query_dynamodb_records() - Lines 189-229

**Before:**
```python
response = webFE_table.scan(
    FilterExpression=Key('timestamp').between(start_time, end_time) & 
                   Key('country').eq(country) & 
                   Key('league').eq(league_name)
)
```

**After:**
```python
response = webFE_table.query(
    IndexName='country-league-index',
    KeyConditionExpression=Key('country').eq(country) & Key('league').eq(league_name),
    FilterExpression=Key('timestamp').between(start_time, end_time)
)
```

**Key Improvements:**
- Uses GSI query instead of table scan
- Handles pagination automatically with while loop
- Only reads fixtures for the specific country/league
- Timestamp filter applied after efficient GSI query
- Added logging for debugging

### 2. fetch_league_fixtures() - Lines 293-336

**Before:**
```python
response = webFE_table.scan(
    FilterExpression=Key('timestamp').between(start_time, end_time) &
                   Key('country').eq(country) &
                   Key('league').eq(league_name),
    ProjectionExpression='...'
)
```

**After:**
```python
response = webFE_table.query(
    IndexName='country-league-index',
    KeyConditionExpression=Key('country').eq(country) & Key('league').eq(league_name),
    FilterExpression=Key('timestamp').between(start_time, end_time),
    ProjectionExpression='...'
)
```

**Key Improvements:**
- Uses GSI query instead of table scan
- Handles pagination automatically
- Maintains same ProjectionExpression for backward compatibility

## Impact Analysis

### Functions Using query_dynamodb_records():
1. **[match_data_handler.py](../../src/handlers/match_data_handler.py:70)** - Main score update handler ✅
2. **[league_calculator.py](../../src/parameters/league_calculator.py:181)** - Multiplier calculations ✅
3. **[database_client.py](../../src/data/database_client.py:574)** - DatabaseClient wrapper ✅

### Functions Using fetch_league_fixtures():
1. **[team_parameter_handler.py](../../src/handlers/team_parameter_handler.py:243)** - Team parameter calculation ✅
2. **[league_parameter_handler.py](../../src/handlers/league_parameter_handler.py:85)** - League parameter calculation ✅
3. **[database_client.py](../../src/data/database_client.py:583)** - DatabaseClient wrapper ✅

### Backward Compatibility
✅ **No breaking changes** - Function signatures unchanged
✅ **Return type unchanged** - Still returns list of fixture records
✅ **All callers work without modification**

## Performance Benefits

### Before (Scan):
- Reads: **Entire table** (601+ items)
- Time: Variable, can timeout on large tables
- Cost: High (reads all items)
- Pagination: Often incomplete

### After (GSI Query):
- Reads: **Only fixtures for specific country/league** (~20-50 items typically)
- Time: Fast, consistent performance
- Cost: Much lower (reads only needed items)
- Pagination: Properly handled

### Expected Improvements:
- 🚀 **10-30x faster** queries
- 💰 **90%+ reduction** in read capacity usage
- ✅ **Complete results** - no more missed fixtures due to pagination
- 🎯 **Targeted reads** - only relevant data

## Testing Recommendations

1. **Verify Score Updates Work:**
   ```bash
   # Invoke match data handler to verify it retrieves all fixtures
   aws lambda invoke --function-name football-match-data-handler output.json
   ```

2. **Check Logs for GSI Usage:**
   ```bash
   # Look for the new log line confirming GSI query usage
   grep "Retrieved .* fixtures .* using GSI query" /var/log/lambda/*.log
   ```

3. **Monitor Read Capacity:**
   ```bash
   # Should see significant reduction in consumed read units
   aws cloudwatch get-metric-statistics \
     --namespace AWS/DynamoDB \
     --metric-name ConsumedReadCapacityUnits \
     --dimensions Name=TableName,Value=football_game_fixtures_prod
   ```

## Rollback Plan

If issues arise, revert to scan-based implementation:
```bash
git revert <commit-hash>
```

The scan-based code is preserved in git history and can be restored if needed.

## Related Documentation

- [Table Isolation Implementation Guide](TABLE_ISOLATION_IMPLEMENTATION_GUIDE.md)
- [Database Schema Documentation](../guides/DATABASE_SCHEMA_DOCUMENTATION.md)
- [Match Data Handler](../../src/handlers/match_data_handler.py)
- [Database Client](../../src/data/database_client.py)