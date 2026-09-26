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

``--self-test`` proves the re-binding on throwaway sqlite fixtures: a ledger
full of ``producer='omo-personal-episode'`` rows but no bridge rows must report
``ok=False``.  That case is the guard against rebinding back to the proxy.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
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


_FIXTURE_DDL = """
CREATE TABLE event_log (
  sequence        INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type      TEXT NOT NULL,
  principal_id    TEXT NOT NULL,
  correlation_id  TEXT NOT NULL,
  producer        TEXT NOT NULL,
  recorded_at     TEXT NOT NULL,
  payload_json    TEXT NOT NULL CHECK(json_valid(payload_json))
)
"""


def _seed_fixture(path: Path, *, bridge_rows: int, episode_rows: int) -> None:
    """Write a throwaway ledger; every row carries the proxy producer label.

    ``producer`` cannot distinguish the bridge from any other episode writer, so
    both fixtures hold the same ``omo-personal-episode`` count and only the
    payload discriminator differs.
    """
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(_FIXTURE_DDL)
        rows = [(True, i) for i in range(bridge_rows)] + [(False, i) for i in range(episode_rows)]
        conn.executemany(
            "INSERT INTO event_log (event_type, principal_id, correlation_id, producer,"
            " recorded_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    "Episode.Decision.v1",
                    "principal:x",
                    f"{'bridge' if is_bridge else 'other'}-{idx}",
                    PRODUCER,
                    "2026-01-01 00:00:00",
                    json.dumps({"verdict": "accept",
                                "source": BRIDGE_SOURCE if is_bridge else "journey-auto-complete"}),
                )
                for is_bridge, idx in rows
            ],
        )
        conn.commit()
    finally:
        conn.close()


def self_test() -> dict:
    """Assert ok tracks the bridge discriminator, not the proxy producer (SH-5.2)."""
    with tempfile.TemporaryDirectory(prefix="episode-probe-") as tmp:
        dead = Path(tmp) / "dead-bridge.sqlite3"
        _seed_fixture(dead, bridge_rows=0, episode_rows=6)
        dead_report = check(dead)

        live = Path(tmp) / "live-bridge.sqlite3"
        _seed_fixture(live, bridge_rows=4, episode_rows=2)
        live_report = check(live)

    proxy_key = f"{PRODUCER}_count"
    cases = {
        "dead_bridge_stays_red": (
            dead_report.get("ok") is False and dead_report.get(proxy_key, 0) > 0
        ),
        "live_bridge_turns_green": (
            live_report.get("ok") is True
            and live_report.get("bridge_event_count") == 4
            and live_report.get("bridge_closeout_count") == 4
        ),
    }
    return {
        "ok": all(cases.values()),
        "cases": cases,
        "detail": {
            "dead_bridge": {proxy_key: dead_report.get(proxy_key),
                            "bridge_event_count": dead_report.get("bridge_event_count"),
                            "ok": dead_report.get("ok")},
            "live_bridge": {proxy_key: live_report.get(proxy_key),
                             "bridge_event_count": live_report.get("bridge_event_count"),
                             "ok": live_report.get("ok")},
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", help="Explicit event-ledger sqlite path")
    parser.add_argument("--strict", action="store_true", help="exit 1 on empty")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true",
                        help="prove ok is bound to the bridge discriminator, not the producer label")
    args = parser.parse_args(argv)

    if args.self_test:
        result = self_test()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for name, passed in result["cases"].items():
                print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
            print(f"  detail: {result['detail']}")
            print(f"=== episode-pipeline self-test: {'PASS' if result['ok'] else 'FAIL'} ===")
        return 0 if result["ok"] else 1

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