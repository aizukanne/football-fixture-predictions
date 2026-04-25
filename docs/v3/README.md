# V3 — SoT-Based Prediction Engine

V3 is the alternate prediction track that runs alongside V1. V1 stays
primary; V3 produces a parallel prediction sourced from shots-on-target
and per-league pooled conversion rates. The API surfaces V1 as
`predicted_goals` and V3 as `predicted_goals_alt`.

The design grew out of two findings:

1. The legacy 2025-03-21 engine outperformed everything we built on top
   of it in walk-forward backtests. V1 has accumulated layers of
   multipliers (manager, archetype, tactical, confidence calibration)
   plus post-hoc constants (×1.30 boost, ×1.35 calibration) — the
   stack was hard to reason about.
2. The V2 xG engine gave opaque predictions: every fixture trended
   toward "1-1" because of structural choices in how priors were
   combined, and the inputs (xG) were themselves a black-box composite
   we didn't compute.

V3 is the simplest model that uses the SoT signal we requested in the
first place, with all constants derived from the data and zero
hand-tuned per-league multipliers.

---

## The formula

```
λ_H = SoT_H_home × conv × (gc_A_away / lg_avg_gc_away)
λ_A = SoT_A_away × conv × (gc_H_home / lg_avg_gc_home)
```

Per team:
- `goals ~ NegBinomial(λ, α=0.3)`
- `predicted_goals = round(λ)` (clamped to [0, MAX_GOALS_ANALYSIS])

Where the inputs are:

| Symbol | Meaning | Source |
|---|---|---|
| `SoT_H_home` | Home team's avg shots-on-target when playing at home | per-team, weekly fit, k=5 shrinkage |
| `SoT_A_away` | Away team's avg shots-on-target when playing away | per-team, weekly fit, k=5 shrinkage |
| `conv` | League's pooled SoT→goal conversion rate (Σ goals / Σ SoT) | per-league, weekly fit |
| `gc_X` | Team X's avg goals conceded at the relevant venue | per-team, weekly fit, k=5 shrinkage |
| `lg_avg_gc_*` | League's avg goals conceded at the relevant venue | per-league, weekly fit |

The defensive ratio `(gc_X / lg_avg_gc_*)` expresses opponent defence
relative to league average — 1.0 means league-average, >1 means leakier
than average, <1 means stingier.

Markets (1X2, O/U, BTTS) derive from per-team marginals under independence.
**No Dixon-Coles correction, no joint distribution.** This matches the
legacy engine.

---

## What V3 explicitly does NOT do

| Excluded | Why |
|---|---|
| Per-league multipliers | All league-specific calibration sits in `conv` and `lg_avg_gc_*`, both data-derived |
| Country-specific boosts (La Liga, Serbia, Denmark) | Same — opaque hand-tuning |
| Form decay / recency weighting | Aggregate season-to-date averages. Simpler, more robust |
| Dixon-Coles ρ | Legacy didn't use it; V3 follows |
| ×1.02 / ×1.30 / ×1.35 calibration constants | These compensated for V1's deflation; V3's λ is at the right scale by construction |
| Manager / archetype / tactical multipliers | V1 keeps these; V3 is a pure SoT track |

The only V3 constants are **α=0.3** (NB dispersion) and **k=5**
(shrinkage prior weight). Both are global and well-justified.

---

## Why these constants

### α = 0.3 (Negative Binomial dispersion)

Goals are mildly overdispersed: variance/mean ≈ 1.06 in real data.
α=0.3 fits this empirically and matches the legacy engine, which used
the same value. With α=0.3 and λ=1.5, P(3+ goals) ≈ 0.19 (NB) vs 0.19
(Poisson) — the difference is in the tail (P(5+ goals) is ~30% higher
under NB, which matters for high-scoring fixtures).

### k = 5 (cold-start shrinkage)

`shrunk = (n × team_mean + k × league_mean) / (n + k)`.

With k=5 a team needs ~5 real matches to outweigh the league prior.
That's enough to stabilize early-season fits without crushing teams
that are genuinely above/below average. By matchday 10–15 a team's
SoT_for is essentially their own data; k just protects matchday 1–4.

### `conv` as a per-league constant

Across our 27 leagues, the pooled SoT→goal conversion rate ranges from
0.27 (Norway) to 0.34 (Saudi Pro League) — a 26% relative spread. A
single global constant misprices Norway by +21% and Saudi by −8%.
Per-league `conv`, recomputed weekly, removes both errors.

The within-league spread of *team* conversion rates is comparable
(P10–P90 ≈ ±15% around the median). We chose **not** to use per-team
conversion rates because doing so causes SoT to algebraically cancel
out of the formula — `SoT × (goals/SoT) × ratio = goals × ratio` —
which collapses V3 back to a goals-only model and discards the SoT
volume signal entirely. Per-league `conv` keeps SoT volume as the
primary attacking input while still capturing the cross-league
finishing-quality differences.

---

## Data flow

```
match_data_handler (post-match)
    ├─→ updates football_game_fixtures_prod with `goals`
    └─→ writes football_match_statistics_prod (SoT, etc.)

(weekly EventBridge trigger)
sot_parameter_handler.lambda_handler
    └─→ for each league:
            sot_fitter.run_fit_for_league(league_id, season)
                ├─ load_league_match_stats()  ← match_statistics_prod
                ├─ load_fixture_goals()       ← game_fixtures_prod (BatchGetItem)
                ├─ fit_league_sot_params()    → league_sot_parameters_prod
                └─ fit_team_sot_params()      → team_sot_parameters_prod (per team)

(per-fixture, on the prediction queue)
prediction_handler.process_fixtures
    ├─→ V1 (untouched) writes predicted_goals to home/away
    └─→ V3 block:
            get_league_sot_params() + get_team_sot_params() (×2)
            calculate_predictions_sot() → λ_H, λ_A, marginals
            create_sot_prediction_summary_dict() → sot_predictions
            writes sot_predicted_goals etc. to home/away

data_formatter.format_fixture_response
    └─→ predicted_goals      ← home.predicted_goals      (V1, primary)
        predicted_goals_alt  ← home.sot_predicted_goals  (V3, alternate)
```

---

## DynamoDB tables

### `football_match_statistics_prod` (already existed, unchanged)

| Key | Type | Purpose |
|---|---|---|
| `fixture_id` | HASH | per-fixture |
| `team_id` | RANGE | per-team-in-fixture |

GSI: `league_date_idx` (PK=`league_id`, SK=`match_date`).
Used by V3 fitter to scan all rows for a league.

### `football_league_sot_parameters_prod` (NEW)

| Key | Type |
|---|---|
| `league_id` | HASH |

Attributes (all numeric unless noted):
- `season` — int
- `sot_to_goal_conv_rate` — pooled Σgoals/ΣSoT
- `league_avg_sot_for` / `league_avg_sot_home` / `league_avg_sot_away`
- `league_avg_goals_conceded` / `league_avg_goals_conceded_home` / `league_avg_goals_conceded_away`
- `home_adv` — convenience ratio `avg_sot_home / avg_sot_away`
- `n_fixtures`, `n_team_rows`
- `last_updated` — ISO timestamp

### `football_team_sot_parameters_prod` (NEW)

| Key | Type |
|---|---|
| `team_id` | HASH |
| `league_id` | RANGE |

Attributes:
- `season` — int
- `sot_for_home` / `sot_for_away` / `sot_for_all` — Bayesian-shrunk
- `goals_conceded_home` / `goals_conceded_away` / `goals_conceded_all` — Bayesian-shrunk
- `n_matches`, `n_matches_home`, `n_matches_away`
- `data_quality` — `cold_start` | `sparse` | `full`
- `last_updated`

Both parameter tables are **overwritten each weekly run** — the fit is
the single source of truth.

---

## Output schema (per fixture record)

V3 writes alongside V1 in `football_game_fixtures_prod`:

```jsonc
{
  "fixture_id": ...,
  "home": {
    // V1 fields unchanged
    "predicted_goals": 2,
    // V3 additions
    "sot_predicted_goals": 2,
    "sot_probability_to_score": 0.77,
    "sot_likelihood": 0.27,
    ...
  },
  "away": { /* same shape */ },
  "predictions": { /* V1 summary */ },
  "alternate_predictions": { /* V1 alternate summary */ },
  "sot_predictions": { /* V3 summary, schema below */ },
  "sot_data_quality": "full" | "sparse" | "cold_start" | "league_avg" | "unavailable",
  "sot_coordination_info": {
    "v3_enabled": true,
    "engine_version": "v3-sot-1.0",
    "lambda_h": 1.872,
    "lambda_a": 1.208,
    "conv_rate": 0.329,
    "def_ratio_for_h": 1.05,
    "def_ratio_for_a": 0.97,
    "team_params_home_source": "team",
    "team_params_away_source": "team"
  }
}
```

`sot_predictions` follows the same schema as V1's `predictions`
(`most_likely_score`, `expected_goals`, `match_outcome`, `goals.over/under/btts`,
`top_scores`, `odds`) — `most_likely_score` is overridden to match
`round(λ)` per team to avoid the marginal-mode collapse to "1-1".

---

## API surface

`data_formatter.format_fixture_response` (filtered subset, used by
the league-fixtures endpoint):

```jsonc
{
  "home": {
    "predicted_goals": 2,         // V1
    "predicted_goals_alt": 2      // V3
  },
  "away": { /* same */ }
}
```

The single-fixture endpoint returns the full record including all the
V3 attributes above.

---

## Operational notes

### Triggering the weekly fit manually

Single league:
```json
{"league_id": 39, "season": 2025}
```

All leagues (default schedule behavior):
```json
{}
```

### Re-enqueueing fixtures after a fit

The fit only updates the parameter tables — it doesn't trigger
predictions. To get V3 onto already-scheduled fixtures, push them back
through the prediction queue. Use `scripts/reenqueue_fixtures.py`.

### Cold-start behavior

If a team has no fitted record (`get_team_sot_params` returns None),
the engine falls back to `league_params_as_team_fallback(league_params)`
— a team-shaped dict built from league averages. This flags
`data_quality = "league_avg"` in the output, which the frontend can
use to surface lower confidence.

If a league has no fitted record at all, the V3 block raises and
records `sot_coordination_info.v3_failed = true`. V1 output is
unaffected. Run the fitter for that league to recover.

### Verifying a prediction by hand

```
λ_H = SoT_H_home × conv × (gc_A_away / lg_avg_gc_away)
```

Pull the inputs from the parameter tables, plug in. The intermediate
multipliers are surfaced in `sot_coordination_info` for any record
(`lambda_h`, `lambda_a`, `conv_rate`, `def_ratio_for_h`, etc.) so this
should never need a debugger.
