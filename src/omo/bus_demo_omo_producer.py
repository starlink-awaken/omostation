"""omo bus demo producer — emits a structured event when omo_worker_dispatch succeeds.

Phase A.1 demo: 验证 agora.bus facade 能被 omo 项目用 (跨仓 import).

依赖: omo/pyproject.toml 加了 agora workspace dep (one-way).
"""

from __future__ import annotations

import uuid

from bus_foundation.facade import event as bus_event  # X1 规范迁移


def _get_trace_id() -> str | None:
    try:
        from bus_foundation.observability import get_current_trace_id
        return get_current_trace_id()
    except ImportError:
        return None


def emit_demo_event(task_id: str, dispatch_id: str | None = None) -> str:
    trace_id = _get_trace_id() or f"omo-trace-{uuid.uuid4().hex[:6]}"
    payload = {
        "task_id": task_id,
        "dispatch_id": dispatch_id or f"dispatch-{uuid.uuid4().hex[:8]}",
    }
    bus_event.publish(
        topic="omo:dispatched",
        payload=payload,
        source_uri="bos://governance/omo_worker_dispatch",
        trace_id=trace_id,
    )
    return trace_id


def main() -> int:
    event_id = emit_demo_event(task_id="demo-task-1")
    print(f"omo demo event published: {event_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
