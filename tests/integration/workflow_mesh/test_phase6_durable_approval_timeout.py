"""BET-Y1Q2-T5-01 integration: durable approval timeout across process restart.

The unit tests in ``projects/omo`` cover the state machine and the scan
primitive. These integration tests exercise the real on-disk append-only log
through the root integration harness (``tests/integration/run-all.sh``) and
verify the *durable* property of the timer:

1. A run in ``waiting_approval`` survives a fresh store instance (restart) with
   its deadline intact.
2. After the 7-day policy elapses (injectable ``now``), a scan persists
   ``ApprovalTimeout`` and the run is projected to ``unavailable``.
3. The persisted expiry is idempotent across a second restart and scan.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from omo.approval_lifecycle import request_approval, scan_approval_timeouts
from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event

WEEK = 7 * 24 * 60 * 60


def _grant(run_id: str, step_run_ids: list[str]) -> dict:
    import hashlib
    import json

    grant = {
        "admission_id": f"adm-{run_id}",
        "status": "admitted",
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "backend": "test",
        "step_run_ids": step_run_ids,
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


def _admit(run_id: str, step_run_ids: list[str]) -> dict:
    grant = _grant(run_id, step_run_ids)
    return new_workflow_event(
        "WorkflowAdmitted", run_id, payload={"admission": grant, **grant}
    )


def _waiting_approval_run(tmp_path, run_id: str = "it-approval") -> WorkflowMeshStore:
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowRequested", run_id))
    store.append(_admit(run_id, ["step-1"]))
    grant = _grant(run_id, ["step-1"])
    store.append(
        new_workflow_event(
            "StepDispatched",
            run_id,
            payload={"step_run_id": "step-1", "admission_id": grant["admission_id"]},
        )
    )
    store.append(
        new_workflow_event(
            "StepStarted",
            run_id,
            payload={"step_run_id": "step-1", "admission_id": grant["admission_id"]},
        )
    )
    request_approval(
        tmp_path,
        workflow_run_id=run_id,
        trace_id=run_id,
        timeout_seconds=WEEK,
    )
    assert store.snapshot(run_id)["state"] == "waiting_approval"
    return store


def test_waiting_approval_survives_restart_with_deadline(tmp_path):
    _waiting_approval_run(tmp_path)

    # Simulate process restart: a brand-new store reads the same on-disk log.
    restarted = WorkflowMeshStore(tmp_path)
    snapshot = restarted.snapshot("it-approval")
    assert snapshot["state"] == "waiting_approval"
    approval = snapshot["approvals"]["workflow"]
    assert approval["state"] == "requested"
    assert approval["timeout_at"]
    assert approval["requested_at"]

    # Day 5: still inside the 7-day policy — nothing expires.
    day5 = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    result = scan_approval_timeouts(tmp_path, now=day5)
    assert result["waiting_count"] == 1
    assert result["due_count"] == 0


def test_seven_day_policy_expires_and_is_durable(tmp_path):
    _waiting_approval_run(tmp_path)

    # Day 7 + 1 minute: the injected clock makes the 7-day scenario instant.
    overdue = (datetime.now(UTC) + timedelta(days=7, minutes=1)).isoformat()
    result = scan_approval_timeouts(tmp_path, now=overdue, apply=True)
    assert result["mode"] == "apply"
    assert result["expired_count"] == 1
    assert result["expired"][0]["event_type"] == "ApprovalTimeout"

    # Durable: a restarted process sees the unavailable projection.
    restarted = WorkflowMeshStore(tmp_path)
    snapshot = restarted.snapshot("it-approval")
    assert snapshot["state"] == "unavailable"
    assert snapshot["approvals"]["workflow"]["state"] == "expired"

    # Idempotent: a second scan on a fresh store persists nothing new.
    again = scan_approval_timeouts(tmp_path, now=overdue, apply=True)
    assert again["expired_count"] == 0
    assert again["errors"] == []
