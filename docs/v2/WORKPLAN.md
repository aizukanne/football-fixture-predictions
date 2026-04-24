# V2 xG-Based Prediction Engine — Workplan

Trackable implementation checklist. Each task links to its implementation guide. Tick each `[ ]` → `[x]` as completed. Phases are sequential; tasks within a phase can be parallelized where they don't share files.

## Phase 1 — Infrastructure

Goal: DynamoDB tables exist and are backfilled with current-season data from our SQLite store.

- [x] **1.1** Create `football_match_statistics_prod` table — see [01](./01-dynamodb-tables.md)
- [x] **1.2** Create `football_team_xg_parameters_prod` table — see [01](./01-dynamodb-tables.md)
- [x] **1.3** Create `football_league_xg_parameters_prod` table — see [01](./01-dynamodb-tables.md)
- [x] **1.4** Write `scripts/backfill_sqlite_to_dynamo.py` — see [02](./02-sqlite-backfill.md)
- [x] **1.5** Run backfill (13,315 items written) — see [02](./02-sqlite-backfill.md)
- [x] **1.6** Verify backfill count matches SQLite, spot-check fixtures — see [02](./02-sqlite-backfill.md)

**Phase 1 done when**: the three tables exist in eu-west-2, `match_statistics` has ≥13,780 items (allowing for the handful of probe-only skipped leagues), and the two param tables are empty and ready to be filled by the fitter.

## Phase 2 — Data pipeline

Goal: new post-match data flows live in DynamoDB; xG parameters are fitted weekly.

- [x] **2.1** Add `get_fixture_statistics(fixture_id)` to `src/data/api_client.py` — see [03](./03-stats-ingestion.md)
- [x] **2.2** Modify `match_data_handler.collect_enhanced_match_data` to call it and write to DynamoDB — see [03](./03-stats-ingestion.md)
- [ ] **2.3** Verify end-to-end on next daily post-match run (pending natural trigger)
- [x] **2.4** Write `src/parameters/xg_fitter.py` — see [04](./04-xg-parameter-fitter.md)
- [x] **2.5** Unit-test fitter (11 tests passing)
- [x] **2.6** Write `src/handlers/xg_parameter_handler.py` (lambda handler) — see [05](./05-fitter-lambda-and-schedule.md)
- [ ] **2.7** Deploy `football-xg-parameter-fitter-prod` lambda via `scripts/deploy_xg_parameter_lambda.sh` (requires `setup_deployment_env.sh` + upload_lambda_to_s3.sh)
- [ ] **2.8** Create EventBridge rule via `scripts/create_xg_fitter_schedule.sh` (cron: Wed 05:00 UTC — after daily match-results at 04:00)
- [x] **2.9** First fit run — 28 leagues fit in 443s, params tables populated

**Phase 2 done when**: `/v3/fixtures/statistics` is being called post-match and landing in DynamoDB, and the weekly fitter has run once and populated both param tables for all 28 kept leagues.

## Phase 3 — Prediction engine

Goal: V2 engine produces all 4 variants per fixture, wired into the same lambda as V1, writing to the same record under `xg_` attributes.

- [x] **3.1** Write `src/prediction/xg_engine.py` core λ computation — see [06](./06-engine-core.md)
- [x] **3.2** Implement Dixon-Coles correction in `xg_engine` — see [06](./06-engine-core.md)
- [x] **3.3** Write `fetch_team_xg_stream` in `src/data/xg_data_access.py` — see [07](./07-engine-integration.md)
- [x] **3.4** Write `get_team_xg_params` / `get_league_xg_params` in `src/data/xg_data_access.py` — see [07](./07-engine-integration.md)
- [x] **3.5** Add V2 block (4 variants) to `process_fixtures` in `src/handlers/prediction_handler.py` — see [07](./07-engine-integration.md)
- [x] **3.6** Populate `xg_*` attributes on fixture record — see [08](./08-output-schema.md)
- [x] **3.7** Implement data-quality flag propagation and SoT-proxy fallback — see [09](./09-data-quality-and-errors.md)
- [x] **3.8** Wrap V2 block in try/except so it can never block V1 — see [09](./09-data-quality-and-errors.md)
- [ ] **3.9** Deploy updated prediction lambda (requires build + upload_lambda_to_s3 + deploy)
- [ ] **3.10** Verify on next fixture batch (pending deploy)

**Phase 3 done when**: every fixture processed by the lambda has all V1 outputs plus all four V2 outputs (`xg_predictions`, `xg_alternate_predictions`, `xg_venue_predictions`, `xg_venue_alternate_predictions`) on the same DynamoDB record.

## Phase 4 — Validation + cutover

Goal: confirm V2 beats V1, complete the parallel-run period, pick a cutover date.

- [ ] **4.1** Confirm external analytics layer is logging both V1 and V2 predictions per fixture — see [10](./10-parallel-validation.md)
- [ ] **4.2** 4-week parallel-run observation window — see [10](./10-parallel-validation.md)
- [ ] **4.3** Re-fit Dixon-Coles ρ per league from accumulated production data — see [10](./10-parallel-validation.md)
- [ ] **4.4** Review Brier-score / MAE / log-loss comparison V1 vs each V2 variant — see [10](./10-parallel-validation.md)
- [ ] **4.5** Document cutover decision (keep both? promote V2? roll back specific variants?) — see [10](./10-parallel-validation.md)

**Phase 4 done when**: a written decision exists in this repo, signed off by stakeholders, saying whether V2 replaces V1, runs alongside indefinitely, or is reverted.

## Dependency graph (summary)

```
Phase 1.1-1.3 (tables)
    ↓
Phase 1.4-1.6 (backfill) ──┬──► Phase 2.1-2.3 (ingestion)
                           │
                           └──► Phase 2.4-2.9 (fitter + schedule)
                                        ↓
                                Phase 3.1-3.10 (engine + integration)
                                        ↓
                                Phase 4.1-4.5 (validation + cutover)
```

Within each phase, tasks in the same guide are sequential; tasks across different guides can be parallelized.

## Status log

Use this section to track progress, blockers, and decisions as work proceeds.

| Date | Phase | Note |
|---|---|---|
| 2026-04-24 | 1.1–1.3 | Created 3 DynamoDB tables in eu-west-2, billing PAY_PER_REQUEST, `league_date_idx` GSI on `match_statistics`. Aligned key schema with existing `football_team_parameters_prod` (team_id HASH, league_id RANGE — dropped planned composite `league_season` SK since params are overwritten each season). |
| 2026-04-24 | 1.4–1.6 | `scripts/backfill_sqlite_to_dynamo.py` written. Run: 6,915 SQLite fixtures seen → 13,315 items written in 131 seconds. 232 empty-payload fixtures skipped (SPARSE leagues). 51 items skipped (no usable xG + no SoT). Spot-check vs SQLite matches exactly. xG source distribution ~85% native / 15% sot_proxy. |
| 2026-04-24 | 2.1 | Added `get_fixture_statistics(fixture_id)` wrapper to `api_client.py`. `@cached`, uses `_make_api_request`. Also added method on `ApiClient` class. Smoke-tested against live API (Arsenal vs Liverpool → 2 team entries, 18 stats each, xG present). |
| 2026-04-24 | 2.2 | Shared module `src/data/match_statistics.py` holds stat parsing logic (used by both ingestion handler and backfill). `collect_enhanced_match_data` in `match_data_handler.py` now: calls the API, parses 18 stats per team with xG/SoT-proxy imputation, writes per-team rows to `football_match_statistics_prod`, AND still produces the legacy `match_statistics` nested attribute for V1 consumers. Wrapped in try/except. |
| 2026-04-24 | 2.4–2.5 | `src/parameters/xg_fitter.py`: pooled + venue-split means, shrinkage `team_mean * n/(n+10) + league_mean * 10/(n+10)`, data_quality flagging (`full`/`sparse`/`sot_proxy`/`cold_start`), preserves existing `rho_dc` when present. `tests/test_xg_fitter.py` has 11 tests, all passing. |
| 2026-04-24 | 2.6 | `src/handlers/xg_parameter_handler.py` lambda handler supports direct (all leagues), single-league, and SQS-style invocation. Uses `get_league_start_date` to resolve each league's current season dynamically. |
| 2026-04-24 | 2.7–2.8 | Deploy scripts: fold the xG fitter lambda deployment into the existing `scripts/deploy_lambda_with_layer.sh` as block [10/10] (same pattern as all V1 lambdas — scipy-layer, python3.13, 1024 MB, 900 s). `scripts/create_xg_fitter_schedule.sh` installs the EventBridge rule at `cron(0 5 ? * WED *)` (Wed 05:00 UTC, AFTER the daily match-results at 04:00 so the weekly fit always includes Tuesday's fixtures). |
| 2026-04-24 | 2.9 | First parameter fit run locally against backfilled data: **all 28 kept leagues fit successfully in 443 seconds**. 3 UEFA competitions return `no_data` (as expected — never backfilled). EPL `league_avg_xg_for=1.391`, `home_adv=1.219` — matches Phase 0–4 analysis results exactly. |
| 2026-04-24 | 3.1–3.2 | `src/prediction/xg_engine.py` written. F3 pooled-ratio formula, √home_adv split, form-decay multiplier clamped [0.7, 1.3], Dixon-Coles joint table with ρ₀=-0.18, Poisson sampling. NO NB, NO 1.35 constant. |
| 2026-04-24 | 3.3–3.4 | `src/data/xg_data_access.py` written — isolated from V1's `database_client.py`. `get_team_xg_params`, `get_league_xg_params`, `fetch_team_xg_stream`, `league_params_as_team_shape` for cold-start fallback, `aggregate_data_quality` for output-level flag. |
| 2026-04-24 | 3.5–3.8 | V2 block (all 4 variants) wired into `prediction_handler.process_fixtures`. Writes `xg_probability_to_score{_alt/_venue/_venue_alt}`, `xg_predicted_goals*`, `xg_likelihood*` per team plus fixture-level `xg_predictions`, `xg_alternate_predictions`, `xg_venue_predictions`, `xg_venue_alternate_predictions`, `xg_coordination_info`, `xg_data_quality`. Wrapped in try/except so V1 never blocks. |
| 2026-04-24 | 3 test | `tests/test_xg_engine.py`: 22 tests all passing. End-to-end prediction run on real data (Arsenal home vs Chelsea away, EPL fitted params): Arsenal λ=1.81 / P(score)=84%, Chelsea λ=0.96 / P(score)=62%, BTTS 52%, O/U 2.5 = 52%, `data_quality='full'`. |
| 2026-04-24 | 4 | `scripts/refit_dixon_coles_rho.py` written: scans `game_fixtures` for V2-annotated finished fixtures, maximizes DC joint log-likelihood over ρ ∈ [-0.30, 0.00] per league, updates `rho_dc` field on `football_league_xg_parameters_prod`. Run manually after 4-week parallel window. |

## Rollback plan

V2 is additive. At any point:

1. Disable the prediction lambda's V2 block by short-circuiting the `try` to skip V2 entirely — V1 attributes still populate normally.
2. `xg_*` attributes stop being written; downstream consumers that reference them must handle their absence gracefully (any consumer already handles missing fields because V2 on a given fixture may be absent under data-quality logic).
3. Disable the xG fitter EventBridge rule — `football_team_xg_parameters_prod` and `football_league_xg_parameters_prod` stop updating; stale data remains but isn't consumed.
4. Tables and backfilled data can remain in place indefinitely; storage is trivial.
