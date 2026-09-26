#!/usr/bin/env python3
"""check-episode-pipeline.py — BET-Y2Q4-SH-5 ledger producer distribution guard.

Reports whether the live event ledger has accumulated rows written by the
closeout → scene bridge, and how the producer distribution looks overall.

BET-Y2Q4-SH-5.2 re-bound ``ok`` to the bridge's own discriminator.  It used to
assert ``producer == 'omo-personal-episode' >= 1``, but that label is not a
bridge fingerprint at all: scene-outcome-recorder deliberately emits
``producer='omo-personal-episode'`` because PersonalEpisodeService.observe_principal
filters on it (see scene-outcome-recorder.py:_write_event_ledger_outcome).  Any
episode row from any producer therefore satisfied the guard while the bridge was
completely dead — which is how SH-5 stayed recorded ``done`` against a pipeline
that had emitted nothing.  Bridge-written rows are identified by
``payload.source == 'scene-outcome-bridge'``.

Default mode is warn-only (``--strict`` upgrades to exit 1 on empty).
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
# Discriminator the closeout→scene bridge stamps on every event it writes.
# Not the producer: the producer is omo-personal-episode by design (SH-5.2).
BRIDGE_SOURCE = "scene-outcome-bridge"


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
        # Bridge-written rows: keyed on the payload discriminator, because the
        # producer column cannot distinguish the bridge from any other writer.
        bridge_row = conn.execute(
            "SELECT COUNT(*) FROM event_log WHERE json_extract(payload_json, '$.source') = ?",
            (BRIDGE_SOURCE,),
        ).fetchone()
        bridge_count = int(bridge_row[0]) if bridge_row else 0
        closeout_row = conn.execute(
            """
            SELECT COUNT(DISTINCT correlation_id) FROM event_log
            WHERE json_extract(payload_json, '$.source') = ?
            """,
            (BRIDGE_SOURCE,),
        ).fetchone()
        bridge_closeouts = int(closeout_row[0]) if closeout_row else 0
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
        "ok": bridge_count >= 1,
        "path": str(db_path),
        "principal_id": principal,
        "total_events": total,
        "producer_distribution": distribution,
        f"{PRODUCER}_count": episode_count,
        "bridge_source": BRIDGE_SOURCE,
        "bridge_event_count": bridge_count,
        "bridge_closeout_count": bridge_closeouts,
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
        print(f"  bridge_event_count:       {report.get('bridge_event_count')}")
        print(f"  bridge_closeout_count:    {report.get('bridge_closeout_count')}")
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