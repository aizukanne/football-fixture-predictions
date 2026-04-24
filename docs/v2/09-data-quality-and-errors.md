# 09 — Data Quality and Error Handling

## Objective

Define exactly how V2 handles imperfect inputs (missing xG, missing SoT, SPARSE leagues, cold-start teams, network failures) without ever corrupting V1 outputs or producing silently-wrong V2 predictions.

## The decision matrix

For each input signal, the behavior is:

| Signal state | Action | Resulting flag |
|---|---|---|
| `expected_goals` present in API response | Use directly | `xg_source = 'native'` |
| `expected_goals` null but `shots_on_goal` present | Impute `xg = sot × 0.32` | `xg_source = 'sot_proxy'` |
| Both null for a team in a match | Don't insert match_statistics row for that team | Fitter has less data for that team |
| `/v3/fixtures/statistics` returns 200 with empty `response` | Log, skip ingestion for that fixture | No V2 data ever for that fixture |
| `/v3/fixtures/statistics` returns 429 | Retry with backoff (existing `_make_api_request` logic) | Eventually succeed or raise |
| `/v3/fixtures/statistics` returns 5xx after retries exhausted | Log; fixture ingestion fails; next daily run retries | Temporary gap |
| Team has zero matches in DynamoDB at fit time | Cold-start: use league means | `data_quality = 'cold_start'` |
| Team has < 10 matches | Heavy shrinkage to league mean | `data_quality = 'sparse'` |
| Team's matches are >20% SoT-proxy imputed | Full fit but flag | `data_quality = 'sot_proxy'` |
| Team's league is in the SPARSE tier (Belgium Challenger, Bulgaria, Slovakia) | Full fit from what's there | `data_quality = 'sparse'` |
| League has zero matches in DynamoDB at fit time | Skip league entirely; no league_xg_params written | Downstream: V2 skips every fixture in this league |
| V2 prediction call raises any exception at runtime | Catch at integration layer; V1 proceeds unaffected; V2 attributes absent | `xg_coordination_info.v2_failed = true` |

## Data-quality flag propagation

The `data_quality` field exists at three levels:

1. **Team parameter level** (stored in `football_team_xg_parameters_prod`). One of: `'full'`, `'sot_proxy'`, `'sparse'`, `'cold_start'`.
2. **Match-statistics row level** (stored in `football_match_statistics_prod` as `xg_source`). One of: `'native'`, `'sot_proxy'`.
3. **Fixture-level aggregate** (written as `xg_data_quality` on the fixture record). Takes the worst-case of the four contributing param dicts:
   - if any is `'cold_start'` → `'cold_start'`
   - elif any is `'sparse'` → `'sparse'`
   - elif any is `'sot_proxy'` → `'sot_proxy'`
   - else `'full'`
   - plus `'unavailable'` for complete V2 failures, `'league_avg'` where league-avg fallback was used for a missing team fit.

This lets downstream consumers display a confidence indicator or simply ignore low-quality V2 rows.

## Error handling rules

### Rule 1 — V2 MUST NEVER block V1

Every V2 interaction is wrapped. The top-level block in `prediction_handler.process_fixtures` is:

```python
try:
    # all V2 code
except Exception as xg_e:
    print(f"V2 xG predictions failed for fixture {fixture_id}: {xg_e}")
    # V1 is already complete at this point; fixture record still gets written
    xg_coordination_info = {'v2_failed': True, 'error': str(xg_e)}
    xg_data_quality = 'unavailable'
    # All xg_prediction_summary_* remain None → attributes omitted on write
```

Nothing V2 does — no missing params, no malformed stats row, no DynamoDB throttle — can cause a fixture's V1 predictions not to be written.

### Rule 2 — Malformed data is not stored

Stats ingestion [03](./03-stats-ingestion.md) only writes a `match_statistics` row if parsing produced a valid item:

- `shots_on_goal` is numeric
- `team_id` and `fixture_id` are positive integers
- at least one of `expected_goals` (native) or `shots_on_goal` > 0 (proxy-able) is present

Otherwise the fixture is skipped (logged) and no row is written. The fitter's dataset stays clean.

### Rule 3 — Params are regenerated weekly from scratch

Each weekly fitter run REPLACES all items in the param tables (or updates with `PutItem`, overwriting). Stale items from a prior run don't linger. If a team's fit drops from `'full'` to `'sparse'` because earlier rows were purged (they won't be, but hypothetically), the new run reflects that.

Items are never conditionally-skipped. If a team has zero matches, we write a cold-start item with league averages.

### Rule 4 — Missing league params → skip V2 entirely for that fixture

If `get_league_xg_params(league_id, season)` returns None, the V2 block raises and falls into the top-level catch. The fixture's V2 attributes are absent. This should not happen in steady state (fitter writes every league that has match data) but we defend against it.

### Rule 5 — Missing team params → fall back to league averages

Handled inline in [07](./07-engine-integration.md):

```python
home_xg_params_team = home_xg_params_team or home_xg_params_league
```

The fixture gets V2 predictions using league-average "team" parameters. `data_quality = 'league_avg'`.

### Rule 6 — API rate limit (429) during stats ingestion

The existing `_make_api_request` has exponential-backoff + jitter + circuit breaker. Inherit unchanged. If an individual `/fixtures/statistics` call eventually gives up, that fixture's stats are missing from DynamoDB this run. The next daily run picks it up again (idempotent overwrite is safe).

### Rule 7 — DynamoDB throttle during fit or write

On-demand billing doesn't pre-throttle but can burst-throttle on ingress spikes. `BatchWriteItem` returns `UnprocessedItems` which must be retried with backoff. Standard boto3 `batch_writer()` handles this for us; otherwise wrap in a retry loop.

## What NOT to do

- **Never zero-fill**: writing `xg_probability_to_score = 0` for a fixture where V2 failed would silently corrupt downstream accuracy measurement. Absence of attribute is the correct signal.
- **Never use V1's outputs as V2's fallback**: if V2 fails, the fixture record still has V1's four predictions. That's sufficient. Don't copy V1 into `xg_*` fields and claim it's V2.
- **Never silently patch missing xG with goals**: if both `xg` and `sot` are unavailable for a match, skip it. Using actual goals would defeat the point of having a separate xG-driven engine (and would also leak goals into the fitting data in a biased way — only matches with missing stats would have goal-as-xg).
- **Never suppress exceptions in the fitter** at the team loop: per-league failures are isolated in the lambda handler, but within a league, if one team's fit fails, log and continue to other teams — don't let one bad team poison the whole league's refit.

## Test plan

- [ ] Inject a malformed API response in the ingestion path, verify it's logged and no row written.
- [ ] Delete all `team_xg_parameters` items for one team, run the prediction lambda — verify V2 uses league-avg fallback for that team (produces `data_quality='league_avg'`), V1 is unaffected.
- [ ] Delete the `league_xg_parameters` item for one league — verify V2 block catches and fixture record has `xg_data_quality='unavailable'`, V1 unaffected.
- [ ] Force an exception mid-V2 block (e.g. by corrupting a param's numeric field). Verify V1 outputs land correctly, `v2_failed=True` appears in `xg_coordination_info`.
- [ ] Fit a team with 3 matches in the DB — verify `data_quality='sparse'` and `mu_xg_for` is closer to league mean than team mean.
- [ ] Fit a team with 0 matches — verify cold-start (pure league means, `data_quality='cold_start'`).
- [ ] Fit a team entirely from SoT-proxy rows — verify `data_quality='sot_proxy'`.

## Dependencies

- Informs 03 (ingestion rules), 04 (fitter rules), 07 (integration error handling).
- No standalone code, but the tests above should be part of the PR that closes those tasks.

## Acceptance criteria

- For every scenario in the decision matrix, the documented action occurs (verified by tests or live observation within the first week of production).
- V1 output is identical before and after V2 goes live, measured by hashing the V1-attribute subset of 1000 fixture records pre/post-deploy on the same inputs.
- CloudWatch logs show `v2_failed` cases are rare (< 1% of fixtures) in steady state.

## Rollback

All rules above are implemented as policies inside V2 code; rolling back V2 (reverting the handler) removes them along with V2 itself.
