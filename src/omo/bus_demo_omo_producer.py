"""omo bus demo producer — emits a structured event when omo_worker_dispatch succeeds.

Phase A.1 demo: 验证 agora.bus facade 能被 omo 项目用 (跨仓 import).

依赖: omo/pyproject.toml 加了 agora workspace dep (one-way).
"""
from __future__ import annotations

import uuid

from bus_foundation import BusEnvelope, publish  # bus-foundation 是 omo 显式依赖 (R67 migration)


def emit_demo_event(task_id: str, dispatch_id: str | None = None) -> str:
    """Emit a single omo:dispatched event via bus facade.

    Returns event_id.
    """
    env = BusEnvelope(
        type="omo:dispatched",
        source="omo_worker_dispatch",
        payload={
            "task_id": task_id,
            "dispatch_id": dispatch_id or f"dispatch-{uuid.uuid4().hex[:8]}",
        },
        trace_id=f"omo-trace-{uuid.uuid4().hex[:6]}",
    )
    return publish(env)


def main() -> int:
    event_id = emit_demo_event(task_id="demo-task-1")
    print(f"omo demo event published: {event_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
