# 02 — SQLite → DynamoDB Backfill

## Objective

One-time migration of the ~6,895 fixtures of per-team statistics already sitting in `data/fixture_stats/stats.db` into the new `football_match_statistics_prod` DynamoDB table, so V2 has current-season history on day one.

## Rationale

We already pulled the data during the analysis phase using `scripts/pull_fixture_stats.py`. Re-pulling from the API would cost ~6,900 calls of your ULTRA quota and change nothing. A local copy exists; lift-and-shift it.

## Files created

- `scripts/backfill_sqlite_to_dynamo.py` — the one-time migration script.

## Files modified

None.

## Inputs

- `data/fixture_stats/stats.db` — SQLite database. Relevant tables:
  - `fixtures` — fixture metadata (fixture_id, league_id, season, date, home_team_id, away_team_id, etc.)
  - `fixture_statistics_raw` — one row per fixture; full JSON payload with `has_xg` flag
  - `fixture_statistics` — flattened per-stat rows keyed by `(fixture_id, team_id, stat_type)`

## Outputs

- DynamoDB `football_match_statistics_prod` populated with ~13,790 items (6,895 fixtures × 2 teams).

## Algorithm

```
For each fixture_id in fixture_statistics_raw:
    Load raw payload JSON
    Load fixture metadata from `fixtures` table
    Parse the two `statistics` entries (one per team)

    For each team's statistics:
        Build DynamoDB item with these attributes:
            fixture_id, team_id (both ints, become N keys)
            league_id, season, match_date (from fixtures table)
            all 18 stat fields, with string percents parsed to numeric
            xg_source = 'native' if expected_goals present else 'sot_proxy'
            If xg_source == 'sot_proxy' and Shots on Goal present:
                expected_goals = shots_on_goal * 0.32
            stat_raw_json = json.dumps(team_entry)
            fetched_at = now (or copy from fixture_statistics_raw.fetched_at)

    Batch writes up to 25 items per BatchWriteItem call.
```

## Key implementation points

- **Idempotency**: use conditional put `attribute_not_exists(fixture_id)` OR simply allow overwrite — running twice is safe, the second run writes the same bytes. Prefer overwrite for simplicity.
- **Resumability**: keep a local file `data/fixture_stats/backfill_progress.json` listing completed fixture_ids. On re-run, skip already-written. Not strictly necessary if the job completes, but a safety net.
- **Batch size**: DynamoDB `BatchWriteItem` caps at 25 items. The script loops. Include exponential backoff on `UnprocessedItems`.
- **Throughput**: on-demand billing, so no capacity concerns. Should complete in ~5 minutes.
- **Boolean → int for the null cards**: the API returns `null` for yellow/red cards when zero; normalize to `0` on write.
- **Empty payloads**: 217 fixtures in SQLite have empty stats (SPARSE leagues). These have `fixture_statistics_raw.has_xg = 0` and no rows in `fixture_statistics`. SKIP these during backfill — they can't produce a useful item without inventing data.

## Credentials and region

- Region: `eu-west-2`
- AWS creds are already configured on the machine (`aws sts get-caller-identity` returns the `terraform` user from earlier).

## Verification

After running:

1. `aws dynamodb describe-table --table-name football_match_statistics_prod --region eu-west-2` — confirm `ItemCount` is near the expected (~13,780 — allowing for the ~217 empty payloads per fixture × 2 = 434 missing items, so expect ~13,356).

    > Note: `ItemCount` is an eventually-consistent statistic; it can lag by several hours.

2. Spot-check 10 random fixtures. For each, query DynamoDB for both teams and compare to the SQLite rows for the same `fixture_id`:

   ```python
   # For fixture_id = 1208399 (EPL Nottingham Forest vs Chelsea, from our probe)
   # Expect two items. Check shots_on_goal = 2 for both, possession 52/48%, xG 1.20/1.09.
   ```

3. Spot-check data-quality mix: run a PartiQL count grouping by `xg_source`:

   ```sql
   SELECT xg_source, COUNT(*) FROM "football_match_statistics_prod" GROUP BY xg_source
   ```

   Expect ~81% `native`, ~19% `sot_proxy` (matching the 5,628 / 6,915 ratio from our earlier coverage report).

## Test plan

- [ ] Dry run: script with `--dry-run` prints first 5 items that would be written
- [ ] Run full backfill
- [ ] Verify item count in DynamoDB (give `ItemCount` ~24h to settle, or use `Scan` with `Select=COUNT`)
- [ ] Spot-check 10 fixtures against SQLite
- [ ] Verify `xg_source` distribution matches expected (~81% native)

## Dependencies

- Blocks on Phase 1 tables existing (task 1.1).
- Runs once. Does not need to be part of scheduled infrastructure.

## Acceptance criteria

`football_match_statistics_prod` contains ~13,356 items, each with all required attributes populated, matching the SQLite source.

## Rollback

This is additive. To rollback: delete all items (or drop the table). No other system is yet reading from this table.
