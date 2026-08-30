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
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
DELIVERY = WORKSPACE / ".omo" / "_delivery"
DAEMON_WATERMARKS = DELIVERY / "resident-orchestrator" / "watermarks"
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
    """daemon 以 cron --once 调度运行, 进程退出是正常行为。

    以最近一次 tick 写入的字节偏移水位文件的新鲜度判定存活:
    水位文件在 STALE_THRESHOLD 内有更新 → daemon 正常轮转。
    """
    watermarks = list(DAEMON_WATERMARKS.glob("*.json"))
    if not watermarks:
        return False, "no daemon watermark files (daemon never ticked)"
    newest = min(watermarks, key=lambda p: p.stat().st_mtime)
    age = time.time() - newest.stat().st_mtime
    ok = age <= STALE_THRESHOLD_SECONDS
    detail = f"last daemon tick {age:.0f}s ago"
    return ok, ("daemon active (" + detail + ")" if ok else "daemon stale (" + detail + ")")


def _check_watermarks() -> tuple[bool, str]:
    ages = []
    for path in list(DAEMON_WATERMARKS.glob("*.json")):
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
    """workflow-mesh 输入流静止是正常状态(无新 workflow 事件), 仅记录不降级。"""
    age = _file_age(EVENTS_JSONL)
    if age is None:
        return True, "events.jsonl missing (no input stream yet)"
    if age > STALE_THRESHOLD_SECONDS:
        return True, f"events.jsonl idle ({age:.0f}s, 输入流静止属正常)"
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
        import importlib.util

        events_file = Path(__file__).resolve().parent / "observability-events.py"
        spec = importlib.util.spec_from_file_location("observability_events", events_file)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        append_event = module.append_event

        append_event(report)
        print(json.dumps({"emitted": True, "severity": report["severity"]}))
    except Exception as exc:  # noqa: BLE001 - emit best-effort
        print(f"emit_failed: {exc}", file=sys.stderr)
        return 1
    return 0 if report["severity"] == "recovered" else 2


if __name__ == "__main__":
    sys.exit(main())
