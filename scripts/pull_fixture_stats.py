"""Data-first ingestion for /v3/fixtures/statistics.

Standalone puller — does NOT use src/data/api_client._make_api_request because that
wrapper discards response headers, and we need `x-ratelimit-*` headers to observe
quota. Same key, same host, same 100ms throttle convention.

Phases (run in order):
  resolve   -> /leagues per league in leagues.py; store current season + coverage flags
  enumerate -> /fixtures?league=X&season=YYYY per league; store finished fixtures
  probe     -> /fixtures/statistics for first N fixtures per league; coverage report
  bulk      -> /fixtures/statistics for every remaining finished fixture (opt-in)

Each phase is idempotent and resumable: already-fetched rows are skipped.

Usage:
    python scripts/pull_fixture_stats.py resolve
    python scripts/pull_fixture_stats.py enumerate
    python scripts/pull_fixture_stats.py probe --per-league 5
    python scripts/pull_fixture_stats.py bulk [--max-calls N]
    python scripts/pull_fixture_stats.py status
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from leagues import allLeagues  # noqa: E402

API_HOST = "api-football-v1.p.rapidapi.com"
API_BASE = f"https://{API_HOST}/v3"
DB_PATH = PROJECT_ROOT / "data" / "fixture_stats" / "stats.db"

FINISHED_STATUSES = {"FT", "AET", "PEN", "FT_PEN"}

MIN_REQUEST_INTERVAL = 0.1  # 100ms — matches existing api_client convention
MAX_BACKOFF = 60.0
SAFETY_FLOOR_PCT = 0.05  # stop if remaining / limit < 5%


# ---------------------------------------------------------------------------
# Rate-limited HTTP client
# ---------------------------------------------------------------------------


class RateLimitedClient:
    """Minimal requests wrapper with throttle, 429 backoff, and header capture."""

    def __init__(self, api_key: str, db: sqlite3.Connection):
        self.key = api_key
        self.db = db
        self._lock = threading.Lock()
        self._last_ts = 0.0
        self.last_headers: dict[str, str] = {}

    def _throttle(self):
        with self._lock:
            elapsed = time.time() - self._last_ts
            if elapsed < MIN_REQUEST_INTERVAL:
                time.sleep(MIN_REQUEST_INTERVAL - elapsed)
            self._last_ts = time.time()

    def get(self, path: str, params: dict[str, Any], max_retries: int = 5) -> dict[str, Any] | None:
        url = f"{API_BASE}{path}"
        headers = {"x-rapidapi-key": self.key, "x-rapidapi-host": API_HOST}
        attempt = 0
        while attempt < max_retries:
            self._throttle()
            start = time.time()
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
            except requests.RequestException as e:
                attempt += 1
                wait = min(2 ** attempt + random.uniform(0, 1), MAX_BACKOFF)
                print(f"  network error {e!r}, retry {attempt}/{max_retries} in {wait:.1f}s")
                time.sleep(wait)
                continue

            duration_ms = int((time.time() - start) * 1000)
            self.last_headers = {k.lower(): v for k, v in resp.headers.items()}
            self._log_call(path, params, resp.status_code, duration_ms)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError as e:
                    print(f"  invalid JSON: {e}")
                    return None
                self._check_safety_floor()
                return data

            if resp.status_code == 429:
                attempt += 1
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else min(2 ** attempt, MAX_BACKOFF)
                wait += random.uniform(0, wait * 0.3)
                print(f"  429 rate limit, retry {attempt}/{max_retries} in {wait:.1f}s")
                time.sleep(wait)
                continue

            if resp.status_code in (500, 502, 503, 504):
                attempt += 1
                wait = min(2 ** attempt, MAX_BACKOFF)
                print(f"  server {resp.status_code}, retry {attempt}/{max_retries} in {wait:.1f}s")
                time.sleep(wait)
                continue

            print(f"  unexpected {resp.status_code}: {resp.text[:200]}")
            return None

        print(f"  exhausted retries for {path} {params}")
        return None

    def _log_call(self, path: str, params: dict, status: int, duration_ms: int):
        h = self.last_headers
        self.db.execute(
            """INSERT INTO api_calls
               (ts, endpoint, params_json, status_code, duration_ms,
                requests_limit, requests_remaining, requests_reset,
                minute_limit, minute_remaining)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                path,
                json.dumps(params, sort_keys=True),
                status,
                duration_ms,
                h.get("x-ratelimit-requests-limit"),
                h.get("x-ratelimit-requests-remaining"),
                h.get("x-ratelimit-requests-reset"),
                h.get("x-ratelimit-minute-limit") or h.get("x-ratelimit-requests-minute-limit"),
                h.get("x-ratelimit-minute-remaining") or h.get("x-ratelimit-requests-minute-remaining"),
            ),
        )
        self.db.commit()

    def _check_safety_floor(self):
        h = self.last_headers
        try:
            limit = float(h.get("x-ratelimit-requests-limit", 0))
            remaining = float(h.get("x-ratelimit-requests-remaining", 0))
        except (TypeError, ValueError):
            return
        if limit <= 0:
            return
        if remaining / limit < SAFETY_FLOOR_PCT:
            reset = h.get("x-ratelimit-requests-reset", "?")
            raise SystemExit(
                f"Safety stop: quota remaining={remaining}/{limit} (<{SAFETY_FLOOR_PCT:.0%}). "
                f"Reset in {reset}s. Re-run later."
            )


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


SCHEMA = """
CREATE TABLE IF NOT EXISTS leagues_meta (
    league_id INTEGER PRIMARY KEY,
    country TEXT NOT NULL,
    name TEXT NOT NULL,
    league_type TEXT,
    season_year INTEGER,
    season_start TEXT,
    season_end TEXT,
    coverage_json TEXT,
    has_stats_coverage INTEGER,
    resolved INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fixtures (
    fixture_id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    date TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    status_short TEXT NOT NULL,
    home_team_id INTEGER NOT NULL,
    home_team_name TEXT,
    away_team_id INTEGER NOT NULL,
    away_team_name TEXT,
    home_goals INTEGER,
    away_goals INTEGER,
    venue_id INTEGER,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fixtures_league ON fixtures(league_id, season);
CREATE INDEX IF NOT EXISTS idx_fixtures_date ON fixtures(date);

CREATE TABLE IF NOT EXISTS fixture_statistics (
    fixture_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    stat_type TEXT NOT NULL,
    value_raw TEXT,
    value_num REAL,
    PRIMARY KEY (fixture_id, team_id, stat_type)
);
CREATE INDEX IF NOT EXISTS idx_stats_fixture ON fixture_statistics(fixture_id);
CREATE INDEX IF NOT EXISTS idx_stats_type ON fixture_statistics(stat_type);

CREATE TABLE IF NOT EXISTS fixture_statistics_raw (
    fixture_id INTEGER PRIMARY KEY,
    payload_json TEXT NOT NULL,
    has_xg INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    params_json TEXT,
    status_code INTEGER,
    duration_ms INTEGER,
    requests_limit TEXT,
    requests_remaining TEXT,
    requests_reset TEXT,
    minute_limit TEXT,
    minute_remaining TEXT
);
"""


def init_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def parse_stat_value(raw: Any) -> tuple[str | None, float | None]:
    """Convert API stat value to (raw_string, numeric) pair.

    Handles ints, floats, strings like "52%" and "1.20", and nulls.
    """
    if raw is None:
        return None, None
    if isinstance(raw, bool):
        return str(raw), float(raw)
    if isinstance(raw, (int, float)):
        return str(raw), float(raw)
    if isinstance(raw, str):
        s = raw.strip()
        try:
            return s, float(s.rstrip("%"))
        except ValueError:
            return s, None
    return str(raw), None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def flatten_leagues() -> list[dict[str, Any]]:
    out = []
    for country, leagues in allLeagues.items():
        for lg in leagues:
            out.append({
                "country": country,
                "league_id": lg["id"],
                "name": lg["name"],
                "type": lg.get("type"),
            })
    return out


def get_api_key() -> str:
    key = os.getenv("RAPIDAPI_KEY")
    if key:
        return key
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from utils.constants import RAPIDAPI_KEY  # type: ignore
        return RAPIDAPI_KEY
    except Exception:
        pass
    # last-resort .env scan
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("RAPIDAPI_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("RAPIDAPI_KEY not found in env, constants, or .env")


# ---------------------------------------------------------------------------
# Phase: resolve
# ---------------------------------------------------------------------------


def phase_resolve(client: RateLimitedClient, db: sqlite3.Connection, force: bool = False):
    leagues = flatten_leagues()
    print(f"[resolve] {len(leagues)} leagues in leagues.py")

    skipped = resolved = no_stats = 0
    for lg in leagues:
        lid = lg["league_id"]
        if not force:
            row = db.execute(
                "SELECT resolved FROM leagues_meta WHERE league_id=?", (lid,)
            ).fetchone()
            if row and row[0]:
                skipped += 1
                continue

        data = client.get("/leagues", {"id": lid, "current": "true"})
        if not data or not data.get("response"):
            print(f"  [{lid}] {lg['country']}/{lg['name']}: no response")
            continue

        entry = data["response"][0]
        seasons = entry.get("seasons", [])
        current = next((s for s in seasons if s.get("current")), None)
        if not current:
            print(f"  [{lid}] {lg['country']}/{lg['name']}: no current season")
            continue

        coverage = current.get("coverage", {})
        has_stats = bool(coverage.get("fixtures", {}).get("statistics_fixtures"))
        if not has_stats:
            no_stats += 1

        db.execute(
            """INSERT OR REPLACE INTO leagues_meta
               (league_id, country, name, league_type, season_year, season_start, season_end,
                coverage_json, has_stats_coverage, resolved, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                lid, lg["country"], lg["name"], lg["type"],
                current.get("year"), current.get("start"), current.get("end"),
                json.dumps(coverage),
                1 if has_stats else 0,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        db.commit()
        resolved += 1
        flag = "" if has_stats else "  (NO stats coverage)"
        print(f"  [{lid}] {lg['country']}/{lg['name']} -> season {current.get('year')}{flag}")

    print(f"[resolve] done: {resolved} resolved, {skipped} skipped (already done), {no_stats} without stats coverage")


# ---------------------------------------------------------------------------
# Phase: enumerate
# ---------------------------------------------------------------------------


def phase_enumerate(client: RateLimitedClient, db: sqlite3.Connection, only_with_stats: bool = True):
    q = "SELECT league_id, country, name, season_year, has_stats_coverage FROM leagues_meta WHERE resolved=1"
    if only_with_stats:
        q += " AND has_stats_coverage=1"
    rows = db.execute(q).fetchall()
    print(f"[enumerate] {len(rows)} leagues to enumerate")

    total_fixtures = 0
    for lid, country, name, season, has_stats in rows:
        existing = db.execute(
            "SELECT COUNT(*) FROM fixtures WHERE league_id=? AND season=?", (lid, season)
        ).fetchone()[0]
        data = client.get("/fixtures", {"league": lid, "season": season})
        if not data or not data.get("response"):
            print(f"  [{lid}] {country}/{name}: empty response")
            continue

        inserted = 0
        for fx in data["response"]:
            fid = fx["fixture"]["id"]
            status = fx["fixture"]["status"]["short"]
            goals = fx.get("goals", {}) or {}
            teams = fx.get("teams", {}) or {}
            venue = (fx["fixture"].get("venue") or {})
            db.execute(
                """INSERT OR REPLACE INTO fixtures
                   (fixture_id, league_id, season, date, timestamp, status_short,
                    home_team_id, home_team_name, away_team_id, away_team_name,
                    home_goals, away_goals, venue_id, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    fid, lid, season,
                    fx["fixture"].get("date"),
                    fx["fixture"].get("timestamp"),
                    status,
                    teams.get("home", {}).get("id"),
                    teams.get("home", {}).get("name"),
                    teams.get("away", {}).get("id"),
                    teams.get("away", {}).get("name"),
                    goals.get("home"),
                    goals.get("away"),
                    venue.get("id"),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            inserted += 1
        db.commit()
        total_fixtures += inserted
        print(f"  [{lid}] {country}/{name} season {season}: {inserted} fixtures ({existing} previously)")
    print(f"[enumerate] done: {total_fixtures} fixtures written")


# ---------------------------------------------------------------------------
# Phase: probe / bulk (same core, different scope)
# ---------------------------------------------------------------------------


def fetch_and_store_stats(client: RateLimitedClient, db: sqlite3.Connection, fixture_id: int) -> bool:
    exists = db.execute(
        "SELECT 1 FROM fixture_statistics_raw WHERE fixture_id=?", (fixture_id,)
    ).fetchone()
    if exists:
        return True

    data = client.get("/fixtures/statistics", {"fixture": fixture_id})
    if data is None:
        return False

    response = data.get("response", []) or []
    payload_json = json.dumps(data)

    has_xg = 0
    for team_entry in response:
        team_id = team_entry.get("team", {}).get("id")
        if not team_id:
            continue
        for stat in team_entry.get("statistics", []) or []:
            stype = stat.get("type")
            raw, num = parse_stat_value(stat.get("value"))
            if stype == "expected_goals" and num is not None:
                has_xg = 1
            db.execute(
                """INSERT OR REPLACE INTO fixture_statistics
                   (fixture_id, team_id, stat_type, value_raw, value_num)
                   VALUES (?, ?, ?, ?, ?)""",
                (fixture_id, team_id, stype, raw, num),
            )

    db.execute(
        """INSERT OR REPLACE INTO fixture_statistics_raw
           (fixture_id, payload_json, has_xg, fetched_at) VALUES (?, ?, ?, ?)""",
        (fixture_id, payload_json, has_xg, datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    return True


def _finished_fixtures_needing_stats(db: sqlite3.Connection, league_id: int, limit: int | None = None) -> list[int]:
    placeholders = ",".join(f"'{s}'" for s in FINISHED_STATUSES)
    q = f"""
        SELECT f.fixture_id FROM fixtures f
        LEFT JOIN fixture_statistics_raw r ON r.fixture_id = f.fixture_id
        WHERE f.league_id = ? AND f.status_short IN ({placeholders})
          AND r.fixture_id IS NULL
        ORDER BY f.timestamp ASC
    """
    if limit is not None:
        q += f" LIMIT {int(limit)}"
    return [row[0] for row in db.execute(q, (league_id,)).fetchall()]


def phase_probe(client: RateLimitedClient, db: sqlite3.Connection, per_league: int = 5):
    rows = db.execute(
        "SELECT league_id, country, name FROM leagues_meta WHERE resolved=1 AND has_stats_coverage=1"
    ).fetchall()
    print(f"[probe] {len(rows)} leagues with stats coverage, {per_league} fixtures each")

    calls_made = 0
    for lid, country, name in rows:
        fids = _finished_fixtures_needing_stats(db, lid, limit=per_league)
        if not fids:
            print(f"  [{lid}] {country}/{name}: no fresh finished fixtures to probe")
            continue
        for fid in fids:
            fetch_and_store_stats(client, db, fid)
            calls_made += 1

    print(f"[probe] {calls_made} calls made")
    print_coverage_report(db)


def phase_bulk(
    client: RateLimitedClient,
    db: sqlite3.Connection,
    max_calls: int | None = None,
    skip_leagues: set[int] | None = None,
):
    skip_leagues = skip_leagues or set()
    # Source of truth for "leagues we care about" is the current leagues.py.
    # Anything removed from that file is naturally excluded from bulk pulls,
    # even if we already enumerated its fixtures into SQLite.
    current_ids = {lg["league_id"] for lg in flatten_leagues()}

    rows = db.execute(
        "SELECT league_id, country, name FROM leagues_meta WHERE resolved=1 AND has_stats_coverage=1"
    ).fetchall()
    rows = [r for r in rows if r[0] in current_ids and r[0] not in skip_leagues]

    if skip_leagues:
        print(f"[bulk] skip list: {sorted(skip_leagues)}")
    print(f"[bulk] {len(rows)} eligible leagues (after leagues.py + skip intersection)")

    total_pending = sum(
        len(_finished_fixtures_needing_stats(db, lid)) for lid, _, _ in rows
    )
    print(f"[bulk] {total_pending} finished fixtures still need stats")

    if max_calls:
        print(f"[bulk] cap: {max_calls} calls this run")

    calls_made = 0
    for lid, country, name in rows:
        fids = _finished_fixtures_needing_stats(db, lid)
        if not fids:
            continue
        print(f"  [{lid}] {country}/{name}: {len(fids)} pending")
        for fid in fids:
            if max_calls is not None and calls_made >= max_calls:
                print(f"[bulk] hit max-calls cap {max_calls}, stopping")
                return
            fetch_and_store_stats(client, db, fid)
            calls_made += 1
            if calls_made % 100 == 0:
                h = client.last_headers
                print(f"    …{calls_made} calls, remaining={h.get('x-ratelimit-requests-remaining')}/"
                      f"{h.get('x-ratelimit-requests-limit')}")
    print(f"[bulk] done: {calls_made} calls made")


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


STAT_TYPES = [
    "Shots on Goal", "Shots off Goal", "Total Shots", "Blocked Shots",
    "Shots insidebox", "Shots outsidebox", "Fouls", "Corner Kicks",
    "Offsides", "Ball Possession", "Yellow Cards", "Red Cards",
    "Goalkeeper Saves", "Total passes", "Passes accurate", "Passes %",
    "expected_goals", "goals_prevented",
]


def print_coverage_report(db: sqlite3.Connection):
    print("\n=== COVERAGE REPORT ===")
    leagues = db.execute(
        """SELECT l.league_id, l.country, l.name,
                  (SELECT COUNT(*) FROM fixture_statistics_raw r
                    JOIN fixtures f ON f.fixture_id=r.fixture_id
                    WHERE f.league_id=l.league_id) AS probed
             FROM leagues_meta l
            WHERE l.resolved=1 AND l.has_stats_coverage=1
            ORDER BY l.country, l.name"""
    ).fetchall()

    header = f"{'League':40s}  {'Probed':>6s}  {'xG%':>5s}  {'SoT%':>5s}  {'Poss%':>5s}  {'Pass%':>5s}"
    print(header)
    print("-" * len(header))

    for lid, country, name, probed in leagues:
        label = f"{country}/{name}"[:40]
        if probed == 0:
            print(f"{label:40s}  {'-':>6s}  {'-':>5s}  {'-':>5s}  {'-':>5s}  {'-':>5s}")
            continue

        def pct(stat_type: str) -> str:
            row = db.execute(
                """SELECT COUNT(*) FROM fixture_statistics s
                     JOIN fixtures f ON f.fixture_id=s.fixture_id
                    WHERE f.league_id=? AND s.stat_type=? AND s.value_num IS NOT NULL""",
                (lid, stat_type),
            ).fetchone()[0]
            total = db.execute(
                """SELECT COUNT(DISTINCT r.fixture_id) * 2 FROM fixture_statistics_raw r
                     JOIN fixtures f ON f.fixture_id=r.fixture_id
                    WHERE f.league_id=?""",
                (lid,),
            ).fetchone()[0] or 1
            return f"{(row / total * 100):.0f}"

        print(f"{label:40s}  {probed:>6d}  {pct('expected_goals'):>5s}  "
              f"{pct('Shots on Goal'):>5s}  {pct('Ball Possession'):>5s}  {pct('Passes %'):>5s}")


def print_status(db: sqlite3.Connection):
    leagues = db.execute("SELECT COUNT(*) FROM leagues_meta WHERE resolved=1").fetchone()[0]
    leagues_with_stats = db.execute("SELECT COUNT(*) FROM leagues_meta WHERE has_stats_coverage=1").fetchone()[0]
    fixtures = db.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0]
    finished = db.execute(
        f"SELECT COUNT(*) FROM fixtures WHERE status_short IN ({','.join('?' * len(FINISHED_STATUSES))})",
        tuple(FINISHED_STATUSES),
    ).fetchone()[0]
    stats_pulled = db.execute("SELECT COUNT(*) FROM fixture_statistics_raw").fetchone()[0]
    calls = db.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0]
    last_call = db.execute(
        "SELECT ts, requests_remaining, requests_limit FROM api_calls ORDER BY id DESC LIMIT 1"
    ).fetchone()

    print(f"leagues resolved:          {leagues}")
    print(f"leagues with stats cov:    {leagues_with_stats}")
    print(f"fixtures enumerated:       {fixtures}")
    print(f"  finished:                {finished}")
    print(f"fixture stats pulled:      {stats_pulled}")
    print(f"api calls logged:          {calls}")
    if last_call:
        ts, remaining, limit = last_call
        print(f"last call:                 {ts}  remaining={remaining}/{limit}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["resolve", "enumerate", "probe", "bulk", "status"])
    ap.add_argument("--per-league", type=int, default=5, help="probe only")
    ap.add_argument("--max-calls", type=int, default=None, help="bulk only; cap calls this run")
    ap.add_argument("--skip-leagues", default="", help="bulk only; comma-separated league IDs to skip")
    ap.add_argument("--force", action="store_true", help="resolve only; re-resolve already-resolved leagues")
    ap.add_argument("--include-no-stats", action="store_true",
                    help="enumerate only; include leagues without stats coverage")
    ap.add_argument("--db", default=str(DB_PATH))
    args = ap.parse_args()

    db = init_db(Path(args.db))
    if args.phase == "status":
        print_status(db)
        return

    client = RateLimitedClient(get_api_key(), db)

    if args.phase == "resolve":
        phase_resolve(client, db, force=args.force)
    elif args.phase == "enumerate":
        phase_enumerate(client, db, only_with_stats=not args.include_no_stats)
    elif args.phase == "probe":
        phase_probe(client, db, per_league=args.per_league)
    elif args.phase == "bulk":
        skip = {int(x) for x in args.skip_leagues.split(",") if x.strip()}
        phase_bulk(client, db, max_calls=args.max_calls, skip_leagues=skip)


if __name__ == "__main__":
    main()
