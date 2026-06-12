"""omo bus demo producer — emits a structured event when omo_worker_dispatch succeeds.

Phase A.0 demo: 验证 agora.bus facade 能被 omo 项目用 (不绕过 omo 自己的 omo_worker_dispatch).

依赖: omo/pyproject.toml 必须有 agora workspace dep (见 Task 2.2.1).
"""
from __future__ import annotations

import uuid

from agora.bus import BusEnvelope, publish  # agora 是 omo 显式依赖, 不需要 sys.path hack


def emit_demo_event(task_id: str, dispatch_id: str | None = None) -> str:
    """Emit a single omo:dispatched event via bus facade.

    Returns event_id.
    """
    env = BusEnvelope(
        type="omo:dispatched",  # omo 命名空间 (Phase A.0 EventType 不全, 用 raw string)
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
