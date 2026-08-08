"""Tests for omo.approval_timeout_runner — governed approval timeout scanner."""

from __future__ import annotations

import hashlib
import json

import pytest
from omo.approval_lifecycle import request_approval
from omo.approval_timeout_runner import (
    _exclusive_run_lock,
    _paths,
    read_latest_approval_timeout_run,
    run_once,
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
        "issued_at": "2026-08-02T00:00:00Z",
        "expires_at": "2026-08-02T01:00:00Z",
    }
    grant["proof"] = hashlib.sha256(
        json.dumps(
            grant, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return grant


def _waiting_approval_run(tmp_path, run_id: str = "run-runner") -> None:
    step_run_id = f"{run_id}:execute"
    grant = _grant(run_id, step_run_id)
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowRequested", run_id))
    store.append(
        new_workflow_event(
            "WorkflowAdmitted", run_id, payload={"admission": grant, **grant}
        )
    )
    from omo.worker_lifecycle import record_step_dispatch

    record_step_dispatch(
        tmp_path,
        workflow_run_id=run_id,
        trace_id=run_id,
        dispatch_id="dispatch-1",
        worker_id="worker-a",
        step_run_id=step_run_id,
        admission_id=grant["admission_id"],
    )
    store.append(
        new_workflow_event(
            "StepStarted",
            run_id,
            payload={
                "step_run_id": step_run_id,
                "admission_id": grant["admission_id"],
                "dispatch_id": "dispatch-1",
                "worker_id": "worker-a",
            },
        )
    )
    request_approval(
        tmp_path,
        workflow_run_id=run_id,
        trace_id=run_id,
        timeout_seconds=86400,
        now="2026-08-01T00:00:00Z",
    )


class TestRunnerDryRun:
    def test_dry_run_does_not_mutate(self, tmp_path):
        _waiting_approval_run(tmp_path)
        before = len(WorkflowMeshStore(tmp_path).events())

        result = run_once(tmp_path, now="2026-08-03T00:00:00Z")

        assert result["status"] == "completed"
        assert result["mode"] == "dry_run"
        assert result["scan"]["due_count"] == 1
        assert result["scan"]["expired_count"] == 0
        after = len(WorkflowMeshStore(tmp_path).events())
        assert before == after

    def test_dry_run_persists_summary(self, tmp_path):
        _waiting_approval_run(tmp_path)
        result = run_once(tmp_path, now="2026-08-03T00:00:00Z")
        assert result["ledger_recorded"] is True
        latest = read_latest_approval_timeout_run(tmp_path)
        assert latest is not None
        assert latest["scan"]["due_count"] == 1


class TestRunnerApply:
    def test_apply_expires(self, tmp_path):
        _waiting_approval_run(tmp_path)
        result = run_once(tmp_path, now="2026-08-03T00:00:00Z", apply=True)
        assert result["status"] == "completed"
        assert result["scan"]["expired_count"] == 1
        assert "run-runner" in result["scan"]["expired_workflow_run_ids"]
        snapshot = WorkflowMeshStore(tmp_path).snapshot("run-runner")
        assert snapshot["state"] == "failed"


class TestRunnerLock:
    def test_concurrent_run_skipped(self, tmp_path):
        _waiting_approval_run(tmp_path)
        _, _, lock_path = _paths(tmp_path)
        with _exclusive_run_lock(lock_path) as acquired:
            assert acquired
            result = run_once(tmp_path, now="2026-08-03T00:00:00Z")
            assert result["status"] == "skipped"
            assert result["skip_reason"] == "already_running"


class TestRunnerNoWaiting:
    def test_no_waiting_approvals(self, tmp_path):
        store = WorkflowMeshStore(tmp_path)
        store.append(new_workflow_event("WorkflowRequested", "run-x"))
        result = run_once(tmp_path, now="2026-08-10T00:00:00Z")
        assert result["status"] == "completed"
        assert result["scan"]["due_count"] == 0
        assert result["scan"]["expired_count"] == 0
