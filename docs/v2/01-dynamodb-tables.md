# 01 — DynamoDB Tables

## Objective

Create the three new DynamoDB tables that V2 depends on, matching the existing `football_*_prod` naming convention, in region `eu-west-2`.

## Tables to create

### 1. `football_match_statistics_prod`

Per-fixture per-team statistics from `/v3/fixtures/statistics`.

**Primary key**:
- Partition key: `fixture_id` (Number)
- Sort key: `team_id` (Number)

**Attributes**:

| Attribute | Type | Notes |
|---|---|---|
| `fixture_id` | N | PK |
| `team_id` | N | SK |
| `league_id` | N | |
| `season` | N | e.g. `2025` |
| `match_date` | S | ISO8601 (from fixture) |
| `shots_on_goal` | N | |
| `shots_off_goal` | N | |
| `total_shots` | N | |
| `blocked_shots` | N | |
| `shots_insidebox` | N | |
| `shots_outsidebox` | N | |
| `fouls` | N | |
| `corner_kicks` | N | |
| `offsides` | N | |
| `ball_possession_pct` | N | parsed float from `"52%"` → `52.0` |
| `yellow_cards` | N | `null` from API stored as `0` |
| `red_cards` | N | same |
| `goalkeeper_saves` | N | |
| `total_passes` | N | |
| `passes_accurate` | N | |
| `passes_pct` | N | parsed float from `"84%"` → `84.0` |
| `expected_goals` | N | `null` → stored as attribute absent |
| `goals_prevented` | N | |
| `xg_source` | S | `'native'` \| `'sot_proxy'` — marks whether `expected_goals` was provided by API or imputed from SoT × 0.32 |
| `stat_raw_json` | S | full JSON response for the team, for audit |
| `fetched_at` | S | ISO8601 timestamp |

**GSI**:
- `league_season_date_idx` — PK `league_season` (S, composite `"{league_id}#{season}"`), SK `match_date` (S). Used by the fitter to scan all fixtures in a league/season efficiently.

**Capacity**: on-demand billing (`PAY_PER_REQUEST`) — matches the current `football_*_prod` pattern.

---

### 2. `football_team_xg_parameters_prod`

Fitted per-team xG parameters. One item per `(team_id, league_id, season)`. Rewritten weekly by the xG fitter.

**Primary key**:
- Partition key: `team_id` (Number)
- Sort key: `league_season` (String, composite `"{league_id}#{season}"`)

**Attributes** (the 11 from [the parameter catalog](./WORKPLAN.md) — see parent discussion):

| Attribute | Type | Notes |
|---|---|---|
| `team_id` | N | PK |
| `league_season` | S | SK — `"{league_id}#{season}"` |
| `league_id` | N | for GSI / readability |
| `season` | N | |
| `mu_xg_for` | N | pooled mean xG generated |
| `mu_xg_against` | N | pooled mean xG conceded |
| `mu_xg_for_home` | N | home-only |
| `mu_xg_against_home` | N | home-only |
| `mu_xg_for_away` | N | away-only |
| `mu_xg_against_away` | N | away-only |
| `n_matches` | N | sample size |
| `n_matches_home` | N | |
| `n_matches_away` | N | |
| `data_quality` | S | `'full'` \| `'sparse'` \| `'sot_proxy'` |
| `last_updated` | S | ISO8601 |

**GSI**:
- `league_season_idx` — PK `league_season` (S). Used by the engine when it needs to pull "all teams in this league for this season."

**Capacity**: on-demand.

---

### 3. `football_league_xg_parameters_prod`

Fitted per-league xG parameters. One item per `(league_id, season)`. Rewritten weekly.

**Primary key**:
- Partition key: `league_id` (Number)
- Sort key: `season` (Number)

**Attributes** (the 7 from parameter catalog):

| Attribute | Type | Notes |
|---|---|---|
| `league_id` | N | PK |
| `season` | N | SK |
| `league_avg_xg_for` | N | mean xG per team per match, pooled |
| `league_avg_xg_home` | N | mean xG scored *by home team* per match |
| `league_avg_xg_away` | N | mean xG scored *by away team* per match |
| `home_adv` | N | `league_avg_xg_home / league_avg_xg_away` |
| `rho_dc` | N | Dixon-Coles ρ; initial −0.18, re-fit per [10](./10-parallel-validation.md) |
| `n_matches` | N | total league match count |
| `last_updated` | S | ISO8601 |

**Capacity**: on-demand.

## Creation method

Use the existing infrastructure conventions. The repo has deployment scripts under `scripts/` — follow the same pattern used when earlier `football_*_prod` tables were created. At minimum:

```bash
aws dynamodb create-table \
  --table-name football_match_statistics_prod \
  --region eu-west-2 \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions \
      AttributeName=fixture_id,AttributeType=N \
      AttributeName=team_id,AttributeType=N \
      AttributeName=league_season,AttributeType=S \
      AttributeName=match_date,AttributeType=S \
  --key-schema \
      AttributeName=fixture_id,KeyType=HASH \
      AttributeName=team_id,KeyType=RANGE \
  --global-secondary-indexes \
      'IndexName=league_season_date_idx,KeySchema=[{AttributeName=league_season,KeyType=HASH},{AttributeName=match_date,KeyType=RANGE}],Projection={ProjectionType=ALL}'
```

Similar commands for the two param tables (no GSI needed on `league_xg_parameters_prod`; GSI on `team_xg_parameters_prod`).

Check whether the repo uses Terraform / CDK / SAM / a shell script to manage existing tables and match that flow. If the existing `football_team_parameters_prod` was created via Terraform, add these to the same Terraform module.

## Test plan

- [ ] `aws dynamodb describe-table` for each table returns `TableStatus: ACTIVE`
- [ ] Write a single test item to each and read it back
- [ ] Verify GSI `league_season_date_idx` on `match_statistics` is `ACTIVE`
- [ ] Verify tags / account match the other production tables

## Dependencies

None — first task in Phase 1.

## Acceptance criteria

All three tables exist, are empty, and are queryable. Their schemas match this guide exactly.
