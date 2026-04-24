# 10 — Parallel Validation and Cutover

## Objective

Run V1 and V2 side-by-side, measure which one actually produces better predictions against real match outcomes, re-fit Dixon-Coles ρ from production data, and document a cutover decision.

The user has a separate analytics system that consumes the prediction records. Accuracy measurement happens there, not in this repo. This guide covers only what *this* codebase needs to expose for the external system to compare V1 and V2, plus the in-repo tasks: ρ re-fit and cutover documentation.

## What this repo provides for the external analytics

Per [08](./08-output-schema.md), every fixture's DynamoDB record contains:
- 4 V1 prediction summaries (`predictions`, `alternate_predictions`, `venue_predictions`, `venue_alternate_predictions`)
- 4 V2 prediction summaries (`xg_predictions`, `xg_alternate_predictions`, `xg_venue_predictions`, `xg_venue_alternate_predictions`)
- Actual match outcome (home_goals, away_goals) added by the post-match handler once games finish

That's all the external analytics needs to compute Brier score, log-loss, MAE, or any other accuracy metric for all 8 variants over time.

No additional fields are needed for the parallel comparison. The analytics system can distinguish V1 vs V2 purely by attribute-name prefix.

## Parallel-run observation window

**Duration**: 4 weeks from the day Phase 3.10 completes.

**Why 4 weeks**:
- Most kept leagues play 1 matchday per week (~10 fixtures per league per week).
- 28 leagues × ~10 fixtures × 4 weeks ≈ 1,120 new fixtures.
- Big-5 leagues alone give ~300-400 fixtures — enough for tight CIs on Brier/log-loss comparisons.
- Short enough that stakeholders aren't waiting forever; long enough that one-week weirdness (injuries, upsets) averages out.

**During the window**:
- Do not disable V1.
- Do not tune V2 on observed production errors (no cherry-picking).
- Only task from this repo: collect enough fixtures for (a) the external analytics comparison, (b) the ρ re-fit at the 4-week mark.

## Dixon-Coles ρ re-fit

At the end of week 4, for each league, re-fit `rho_dc` from the accumulated joint-outcome data.

### Why re-fit

The initial `rho_dc = -0.18` is a literature default (Dixon & Coles 1997, average across multiple European leagues). Individual leagues have different low-score patterns:

- Leagues with low average goal rate (La Liga 2.6, Serie A 2.4) tend to have more 0-0 and 1-0 → more negative ρ.
- High-scoring leagues (Eredivisie 3.3, Bundesliga 3.2) have fewer 0-0 → less negative or near-zero ρ.

Using one global −0.18 works but is slightly sub-optimal per league.

### Re-fit procedure

For each league with sufficient data (target: ≥30 finished fixtures in the parallel-run window):

1. Pull from `football_game_fixtures_prod`: `fixture_id, home_goals, away_goals, xg_coordination_info.v2a.lambda_H, xg_coordination_info.v2a.lambda_A`.
2. For candidate ρ values in `[-0.30, -0.25, -0.20, -0.15, -0.10, -0.05, 0.00]`:
   - Compute DC joint-prob matrix for every fixture using that ρ and the predicted λ pair.
   - Sum log-likelihood of actual `(home_goals, away_goals)` outcome under each ρ.
3. Pick the ρ that maximizes log-likelihood.
4. Write the new ρ to `football_league_xg_parameters_prod` (update the `rho_dc` attribute).

This is a small standalone script: `scripts/refit_dixon_coles_rho.py`. Not scheduled; run manually at the 4-week milestone, and again ~quarterly thereafter as data accumulates.

### Effect on V2 predictions

Negligible day-to-day — ρ tweaks only affect the four low-score cells (0,0), (0,1), (1,0), (1,1) and only by a few percentage points each. But systematically gets BTTS-no, 0-0-exact-score, and totals-under-2.5 predictions a bit closer to reality per league.

## Cutover decision

At the end of week 4, the external analytics produces a summary something like:

| Variant | Brier score | Log-loss | MAE on predicted_goals |
|---|---|---|---|
| V1a (predictions) | … | … | … |
| V2a (xg_predictions) | … | … | … |
| … | … | … | … |

Four possible outcomes per variant pair:

1. **V2 beats V1 clearly** (Brier diff > 1%, consistent across Tier A leagues, log-loss and MAE agree). → Promote that V2 variant: downstream consumers default to `xg_*` attributes. Keep writing V1 for another release cycle for rollback safety.
2. **V2 matches V1 within noise** (Brier diff < 0.5%, CIs overlap). → Keep both running indefinitely. Downstream chooses per their own A/B framework. No cutover.
3. **V2 loses to V1** (Brier worse by > 1%). → Don't promote. Investigate: data-quality issues? wrong λ formula? insufficient history? Before reverting V2, check whether the loss is concentrated in Tier C leagues (then limit V2 to Tier A/B) or uniform (then debug the math).
4. **Mixed — V2 wins in some variants, loses in others** (e.g., V2a > V1a but V2c < V1c). → Promote the winners, deprecate the losers. Each variant independently gated.

### What to document after the window

Write to `docs/v2/CUTOVER_DECISION.md` (new file; not planned in advance because its content depends on data):

- Summary table of Brier / log-loss / MAE per variant per league-tier.
- Decision: which variants are promoted / kept parallel / deprecated.
- Rationale.
- Next-review date (typically 3 months).

## Ongoing monitoring (post-cutover)

Even after any promotion, keep these light-weight checks:

- **CloudWatch alarm**: V2 lambda error rate > 1% over 5 min → page.
- **CloudWatch alarm**: stats ingestion failure > 10 fixtures in a day → email.
- **CloudWatch alarm**: fitter lambda duration > 10 min (should be < 5) → investigate.
- **Weekly CloudWatch log review**: skim `v2_failed` entries in prediction lambda logs; look for patterns.

## Don't do

- Don't tune λ formulas or parameters mid-window based on observed errors. That's cherry-picking. If an obvious bug is found (e.g., a missing factor), fix it and reset the window.
- Don't deprecate V1 during the window. Parallel means parallel.
- Don't conflate "V2 produces different numbers from V1" with "V2 is wrong". V2 is deliberately different. The question is only whether it's more accurate against real outcomes.

## Test plan

- [ ] After Phase 3.10, spot-check 5 fixtures in DynamoDB: V1 and V2 outputs both present, both look plausible.
- [ ] Week 1: confirm external analytics is reading both and can compute Brier for both. (Check with the external system's owner.)
- [ ] Week 4: verify enough fixtures have accumulated per league (≥30 finished for Tier A; waive for SPARSE leagues).
- [ ] Run ρ re-fit script, inspect the ρ distribution per league (expect most in [-0.25, -0.10]). Update `football_league_xg_parameters_prod`.
- [ ] Author `CUTOVER_DECISION.md`.

## Dependencies

- Blocks on Phase 3.10 (V2 live in production).
- Does not block anything else — this is the terminal task.

## Acceptance criteria

- `football_league_xg_parameters_prod.rho_dc` contains re-fit values per league (not all `-0.18`).
- `docs/v2/CUTOVER_DECISION.md` exists with a clear decision per variant.
- Monitoring alarms are live in CloudWatch.

## Rollback

If after the window V2 is universally worse or unstable:
1. Disable the V2 block in `prediction_handler.process_fixtures` by short-circuiting its `try`.
2. `xg_*` attributes stop being written.
3. Disable `football-xg-parameter-weekly-prod` EventBridge rule.
4. Keep the tables and accumulated data — cheap to keep, expensive to rebuild if we change our mind.
5. Record the rollback decision in `CUTOVER_DECISION.md`.
