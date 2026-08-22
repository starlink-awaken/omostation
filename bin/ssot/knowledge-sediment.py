#!/usr/bin/env python3
"""knowledge-sediment — turn workflow-mesh events into knowledge drafts.

Consumes ledger events (success → run retro draft; failure → failure pattern
draft) and writes them under `.omo/_knowledge/sediment/`. These are
event-driven drafts (traceable, verifiable) that a resident knowledge agent or
the human can later consolidate into full retros/patterns.

Wired into resident-orchestrator-daemon via register_with_daemon().
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
SEDIMENT_ROOT = WORKSPACE / ".omo" / "_knowledge" / "sediment"
SUCCESS_EVENTS = frozenset({"WorkflowSucceeded", "WorkflowClosed"})
FAILURE_EVENTS = frozenset({"WorkflowFailed", "StepFailed", "StepTimeout"})


def _safe_slug(value: str, max_len: int = 80) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]", "-", str(value))
    return value.strip("-")[:max_len] or "unknown"


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _event_type(event: dict[str, Any]) -> str:
    return str(event.get("event_type") or "")


def _sediment_run(event: dict[str, Any], *, kind: str) -> Path | None:
    """Write a sediment draft for one event; returns the file path or None."""
    run_id = str(event.get("workflow_run_id") or event.get("trace_id") or "unknown")
    event_id = str(event.get("event_id") or "")
    slug = _safe_slug(run_id)
    if kind == "failure":
        target = SEDIMENT_ROOT / "failures" / f"{slug}-{event_id[:8]}.md"
        title = "失败模式沉淀(事件驱动草稿)"
        section = "## 失败上下文"
    else:
        target = SEDIMENT_ROOT / "runs" / f"{slug}.md"
        title = "运行复盘沉淀(事件驱动草稿)"
        section = "## 运行上下文"
    target.parent.mkdir(parents=True, exist_ok=True)
    body = (
        f"# {title}\n\n"
        f"- event_type: {_event_type(event)}\n"
        f"- workflow_run_id: {run_id}\n"
        f"- trace_id: {event.get('trace_id')}\n"
        f"- event_id: {event_id}\n"
        f"- occurred_at: {event.get('occurred_at')}\n"
        f"- generated_at: {_utc()}\n"
        f"- status: draft (事件驱动生成, 待运营 agent/人工完善为完整 retro/pattern)\n\n"
        f"{section}\n\n"
        f"- producer: {event.get('producer')}\n"
        f"- payload: 事件侧元数据见 ledger sequence(可通过 event_id 追溯)\n\n"
        f"## 待补充(五问/模式提炼)\n\n"
        f"- [ ] 计划 vs 实际\n- [ ] 结果与证据\n- [ ] 关键发现\n- [ ] 净增减\n- [ ] 交接建议\n"
    )
    target.write_text(body, encoding="utf-8")
    return target


def consume_event(event: dict[str, Any]) -> Path | None:
    """Route one event to a sediment draft; returns path or None if ignored."""
    event_type = _event_type(event)
    if event_type in SUCCESS_EVENTS:
        return _sediment_run(event, kind="success")
    if event_type in FAILURE_EVENTS:
        return _sediment_run(event, kind="failure")
    return None


def register_with_daemon(daemon_module: Any) -> None:
    """Wire sediment handlers into resident-orchestrator-daemon.

    Sediment handlers are read-only (write drafts under .omo/_knowledge/sediment)
    so they are registered as ``safe`` (no human-approval gate required).
    """
    for event_type in SUCCESS_EVENTS:
        daemon_module.register_handler(event_type, _success_handler, safe=True)
    for event_type in FAILURE_EVENTS:
        daemon_module.register_handler(event_type, _failure_handler, safe=True)


def _success_handler(event: dict[str, Any]) -> None:
    path = _sediment_run(event, kind="success")
    if path is not None:
        _log(f"sediment_written kind=success run={event.get('workflow_run_id')} path={path.name}")


def _failure_handler(event: dict[str, Any]) -> None:
    path = _sediment_run(event, kind="failure")
    if path is not None:
        _log(f"sediment_written kind=failure run={event.get('workflow_run_id')} path={path.name}")


def _log(msg: str) -> None:
    print(f"[knowledge-sediment] {msg}", file=sys.stderr)


def main() -> int:
    """CLI: consume a JSON event from stdin and write a sediment draft."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="event JSON string")
    args = parser.parse_args()
    if args.json:
        event = json.loads(args.json)
    else:
        event = json.loads(sys.stdin.read())
    path = consume_event(event)
    print(json.dumps({"written": path is not None, "path": str(path) if path else None}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
