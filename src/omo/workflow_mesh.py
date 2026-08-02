"""Workflow Mesh 事件存储与运行态投影。

OMO 是 Workflow Mesh 的证据平面：只接受完整事件信封，使用 append-only
JSONL 保存原始事件，并从事件重建可审计的运行态。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
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
    "StepRetryScheduled": "running",
    "CheckpointSaved": "running",
    "EvidenceRecorded": "succeeded",
    "ApprovalRequested": "waiting_approval",
    "ApprovalGranted": "running",
    "CompensationStarted": "compensating",
    "StepFailed": "failed",
    "BackendUnavailable": "unavailable",
    "WorkflowRecovered": "running",
    "WorkflowVerified": "verified",
    "PRMerged": "merged",
    "WorkflowSucceeded": "succeeded",
    "WorkflowFailed": "failed",
    "WorkflowCancelled": "cancelled",
    "WorkflowClosed": "closed",
    "WorkerAcknowledged": "dispatched",
    "WorkerLeaseRenewed": "running",
    "WorkerLeaseExpired": "unavailable",
    "WorkerReclaimed": "running",
}
# 只有 closed 才是不可再推进的生命周期终态。succeeded/failed/unavailable
# 仍可能进入验证、关闭或受控恢复。
TERMINAL_STATES = {"closed"}
_ALLOWED_TRANSITIONS = {
    "unknown": {"planned"},
    "planned": {
        "admitted",
        "dispatched",
        "running",
        "failed",
        "unavailable",
        "cancelled",
    },
    "admitted": {"dispatched", "running", "failed", "unavailable", "cancelled"},
    "dispatched": {"dispatched", "running", "failed", "unavailable", "cancelled"},
    "running": {
        "running",
        "waiting_approval",
        "compensating",
        "failed",
        "unavailable",
        "succeeded",
        "cancelled",
    },
    "waiting_approval": {"running", "failed", "unavailable", "cancelled"},
    "compensating": {"running", "failed", "unavailable", "succeeded", "cancelled"},
    "failed": {"running", "failed", "closed"},
    "unavailable": {"running", "unavailable", "closed"},
    "succeeded": {"succeeded", "verified", "closed"},
    "verified": {"merged", "closed"},
    "merged": {"closed"},
    "cancelled": {"closed"},
    "closed": set(),
}
_ALLOWED_EVENTS = {
    "unknown": {"WorkflowRequested"},
    "planned": {
        "WorkflowAdmitted",
        "StepDispatched",
        "StepStarted",
        "WorkflowFailed",
        "BackendUnavailable",
        "WorkflowCancelled",
    },
    "admitted": {
        "StepDispatched",
        "StepStarted",
        "WorkflowFailed",
        "BackendUnavailable",
        "WorkflowCancelled",
    },
    "dispatched": {
        "StepDispatched",
        "StepStarted",
        "WorkerAcknowledged",
        "WorkerLeaseRenewed",
        "WorkerLeaseExpired",
        "WorkflowFailed",
        "BackendUnavailable",
        "WorkflowCancelled",
    },
    "running": {
        "StepDispatched",
        "StepStarted",
        "StepHeartbeat",
        "StepRetryScheduled",
        "CheckpointSaved",
        "WorkerAcknowledged",
        "WorkerLeaseRenewed",
        "WorkerLeaseExpired",
        "ApprovalRequested",
        "CompensationStarted",
        "StepFailed",
        "BackendUnavailable",
        "WorkflowSucceeded",
        "WorkflowCancelled",
    },
    "waiting_approval": {
        "ApprovalGranted",
        "StepFailed",
        "BackendUnavailable",
        "WorkflowCancelled",
    },
    "compensating": {
        "WorkflowRecovered",
        "StepFailed",
        "WorkflowFailed",
        "BackendUnavailable",
        "WorkflowSucceeded",
        "WorkflowCancelled",
    },
    "failed": {"WorkflowRecovered", "StepFailed", "WorkflowFailed", "WorkflowClosed"},
    "unavailable": {
        "WorkflowRecovered",
        "WorkerReclaimed",
        "BackendUnavailable",
        "WorkflowClosed",
    },
    "succeeded": {
        "WorkflowSucceeded",
        "EvidenceRecorded",
        "WorkflowVerified",
        "WorkflowClosed",
    },
    "verified": {"PRMerged", "WorkflowClosed"},
    "merged": {"WorkflowClosed"},
    "cancelled": {"WorkflowClosed"},
    "closed": set(),
}

_WORKER_EVENTS = {
    "WorkerAcknowledged",
    "WorkerLeaseRenewed",
    "WorkerLeaseExpired",
    "WorkerReclaimed",
}
SCENE_BINDING_FIELDS = frozenset({"scene_id", "journey_id", "outcome_metric"})


class WorkflowMeshEventError(ValueError):
    """事件结构或状态转换不符合 Workflow Mesh 契约。"""


def _scene_binding(payload: Mapping[str, Any]) -> dict[str, str] | None:
    """Return the minimal business context carried by a workflow run.

    The Mesh does not own permissions or raw business data. It only preserves
    the stable identifiers that let product surfaces and evidence receipts
    relate an execution to a user journey and a measurable outcome.
    """
    value = payload.get("scene_binding")
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise WorkflowMeshEventError("scene_binding must be an object")
    missing = sorted(SCENE_BINDING_FIELDS - value.keys())
    if missing:
        raise WorkflowMeshEventError(
            f"scene_binding missing fields: {missing}"
        )
    binding = {field: str(value[field]).strip() for field in SCENE_BINDING_FIELDS}
    empty = sorted(field for field, item in binding.items() if not item)
    if empty:
        raise WorkflowMeshEventError(
            f"scene_binding fields must be non-empty: {empty}"
        )
    return binding


def _canonical_admission(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _validate_admission_payload(payload: dict[str, Any]) -> dict[str, Any]:
    admission = payload.get("admission") or payload
    if not isinstance(admission, dict):
        raise WorkflowMeshEventError("WorkflowAdmitted requires an admission grant")
    required = {
        "admission_id",
        "status",
        "workflow_run_id",
        "trace_id",
        "step_run_ids",
        "capabilities",
        "policy_digest",
        "issued_at",
        "expires_at",
        "proof",
    }
    missing = sorted(required - admission.keys())
    if missing:
        raise WorkflowMeshEventError(f"Admission grant missing fields: {missing}")
    if admission["status"] != "admitted":
        raise WorkflowMeshEventError("WorkflowAdmitted grant must be admitted")
    unsigned = {key: value for key, value in admission.items() if key != "proof"}
    expected_proof = hashlib.sha256(_canonical_admission(unsigned)).hexdigest()
    if admission["proof"] != expected_proof:
        raise WorkflowMeshEventError("Admission grant proof mismatch")
    if not isinstance(admission["step_run_ids"], list) or not admission["step_run_ids"]:
        raise WorkflowMeshEventError("Admission grant requires step_run_ids")
    return admission


def _step_is_admitted(step_run_id: str, admission: dict[str, Any]) -> bool:
    return any(
        step_run_id == admitted or step_run_id.startswith(f"{admitted}:")
        for admitted in admission["step_run_ids"]
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_workflow_event(
    event_type: str,
    workflow_run_id: str,
    *,
    trace_id: str | None = None,
    producer: str = "omo",
    payload: dict[str, Any] | None = None,
    scene_binding: Mapping[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    event_id = uuid4().hex
    event_payload = dict(payload or {})
    if scene_binding is not None:
        existing = event_payload.get("scene_binding")
        if existing is not None and existing != scene_binding:
            raise WorkflowMeshEventError("conflicting scene_binding payload")
        event_payload["scene_binding"] = dict(scene_binding)
    return {
        "event_id": event_id,
        "event_type": event_type,
        "trace_id": trace_id or workflow_run_id,
        "workflow_run_id": workflow_run_id,
        "occurred_at": _utc_now(),
        "producer": producer,
        "schema_version": "workflow-mesh/v1",
        "idempotency_key": idempotency_key
        or f"{workflow_run_id}:{event_type}:{event_payload.get('step_run_id', 'workflow')}",
        "payload": event_payload,
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
        raise WorkflowMeshEventError(
            f"Unknown Workflow Mesh event: {event['event_type']}"
        )
    if not isinstance(event["payload"], dict):
        raise WorkflowMeshEventError("Workflow Mesh event payload must be an object")
    _scene_binding(event["payload"])
    return event


def project_workflow_run(
    events: list[dict[str, Any]], workflow_run_id: str
) -> dict[str, Any]:
    """从事件重建一个运行快照，拒绝终态后的幽灵事件。"""
    # Append-only 文件顺序是状态机顺序；不能按调用方时间戳重排，否则迟到事件
    # 可能被插入历史位置，绕过终态和恢复检查。
    relevant = [
        event for event in events if event.get("workflow_run_id") == workflow_run_id
    ]
    snapshot: dict[str, Any] = {
        "workflow_run_id": workflow_run_id,
        "trace_id": None,
        "state": "unknown",
        "event_count": 0,
        "step_states": {},
        "last_event_type": None,
        "last_event_at": None,
        "metadata": {},
        "step_runs": {},
        "checkpoints": [],
        "evidence": {},
        "approvals": {},
        "admission": None,
        "worker": None,
        "worker_events": [],
        "scene_binding": None,
    }
    for event in relevant:
        validate_workflow_event(event)
        event_type = event["event_type"]
        next_state = EVENT_STATE[event_type]
        # Step-level progress can arrive out of order or in batches. It updates
        # the step projection without moving the workflow backwards.
        if snapshot["state"] == "running" and event_type in {
            "StepDispatched",
            "StepStarted",
            "StepHeartbeat",
            "CheckpointSaved",
        }:
            next_state = "running"
        elif snapshot["state"] == "dispatched" and event_type == "StepDispatched":
            next_state = "dispatched"
        elif event_type == "WorkerAcknowledged" and snapshot["state"] in {
            "dispatched",
            "running",
        }:
            next_state = snapshot["state"]
        if snapshot["state"] in TERMINAL_STATES:
            raise WorkflowMeshEventError(
                f"Workflow run is terminal; event is not allowed: {event['event_type']}"
            )
        if event_type not in _ALLOWED_EVENTS.get(
            snapshot["state"], set()
        ) or next_state not in _ALLOWED_TRANSITIONS.get(snapshot["state"], set()):
            raise WorkflowMeshEventError(
                "Workflow run is terminal or requires recovery; "
                f"invalid transition {snapshot['state']} -> {next_state} "
                f"for {event_type}"
            )
        if event_type == "EvidenceRecorded" and not event["payload"].get("evidence_id"):
            raise WorkflowMeshEventError("EvidenceRecorded requires evidence_id")
        if event_type == "WorkflowAdmitted":
            admission = _validate_admission_payload(event["payload"])
            if admission["workflow_run_id"] != workflow_run_id:
                raise WorkflowMeshEventError("Admission grant workflow_run_id mismatch")
            snapshot["admission"] = dict(admission)
        scene_binding = _scene_binding(event["payload"])
        if event_type == "WorkflowRequested":
            snapshot["scene_binding"] = scene_binding
        elif scene_binding is not None:
            if snapshot["scene_binding"] is None:
                raise WorkflowMeshEventError(
                    "scene_binding requires a prior WorkflowRequested event"
                )
            if scene_binding != snapshot["scene_binding"]:
                raise WorkflowMeshEventError("scene_binding cannot change within a run")
        if (
            event_type
            in {
                "StepDispatched",
                "StepStarted",
                "StepHeartbeat",
                "StepRetryScheduled",
                "CheckpointSaved",
                "CompensationStarted",
                "StepFailed",
            }
            | _WORKER_EVENTS
        ):
            step_run_id = event["payload"].get("step_run_id")
            admission = snapshot.get("admission")
            if not step_run_id or not isinstance(admission, dict):
                raise WorkflowMeshEventError(
                    f"{event_type} requires an admitted StepRun"
                )
            if event["payload"].get("admission_id") != admission["admission_id"]:
                raise WorkflowMeshEventError(f"{event_type} admission_id mismatch")
            if not _step_is_admitted(step_run_id, admission):
                raise WorkflowMeshEventError(f"StepRun is not admitted: {step_run_id}")
            if (
                event_type != "StepDispatched"
                and step_run_id not in snapshot["step_runs"]
            ):
                raise WorkflowMeshEventError(
                    f"{event_type} requires prior StepDispatched"
                )
        if event_type in _WORKER_EVENTS:
            required_worker_fields = {
                "dispatch_id",
                "worker_id",
                "step_run_id",
                "admission_id",
            }
            missing_worker_fields = sorted(
                required_worker_fields - event["payload"].keys()
            )
            if missing_worker_fields:
                raise WorkflowMeshEventError(
                    f"{event_type} missing worker fields: {missing_worker_fields}"
                )
            event_specific_fields = {
                "WorkerAcknowledged": {"acknowledged_at", "lease_expires_at"},
                "WorkerLeaseRenewed": {
                    "heartbeat_id",
                    "heartbeat_at",
                    "lease_expires_at",
                },
                "WorkerLeaseExpired": {
                    "expired_at",
                    "lease_expires_at",
                    "reason",
                },
                "WorkerReclaimed": {
                    "reclaimed_at",
                    "successor_worker_id",
                    "successor_dispatch_id",
                    "reason",
                },
            }[event_type]
            missing_specific_fields = sorted(
                event_specific_fields - event["payload"].keys()
            )
            if missing_specific_fields:
                raise WorkflowMeshEventError(
                    f"{event_type} missing fields: {missing_specific_fields}"
                )
            current_worker = snapshot.get("worker")
            if not isinstance(current_worker, dict):
                raise WorkflowMeshEventError(
                    f"{event_type} requires prior StepDispatched worker context"
                )
            for key in ("dispatch_id", "worker_id", "step_run_id", "admission_id"):
                if current_worker.get(key) != event["payload"].get(key):
                    raise WorkflowMeshEventError(
                        f"{event_type} worker context mismatch: {key}"
                    )
            worker_state = current_worker.get("state")
            if event_type == "WorkerAcknowledged" and worker_state not in {
                "dispatched",
                "acknowledged",
            }:
                raise WorkflowMeshEventError(
                    "WorkerAcknowledged requires a dispatched worker"
                )
            if event_type == "WorkerLeaseRenewed" and worker_state not in {
                "acknowledged",
                "active",
            }:
                raise WorkflowMeshEventError(
                    "WorkerLeaseRenewed requires an acknowledged worker"
                )
            if event_type == "WorkerLeaseExpired" and worker_state not in {
                "acknowledged",
                "active",
            }:
                raise WorkflowMeshEventError(
                    "WorkerLeaseExpired requires a live worker lease"
                )
            if event_type == "WorkerReclaimed" and worker_state != "lease_expired":
                raise WorkflowMeshEventError(
                    "WorkerReclaimed requires an expired worker lease"
                )
        if event_type == "WorkflowVerified" and not snapshot["evidence"]:
            raise WorkflowMeshEventError(
                "WorkflowVerified requires at least one EvidenceRecorded event"
            )
        snapshot["trace_id"] = snapshot["trace_id"] or event["trace_id"]
        snapshot["state"] = next_state
        snapshot["event_count"] += 1
        snapshot["last_event_type"] = event["event_type"]
        snapshot["last_event_at"] = event["occurred_at"]
        for key in (
            "workflow",
            "workflow_definition_id",
            "intent_id",
            "task_id",
            "evidence_id",
            "pr_id",
            "pr_url",
        ):
            if key in event["payload"] and key not in snapshot["metadata"]:
                snapshot["metadata"][key] = event["payload"][key]
        step_run_id = event["payload"].get("step_run_id")
        if step_run_id:
            step_projection = snapshot["step_runs"].setdefault(
                step_run_id,
                {
                    "step_run_id": step_run_id,
                    "step_name": event["payload"].get("step_name"),
                    "state": "unknown",
                    "attempt": event["payload"].get("attempt", 1),
                    "last_event_type": None,
                    "checkpoint": None,
                    "admission_id": event["payload"].get("admission_id"),
                },
            )
            step_projection["step_name"] = step_projection.get("step_name") or event[
                "payload"
            ].get("step_name")
            step_projection["state"] = {
                "StepDispatched": "dispatched",
                "StepStarted": "running",
                "StepHeartbeat": "running",
                "StepRetryScheduled": "running",
                "CheckpointSaved": "running",
                "CompensationStarted": "compensating",
                "StepFailed": "failed",
                "WorkerLeaseRenewed": "running",
                "WorkerLeaseExpired": "unavailable",
                "WorkerReclaimed": "running",
            }.get(event_type, step_projection["state"])
            step_projection["last_event_type"] = event_type
            step_projection["admission_id"] = event["payload"].get(
                "admission_id", step_projection.get("admission_id")
            )
            if event_type == "CheckpointSaved":
                checkpoint = {
                    "checkpoint_id": event["payload"].get("checkpoint_id")
                    or event["event_id"],
                    "step_run_id": step_run_id,
                    "attempt": event["payload"].get("attempt", 1),
                    "next_turn": event["payload"].get("next_turn"),
                    "checkpoint": event["payload"].get("checkpoint"),
                    "event_id": event["event_id"],
                }
                step_projection["checkpoint"] = checkpoint
                snapshot["checkpoints"].append(checkpoint)
            snapshot["step_states"][step_run_id] = {
                "state": step_projection["state"],
                "last_event_type": event["event_type"],
            }
        if event_type == "StepDispatched" and event["payload"].get("dispatch_id"):
            snapshot["worker"] = {
                "dispatch_id": event["payload"]["dispatch_id"],
                "worker_id": event["payload"].get("worker_id"),
                "step_run_id": event["payload"].get("step_run_id"),
                "admission_id": event["payload"].get("admission_id"),
                "state": "dispatched",
                "dispatched_at": event["occurred_at"],
            }
        if event_type in _WORKER_EVENTS:
            worker = snapshot["worker"]
            assert isinstance(worker, dict)
            payload = event["payload"]
            if event_type == "WorkerAcknowledged":
                worker.update(
                    {
                        "state": "acknowledged",
                        "acknowledged_at": payload["acknowledged_at"],
                        "lease_expires_at": payload["lease_expires_at"],
                    }
                )
            elif event_type == "WorkerLeaseRenewed":
                worker.update(
                    {
                        "state": "active",
                        "heartbeat_id": payload["heartbeat_id"],
                        "heartbeat_at": payload["heartbeat_at"],
                        "lease_expires_at": payload["lease_expires_at"],
                    }
                )
            elif event_type == "WorkerLeaseExpired":
                worker.update(
                    {
                        "state": "lease_expired",
                        "expired_at": payload["expired_at"],
                        "lease_expires_at": payload["lease_expires_at"],
                        "reason": payload.get("reason"),
                    }
                )
            else:
                worker.update(
                    {
                        "state": "reclaimed",
                        "reclaimed_at": payload["reclaimed_at"],
                        "reason": payload.get("reason"),
                        "successor_worker_id": payload["successor_worker_id"],
                        "successor_dispatch_id": payload["successor_dispatch_id"],
                    }
                )
            snapshot["worker_events"].append(
                {
                    "event_id": event["event_id"],
                    "event_type": event_type,
                    "dispatch_id": payload["dispatch_id"],
                    "worker_id": payload["worker_id"],
                    "occurred_at": event["occurred_at"],
                }
            )
        if event_type == "EvidenceRecorded":
            evidence_id = event["payload"]["evidence_id"]
            snapshot["evidence"][evidence_id] = {
                "evidence_id": evidence_id,
                "kind": event["payload"].get("kind"),
                "uri": event["payload"].get("uri"),
                "sha256": event["payload"].get("sha256"),
                "event_id": event["event_id"],
            }
        if event_type in {"ApprovalRequested", "ApprovalGranted"}:
            approval_id = event["payload"].get("approval_id") or "workflow"
            snapshot["approvals"][approval_id] = {
                "approval_id": approval_id,
                "state": "requested"
                if event_type == "ApprovalRequested"
                else "granted",
                "event_id": event["event_id"],
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
                if (
                    existing.get("event_id") != event["event_id"]
                    and existing.get("idempotency_key") != event["idempotency_key"]
                ):
                    continue
                if existing == event:
                    return existing
                raise WorkflowMeshEventError(
                    "Conflicting duplicate Workflow Mesh event: "
                    f"{event['event_id']} / {event['idempotency_key']}"
                )
            run_id = event["workflow_run_id"]
            candidate = [*current, event]
            project_workflow_run(candidate, run_id)
            return self._log.append(event, sort_keys=True)

    def snapshot(self, workflow_run_id: str) -> dict[str, Any]:
        return project_workflow_run(self.events(), workflow_run_id)

    def step_snapshot(
        self, workflow_run_id: str, step_run_id: str
    ) -> dict[str, Any] | None:
        """Return the projected StepRun owned by a WorkflowRun."""
        return self.snapshot(workflow_run_id)["step_runs"].get(step_run_id)

    def evidence_snapshot(
        self, workflow_run_id: str, evidence_id: str
    ) -> dict[str, Any] | None:
        """Return one evidence projection owned by a WorkflowRun."""
        return self.snapshot(workflow_run_id)["evidence"].get(evidence_id)

    def worker_snapshot(self, workflow_run_id: str) -> dict[str, Any] | None:
        """Return the current durable worker lease projection for a run."""
        return self.snapshot(workflow_run_id).get("worker")

    def snapshots(self) -> list[dict[str, Any]]:
        """返回所有运行快照，顺序按事件日志中最后一次出现的顺序。"""
        events = self.events()
        run_ids = list(
            dict.fromkeys(
                event.get("workflow_run_id")
                for event in events
                if event.get("workflow_run_id")
            )
        )
        last_indexes = {
            str(run_id): index
            for index, event in enumerate(events)
            for run_id in [event.get("workflow_run_id")]
            if run_id
        }
        snapshots = []
        for run_id in run_ids:
            snapshot = project_workflow_run(events, str(run_id))
            snapshot["event_sequence"] = last_indexes[str(run_id)]
            snapshots.append(snapshot)
        return sorted(snapshots, key=lambda snapshot: snapshot["event_sequence"])

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
