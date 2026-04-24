# 04 — xG Parameter Fitter

## Objective

A module that reads `football_match_statistics_prod`, computes the 11 per-team parameters and 7 per-league parameters from [the parameter catalog](./WORKPLAN.md), and writes them to the two new param tables.

Runs weekly (Phase 2.8) but is importable and callable ad-hoc for testing.

## Files created

- `src/parameters/xg_fitter.py` — fitting logic (this guide).
- `tests/test_xg_fitter.py` — unit tests against SQLite sample data.

## Files modified

None.

## Public API

```python
def fit_team_xg_params(
    team_id: int,
    league_id: int,
    season: int,
    match_stats_df: pd.DataFrame,
    league_params: Dict,  # output of fit_league_xg_params for this league/season
) -> Dict:
    """Fit the 11 per-team xG parameters.

    Args:
        team_id: Team identifier.
        league_id: League identifier.
        season: Season year, e.g. 2025.
        match_stats_df: DataFrame with columns:
            [fixture_id, team_id, is_home, xg_for, xg_against, xg_source,
             match_date, opp_team_id]
            — already filtered to the team's matches, OR all matches in
            the league (function filters internally by team_id).
        league_params: Dict produced by fit_league_xg_params — used for
            the league-mean shrinkage prior when the team has few matches.

    Returns:
        Dict matching the schema of football_team_xg_parameters_prod.
    """

def fit_league_xg_params(
    league_id: int,
    season: int,
    match_stats_df: pd.DataFrame,
) -> Dict:
    """Fit the 7 per-league xG parameters.

    Args:
        league_id, season: identifiers.
        match_stats_df: All per-team match stats in this league for this
            season. Same schema as above.

    Returns:
        Dict matching the schema of football_league_xg_parameters_prod.
    """

def run_fit_for_league(league_id: int, season: int) -> None:
    """End-to-end for one league: load stats from DynamoDB, fit league
    params first, then fit each team's params, write all back to DynamoDB.

    This is what the scheduled lambda calls once per league.
    """
```

## Algorithm

### `fit_league_xg_params`

```
all_rows = match_stats_df filtered to league_id and season
n_matches = unique fixture_id count in all_rows
home_rows = rows where is_home == True
away_rows = rows where is_home == False

league_avg_xg_home = home_rows['xg_for'].mean()
league_avg_xg_away = away_rows['xg_for'].mean()
league_avg_xg_for = all_rows['xg_for'].mean()          # pooled
home_adv = league_avg_xg_home / league_avg_xg_away     # guard ÷0

# Dixon-Coles ρ: start at -0.18 (literature default); will be re-fit
# per 10-parallel-validation.md after ~4 weeks of production data.
rho_dc = get_or_init_rho_dc(league_id, season)

return {
    'league_id': league_id,
    'season': season,
    'league_avg_xg_for': league_avg_xg_for,
    'league_avg_xg_home': league_avg_xg_home,
    'league_avg_xg_away': league_avg_xg_away,
    'home_adv': home_adv,
    'rho_dc': rho_dc,
    'n_matches': n_matches,
    'last_updated': iso_now(),
}
```

### `fit_team_xg_params`

```
team_rows = match_stats_df filtered to team_id
n = len(team_rows)
n_home = (team_rows['is_home'] == True).sum()
n_away = n - n_home

if n == 0:
    # Cold-start: pure league mean
    return {
        'mu_xg_for':        league_params['league_avg_xg_for'],
        'mu_xg_against':    league_params['league_avg_xg_for'],   # symmetric
        'mu_xg_for_home':   league_params['league_avg_xg_home'],
        'mu_xg_against_home': league_params['league_avg_xg_away'], # what away teams score at this venue on average
        'mu_xg_for_away':   league_params['league_avg_xg_away'],
        'mu_xg_against_away': league_params['league_avg_xg_home'],
        'n_matches': 0, 'n_matches_home': 0, 'n_matches_away': 0,
        'data_quality': 'cold_start',
        ...
    }

# Raw means
raw_xg_for = team_rows['xg_for'].mean()
raw_xg_against = team_rows['xg_against'].mean()
raw_xg_for_home = team_rows[team_rows.is_home].xg_for.mean()   if n_home else league_params['league_avg_xg_home']
raw_xg_for_away = team_rows[~team_rows.is_home].xg_for.mean()  if n_away else league_params['league_avg_xg_away']
raw_xg_against_home = team_rows[team_rows.is_home].xg_against.mean()  if n_home else league_params['league_avg_xg_away']
raw_xg_against_away = team_rows[~team_rows.is_home].xg_against.mean() if n_away else league_params['league_avg_xg_home']

# Shrinkage toward league mean
K = 10  # SHRINKAGE_K constant
def shrink(team_mean, league_mean, n_sub):
    w = n_sub / (n_sub + K)
    return w * team_mean + (1 - w) * league_mean

mu_xg_for         = shrink(raw_xg_for,         league_params['league_avg_xg_for'],  n)
mu_xg_against     = shrink(raw_xg_against,     league_params['league_avg_xg_for'],  n)
mu_xg_for_home    = shrink(raw_xg_for_home,    league_params['league_avg_xg_home'], n_home)
mu_xg_for_away    = shrink(raw_xg_for_away,    league_params['league_avg_xg_away'], n_away)
mu_xg_against_home = shrink(raw_xg_against_home, league_params['league_avg_xg_away'], n_home)
mu_xg_against_away = shrink(raw_xg_against_away, league_params['league_avg_xg_home'], n_away)

# data_quality flag
proxy_fraction = (team_rows['xg_source'] == 'sot_proxy').mean()
if n < 10:
    data_quality = 'sparse'
elif proxy_fraction > 0.2:
    data_quality = 'sot_proxy'
else:
    data_quality = 'full'

return {
    'team_id': team_id,
    'league_season': f'{league_id}#{season}',
    'league_id': league_id, 'season': season,
    'mu_xg_for': mu_xg_for, 'mu_xg_against': mu_xg_against,
    'mu_xg_for_home': mu_xg_for_home, 'mu_xg_against_home': mu_xg_against_home,
    'mu_xg_for_away': mu_xg_for_away, 'mu_xg_against_away': mu_xg_against_away,
    'n_matches': n, 'n_matches_home': n_home, 'n_matches_away': n_away,
    'data_quality': data_quality,
    'last_updated': iso_now(),
}
```

### `run_fit_for_league`

```
1. Load all match_statistics items for this league/season via the
   league_season_date_idx GSI. Build DataFrame.
2. Derive opp_team_id per row: for each fixture, the two team rows
   are each other's opponent. Join on fixture_id.
3. Derive is_home per row: look up fixture_id → home_team_id in the
   `game_fixtures` table (or store is_home directly in match_statistics
   during ingestion to avoid the join).
4. fit_league_xg_params(league_id, season, df)  → write to
   football_league_xg_parameters_prod.
5. For each unique team_id in df:
     fit_team_xg_params(team_id, league_id, season, df, league_params)
     → write to football_team_xg_parameters_prod.
6. Log counts and quality-flag distribution.
```

### Form decay placement

The fitter produces **unweighted means** (each match counted once). Form decay is applied at prediction time in the engine ([06](./06-engine-core.md)), not here. This mirrors V1's structure and keeps the fitter a pure aggregation function.

If we later decide to move decay into the fit, the fitter is the right place to put it and the engine needs no change.

## Implementation details

- **Storage**: use boto3 `Table.batch_writer()` for writes. On-demand billing = no capacity tuning.
- **Is_home derivation**: simplest to store `is_home` directly in `match_statistics` during ingestion (add to [03](./03-stats-ingestion.md) item shape) instead of joining to `game_fixtures` at fit time. Include it in the backfill too.
- **Season handling**: `season` in this codebase is the start year of the season (e.g. `2025` for 2025-26 season). Match the existing convention.
- **Fitting only high-confidence data**: for v1 production of xG params, include all ingested rows. Data-quality flag differentiates reliability downstream.

## Test plan

- [ ] Unit test: `fit_league_xg_params` against EPL SQLite subset — verify `league_avg_xg_for` ≈ 1.39 (from our Phase 1 analysis of EPL 664 team-fixtures, mean 1.39).
- [ ] Unit test: `fit_team_xg_params` for Man City EPL 2025 — verify `mu_xg_for` is elite-tier (>1.8), `mu_xg_against` is low (<1.0), `data_quality` == 'full'.
- [ ] Unit test: shrinkage — for a team with n=3 matches, verify `mu_xg_for` is closer to league mean than to the raw team mean.
- [ ] Unit test: cold-start — team with n=0 returns league means and `data_quality == 'cold_start'`.
- [ ] Unit test: SPARSE — a Slovakia team with ~17 matches and 50% sot_proxy returns `data_quality == 'sot_proxy'`.

## Dependencies

- Blocks on task 1.1–1.3 (tables exist) and 1.4–1.6 (data is in the tables).
- Blocks Phase 2.6–2.9 (the lambda that wraps this module).

## Acceptance criteria

`fit_league_xg_params` and `fit_team_xg_params` produce correct outputs on our existing SQLite data (verified by unit test), and `run_fit_for_league` successfully writes to DynamoDB when called with a real league_id/season.

## Rollback

Delete all items from both param tables. Downstream engine will detect missing params and skip V2 for affected fixtures. V1 is unaffected.
