# 05 — Fitter Lambda and EventBridge Schedule

## Objective

Package [04's](./04-xg-parameter-fitter.md) `xg_fitter` module into a scheduled lambda that runs weekly and refreshes all team + league xG parameters.

## Files created

- `src/handlers/xg_parameter_handler.py` — lambda handler.
- `scripts/deploy_xg_parameter_lambda.sh` — deploy script (follow existing `scripts/deploy_*.sh` conventions).
- `scripts/create_xg_fitter_schedule.sh` — EventBridge rule creation.

## Files modified

None to existing code. New lambda is entirely additive.

## The handler

```python
# src/handlers/xg_parameter_handler.py
"""
Weekly xG parameter fitter lambda.

Triggered by EventBridge rule `football-xg-parameter-weekly-prod` on
Wednesdays at 05:00 UTC (after daily match-results at 04:00 UTC, which
is itself after the V1 team-parameter fit at 03:00).

Iterates over all leagues in leagues.py; for each, calls
run_fit_for_league() which reads match_statistics, computes params,
writes to football_team_xg_parameters_prod and football_league_xg_parameters_prod.
"""

import json
import traceback
from datetime import datetime

from leagues import allLeagues
from src.parameters.xg_fitter import run_fit_for_league
from src.utils.constants import CURRENT_SEASONS  # { league_id: season_year }


def lambda_handler(event, context):
    start = datetime.utcnow()
    leagues_processed = 0
    leagues_failed = []

    # Allow a single-league invocation via event (for retries / manual runs)
    if event.get('league_id'):
        target_leagues = [(event['league_id'], event['season'])]
    else:
        target_leagues = [
            (lg['id'], CURRENT_SEASONS.get(lg['id']))
            for country, lgs in allLeagues.items()
            for lg in lgs
        ]

    for league_id, season in target_leagues:
        if season is None:
            print(f"Skipping league {league_id}: no current season known")
            continue
        try:
            print(f"Fitting xG params for league {league_id} season {season}")
            run_fit_for_league(league_id, season)
            leagues_processed += 1
        except Exception as e:
            print(f"Fit failed for league {league_id}: {e}")
            traceback.print_exc()
            leagues_failed.append({'league_id': league_id, 'error': str(e)})

    elapsed = (datetime.utcnow() - start).total_seconds()
    result = {
        'leagues_processed': leagues_processed,
        'leagues_failed': leagues_failed,
        'elapsed_seconds': elapsed,
    }
    print(json.dumps(result))
    return result
```

### Per-league failure isolation

If one league's fit fails (bad data, sudden schema issue), it does not block the others. Failures are logged and surfaced in the return value, which CloudWatch retains.

### Manual invocation

Passing `{"league_id": 39, "season": 2025}` in the EventBridge event (or via `aws lambda invoke`) fits just that one league. Useful for one-off re-fits or debugging.

## `CURRENT_SEASONS` constant

Add to `src/utils/constants.py`:

```python
# Current season by league_id. Updated manually when seasons roll over.
# Nordic leagues (Norway, Sweden) run on calendar year, rest on split-year.
CURRENT_SEASONS = {
    # Default for most European leagues
    **{lg['id']: 2025 for country, lgs in allLeagues.items() for lg in lgs},
    # Overrides for Nordic schedule
    103: 2026,  # Norway Eliteserien
    113: 2026,  # Sweden Allsvenskan
}
```

Alternative: store current-season state in DynamoDB or read it dynamically via `/leagues?id=X&current=true` at lambda cold-start. The latter avoids manual maintenance but adds an API call per league. For first release, the constant is simpler.

## Lambda deployment

Match existing convention. Each existing lambda has a deploy script under `scripts/`. The new lambda needs:

- **Name**: `football-xg-parameter-fitter-prod`
- **Runtime**: Python 3.x (match existing lambdas)
- **Handler**: `src.handlers.xg_parameter_handler.lambda_handler`
- **Memory**: 1024 MB (start; scale up if fitting 28 leagues takes too long)
- **Timeout**: 900 seconds (15 min; plenty for 28 small fits)
- **IAM role**: existing `football-prediction-lambda-role` (or equivalent) extended with `PutItem` / `BatchWriteItem` / `Query` / `Scan` permissions on the three new tables from [01](./01-dynamodb-tables.md).
- **Env vars**: `AWS_REGION=eu-west-2`, `TABLE_PREFIX=football_`, `TABLE_SUFFIX=_prod`, `RAPIDAPI_KEY` (inherited — not used by this lambda unless future re-fetches needed).
- **VPC**: match existing lambdas' VPC config if any.

Deploy via the repo's existing lambda deploy pattern. Inspect one of the `scripts/deploy_*.sh` scripts for the exact command pattern, then adapt.

## EventBridge schedule

**Rule name**: `football-xg-parameter-weekly-prod`
**Cron**: `cron(0 5 ? * WED *)` (Wednesday 05:00 UTC). Chosen to run AFTER the daily match-results ingestion (which fires at 04:00 UTC every day and writes Tuesday's matches into `football_match_statistics_prod` on Wednesday) so the weekly fit always includes through-Tuesday data.
**Target**: the new lambda.
**Input**: empty `{}` → fits all leagues in `allLeagues`.

```bash
aws events put-rule \
  --name football-xg-parameter-weekly-prod \
  --schedule-expression 'cron(0 5 ? * WED *)' \
  --region eu-west-2 \
  --description "Weekly refresh of xG-based team and league parameters"

aws events put-targets \
  --rule football-xg-parameter-weekly-prod \
  --region eu-west-2 \
  --targets "Id"="1","Arn"="arn:aws:lambda:eu-west-2:985019772236:function:football-xg-parameter-fitter-prod"

aws lambda add-permission \
  --function-name football-xg-parameter-fitter-prod \
  --statement-id AllowEventBridgeWeekly \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:eu-west-2:985019772236:rule/football-xg-parameter-weekly-prod \
  --region eu-west-2
```

## Test plan

- [ ] Local smoke test: import and run `run_fit_for_league(39, 2025)` against real DynamoDB (after Phase 1 backfill) — verify both param tables are populated for EPL.
- [ ] Manual invoke of the deployed lambda with `{"league_id": 39, "season": 2025}` — verify CloudWatch logs show fit progress, tables populated.
- [ ] Full manual invoke with empty event — verify all 28 kept leagues fit without errors. Expected runtime: under 5 minutes for all 28.
- [ ] Verify EventBridge rule is `ENABLED` and next-run timestamp falls on next Wednesday 05:00 UTC.
- [ ] Wait for first scheduled run. Verify it produces identical outputs to the manual run (modulo `last_updated` timestamps).

## Dependencies

- Blocks on 04 (fitter module complete).
- Blocks on Phase 1 tables and backfill.
- Blocks Phase 3.3–3.4 (engine needs fitted params to consume).

## Acceptance criteria

The EventBridge rule exists, the lambda is deployed, a manual invocation successfully populates both param tables for all 28 leagues within the timeout, and CloudWatch logs show no errors.

## Rollback

Disable the EventBridge rule (`aws events disable-rule`). Lambda remains deployed but never runs. Param tables stop updating. Engine [06](./06-engine-core.md) continues to read stale params; V1 is unaffected. To fully roll back: delete the rule and lambda.

## Cost

Lambda: weekly 1-minute run at 1 GB memory. ~$0.00/month.
EventBridge: 1 rule, 4 invocations/month. Free tier.
DynamoDB: writes are on-demand, ~28 × ~20 team items + 28 league items per run ≈ 588 writes/week. Free tier.
