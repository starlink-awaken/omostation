from __future__ import annotations

# ruff: noqa: I001

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from omo.worker_lifecycle import (
    WorkerLifecycleError,
    acknowledge_worker,
    expire_worker_lease,
    reclaim_worker,
    record_step_dispatch,
    renew_worker_lease,
)
from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event


def _grant(run_id: str, step_run_id: str) -> dict:
    grant = {
        "admission_id": f"adm-{run_id}",
        "status": "admitted",
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "backend": "test",
        "step_run_ids": [step_run_id],
        "capabilities": ["execute"],
        "policy_digest": "policy-test",
        "issued_at": datetime.now(UTC).isoformat(),
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    grant["proof"] = hashlib.sha256(
        json.dumps(
            grant, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return grant


def _admit(store: WorkflowMeshStore, run_id: str, grant: dict) -> None:
    store.append(new_workflow_event("WorkflowRequested", run_id))
    store.append(
        new_workflow_event(
            "WorkflowAdmitted", run_id, payload={"admission": grant, **grant}
        )
    )


def _context(tmp_path, run_id: str = "run-worker") -> dict[str, str]:
    step_run_id = f"{run_id}:execute"
    grant = _grant(run_id, step_run_id)
    store = WorkflowMeshStore(tmp_path)
    _admit(store, run_id, grant)
    record_step_dispatch(
        tmp_path,
        workflow_run_id=run_id,
        trace_id=run_id,
        dispatch_id="dispatch-1",
        worker_id="worker-a",
        step_run_id=step_run_id,
        admission_id=grant["admission_id"],
    )
    return {
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "dispatch_id": "dispatch-1",
        "worker_id": "worker-a",
        "step_run_id": step_run_id,
        "admission_id": grant["admission_id"],
    }


def test_worker_lifecycle_is_durable_and_idempotent(tmp_path):
    context = _context(tmp_path)
    ack = acknowledge_worker(
        tmp_path, **context, lease_seconds=60, now="2026-08-02T00:00:00Z"
    )
    assert (
        acknowledge_worker(
            tmp_path, **context, lease_seconds=60, now="2026-08-02T00:00:00Z"
        )
        == ack
    )

    renewed = renew_worker_lease(
        tmp_path,
        **context,
        lease_seconds=60,
        now="2026-08-02T00:00:30Z",
        heartbeat_id="hb-1",
    )
    snapshot = WorkflowMeshStore(tmp_path).snapshot(context["workflow_run_id"])
    assert renewed["event_type"] == "WorkerLeaseRenewed"
    assert snapshot["state"] == "running"
    assert snapshot["worker"]["state"] == "active"
    assert snapshot["worker"]["heartbeat_id"] == "hb-1"
    assert len(snapshot["worker_events"]) == 2


def test_worker_lease_expires_only_after_deadline_and_can_be_reclaimed(tmp_path):
    context = _context(tmp_path, "run-expiry")
    acknowledge_worker(
        tmp_path, **context, lease_seconds=60, now="2026-08-02T00:00:00Z"
    )
    with pytest.raises(WorkerLifecycleError, match="not expired"):
        expire_worker_lease(tmp_path, **context, now="2026-08-02T00:00:30Z")

    expired = expire_worker_lease(
        tmp_path,
        **context,
        now="2026-08-02T00:01:00Z",
        reason="worker_lost",
    )
    assert expired["event_type"] == "WorkerLeaseExpired"
    assert (
        expire_worker_lease(
            tmp_path,
            **context,
            now="2026-08-02T00:02:00Z",
            reason="worker_lost",
        )
        == expired
    )

    reclaimed = reclaim_worker(
        tmp_path,
        **context,
        successor_worker_id="worker-b",
        successor_dispatch_id="dispatch-2",
        now="2026-08-02T00:01:05Z",
    )
    snapshot = WorkflowMeshStore(tmp_path).snapshot(context["workflow_run_id"])
    assert reclaimed["event_type"] == "WorkerReclaimed"
    assert snapshot["state"] == "running"
    assert snapshot["worker"]["state"] == "reclaimed"
    assert snapshot["worker"]["successor_worker_id"] == "worker-b"


def test_worker_heartbeat_requires_ack_and_owner_context(tmp_path):
    context = _context(tmp_path, "run-invalid")
    with pytest.raises(WorkerLifecycleError, match="ACK"):
        renew_worker_lease(tmp_path, **context)

    acknowledge_worker(
        tmp_path, **context, lease_seconds=60, now="2026-08-02T00:00:00Z"
    )
    with pytest.raises(WorkerLifecycleError, match="owner"):
        renew_worker_lease(
            tmp_path,
            **{**context, "worker_id": "worker-other"},
            heartbeat_id="hb-other",
            now="2026-08-02T00:00:30Z",
        )


def test_worker_reclaim_requires_expiry(tmp_path):
    context = _context(tmp_path, "run-reclaim-before-expiry")
    acknowledge_worker(
        tmp_path, **context, lease_seconds=60, now="2026-08-02T00:00:00Z"
    )
    with pytest.raises(WorkerLifecycleError, match="expired"):
        reclaim_worker(
            tmp_path,
            **context,
            successor_worker_id="worker-b",
            successor_dispatch_id="dispatch-2",
            now="2026-08-02T00:01:00Z",
        )
