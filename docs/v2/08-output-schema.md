# 08 — Output Schema

## Objective

Pin down the exact attribute names, types, and shapes that V2 writes to the existing `football_game_fixtures_prod` DynamoDB item per fixture. This is the contract the downstream consumers (analytics, UIs, AI analytics) will read from.

## Per-team attributes (inside `home` and `away` dicts)

Each suffix corresponds to one V2 variant. Exactly parallel to V1's naming (which uses no prefix and the same `_alt`, `_venue`, `_venue_alt` suffixes).

| Variant | Attribute name (per-team) | Type | Meaning |
|---|---|---|---|
| V2a | `xg_probability_to_score` | Decimal | P(team scores ≥ 1) |
| V2a | `xg_predicted_goals` | Number | mode of goal distribution |
| V2a | `xg_likelihood` | Decimal | probability of the mode |
| V2b | `xg_probability_to_score_alt` | Decimal | same semantics, team-params variant |
| V2b | `xg_predicted_goals_alt` | Number | |
| V2b | `xg_likelihood_alt` | Decimal | |
| V2c | `xg_probability_to_score_venue` | Decimal | venue-filtered, league params |
| V2c | `xg_predicted_goals_venue` | Number | |
| V2c | `xg_likelihood_venue` | Decimal | |
| V2d | `xg_probability_to_score_venue_alt` | Decimal | venue-filtered, team params |
| V2d | `xg_predicted_goals_venue_alt` | Number | |
| V2d | `xg_likelihood_venue_alt` | Decimal | |

12 new per-team attributes (3 fields × 4 variants).

## Fixture-level attributes

| Attribute | Type | Meaning |
|---|---|---|
| `xg_predictions` | Map | V2a summary — same shape as V1's `predictions` |
| `xg_alternate_predictions` | Map | V2b summary |
| `xg_venue_predictions` | Map | V2c summary |
| `xg_venue_alternate_predictions` | Map | V2d summary |
| `xg_coordination_info` | Map | per-variant metadata (lambdas, form multipliers, ρ, etc.) |
| `xg_data_quality` | String | `'full'` \| `'sot_proxy'` \| `'sparse'` \| `'cold_start'` \| `'unavailable'` |

Note: downstream consumers should treat any missing `xg_*` attribute as "V2 didn't produce for this fixture" — they must not assume presence. See [09](./09-data-quality-and-errors.md) for when V2 legitimately skips a fixture.

## Summary-dict shape

Each of `xg_predictions`, `xg_alternate_predictions`, `xg_venue_predictions`, `xg_venue_alternate_predictions` has the same shape as V1's `predictions` dict. The implementation in [07](./07-engine-integration.md) reuses V1's `create_prediction_summary_dict`, which produces:

```json
{
    "home": {
        "probability_to_score": 0.721,
        "predicted_goals": 1,
        "likelihood": 0.315,
        "goal_probabilities": {"0": 0.279, "1": 0.315, "2": 0.218, "3": 0.112, "4": 0.047, "5": 0.016, "6": 0.005, "7": 0.001, "8": 0.0005, "9": 0.0001, "10": 0.00002},
        "over_1_5": 0.721,
        "over_2_5": 0.406,
        "over_3_5": 0.180,
        "under_2_5": 0.594
    },
    "away": { ... same shape ... },
    "btts_yes": 0.578,
    "btts_no": 0.422,
    "total_goals_over_2_5": 0.651,
    ...
}
```

The inner field names intentionally match V1's — downstream consumers parsing `xg_predictions.home.probability_to_score` use identical code paths to `predictions.home.probability_to_score`. The only thing different between V1 and V2 is the engine producing the numbers.

## `xg_coordination_info` shape

```json
{
    "v2a": {
        "engine_version": "v2-xg",
        "lambda_H": 1.425,
        "lambda_A": 1.086,
        "home_adv_applied": true,
        "form_multiplier_H": 0.98,
        "form_multiplier_A": 1.03,
        "rho_dc": -0.18,
        "data_quality_home": "league_avg",
        "data_quality_away": "league_avg",
        "prediction_timestamp": 1734025823
    },
    "v2b": { ... similar for team params ... },
    "v2c": { ... similar for venue league params ... },
    "v2d": { ... similar for venue team params ... },
    "xg_engine_version": "v2-xg-1.0"
}
```

Equivalent to V1's `coordination_info` for each variant. Used for debugging/analytics; not part of the user-facing prediction.

## Full fixture record shape (V1 + V2)

```json
{
    "fixture_id": 1208399,
    "country": "England",
    "league": "Premier League",
    "league_id": 39,
    "season": 2025,
    "date": "2025-11-02T15:00:00+00:00",
    "venue": { "venue_id": 556, "venue_name": "..." },

    "home": {
        "team_id": 65,
        "team_name": "Nottingham Forest",
        ... existing V1 fields ...
        "probability_to_score": 0.68,
        "probability_to_score_alt": 0.65,
        "probability_to_score_venue": 0.70,
        "probability_to_score_venue_alt": 0.67,
        "predicted_goals": 1, "predicted_goals_alt": 1,
        "predicted_goals_venue": 1, "predicted_goals_venue_alt": 1,
        "likelihood": 0.31, "likelihood_alt": 0.30,
        "likelihood_venue": 0.32, "likelihood_venue_alt": 0.31,

        // NEW V2 attributes:
        "xg_probability_to_score": 0.72,
        "xg_probability_to_score_alt": 0.71,
        "xg_probability_to_score_venue": 0.73,
        "xg_probability_to_score_venue_alt": 0.72,
        "xg_predicted_goals": 1, "xg_predicted_goals_alt": 1,
        "xg_predicted_goals_venue": 1, "xg_predicted_goals_venue_alt": 1,
        "xg_likelihood": 0.32, "xg_likelihood_alt": 0.31,
        "xg_likelihood_venue": 0.33, "xg_likelihood_venue_alt": 0.32,

        ... injuries, past_fixtures, etc. unchanged ...
    },
    "away": { ... same shape ... },

    // V1 fixture-level predictions:
    "predictions": { ... V1 summary ... },
    "alternate_predictions": { ... },
    "venue_predictions": { ... },
    "venue_alternate_predictions": { ... },
    "coordination_info": { ... },
    "prediction_metadata": { ... },

    // NEW V2 fixture-level predictions:
    "xg_predictions": { ... V2a summary ... },
    "xg_alternate_predictions": { ... V2b summary ... },
    "xg_venue_predictions": { ... V2c summary ... },
    "xg_venue_alternate_predictions": { ... V2d summary ... },
    "xg_coordination_info": { ... per-variant metadata ... },
    "xg_data_quality": "full",

    "h2h": [...],
    "timestamp": 1734025823
}
```

## Attribute-name clash check

Verified in [the DynamoDB exploration](./WORKPLAN.md): no existing attribute on `football_game_fixtures_prod` items starts with `xg` or `xG`. The only xG reference in the code is a `.get('pre_sub_xg', 0)` read on an API response in `src/features/tactical_analyzer.py`, which never becomes a stored attribute. Safe.

## DynamoDB item size

V2 adds roughly:
- 12 per-team attributes × 2 teams × ~40 bytes = ~1 KB
- 4 summary dicts × ~2 KB = ~8 KB
- `xg_coordination_info` × ~4 KB = ~4 KB
- Quality flag + small metadata: ~100 bytes

Total additional: **~13 KB per fixture record**.

DynamoDB item size limit is 400 KB. Current records (with 4 V1 variants) are ~50 KB; adding 13 KB of V2 data keeps us well under limit.

## Type handling

Numeric values must be wrapped in `Decimal` before writing (DynamoDB does not accept Python `float` directly — this is standard throughout V1). All 12 per-team numeric attributes and numeric fields inside the summary dicts are `Decimal`.

Use the existing `convert_floats_to_decimal` helper in V1's handler — already imported and in use — to convert the entire V2 output tree before `put_fixture_record`.

## Downstream implications

- **Visualization UI, post-match UI**: can show V1 and V2 side-by-side by reading both prefix/suffix-keyed attributes. May want a toggle "Show V2 predictions" during the parallel-run period.
- **Analytics app**: can compute accuracy on both engines over time using the same fixture records (no schema change to the consumer side).
- **Secondary AI analytics**: whichever prompt template the AI uses will need to be updated if you want it to reason over V2 numbers. Adding the new fields is additive; ignoring them is the default.

## Test plan

- [ ] After deploy, pull one DynamoDB record via `aws dynamodb get-item` and validate JSON shape matches the example above.
- [ ] Verify `home.xg_probability_to_score` and related fields are `Decimal` types (DynamoDB will show as `{"N": "0.72"}`).
- [ ] Verify `xg_predictions` exists as a Map with `home`, `away`, and market-level nested fields.
- [ ] Pull 10 fixtures; verify none have a size exceeding ~80 KB.
- [ ] Confirm with the analytics API (`https://esqyjhhc4e.execute-api.eu-west-2.amazonaws.com/prod/predictions?league_id=39&prediction_type=all`) that it returns the new `xg_*` fields correctly or that the analytics app has been updated to include them.

## Dependencies

- Blocks on 07 (integration writes these attributes).

## Acceptance criteria

All named attributes exist on every fixture record produced by the post-deploy lambda. No V1 attribute was accidentally dropped or renamed. Item size stays under 400 KB.

## Rollback

Revert the prediction handler. Downstream consumers that started depending on `xg_*` fields must tolerate their absence — this should already be the case because V2 is allowed to skip fixtures (see [09](./09-data-quality-and-errors.md)).
