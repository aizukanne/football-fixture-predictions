"""Re-fit the Dixon-Coles rho parameter per league from accumulated production data.

Run manually ~4 weeks into the parallel-run window (and quarterly
thereafter as data accumulates). Overwrites the `rho_dc` attribute on
each league's football_league_xg_parameters_prod row while leaving every
other field untouched.

Methodology: maximum likelihood over observed (home_goals, away_goals)
given each fixture's predicted (lambda_H, lambda_A). For each candidate
rho value, compute the DC-corrected joint log-likelihood across every
finished fixture with V2 predictions and pick the rho that maximizes it.

Usage:
    python scripts/refit_dixon_coles_rho.py [--league-id N] [--dry-run]
        [--min-fixtures 30]
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import boto3
from boto3.dynamodb.conditions import Key

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

os.environ.setdefault("TABLE_PREFIX", "football_")
os.environ.setdefault("TABLE_SUFFIX", "_prod")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")

from src.utils.constants import (  # noqa: E402
    GAME_FIXTURES_TABLE,
    LEAGUE_XG_PARAMETERS_TABLE,
)
from src.prediction.xg_engine import dixon_coles_joint_probs  # noqa: E402


# Candidate rho grid.
RHO_CANDIDATES = [-0.30, -0.25, -0.20, -0.15, -0.10, -0.05, 0.00]


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_fixtures_for_league(league_id: int) -> List[dict]:
    """Load game_fixtures items for a league where V2 predictions were
    written and the actual final score is available.
    """
    ddb = boto3.resource("dynamodb")
    table = ddb.Table(GAME_FIXTURES_TABLE)

    items: List[dict] = []
    kwargs: Dict[str, Any] = {
        "FilterExpression":
            "league_id = :lid AND attribute_exists(xg_coordination_info)",
        "ExpressionAttributeValues": {":lid": league_id},
    }
    # The game_fixtures table's partition design isn't known to be
    # league-keyed, so we Scan. Called infrequently (quarterly), OK.
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek
    return items


def extract_outcomes(fixtures: List[dict]) -> List[Tuple[float, float, int, int]]:
    """Return a list of (lambda_H, lambda_A, home_goals, away_goals) tuples
    for each finished fixture that has usable V2 data.
    """
    outcomes: List[Tuple[float, float, int, int]] = []
    for fx in fixtures:
        info = fx.get("xg_coordination_info") or {}
        v2a = info.get("v2a") or {}
        lh = _to_float(v2a.get("lambda_H"))
        la = _to_float(v2a.get("lambda_A"))
        if lh is None or la is None or lh <= 0 or la <= 0:
            continue

        goals_obj = fx.get("goals") or {}
        hg = goals_obj.get("home")
        ag = goals_obj.get("away")
        if hg is None or ag is None:
            continue
        try:
            outcomes.append((lh, la, int(hg), int(ag)))
        except (TypeError, ValueError):
            continue
    return outcomes


def log_likelihood(
    outcomes: List[Tuple[float, float, int, int]], rho: float
) -> float:
    """Sum log P(observed | lambda_H, lambda_A, rho) across outcomes."""
    total = 0.0
    for (lh, la, hg, ag) in outcomes:
        # Clip goal values into the engine's truncation grid.
        if hg > 10 or ag > 10:
            continue
        joint = dixon_coles_joint_probs(lh, la, rho=rho, max_goals=10)
        p = joint.get(hg, {}).get(ag, 0.0)
        # Avoid log(0); tiny floor on the rare long-tail miss.
        total += math.log(max(p, 1e-12))
    return total


def best_rho(
    outcomes: List[Tuple[float, float, int, int]],
    candidates: List[float] = RHO_CANDIDATES,
) -> Tuple[float, float]:
    """Return (best_rho, log_likelihood) over the candidate grid."""
    best = None
    for rho in candidates:
        ll = log_likelihood(outcomes, rho)
        if best is None or ll > best[1]:
            best = (rho, ll)
    return best


def update_league_rho(league_id: int, rho: float) -> None:
    """Overwrite `rho_dc` on the league's xG-params row. Preserves every
    other attribute via update-expression (no full put).
    """
    ddb = boto3.resource("dynamodb")
    table = ddb.Table(LEAGUE_XG_PARAMETERS_TABLE)
    table.update_item(
        Key={"league_id": int(league_id)},
        UpdateExpression="SET rho_dc = :r",
        ExpressionAttributeValues={":r": Decimal(str(round(rho, 4)))},
    )


def refit_league(
    league_id: int, min_fixtures: int = 30, dry_run: bool = False
) -> Dict[str, Any]:
    fixtures = load_fixtures_for_league(league_id)
    outcomes = extract_outcomes(fixtures)

    if len(outcomes) < min_fixtures:
        return {
            "league_id": league_id,
            "status": "insufficient_data",
            "n_fixtures_total": len(fixtures),
            "n_fixtures_usable": len(outcomes),
            "min_required": min_fixtures,
        }

    rho, ll = best_rho(outcomes)

    # Also log likelihoods for the full grid so we can see curvature.
    grid = [(r, log_likelihood(outcomes, r)) for r in RHO_CANDIDATES]

    result = {
        "league_id": league_id,
        "status": "ok" if not dry_run else "dry_run",
        "n_fixtures_usable": len(outcomes),
        "best_rho": rho,
        "best_log_likelihood": round(ll, 3),
        "grid": [(r, round(v, 3)) for r, v in grid],
    }

    if not dry_run:
        update_league_rho(league_id, rho)

    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league-id", type=int, default=None,
                    help="Re-fit only this league. Omit to re-fit every league "
                         "that has a row in football_league_xg_parameters_prod.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Compute the best rho per league but do not write it back.")
    ap.add_argument("--min-fixtures", type=int, default=30,
                    help="Skip leagues with fewer than N usable fixtures.")
    args = ap.parse_args()

    if args.league_id is not None:
        target_leagues = [int(args.league_id)]
    else:
        ddb = boto3.resource("dynamodb")
        table = ddb.Table(LEAGUE_XG_PARAMETERS_TABLE)
        target_leagues = []
        resp = table.scan(ProjectionExpression="league_id")
        for it in resp.get("Items", []):
            try:
                target_leagues.append(int(it["league_id"]))
            except (KeyError, TypeError, ValueError):
                continue

    print(f"Refitting rho for {len(target_leagues)} league(s)")
    summaries = []
    for lid in sorted(target_leagues):
        try:
            s = refit_league(lid, min_fixtures=args.min_fixtures, dry_run=args.dry_run)
        except Exception as e:
            s = {"league_id": lid, "status": "error", "error": str(e)}
        summaries.append(s)
        msg = f"[{lid:>4}] {s['status']}"
        if s["status"] in ("ok", "dry_run"):
            msg += f" n={s['n_fixtures_usable']} best_rho={s['best_rho']:+.2f}"
        elif s["status"] == "insufficient_data":
            msg += (
                f" n={s['n_fixtures_usable']} "
                f"(need {s['min_required']})"
            )
        print(msg)

    updated = sum(1 for s in summaries if s["status"] == "ok")
    print(f"\nUpdated rho_dc in {updated} league(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
