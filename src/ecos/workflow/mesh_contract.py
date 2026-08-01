"""Workflow Mesh 的跨边界运行契约。

ECOS 只负责生成稳定的运行身份和事件信封，不直接依赖 OMO 的存储实现。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
import re
from typing import Any
from uuid import uuid4


class WorkflowRunState(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_workflow_run_id(workflow_name: str, supplied: str | None = None) -> str:
    """返回可由调用方幂等传入、否则自动生成的运行 ID。"""
    if supplied:
        return supplied
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", workflow_name).strip("-")
    return f"{safe_name or 'workflow'}-{uuid4().hex[:12]}"


def run_metadata(
    workflow_name: str,
    *,
    workflow_definition_id: str | None = None,
    backend: str = "default",
    execution_mode: str = "real",
    workflow_run_id: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """构造 OMO/控制面可识别的运行元数据。"""
    run_id = new_workflow_run_id(workflow_name, workflow_run_id)
    return {
        "workflow_run_id": run_id,
        "workflow_definition_id": workflow_definition_id or workflow_name,
        "backend": backend,
        "trace_id": trace_id or run_id,
        "state": WorkflowRunState.PLANNED.value,
        "execution_mode": execution_mode,
        "started_at": _now(),
    }


def new_workflow_event(
    event_type: str,
    workflow_run_id: str,
    *,
    trace_id: str | None = None,
    producer: str = "ecos",
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """生成 workflow-mesh/v1 事件信封。"""
    event_id = uuid4().hex
    event_payload = payload or {}
    return {
        "event_id": event_id,
        "event_type": event_type,
        "trace_id": trace_id or workflow_run_id,
        "workflow_run_id": workflow_run_id,
        "occurred_at": _now(),
        "producer": producer,
        "schema_version": "workflow-mesh/v1",
        "idempotency_key": idempotency_key or f"{workflow_run_id}:{event_type}:{event_payload.get('step_run_id', 'workflow')}",
        "payload": event_payload,
    }


def is_silent_mock(result: Any) -> bool:
    """识别会伪装成成功的 mock/simulation 结果。"""
    if isinstance(result, dict):
        mode = str(result.get("mode", "")).lower()
        if mode in {"mock", "simulated", "simulation"}:
            return True
        return any(is_silent_mock(value) for value in result.values())
    if isinstance(result, list):
        return any(is_silent_mock(value) for value in result)
    return False
