# 03 — Post-match Stats Ingestion

## Objective

From today forward, every finished fixture processed by the daily post-match handler also fetches `/v3/fixtures/statistics` and writes the 18 per-team stats to `football_match_statistics_prod`.

## Files created

None — the integration point already exists.

## Files modified

1. `src/data/api_client.py` — add `get_fixture_statistics(fixture_id, max_retries=DEFAULT_MAX_RETRIES)`.
2. `src/handlers/match_data_handler.py` — replace the `return None` stub in `collect_enhanced_match_data` (currently at around line 265) with a real implementation that calls the new wrapper and writes to DynamoDB.
3. `src/utils/constants.py` — add `MATCH_STATISTICS_TABLE` constant (and `TABLE_PREFIX`/`TABLE_SUFFIX` handling to keep parity with existing convention).

## The new API wrapper

Mirrors the existing `get_fixtures_goals_by_ids` and other wrappers. Uses the shared `_make_api_request` for throttling/backoff/circuit-breaker/metrics consistency.

```python
@cached  # reuse the existing within-invocation cache decorator
def get_fixture_statistics(fixture_id, max_retries=DEFAULT_MAX_RETRIES):
    """Fetch per-team statistics for a single finished fixture.

    Returns the full API response dict, or an empty dict if the API has no
    coverage for this fixture (some lower leagues / qualifying rounds).
    """
    url = f"{API_FOOTBALL_BASE_URL}/fixtures/statistics"
    params = {"fixture": str(fixture_id)}
    data = _make_api_request(url, params, max_retries=max_retries)
    if not data or "response" not in data:
        return {}
    return data
```

## The ingestion logic

Replacement for `collect_enhanced_match_data` in `src/handlers/match_data_handler.py`:

```python
def collect_enhanced_match_data(fixture_id, goal_data):
    """Fetch per-team stats for a finished fixture and persist.

    Called from the post-match results handler after goals are confirmed.
    Returns the parsed stats dict for inclusion in the fixture record (for
    visibility / debugging), but the persistence side-effect is the primary
    purpose.
    """
    try:
        response = get_fixture_statistics(fixture_id)
        teams = response.get("response", [])
        if not teams:
            # The API has no stats for this fixture (SPARSE league / qualifier).
            # Log, don't fail the pipeline. V2 will skip this fixture.
            print(f"No stats available for fixture {fixture_id}")
            return None

        fixture_meta = get_fixture_metadata(fixture_id)  # league_id, season, date, team IDs
        items = []
        for team_entry in teams:
            item = _parse_team_stats(
                fixture_id=fixture_id,
                team_entry=team_entry,
                fixture_meta=fixture_meta,
            )
            items.append(item)

        _batch_put_match_statistics(items)
        return {"teams": [_strip_for_logs(i) for i in items]}

    except Exception as e:
        print(f"Error collecting stats for fixture {fixture_id}: {e}")
        return None
```

### `_parse_team_stats`

Converts the API's `statistics: [{type, value}, ...]` array into the flat DynamoDB item shape from [01](./01-dynamodb-tables.md). Rules:

- Integer fields: coerce to `int`, `null` → `0`.
- `Ball Possession`: strip `%`, cast to `float` → `ball_possession_pct`.
- `Passes %`: strip `%`, cast to `float` → `passes_pct`.
- `expected_goals`: parse float; if absent, impute `shots_on_goal * 0.32` and set `xg_source = 'sot_proxy'`; otherwise `'native'`.
- `goals_prevented`: coerce to `float`.
- `stat_raw_json`: `json.dumps(team_entry)` for audit.
- `fetched_at`: current UTC ISO8601.

### `_batch_put_match_statistics`

Uses boto3 `Table.batch_writer()` context manager. Each fixture produces at most 2 items, so the batch is trivial, but use `batch_writer` for retry-on-throttle semantics.

## Integration point in the pipeline

`collect_enhanced_match_data` is currently called from `src/handlers/match_data_handler.py` in the match-results flow (triggered by the `football-match-results-daily-prod` EventBridge rule at 04:00 UTC daily).

Call order for each finished fixture:
1. Fetch final score from `/fixtures` (existing)
2. Update fixture record with final score (existing)
3. **NEW**: call `collect_enhanced_match_data` → writes to `football_match_statistics_prod`
4. Downstream analytics already handle the score update

The stats write is step 3, immediately after score confirmation. It does not block score updates if it fails.

## Rate-limit math

`/v3/fixtures/statistics` takes one fixture at a time (no batching). On a busy weekend ~100 fixtures finish. Each = 1 API call. Plus the existing goal-check calls. Still tiny against the 75K/day ULTRA quota. The existing 100ms throttle in `_make_api_request` remains sufficient.

## Idempotency

Same fixture called twice writes the same item twice (overwrite). Safe. No special guard needed.

## Test plan

- [ ] Unit test `_parse_team_stats` against the saved sample payload at `data/fixture_stats/stats.db:fixture_statistics_raw` for fixture 1208399 — expect numeric attributes match expected values (Nottingham Forest SoT=2, Chelsea SoT=2, etc.).
- [ ] Integration test against one real fixture after deploy: tail the match-results lambda logs, verify the new log line, then query DynamoDB for the fixture_id to confirm both team items were written.
- [ ] Log rate: run once against a quiet night (~20 fixtures) before enabling on a full weekend — check call count, response times, any 429s.

## Dependencies

- Blocks on Phase 1 tables existing (task 1.1).
- Does not block on the backfill (task 1.5) — ingestion and backfill are independent paths into the same table.

## Acceptance criteria

The next scheduled `football-match-results-daily-prod` run populates `football_match_statistics_prod` with a new batch of items (one pair per finished fixture from the previous 24h) with no errors, no API quota warnings, and no impact on the existing score-update flow.

## Rollback

Revert `collect_enhanced_match_data` to `return None`. Ingestion stops. Existing data in the table is retained and remains usable.
