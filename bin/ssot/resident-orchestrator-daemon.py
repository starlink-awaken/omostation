#!/usr/bin/env python3
"""resident-orchestrator-daemon — subscribe→execute bridge for resident agents.

Polls the event ledger from a persisted checkpoint (resume-safe), routes each
new event by topic to a handler, and advances the checkpoint. Handlers are
plug-in functions registered in the ROUTES table; the knowledge-sediment
handler (WP3) is wired once it exists.

Design: 事件中心(ledger 持久) + checkpoint 消费水位(断点续传) + 主题路由(主题级,
规则级预留为 YAML 加载)。借鉴 omo_daemon.run_daemon 骨架(PID+signal+loop)。
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = WORKSPACE / "runtime" / "omo" / "event-ledger.sqlite3"
DEFAULT_EVENTS_JSONL = WORKSPACE / ".omo" / "_knowledge" / "workflow-mesh" / "events.jsonl"
PID_FILE = WORKSPACE / ".omo" / "_delivery" / "resident-orchestrator" / "daemon.pid"
LOG_FILE = WORKSPACE / ".omo" / "_delivery" / "resident-orchestrator" / "daemon.log"
PROJECTOR_ID = "resident-sub"

# 主题路由: event_type → handler 名(硬编码主题级;规则级 = YAML 加载预留)
# handler 实现在 WP3 接入(knowledge-sediment),当前为占位(记录日志)。
_EVENT_HANDLERS: dict[str, Callable[[dict[str, Any]], None]] = {}
_SAFE_HANDLERS: set[str] = set()
# 人工批准门: 非 safe handler 需 --yes(防自主 agent 执行破坏性动作)。
_APPROVAL_REQUIRED = True


def _inject_paths() -> None:
    for sub in ("projects/omo/src", "projects/bus-foundation/src"):
        candidate = WORKSPACE / sub
        if candidate.is_dir() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))


def _handler_placeholder(event: dict[str, Any]) -> None:
    """Placeholder handler — replaced by real handlers (WP3)."""
    _log(f"handler_placeholder event_type={event.get('event_type')} run={event.get('workflow_run_id')}")


def register_handler(event_type: str, fn: Callable[[dict[str, Any]], None], *, safe: bool = False) -> None:
    """Register a topic handler. ``safe=True`` marks read-only/non-destructive
    handlers (may run without approval); others require --yes."""
    _EVENT_HANDLERS[event_type] = fn
    if safe:
        _SAFE_HANDLERS.add(fn.__name__)


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}\n")
    except OSError:
        pass


def _route(event: dict[str, Any]) -> None:
    event_type = str(event.get("event_type") or "")
    handler = _EVENT_HANDLERS.get(event_type, _handler_placeholder)
    if _APPROVAL_REQUIRED and handler.__name__ not in _SAFE_HANDLERS:
        _log(f"handler_blocked_awaiting_approval event_type={event_type} handler={handler.__name__}")
        return
    try:
        handler(event)
    except Exception as exc:  # noqa: BLE001 - handler isolation
        _log(f"handler_error event_type={event_type} err={type(exc).__name__}: {exc}")


def tick_once(broker: Any, events_jsonl: Path) -> dict[str, Any]:
    """Read new events from the JSONL (after checkpoint), route each, advance watermark."""
    cp = broker.checkpoint_get(PROJECTOR_ID)
    last_index = int((cp or {}).get("last_sequence", 0))
    events = _read_events(events_jsonl)
    new_events = events[last_index:]
    processed = 0
    for event in new_events:
        _route(event)
        processed += 1
    if new_events:
        broker.checkpoint_set(PROJECTOR_ID, last_index + len(new_events))
    else:
        broker.checkpoint_set(PROJECTOR_ID, last_index)
    return {"start_index": last_index, "processed": processed, "events_in_file": len(events)}


def _read_events(events_jsonl: Path) -> list[dict[str, Any]]:
    import json  # noqa: PLC0415

    if not events_jsonl.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in events_jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _events_after(events: list[dict[str, Any]], last_event_id: str) -> list[dict[str, Any]]:
    new: list[dict[str, Any]] = []
    seen_last = not last_event_id
    for ev in events:
        ev_id = str(ev.get("event_id") or "")
        if ev_id == last_event_id:
            seen_last = True
            continue
        if seen_last:
            new.append(ev)
    return new


def _register_default_handlers() -> None:
    """Wire default handlers (knowledge-sediment) if importable."""
    try:
        import importlib.util

        sediment_path = Path(__file__).resolve().parent / "knowledge-sediment.py"
        spec = importlib.util.spec_from_file_location("knowledge_sediment", sediment_path)
        assert spec is not None and spec.loader is not None
        sediment = importlib.util.module_from_spec(spec)
        sys.modules["knowledge_sediment"] = sediment
        spec.loader.exec_module(sediment)
        sediment.register_with_daemon(sys.modules[__name__])
        _log("default_handlers registered (knowledge-sediment)")
    except Exception as exc:  # noqa: BLE001 - handlers are optional
        _log(f"default_handlers skipped: {type(exc).__name__}: {exc}")


def run_daemon(
    *, ledger: Path, events_jsonl: Path = DEFAULT_EVENTS_JSONL, interval: float = 30.0, once: bool = False
) -> int:
    _inject_paths()
    _register_default_handlers()
    from omo.event_ledger.broker import LedgerBroker  # noqa: PLC0415

    broker = LedgerBroker.connect(str(ledger))
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

    if once:
        report = tick_once(broker, events_jsonl)
        broker.close()
        print(json.dumps(report, sort_keys=True))
        return 0

    stop_event = threading.Event()

    def _handle_signal(signum, _frame):  # noqa: ANN001, ARG001
        _log(f"signal_received signum={signum}")
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    _log(f"resident_orchestrator_started pid={os.getpid()} interval={interval}s")
    try:
        while not stop_event.is_set():
            report = tick_once(broker, events_jsonl)
            _log(f"tick_done processed={report['processed']} events_in_file={report['events_in_file']}")
            stop_event.wait(interval)
    finally:
        broker.close()
        PID_FILE.unlink(missing_ok=True)
        _log("resident_orchestrator_stopped")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--events-jsonl", type=Path, default=DEFAULT_EVENTS_JSONL)
    parser.add_argument("--interval", type=float, default=30.0)
    parser.add_argument("--once", action="store_true", help="run a single tick and exit")
    parser.add_argument("--yes", action="store_true", help="bypass human-approval gate for non-safe handlers")
    args = parser.parse_args()
    if args.yes:
        global _APPROVAL_REQUIRED  # noqa: PLW0603
        _APPROVAL_REQUIRED = False
    return run_daemon(ledger=args.ledger, events_jsonl=args.events_jsonl, interval=args.interval, once=args.once)


if __name__ == "__main__":
    sys.exit(main())
