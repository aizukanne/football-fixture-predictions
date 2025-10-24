# Fix: Add Season Parameter to get_fixtures_goals()

## Issue Summary

**Severity**: CRITICAL  
**Component**: `src/data/api_client.py::get_fixtures_goals()`  
**Impact**: ALL leagues return 0 fixtures, breaking tactical analysis system-wide

## Root Cause

The API-Football `/v3/fixtures` endpoint **requires** the `season` parameter to return any fixtures. Without it, ALL leagues return empty results (0 fixtures), regardless of league or date range.

### Test Evidence

| League | ID | Without Season | With Season |
|--------|----|----|-----|
| Premier League | 39 | 0 fixtures ❌ | 81 fixtures ✓ |
| Championship | 40 | 0 fixtures ❌ | 132 fixtures ✓ |
| Eliteserien | 103 | 0 fixtures ❌ | 71 fixtures ✓ |

**Test script**: `test_multiple_leagues_season.py`

## Current Code Issues

### 1. Function Signature Missing Season

**File**: `src/data/api_client.py:616`

```python
# CURRENT (BROKEN)
def get_fixtures_goals(league_id, start_timestamp, end_timestamp, max_retries=DEFAULT_MAX_RETRIES):
    params = {
        "league": str(league_id),
        "from": datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d'),
        "to": datetime.fromtimestamp(end_timestamp).strftime('%Y-%m-%d')
    }
    # Missing season parameter!
```

### 2. Callers Have Season But Don't Pass It

**File**: `src/features/tactical_analyzer.py:646`

```python
# Has season available
season_year = int(season) if isinstance(season, str) else season
start_ts = int(datetime(season_year, 8, 1).timestamp())
end_ts = int(datetime.now().timestamp())

# But doesn't pass it!
fixtures = get_fixtures_goals(league_id, start_ts, end_ts)  # ❌ Missing season
```

**File**: `src/features/tactical_analyzer.py:828` - Same issue

## Required Changes

### Change 1: Update Function Signature

**File**: `src/data/api_client.py:616`

```python
def get_fixtures_goals(league_id, start_timestamp, end_timestamp, season, max_retries=DEFAULT_MAX_RETRIES):
    """
    Fetch fixture goals for a specific league within a time range.
    
    Args:
        league_id: League identifier
        start_timestamp: Start timestamp
        end_timestamp: End timestamp
        season: Season year (REQUIRED) - e.g. "2024" or 2024
        max_retries: Maximum retry attempts
    
    Returns:
        List of fixture dictionaries with full details
    """
    params = {
        "league": str(league_id),
        "season": str(season),  # ADD THIS
        "from": datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d'),
        "to": datetime.fromtimestamp(end_timestamp).strftime('%Y-%m-%d')
    }
    # ... rest unchanged
```

### Change 2: Update APIClient Wrapper

**File**: `src/data/api_client.py:957`

```python
def get_fixtures_goals(self, league_id, start_timestamp, end_timestamp, season, max_retries=DEFAULT_MAX_RETRIES):
    return get_fixtures_goals(league_id, start_timestamp, end_timestamp, season, max_retries)
```

### Change 3: Update Caller 1

**File**: `src/features/tactical_analyzer.py:646`

```python
season_year = int(season) if isinstance(season, str) else season
start_ts = int(datetime(season_year, 8, 1).timestamp())
end_ts = int(datetime.now().timestamp())
fixtures = get_fixtures_goals(league_id, start_ts, end_ts, season)  # ADD season
```

### Change 4: Update Caller 2

**File**: `src/features/tactical_analyzer.py:828`

```python
season_year = int(season) if isinstance(season, str) else season
start_ts = int(datetime(season_year, 8, 1).timestamp())
end_ts = int(datetime.now().timestamp())
all_fixtures = get_fixtures_goals(league_id, start_ts, end_ts, season)  # ADD season
```

## Files to Modify

1. `src/data/api_client.py` - Add season parameter (lines 616, 634, 957)
2. `src/features/tactical_analyzer.py` - Pass season to function (lines 646, 828)

## Testing Plan

### Before Fix
```bash
python3 test_multiple_leagues_season.py
# Expected: All leagues return 0 fixtures without season
```

### After Fix
```bash
# Test that season parameter is now passed
python3 -c "
from src.data.api_client import get_fixtures_goals
from datetime import datetime

league_id = 40
season = 2024
start_ts = int(datetime(2024, 8, 1).timestamp())
end_ts = int(datetime.now().timestamp())

fixtures = get_fixtures_goals(league_id, start_ts, end_ts, season)
print(f'Fixtures returned: {len(fixtures)}')
assert len(fixtures) > 0, 'Should return fixtures with season parameter'
print('✓ Test passed')
"
```

## Impact Assessment

### Benefits
- ✅ Fixes tactical analysis for ALL leagues
- ✅ Resolves "No fixtures data" warnings
- ✅ Enables formation analysis across all teams
- ✅ Improves data quality for team parameters

### Risks
- ⚠️ **Breaking change**: Adds required parameter to function signature
- ⚠️ Any undiscovered callers will break until updated
- ⚠️ Must verify all callers are updated before deployment

### Mitigation
- Search codebase for all `get_fixtures_goals(` calls
- Verify `tactical_data_collector.py` wrapper handles the change
- Test with multiple leagues after implementation
- Deploy during maintenance window

## Related Issues

- Original issue: League 40 (Championship) warnings
- Discovered: Universal problem affecting ALL leagues
- Related function: `get_league_teams()` also has return type issues (separate fix needed)

## References

- Test script: `test_multiple_leagues_season.py`
- API documentation: API-Football v3 fixtures endpoint
- Related file: `src/data/database_client.py` (uses different query method, unaffected)