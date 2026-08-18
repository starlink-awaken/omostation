"""Swarm 侧 Workflow Mesh v1 事件信封。

Swarm 只生成控制面事件，不绑定 OMO 存储。上层通过 ``event_sink`` 注入
append-only sink，即可把图执行接入统一 Workflow Mesh。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def new_workflow_event(
    event_type: str,
    workflow_run_id: str,
    *,
    trace_id: str | None = None,
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    payload = dict(payload or {})
    step_run_id = payload.get("step_run_id", "workflow")
    return {
        "event_id": uuid4().hex,
        "event_type": event_type,
        "trace_id": trace_id or workflow_run_id,
        "workflow_run_id": workflow_run_id,
        "occurred_at": datetime.now(UTC).isoformat(),
        "producer": "aetherforge.swarm",
        "schema_version": "workflow-mesh/v1",
        "idempotency_key": idempotency_key or f"{workflow_run_id}:{event_type}:{step_run_id}",
        "payload": payload,
    }


EventSink = Callable[[dict[str, Any]], Any]

__all__ = ["EventSink", "new_workflow_event"]
