"""Workflow Mesh 事件存储与运行态投影。

OMO 是 Workflow Mesh 的证据平面：只接受完整事件信封，使用 append-only
JSONL 保存原始事件，并从事件重建可审计的运行态。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from omo.omo_io import AppendOnlyLog, fcntl_lock

WORKFLOW_MESH_LOG = Path("_knowledge/workflow-mesh/events.jsonl")
REQUIRED_EVENT_FIELDS = {
    "event_id",
    "event_type",
    "trace_id",
    "workflow_run_id",
    "occurred_at",
    "producer",
    "schema_version",
    "idempotency_key",
    "payload",
}
EVENT_STATE = {
    "WorkflowRequested": "planned",
    "WorkflowAdmitted": "admitted",
    "StepDispatched": "dispatched",
    "StepStarted": "running",
    "StepHeartbeat": "running",
    "CheckpointSaved": "running",
    "ApprovalRequested": "waiting_approval",
    "ApprovalGranted": "running",
    "CompensationStarted": "compensating",
    "StepFailed": "failed",
    "BackendUnavailable": "unavailable",
    "WorkflowVerified": "verified",
    "PRMerged": "merged",
    "WorkflowSucceeded": "succeeded",
    "WorkflowFailed": "failed",
    "WorkflowCancelled": "cancelled",
    "WorkflowClosed": "closed",
}
TERMINAL_STATES = {"succeeded", "failed", "unavailable", "cancelled", "closed"}


class WorkflowMeshEventError(ValueError):
    """事件结构或状态转换不符合 Workflow Mesh 契约。"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_workflow_event(
    event_type: str,
    workflow_run_id: str,
    *,
    trace_id: str | None = None,
    producer: str = "omo",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_id = uuid4().hex
    return {
        "event_id": event_id,
        "event_type": event_type,
        "trace_id": trace_id or workflow_run_id,
        "workflow_run_id": workflow_run_id,
        "occurred_at": _utc_now(),
        "producer": producer,
        "schema_version": "workflow-mesh/v1",
        "idempotency_key": f"{workflow_run_id}:{event_type}:{event_id}",
        "payload": payload or {},
    }


def validate_workflow_event(event: dict[str, Any]) -> dict[str, Any]:
    missing = REQUIRED_EVENT_FIELDS - event.keys()
    if missing:
        raise WorkflowMeshEventError(
            f"Workflow Mesh event missing fields: {sorted(missing)}"
        )
    if event["schema_version"] != "workflow-mesh/v1":
        raise WorkflowMeshEventError("Unsupported Workflow Mesh event schema")
    if event["event_type"] not in EVENT_STATE:
        raise WorkflowMeshEventError(f"Unknown Workflow Mesh event: {event['event_type']}")
    if not isinstance(event["payload"], dict):
        raise WorkflowMeshEventError("Workflow Mesh event payload must be an object")
    return event


def project_workflow_run(
    events: list[dict[str, Any]], workflow_run_id: str
) -> dict[str, Any]:
    """从事件重建一个运行快照，拒绝终态后的幽灵事件。"""
    relevant = sorted(
        (event for event in events if event.get("workflow_run_id") == workflow_run_id),
        key=lambda event: event["occurred_at"],
    )
    snapshot: dict[str, Any] = {
        "workflow_run_id": workflow_run_id,
        "trace_id": None,
        "state": "unknown",
        "event_count": 0,
        "step_states": {},
        "last_event_type": None,
    }
    for event in relevant:
        validate_workflow_event(event)
        if snapshot["state"] in TERMINAL_STATES:
            raise WorkflowMeshEventError(
                f"Workflow run is terminal; event is not allowed: {event['event_type']}"
            )
        snapshot["trace_id"] = snapshot["trace_id"] or event["trace_id"]
        snapshot["state"] = EVENT_STATE[event["event_type"]]
        snapshot["event_count"] += 1
        snapshot["last_event_type"] = event["event_type"]
        step_run_id = event["payload"].get("step_run_id")
        if step_run_id:
            snapshot["step_states"][step_run_id] = {
                "state": snapshot["state"],
                "last_event_type": event["event_type"],
            }
    return snapshot


class WorkflowMeshStore:
    """OMO 中 Workflow Mesh 事件的 append-only 存储和投影入口。"""

    def __init__(self, omo_dir: Path | str) -> None:
        self.omo_dir = Path(omo_dir)
        self.log_path = self.omo_dir / WORKFLOW_MESH_LOG
        self._lock = fcntl_lock(
            self.log_path.with_suffix(self.log_path.suffix + ".lock")
        )
        self._log = AppendOnlyLog(
            self.log_path,
            lock=self._lock,
        )

    def events(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._log.read_all()

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        validate_workflow_event(event)
        with self._lock:
            current = self._log.read_all()
            for existing in current:
                if existing.get("event_id") != event["event_id"]:
                    continue
                if existing == event:
                    return existing
                raise WorkflowMeshEventError(
                    f"Conflicting duplicate Workflow Mesh event: {event['event_id']}"
                )
            run_id = event["workflow_run_id"]
            candidate = [*current, event]
            project_workflow_run(candidate, run_id)
            return self._log.append(event, sort_keys=True)

    def snapshot(self, workflow_run_id: str) -> dict[str, Any]:
        return project_workflow_run(self.events(), workflow_run_id)

    def sink(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        return self.append


__all__ = [
    "EVENT_STATE",
    "TERMINAL_STATES",
    "WORKFLOW_MESH_LOG",
    "WorkflowMeshEventError",
    "WorkflowMeshStore",
    "new_workflow_event",
    "project_workflow_run",
    "validate_workflow_event",
]
