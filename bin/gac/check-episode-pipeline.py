#!/usr/bin/env python3
"""check-episode-pipeline.py — BET-Y2Q4-SH-5 ledger producer distribution guard.

Reports whether the live event ledger has accumulated any
``producer == 'omo-personal-episode'`` rows.  PersonalEpisodeService
criterion: at least one episode decision per principal is required to
move the north-star personal_value gate from ``not_ready`` to
``collecting``.

Default mode is warn-only (``--strict`` upgrades to exit 1 on empty).
Wire into ``make gac-local-gate`` to surface drift before north-star
silently regresses.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_DB = WORKSPACE / "runtime" / "omo" / "event-ledger.sqlite3"
PRODUCER = "omo-personal-episode"


def _resolve_db(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("OMO_EVENT_LEDGER_DB")
    if env:
        return Path(env).resolve()
    return DEFAULT_DB


def check(db_path: Path) -> dict:
    if not db_path.is_file():
        return {
            "ok": False,
            "reason": f"ledger db missing: {db_path}",
            "path": str(db_path),
        }
    conn = sqlite3.connect(str(db_path))
    try:
        # total event_log count
        total_row = conn.execute("SELECT COUNT(*) FROM event_log").fetchone()
        total = int(total_row[0]) if total_row else 0
        # producer distribution
        rows = conn.execute(
            "SELECT producer, COUNT(*) FROM event_log GROUP BY producer ORDER BY 2 DESC"
        ).fetchall()
        distribution = {str(p): int(c) for p, c in rows}
        episode_count = distribution.get(PRODUCER, 0)
        # recent episodes for principal (last 7 days)
        principal = os.environ.get("OMO_PRINCIPAL_ID", "xiamingxing")
        recent_row = conn.execute(
            """
            SELECT COUNT(*) FROM event_log
            WHERE producer = ?
              AND principal_id = ?
              AND recorded_at >= datetime('now', '-7 days')
            """,
            (PRODUCER, principal),
        ).fetchone()
        recent = int(recent_row[0]) if recent_row else 0
    finally:
        conn.close()
    return {
        "ok": episode_count >= 1,
        "path": str(db_path),
        "principal_id": principal,
        "total_events": total,
        "producer_distribution": distribution,
        f"{PRODUCER}_count": episode_count,
        "recent_7d_episodes": recent,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", help="Explicit event-ledger sqlite path")
    parser.add_argument("--strict", action="store_true", help="exit 1 on empty")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = check(_resolve_db(args.db))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"=== episode-pipeline check (BET-Y2Q4-SH-5) ===")
        print(f"  db:                       {report.get('path')}")
        print(f"  total_events:             {report.get('total_events')}")
        print(f"  {PRODUCER}_count:        {report.get(f'{PRODUCER}_count')}")
        print(f"  recent_7d_episodes:       {report.get('recent_7d_episodes')}")
        print(f"  producer_distribution:    {report.get('producer_distribution')}")
        print(f"  ok:                       {report.get('ok')}")
        if "reason" in report:
            print(f"  reason:                   {report['reason']}")

    if not report.get("ok"):
        return 1 if args.strict else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())