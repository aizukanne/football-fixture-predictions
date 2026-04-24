# 06 — V2 Engine Core (λ Math, Poisson, Dixon-Coles)

## Objective

Implement the V2 prediction engine as a standalone module with zero code shared with V1's `prediction_engine.py`. It takes the fitted xG parameters and produces the same output shape as V1's `calculate_coordinated_predictions`.

## Files created

- `src/prediction/xg_engine.py` — the engine.
- `tests/test_xg_engine.py` — unit tests.

## Files modified

None.

## Public API

Mirrors V1's `calculate_coordinated_predictions` signature so the orchestrator in [07](./07-engine-integration.md) can call it interchangeably per variant.

```python
def calculate_coordinated_predictions_xg(
    home_team_xg_stats: List[float],      # recent xG_for stream for form decay
    away_team_xg_stats: List[float],
    home_params: Dict,                    # team xG params OR league xG params (variant-dependent)
    away_params: Dict,
    league_params: Dict,                  # league xG params (always present)
    league_id: int,
    season: int = None,
    home_team_id: int = None,
    away_team_id: int = None,
    prediction_date: datetime = None,
    skip_home_adv: bool = False,
) -> Tuple[
    float,  # home_score_prob
    int,    # home_predicted_goals (mode)
    float,  # home_likelihood (prob of mode)
    Dict[int, float],  # home_probs {0..10: prob}
    float,  # away_score_prob
    int,    # away_predicted_goals
    float,  # away_likelihood
    Dict[int, float],  # away_probs
    Dict,   # coordination_info (xg-specific metadata)
]:
    """V2 xG-based coordinated predictions."""
```

The 9-tuple shape matches V1 exactly so the integration in [07](./07-engine-integration.md) is symmetric.

## Algorithm

```
# 1. Extract means. For variants V2a/V2c, home_params == league_params
#    (with a few semantic tweaks — see integration doc). For V2b/V2d,
#    home_params is the team-specific fit. The math is the same either way.
mu_atk_home   = home_params['mu_xg_for']        # or mu_xg_for_home for venue variants
mu_def_home   = home_params['mu_xg_against']    # same
mu_atk_away   = away_params['mu_xg_for']
mu_def_away   = away_params['mu_xg_against']
league_avg    = league_params['league_avg_xg_for']
home_adv      = league_params['home_adv']

# 2. Form decay on the recent xG streams. Mirrors V1's 0.9^i weighting.
#    If the stream is empty (cold-start), form_multiplier_H = 1.0.
form_mult_H = compute_form_multiplier(home_team_xg_stats, mu_atk_home)
form_mult_A = compute_form_multiplier(away_team_xg_stats, mu_atk_away)

# 3. Core λ — the F3 pooled-ratio formula validated in our walk-forward tests.
lambda_H = mu_atk_home * mu_def_away / league_avg
lambda_A = mu_atk_away * mu_def_home / league_avg

# 4. Apply form decay
lambda_H *= form_mult_H
lambda_A *= form_mult_A

# 5. Home advantage — chance-creation multiplier, not finishing.
#    skip_home_adv is TRUE when the input data is already venue-filtered
#    (variants V2c/V2d) — the venue effect is already inside mu_atk_home /
#    mu_def_away_at_away etc.
if not skip_home_adv:
    lambda_H *= math.sqrt(home_adv)
    lambda_A /= math.sqrt(home_adv)

# 6. Sanity bounds (inherits V1's squash_lambda for extreme values)
lambda_H = squash_lambda(lambda_H)   # reuse src/statistics/distributions.squash_lambda
lambda_A = squash_lambda(lambda_A)

# 7. Compute the joint goal-probability matrix with Dixon-Coles correction.
joint_probs = dixon_coles_joint_probs(lambda_H, lambda_A, rho=league_params['rho_dc'])
# joint_probs[h][a] = P(home=h, away=a) for h,a in 0..MAX_GOALS

# 8. Marginalize.
home_probs = { h: sum(joint_probs[h][a] for a in range(MAX_GOALS+1))
               for h in range(MAX_GOALS+1) }
away_probs = { a: sum(joint_probs[h][a] for h in range(MAX_GOALS+1))
               for a in range(MAX_GOALS+1) }

home_score_prob = 1 - home_probs[0]
away_score_prob = 1 - away_probs[0]
home_predicted_goals = max(home_probs, key=home_probs.get)
away_predicted_goals = max(away_probs, key=away_probs.get)
home_likelihood = home_probs[home_predicted_goals]
away_likelihood = away_probs[away_predicted_goals]

coordination_info = {
    'engine_version': 'v2-xg',
    'lambda_H': lambda_H,
    'lambda_A': lambda_A,
    'home_adv_applied': not skip_home_adv,
    'form_multiplier_H': form_mult_H,
    'form_multiplier_A': form_mult_A,
    'rho_dc': league_params['rho_dc'],
    'data_quality_home': home_params.get('data_quality', 'unknown'),
    'data_quality_away': away_params.get('data_quality', 'unknown'),
    'prediction_timestamp': int(time.time()),
}
return (home_score_prob, home_predicted_goals, home_likelihood, home_probs,
        away_score_prob, away_predicted_goals, away_likelihood, away_probs,
        coordination_info)
```

## Form decay function

Same shape as V1's `calculate_team_form`, adapted to operate on an xG stream.

```python
def compute_form_multiplier(recent_xg_stream, baseline_xg, decay=0.9, max_matches=10):
    """Weight recent matches' xG vs baseline; return a multiplier near 1.0.

    Stream is ordered most-recent-first. Weighted mean / baseline gives a
    multiplier: >1 if team is in hot form, <1 if in cold form.
    """
    if not recent_xg_stream or baseline_xg <= 0:
        return 1.0

    xs = recent_xg_stream[:max_matches]
    weights = [decay ** i for i in range(len(xs))]
    weighted_avg = sum(x * w for x, w in zip(xs, weights)) / sum(weights)
    # Clamp to [0.7, 1.3] to prevent runaway hot-streak bias
    return max(0.7, min(1.3, weighted_avg / baseline_xg))
```

## Dixon-Coles correction

Standard DC (Dixon & Coles 1997) low-score adjustment. Pure function, ~15 lines.

```python
def dixon_coles_joint_probs(lambda_h, lambda_a, rho, max_goals=MAX_GOALS):
    """Compute the joint P(H=h, A=a) table with DC low-score correction.

    DC multiplies the independent-Poisson joint probability by tau(h, a):
        tau(0,0) = 1 - lambda_h * lambda_a * rho
        tau(0,1) = 1 + lambda_h * rho
        tau(1,0) = 1 + lambda_a * rho
        tau(1,1) = 1 - rho
        tau(h,a) = 1 otherwise

    rho is typically negative (~-0.18) — makes low scores slightly more
    likely, high scores slightly less.
    """
    joint = {}
    for h in range(max_goals + 1):
        joint[h] = {}
        for a in range(max_goals + 1):
            p = poisson_pmf(h, lambda_h) * poisson_pmf(a, lambda_a)
            tau = _dc_tau(h, a, lambda_h, lambda_a, rho)
            joint[h][a] = p * tau
    # Renormalize — truncation + tau correction may leave sum != 1.
    total = sum(joint[h][a] for h in joint for a in joint[h])
    if total > 0:
        for h in joint:
            for a in joint[h]:
                joint[h][a] /= total
    return joint


def _dc_tau(h, a, lambda_h, lambda_a, rho):
    if h == 0 and a == 0:
        return 1 - lambda_h * lambda_a * rho
    if h == 0 and a == 1:
        return 1 + lambda_h * rho
    if h == 1 and a == 0:
        return 1 + lambda_a * rho
    if h == 1 and a == 1:
        return 1 - rho
    return 1.0
```

`poisson_pmf` — reuse the existing one in `src/statistics/distributions.py` (clean, well-tested).

## What V2 does NOT do

To prevent anyone from reintroducing V1's layers later:

- **No NB**: pure Poisson. Goals given xG are well-modelled by Poisson (our analysis showed V/M ≈ 1.06 ≈ Poisson).
- **No 1.35 calibration constant**: that was fit for V1's goals-based λ. V2's λ is already calibrated to xG.
- **No opponent stratification**: walk-forward evidence said it hurts.
- **No H2H multiplier**: walk-forward evidence said it hurts.
- **No manager/tactical/archetype multipliers**: our analysis showed they have no detectable signal.
- **No confidence calibration layer** inside the engine: that's a meta-layer external to prediction math. If V1's Phase 6 code is reused to annotate V2 outputs, it must be called *outside* this engine — probably in the integration layer at [07](./07-engine-integration.md).

## Reusing V1 utilities

These can be imported from V1's codebase — they're pure math and carry no V1-specific semantics:

- `src/statistics/distributions.poisson_pmf` — Poisson PMF.
- `src/statistics/distributions.squash_lambda` — sanity bound for extreme λ.
- `src/utils/constants.MAX_GOALS_ANALYSIS` — the `0..10` range.

Everything else must not be imported. No `version_manager`, no `transition_manager`, no smoothing functions (the fitter already produced shrinkage-adjusted means), no phase stacks.

## Unit tests

- [ ] `test_lambda_formula`: given toy params (mu_atk_home=1.5, mu_def_away=1.2, league_avg=1.4, home_adv=1.23, skip=False), verify `lambda_H = 1.5 * 1.2 / 1.4 * sqrt(1.23) ≈ 1.425`.
- [ ] `test_skip_home_adv`: same params with `skip_home_adv=True` → `lambda_H = 1.5 * 1.2 / 1.4 = 1.286` (no home_adv applied).
- [ ] `test_form_multiplier_flat`: recent stream == baseline → multiplier == 1.0.
- [ ] `test_form_multiplier_hot`: recent stream all above baseline → multiplier > 1.0, clamped at 1.3.
- [ ] `test_form_multiplier_cold`: all below baseline → <1.0, clamped at 0.7.
- [ ] `test_dc_tau_cases`: verify the five cases match the formula.
- [ ] `test_joint_probs_sum_to_1`: sum over full grid == 1.0 to 1e-9.
- [ ] `test_marginals`: `sum_a joint[h][a]` for each h should be close to Poisson(h, lambda_h) with small DC-induced perturbation.
- [ ] `test_end_to_end_epl`: pull one real EPL fixture from `match_statistics`, use fitted params, run full engine, verify output shape and reasonable probabilities (e.g. `home_score_prob + P(0-0 | some perspective)` in the right ballpark).

## Dependencies

- Blocks on 04 (parameter shape definition).
- Does not require any production data; unit tests run on synthetic inputs.

## Acceptance criteria

Unit tests all pass. Manual test on one EPL fixture produces sensible numbers (both teams ~50-70% scoring probability, predicted_goals in range 0-3, joint probs sum to 1).

## Rollback

Not applicable — pure library code. If V2 misbehaves in production, disable it at [07](./07-engine-integration.md) (wrap the call in early-return).
