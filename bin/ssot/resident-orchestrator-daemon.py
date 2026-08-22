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


_ROUTES_FILE = Path(__file__).resolve().parent / "resident-routes.yaml"
_ROUTES: dict[str, dict[str, Any]] = {}


def _load_routes(path: Path = _ROUTES_FILE) -> dict[str, dict[str, Any]]:
    """Load the rule-level subscription routes (fail-closed on invalid YAML)."""
    import yaml  # noqa: PLC0415

    global _ROUTES  # noqa: PLW0603
    if not path.is_file():
        _ROUTES = {}
        return _ROUTES
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        _log(f"routes_load_failed invalid_yaml: {exc}")
        raise
    routes = doc.get("routes", []) if isinstance(doc, dict) else None
    if not isinstance(routes, list):
        _log("routes_load_failed missing_routes_list")
        raise ValueError("resident-routes.yaml must contain a routes list")
    result: dict[str, dict[str, Any]] = {}
    for rule in routes:
        if not isinstance(rule, dict) or not rule.get("event_type"):
            _log("routes_load_failed invalid_rule")
            raise ValueError("each route needs event_type")
        result[str(rule["event_type"])] = rule
    _ROUTES = result
    return result


def _condition_holds(condition: str, event: dict[str, Any]) -> bool:
    """Evaluate a restricted condition expression against the event.

    Supports simple ``payload.<field> <op> <literal>`` comparisons and the
    ``in (<a>,<b>)`` membership check. Anything else is rejected (fail-closed).
    """
    import ast  # noqa: PLC0415

    expr = condition.strip()
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return False
    node = tree.body

    # payload.field in (a, b)
    if (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.In)
        and isinstance(node.left, ast.Attribute)
        and isinstance(node.left.value, ast.Name)
        and node.left.value.id == "payload"
        and isinstance(node.comparators[0], ast.Tuple)
    ):
        field = node.left.attr
        actual = event.get("payload", {}).get(field) if isinstance(event.get("payload"), dict) else None
        allowed = {c.value for c in node.comparators[0].elts if isinstance(c, ast.Constant)}
        return actual in allowed

    # payload.field == literal
    if (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.Eq)
        and isinstance(node.left, ast.Attribute)
        and isinstance(node.left.value, ast.Name)
        and node.left.value.id == "payload"
        and isinstance(node.comparators[0], ast.Constant)
    ):
        field = node.left.attr
        actual = event.get("payload", {}).get(field) if isinstance(event.get("payload"), dict) else None
        return actual == node.comparators[0].value

    return False  # unsupported expression → fail-closed


def _route(event: dict[str, Any]) -> None:
    event_type = str(event.get("event_type") or "")
    rule = _ROUTES.get(event_type)
    handler = None
    if rule is not None:
        condition = rule.get("condition")
        if condition and not _condition_holds(str(condition), event):
            return  # condition not met → skip
        action = str(rule.get("action") or "")
        handler = _EVENT_HANDLERS.get(action, _handler_placeholder)
        # safe 由规则声明; 若未声明则按 handler 注册的 safe 集合判断
        safe = bool(rule.get("safe", False)) or handler.__name__ in _SAFE_HANDLERS
    else:
        handler = _handler_placeholder
        safe = True
    if _APPROVAL_REQUIRED and not safe:
        _log(f"handler_blocked_awaiting_approval event_type={event_type} handler={handler.__name__}")
        return
    try:
        handler(event)
    except Exception as exc:  # noqa: BLE001 - handler isolation
        _log(f"handler_error event_type={event_type} err={type(exc).__name__}: {exc}")


def _wm_path(projector: str) -> Path:
    return WORKSPACE / ".omo" / "_delivery" / "resident-orchestrator" / "watermarks" / f"{projector}.json"


def _load_byte_offset(projector: str) -> int:
    try:
        data = json.loads(_wm_path(projector).read_text(encoding="utf-8"))
        return int(data.get("byte_offset", 0))
    except (OSError, json.JSONDecodeError):
        return 0


def _save_byte_offset(projector: str, byte_offset: int) -> None:
    path = _wm_path(projector)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"byte_offset": byte_offset}), encoding="utf-8")


def _read_incremental(events_jsonl: Path, byte_offset: int) -> tuple[list[dict[str, Any]], int]:
    """Seek-read only the bytes after ``byte_offset`` (incremental tail read).

    If the file was truncated/rebuilt (size < offset) we fall back to a full
    scan from byte 0. Returns (new_events, new_file_size).
    """
    if not events_jsonl.is_file():
        return [], 0
    file_size = events_jsonl.stat().st_size
    if file_size < byte_offset:
        byte_offset = 0  # truncate/recreate → full rescan
    if byte_offset == file_size:
        return [], file_size
    events: list[dict[str, Any]] = []
    with events_jsonl.open("rb") as fh:
        fh.seek(byte_offset)
        data = fh.read()
    for line in data.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events, file_size


def tick_once(
    broker: Any, events_jsonl: Path, *, projector: str = PROJECTOR_ID, topic_filter: set[str] | None = None
) -> dict[str, Any]:
    """Read new events incrementally (byte-offset watermark), route, advance.

    ``projector`` is this daemon's independent checkpoint name (multi-agent
    parallelism). ``topic_filter`` restricts which event types this daemon
    handles. The ledger checkpoint stores the row watermark (compat); the local
    watermark file stores the byte offset for incremental tail reads.
    """
    cp = broker.checkpoint_get(projector)
    last_index = int((cp or {}).get("last_sequence", 0))
    byte_offset = _load_byte_offset(projector)
    scanned, file_size = _read_incremental(events_jsonl, byte_offset)
    # 每个 agent 扫描增量窗口, 但只处理属于自己 topic_filter 的事件。
    new_events = scanned if not topic_filter else [ev for ev in scanned if (ev.get("event_type") or "") in topic_filter]
    processed = 0
    for event in new_events:
        _route(event)
        processed += 1
    broker.checkpoint_set(projector, last_index + len(scanned))
    _save_byte_offset(projector, file_size)
    return {"start_index": last_index, "processed": processed, "events_in_file": last_index + len(scanned)}


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


def _connect_with_retry(ledger: Path, *, attempts: int = 5) -> Any:
    """Connect to the ledger with retry (SQLite cross-process init lock)."""
    from omo.event_ledger.broker import LedgerBroker  # noqa: PLC0415
    import sqlite3  # noqa: PLC0415

    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return LedgerBroker.connect(str(ledger))
        except sqlite3.OperationalError as exc:
            last_exc = exc
            time.sleep(0.2 * (attempt + 1))
    raise RuntimeError(f"ledger connect failed after {attempts} attempts: {last_exc}")


def run_daemon(
    *,
    ledger: Path,
    events_jsonl: Path = DEFAULT_EVENTS_JSONL,
    interval: float = 30.0,
    once: bool = False,
    projector: str = PROJECTOR_ID,
    topic_filter: set[str] | None = None,
) -> int:
    _inject_paths()
    _register_default_handlers()
    _load_routes()  # WP-C: rule-level subscription table (fail-closed)
    broker = _connect_with_retry(ledger)
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

    if once:
        report = tick_once(broker, events_jsonl, projector=projector, topic_filter=topic_filter)
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
            report = tick_once(broker, events_jsonl, projector=projector, topic_filter=topic_filter)
            _log(
                f"tick_done projector={projector} processed={report['processed']} events_in_file={report['events_in_file']}"
            )
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
    parser.add_argument(
        "--projector", default=PROJECTOR_ID, help="independent checkpoint name (multi-agent parallelism)"
    )
    parser.add_argument(
        "--topic-filter", default="", help="comma-separated event types this daemon handles (empty = all)"
    )
    args = parser.parse_args()
    if args.yes:
        global _APPROVAL_REQUIRED  # noqa: PLW0603
        _APPROVAL_REQUIRED = False
    topic_filter = {t.strip() for t in args.topic_filter.split(",") if t.strip()} or None
    return run_daemon(
        ledger=args.ledger,
        events_jsonl=args.events_jsonl,
        interval=args.interval,
        once=args.once,
        projector=args.projector,
        topic_filter=topic_filter,
    )


if __name__ == "__main__":
    sys.exit(main())
