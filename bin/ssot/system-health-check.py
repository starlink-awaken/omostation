#!/usr/bin/env python3
"""system-health-check — monitor resident system component health.

Periodically checks the resident agent system's health: daemon liveness,
checkpoint freshness (daemon watermarks), event-ingest watermark freshness,
event-stream activity, and ledger integrity. Emits an observability event
(domain=runtime) with a severity that alert-forwarder will route to channels.

Extends the monitoring/alerting surface beyond the observability event plane:
this is the system's own health probe (WP-monitoring completion).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
DELIVERY = WORKSPACE / ".omo" / "_delivery"
DAEMON_PID = DELIVERY / "resident-orchestrator" / "daemon.pid"
DAEMON_WATERMARKS = DELIVERY / "resident-orchestrator" / "watermarks"
INGEST_WATERMARK = DELIVERY / "event-ingest" / "watermark.json"
EVENTS_JSONL = WORKSPACE / ".omo" / "_knowledge" / "workflow-mesh" / "events.jsonl"
LEDGER = WORKSPACE / "runtime" / "omo" / "event-ledger.sqlite3"
# 阈值: 组件状态文件超过该时长视为 stale
STALE_THRESHOLD_SECONDS = 1800  # 30min


def _now() -> datetime:
    return datetime.now(UTC)


def _file_age(path: Path) -> float | None:
    if not path.is_file():
        return None
    return time.time() - path.stat().st_mtime


def _check_daemon_alive() -> tuple[bool, str]:
    if not DAEMON_PID.is_file():
        return False, "daemon.pid missing (daemon not running)"
    try:
        pid = int(DAEMON_PID.read_text().strip())
        os.kill(pid, 0)
        return True, f"daemon alive (pid={pid})"
    except (ValueError, ProcessLookupError):
        return False, f"daemon pid {DAEMON_PID.read_text().strip()[:8]} not alive"


def _check_watermarks() -> tuple[bool, str]:
    ages = []
    for path in list(DAEMON_WATERMARKS.glob("*.json")) + [INGEST_WATERMARK]:
        age = _file_age(path)
        if age is not None:
            ages.append((path.name, age))
    if not ages:
        return False, "no watermark files (system never ran)"
    oldest = max(ages, key=lambda x: x[1])
    stale = oldest[1] > STALE_THRESHOLD_SECONDS
    detail = f"oldest watermark {oldest[0]} age={oldest[1]:.0f}s"
    return (not stale), ("ok: " + detail if not stale else "stale: " + detail)


def _check_events_active() -> tuple[bool, str]:
    age = _file_age(EVENTS_JSONL)
    if age is None:
        return False, "events.jsonl missing"
    if age > STALE_THRESHOLD_SECONDS:
        return False, f"events.jsonl stale ({age:.0f}s)"
    return True, f"events active (age={age:.0f}s)"


def _check_ledger() -> tuple[bool, str]:
    if not LEDGER.is_file():
        return False, "event-ledger.sqlite3 missing"
    try:
        sys.path.insert(0, str(WORKSPACE / "projects" / "omo" / "src"))
        from omo.event_ledger.broker import LedgerBroker  # noqa: PLC0415

        broker = LedgerBroker.connect(str(LEDGER))
        try:
            chain = broker.verify_chain()
            ok = bool(chain.get("ok"))
            return ok, ("ledger ok" if ok else f"ledger chain broken: {chain.get('error')}")
        finally:
            broker.close()
    except Exception as exc:  # noqa: BLE001 - ledger check best-effort
        return False, f"ledger check failed: {type(exc).__name__}: {exc}"


def check_all() -> dict[str, Any]:
    checks = {
        "daemon": _check_daemon_alive(),
        "watermarks": _check_watermarks(),
        "events_stream": _check_events_active(),
        "ledger": _check_ledger(),
    }
    failed = [name for name, (ok, _) in checks.items() if not ok]
    severity = "degraded" if failed else "recovered"
    return {
        "domain": "runtime",
        "event_type": "system.health",
        "severity": severity,
        "title": f"resident system health: {'DEGRADED' if failed else 'OK'}",
        "message": "; ".join(f"{n}: {d}" for n, (_, d) in checks.items()),
        "checks": {name: {"ok": ok, "detail": detail} for name, (ok, detail) in checks.items()},
        "ts": _now().isoformat().replace("+00:00", "Z"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit", action="store_true", help="emit health event to observability plane")
    parser.add_argument("--json", action="store_true", help="print health as JSON")
    args = parser.parse_args()

    report = check_all()
    if args.json or not args.emit:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report["severity"] == "recovered" else 2

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from observability_events import append_event  # noqa: PLC0415

        append_event(report)
        print(json.dumps({"emitted": True, "severity": report["severity"]}))
    except Exception as exc:  # noqa: BLE001 - emit best-effort
        print(f"emit_failed: {exc}", file=sys.stderr)
        return 1
    return 0 if report["severity"] == "recovered" else 2


if __name__ == "__main__":
    sys.exit(main())
