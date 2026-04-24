# 07 — Engine Integration (wiring the 4 V2 variants)

## Objective

Call [06](./06-engine-core.md)'s engine four times per fixture inside the existing `process_fixtures` loop, after the four V1 variants, writing results to the same DynamoDB item under `xg_*` attributes.

## Files created

- `src/data/xg_data_access.py` — DB readers for the new tables.

## Files modified

- `src/handlers/prediction_handler.py` — add the V2 block after the existing V1 blocks.

## The 2×2 variant matrix

Same shape as V1. Each variant is a combination of two independent choices:

| Variant | Params source | Match stats window | Corresponds to V1 |
|---|---|---|---|
| V2a | `league_xg_params` (league fit) | pooled (all matches) | predictions |
| V2b | `team_xg_params` (team fit) | pooled (all matches) | alternate_predictions |
| V2c | `league_xg_params` | home-only for home / away-only for away | venue_predictions |
| V2d | `team_xg_params` | same as V2c | venue_alternate_predictions |

For V2a: we pass the league's average values (`league_avg_xg_for` etc.) as if they were the team's params — this is the V1 pattern where `home_league_params` gets used when we don't trust team-specific data. For V2c/V2d: `skip_home_adv=True` because venue-filtered means already encode the home-vs-away difference.

## DB reader module

```python
# src/data/xg_data_access.py
"""Read helpers for V2's new DynamoDB tables. Separated from V1's
data/db_reader so engines can't accidentally cross-contaminate."""

import boto3
from boto3.dynamodb.conditions import Key
from typing import Optional, Dict, List

from ..utils.constants import (
    MATCH_STATISTICS_TABLE,
    TEAM_XG_PARAMETERS_TABLE,
    LEAGUE_XG_PARAMETERS_TABLE,
)

_ddb = boto3.resource('dynamodb', region_name='eu-west-2')


def get_team_xg_params(team_id: int, league_id: int, season: int) -> Optional[Dict]:
    """Fetch fitted xG params for a team. Returns None if missing."""
    table = _ddb.Table(TEAM_XG_PARAMETERS_TABLE)
    resp = table.get_item(Key={
        'team_id': team_id,
        'league_season': f'{league_id}#{season}',
    })
    return resp.get('Item')


def get_league_xg_params(league_id: int, season: int) -> Optional[Dict]:
    table = _ddb.Table(LEAGUE_XG_PARAMETERS_TABLE)
    resp = table.get_item(Key={'league_id': league_id, 'season': season})
    return resp.get('Item')


def fetch_team_xg_stream(
    team_id: int, league_id: int, season: int,
    venue: Optional[str] = None,           # 'home' | 'away' | None
    limit: int = 38,
) -> List[float]:
    """Recent xG_for stream, most-recent-first. Used for form decay.

    Queries football_match_statistics_prod's GSI by league_season, filters
    to matches involving this team, returns a list of xG values ordered
    most-recent-first.
    """
    table = _ddb.Table(MATCH_STATISTICS_TABLE)
    items = table.query(
        IndexName='league_season_date_idx',
        KeyConditionExpression=Key('league_season').eq(f'{league_id}#{season}'),
        ScanIndexForward=False,   # newest first
        Limit=limit * 2,          # each fixture has 2 team items
    ).get('Items', [])
    # Filter to this team; optionally to venue
    stream = []
    for it in items:
        if it['team_id'] != team_id:
            continue
        if venue == 'home' and not it.get('is_home'):
            continue
        if venue == 'away' and it.get('is_home'):
            continue
        stream.append(float(it['expected_goals']))
        if len(stream) >= limit:
            break
    return stream
```

Note: `expected_goals` is stored as Decimal by DynamoDB; the cast to `float` is required for the engine's math.

## Integration in `process_fixtures`

Add a new block immediately after the existing `venue_alternate_predictions` block (~line 427 of `src/handlers/prediction_handler.py` in the existing code path) and before the "Add additional fixture data" section at line 430.

```python
# =================================================================
# V2 XG-BASED PREDICTION CALCULATION (4 VARIANTS)
# Runs in parallel with V1. Never affects V1 outputs.
# =================================================================
try:
    from src.data.xg_data_access import (
        get_team_xg_params, get_league_xg_params, fetch_team_xg_stream,
    )
    from src.prediction.xg_engine import calculate_coordinated_predictions_xg
    from src.prediction.xg_engine import create_xg_prediction_summary_dict

    # Fetch params
    league_xg_params = get_league_xg_params(league_id, season)
    home_xg_params_team = get_team_xg_params(home_team_id, league_id, season)
    away_xg_params_team = get_team_xg_params(away_team_id, league_id, season)

    if not league_xg_params:
        raise RuntimeError(f"No league xG params for league {league_id} season {season}")

    # Fallback: team params default to league params if team fit missing
    home_xg_params_league = _league_params_as_team_shape(league_xg_params)
    away_xg_params_league = _league_params_as_team_shape(league_xg_params)
    home_xg_params_team = home_xg_params_team or home_xg_params_league
    away_xg_params_team = away_xg_params_team or away_xg_params_league

    # Form streams (pooled & venue-filtered)
    h_xg_stream_total = fetch_team_xg_stream(home_team_id, league_id, season, venue=None)
    a_xg_stream_total = fetch_team_xg_stream(away_team_id, league_id, season, venue=None)
    h_xg_stream_home  = fetch_team_xg_stream(home_team_id, league_id, season, venue='home')
    a_xg_stream_away  = fetch_team_xg_stream(away_team_id, league_id, season, venue='away')

    # --- V2a: league params + pooled stream ---
    (h_score_xg, h_goals_xg, h_lh_xg, h_probs_xg,
     a_score_xg, a_goals_xg, a_lh_xg, a_probs_xg,
     v2a_info) = calculate_coordinated_predictions_xg(
        home_team_xg_stats=h_xg_stream_total,
        away_team_xg_stats=a_xg_stream_total,
        home_params=home_xg_params_league,
        away_params=away_xg_params_league,
        league_params=league_xg_params,
        league_id=league_id, season=season,
        home_team_id=home_team_id, away_team_id=away_team_id,
        prediction_date=date_dt,
        skip_home_adv=False,
    )
    home_team_stats['xg_probability_to_score'] = Decimal(str(h_score_xg))
    away_team_stats['xg_probability_to_score'] = Decimal(str(a_score_xg))
    home_team_stats['xg_predicted_goals'] = h_goals_xg
    away_team_stats['xg_predicted_goals'] = a_goals_xg
    home_team_stats['xg_likelihood'] = Decimal(str(h_lh_xg))
    away_team_stats['xg_likelihood'] = Decimal(str(a_lh_xg))
    xg_prediction_summary = create_xg_prediction_summary_dict(h_probs_xg, a_probs_xg)

    # --- V2b: team params + pooled stream ---
    (..., v2b_info) = calculate_coordinated_predictions_xg(
        home_team_xg_stats=h_xg_stream_total, away_team_xg_stats=a_xg_stream_total,
        home_params=home_xg_params_team, away_params=away_xg_params_team,
        league_params=league_xg_params, skip_home_adv=False, ...
    )
    # → xg_probability_to_score_alt, xg_predicted_goals_alt, xg_likelihood_alt,
    #   xg_alternate_predictions

    # --- V2c: league params + venue stream ---
    # Uses venue-filtered streams AND venue-specific mu fields from params.
    home_xg_params_league_venue = _venue_variant(home_xg_params_league, side='home')
    away_xg_params_league_venue = _venue_variant(away_xg_params_league, side='away')
    (..., v2c_info) = calculate_coordinated_predictions_xg(
        home_team_xg_stats=h_xg_stream_home, away_team_xg_stats=a_xg_stream_away,
        home_params=home_xg_params_league_venue, away_params=away_xg_params_league_venue,
        league_params=league_xg_params, skip_home_adv=True, ...
    )
    # → xg_probability_to_score_venue, xg_predicted_goals_venue, xg_likelihood_venue,
    #   xg_venue_predictions

    # --- V2d: team params + venue stream ---
    home_xg_params_team_venue = _venue_variant(home_xg_params_team, side='home')
    away_xg_params_team_venue = _venue_variant(away_xg_params_team, side='away')
    (..., v2d_info) = calculate_coordinated_predictions_xg(...)
    # → xg_probability_to_score_venue_alt, xg_predicted_goals_venue_alt, xg_likelihood_venue_alt,
    #   xg_venue_alternate_predictions

    # Aggregate metadata
    xg_coordination_info = {
        'v2a': v2a_info, 'v2b': v2b_info, 'v2c': v2c_info, 'v2d': v2d_info,
        'xg_engine_version': 'v2-xg-1.0',
    }
    xg_data_quality = _aggregate_quality(
        home_xg_params_team, away_xg_params_team,
        home_xg_params_league, away_xg_params_league,
    )

except Exception as xg_e:
    print(f"V2 xG predictions failed for fixture {fixture_id}: {xg_e}")
    import traceback; traceback.print_exc()
    # No xg_* attributes written. V1 continues normally.
    xg_prediction_summary = None
    xg_alternate_prediction_summary = None
    xg_venue_prediction_summary = None
    xg_venue_alternate_prediction_summary = None
    xg_coordination_info = {'v2_failed': True, 'error': str(xg_e)}
    xg_data_quality = 'unavailable'
```

### Helpers

```python
def _league_params_as_team_shape(league_params):
    """Adapt league params dict to the team params shape the engine expects.
    For V2a: we pretend 'team params' are league averages."""
    return {
        'mu_xg_for':         league_params['league_avg_xg_for'],
        'mu_xg_against':     league_params['league_avg_xg_for'],
        'mu_xg_for_home':    league_params['league_avg_xg_home'],
        'mu_xg_against_home': league_params['league_avg_xg_away'],
        'mu_xg_for_away':    league_params['league_avg_xg_away'],
        'mu_xg_against_away': league_params['league_avg_xg_home'],
        'data_quality':      'league_avg',
    }

def _venue_variant(team_params, side):
    """Replace pooled means with venue-specific ones for V2c/V2d."""
    out = dict(team_params)
    if side == 'home':
        out['mu_xg_for']     = team_params['mu_xg_for_home']
        out['mu_xg_against'] = team_params['mu_xg_against_home']
    else:  # 'away'
        out['mu_xg_for']     = team_params['mu_xg_for_away']
        out['mu_xg_against'] = team_params['mu_xg_against_away']
    return out

def _aggregate_quality(*param_dicts):
    qualities = [p.get('data_quality', 'unknown') for p in param_dicts]
    if 'cold_start' in qualities: return 'cold_start'
    if 'sparse' in qualities:     return 'sparse'
    if 'sot_proxy' in qualities:  return 'sot_proxy'
    return 'full'
```

## `aggregated_fixture_data` updates

Add the four new summary dicts to the final fixture record:

```python
aggregated_fixture_data = {
    # ... existing V1 keys unchanged ...
    "predictions": prediction_summary,
    "alternate_predictions": prediction_summary_alt,
    "venue_predictions": venue_prediction_summary,
    "venue_alternate_predictions": venue_prediction_summary_alt,

    # NEW V2 keys
    "xg_predictions": xg_prediction_summary,
    "xg_alternate_predictions": xg_alternate_prediction_summary,
    "xg_venue_predictions": xg_venue_prediction_summary,
    "xg_venue_alternate_predictions": xg_venue_alternate_prediction_summary,
    "xg_coordination_info": xg_coordination_info,
    "xg_data_quality": xg_data_quality,

    # ... rest unchanged ...
}
```

The per-team stats dicts (already modified above with `xg_*` attributes) flow into `home` and `away` keys as before.

## `create_xg_prediction_summary_dict`

Same shape as V1's `create_prediction_summary_dict` in `src/prediction/prediction_engine.py`. Simplest: reuse V1's function directly — it takes two `probs` dicts and returns a summary. No need to re-implement.

## Deploy

Redeploy `football-fixture-predictions-prod` lambda (or whatever the V1 prediction lambda is called — check `aws lambda list-functions --region eu-west-2`) with the updated `prediction_handler.py` and the new `xg_engine.py` / `xg_data_access.py` files.

## Test plan

- [ ] Unit test `_league_params_as_team_shape`, `_venue_variant`, `_aggregate_quality`.
- [ ] Local integration test: mock the three DB readers, call the new V2 block with realistic inputs, verify all 4 variants produce results and all `xg_*` attributes are populated.
- [ ] Dry-deploy to a non-prod lambda alias or staging; invoke with one real fixture; verify DynamoDB item now has both V1 and V2 attributes.
- [ ] Force an exception in the V2 block (e.g. by deleting params); verify V1 still completes and writes normal output with no `xg_*` attributes (except the `xg_coordination_info.v2_failed: true` diagnostic).
- [ ] Live fixture batch after deploy: spot-check 5 fixtures in DynamoDB, verify all 4 V2 variants produce plausible numbers and V1 numbers match a pre-deploy baseline.

## Dependencies

- Blocks on 06 (engine).
- Blocks on 2.9 (params populated).
- Blocks on 1.1–1.3 + 2.2 (match_statistics populated).

## Acceptance criteria

After deploy, every fixture processed by the lambda produces a DynamoDB item with:
- All V1 attributes unchanged from pre-deploy.
- Exactly 4 new summary dicts: `xg_predictions`, `xg_alternate_predictions`, `xg_venue_predictions`, `xg_venue_alternate_predictions`.
- Per-team stats decorated with 12 new keys (4 suffixes × 3 fields).
- `xg_coordination_info` and `xg_data_quality` fields present.

## Rollback

Revert the prediction handler to the previous version (git). V2 attributes stop being written on new fixtures. Existing fixtures retain whatever they had. V1 is untouched at all times.
