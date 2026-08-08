"""Tests for omo.approval_lifecycle — durable approval timeout."""

from __future__ import annotations

import hashlib
import json

import pytest
from omo.approval_lifecycle import (
    ApprovalLifecycleError,
    expire_approval_timeout,
    grant_approval,
    request_approval,
    scan_approval_timeouts,
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


def _running_run(tmp_path, run_id: str = "run-approval") -> None:
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


class TestRequestApproval:
    def test_request_with_default_timeout(self, tmp_path):
        _running_run(tmp_path)
        event = request_approval(
            tmp_path,
            workflow_run_id="run-approval",
            trace_id="run-approval",
            now="2026-08-01T00:00:00Z",
        )
        assert event["event_type"] == "ApprovalRequested"
        assert event["payload"]["timeout_seconds"] == 604_800
        assert event["payload"]["requested_at"] == "2026-08-01T00:00:00Z"
        assert event["payload"]["timeout_at"] == "2026-08-08T00:00:00Z"

    def test_request_with_custom_timeout(self, tmp_path):
        _running_run(tmp_path)
        event = request_approval(
            tmp_path,
            workflow_run_id="run-approval",
            trace_id="run-approval",
            timeout_seconds=3600,
            now="2026-08-01T00:00:00Z",
        )
        assert event["payload"]["timeout_seconds"] == 3600
        assert event["payload"]["timeout_at"] == "2026-08-01T01:00:00Z"

    def test_request_rejects_non_running(self, tmp_path):
        store = WorkflowMeshStore(tmp_path)
        store.append(new_workflow_event("WorkflowRequested", "run-x"))
        with pytest.raises(ApprovalLifecycleError, match="cannot request approval"):
            request_approval(
                tmp_path,
                workflow_run_id="run-x",
                trace_id="run-x",
            )

    def test_request_idempotent(self, tmp_path):
        _running_run(tmp_path)
        e1 = request_approval(
            tmp_path,
            workflow_run_id="run-approval",
            trace_id="run-approval",
            now="2026-08-01T00:00:00Z",
        )
        e2 = request_approval(
            tmp_path,
            workflow_run_id="run-approval",
            trace_id="run-approval",
            now="2026-08-01T00:00:00Z",
        )
        assert e1["event_id"] == e2["event_id"]

    def test_request_rejects_zero_timeout(self, tmp_path):
        _running_run(tmp_path)
        with pytest.raises(ApprovalLifecycleError, match="timeout_seconds must be positive"):
            request_approval(
                tmp_path,
                workflow_run_id="run-approval",
                trace_id="run-approval",
                timeout_seconds=0,
            )


class TestGrantApproval:
    def test_grant_transitions_to_running(self, tmp_path):
        _running_run(tmp_path)
        request_approval(
            tmp_path,
            workflow_run_id="run-approval",
            trace_id="run-approval",
            now="2026-08-01T00:00:00Z",
        )
        snapshot = WorkflowMeshStore(tmp_path).snapshot("run-approval")
        assert snapshot["state"] == "waiting_approval"

        grant_approval(
            tmp_path,
            workflow_run_id="run-approval",
            trace_id="run-approval",
            now="2026-08-02T00:00:00Z",
        )
        snapshot = WorkflowMeshStore(tmp_path).snapshot("run-approval")
        assert snapshot["state"] == "running"
        assert snapshot["approvals"]["workflow"]["state"] == "granted"

    def test_grant_rejects_non_waiting(self, tmp_path):
        _running_run(tmp_path)
        with pytest.raises(ApprovalLifecycleError, match="cannot grant approval"):
            grant_approval(
                tmp_path,
                workflow_run_id="run-approval",
                trace_id="run-approval",
            )


class TestExpireApprovalTimeout:
    def test_expire_after_timeout(self, tmp_path):
        _running_run(tmp_path)
        request_approval(
            tmp_path,
            workflow_run_id="run-approval",
            trace_id="run-approval",
            timeout_seconds=86400,
            now="2026-08-01T00:00:00Z",
        )
        event = expire_approval_timeout(
            tmp_path,
            workflow_run_id="run-approval",
            trace_id="run-approval",
            now="2026-08-03T00:00:00Z",
        )
        assert event["event_type"] == "ApprovalTimeout"
        assert event["payload"]["reason"] == "approval_timeout"
        snapshot = WorkflowMeshStore(tmp_path).snapshot("run-approval")
        assert snapshot["state"] == "failed"
        assert snapshot["approvals"]["workflow"]["state"] == "timed_out"

    def test_expire_rejects_before_timeout(self, tmp_path):
        _running_run(tmp_path)
        request_approval(
            tmp_path,
            workflow_run_id="run-approval",
            trace_id="run-approval",
            timeout_seconds=86400,
            now="2026-08-01T00:00:00Z",
        )
        with pytest.raises(ApprovalLifecycleError, match="has not expired"):
            expire_approval_timeout(
                tmp_path,
                workflow_run_id="run-approval",
                trace_id="run-approval",
                now="2026-08-01T12:00:00Z",
            )

    def test_expire_rejects_non_waiting(self, tmp_path):
        _running_run(tmp_path)
        with pytest.raises(ApprovalLifecycleError, match="cannot expire"):
            expire_approval_timeout(
                tmp_path,
                workflow_run_id="run-approval",
                trace_id="run-approval",
            )


class TestScanApprovalTimeouts:
    def test_dry_run_does_not_mutate(self, tmp_path):
        _running_run(tmp_path)
        request_approval(
            tmp_path,
            workflow_run_id="run-approval",
            trace_id="run-approval",
            timeout_seconds=86400,
            now="2026-08-01T00:00:00Z",
        )
        before = len(WorkflowMeshStore(tmp_path).events())
        result = scan_approval_timeouts(
            tmp_path, now="2026-08-03T00:00:00Z"
        )
        after = len(WorkflowMeshStore(tmp_path).events())
        assert before == after
        assert result["due_count"] == 1
        assert result["expired_count"] == 0
        assert result["mode"] == "dry_run"

    def test_apply_expires(self, tmp_path):
        _running_run(tmp_path)
        request_approval(
            tmp_path,
            workflow_run_id="run-approval",
            trace_id="run-approval",
            timeout_seconds=86400,
            now="2026-08-01T00:00:00Z",
        )
        result = scan_approval_timeouts(
            tmp_path, now="2026-08-03T00:00:00Z", apply=True
        )
        assert result["expired_count"] == 1
        assert result["expired"][0]["workflow_run_id"] == "run-approval"
        snapshot = WorkflowMeshStore(tmp_path).snapshot("run-approval")
        assert snapshot["state"] == "failed"

    def test_seven_day_scenario(self, tmp_path):
        _running_run(tmp_path, "run-7day")
        request_approval(
            tmp_path,
            workflow_run_id="run-7day",
            trace_id="run-7day",
            now="2026-08-01T00:00:00Z",
        )
        result_before = scan_approval_timeouts(
            tmp_path, now="2026-08-07T23:59:59Z"
        )
        assert result_before["due_count"] == 0

        result_after = scan_approval_timeouts(
            tmp_path, now="2026-08-08T00:00:00Z", apply=True
        )
        assert result_after["expired_count"] == 1

    def test_process_restart_survival(self, tmp_path):
        _running_run(tmp_path, "run-restart")
        request_approval(
            tmp_path,
            workflow_run_id="run-restart",
            trace_id="run-restart",
            timeout_seconds=86400,
            now="2026-08-01T00:00:00Z",
        )
        new_store = WorkflowMeshStore(tmp_path)
        snapshot = new_store.snapshot("run-restart")
        assert snapshot["state"] == "waiting_approval"
        assert snapshot["approvals"]["workflow"]["timeout_at"] == "2026-08-02T00:00:00Z"

        result = scan_approval_timeouts(
            tmp_path, now="2026-08-03T00:00:00Z", apply=True
        )
        assert result["expired_count"] == 1

    def test_skips_non_waiting(self, tmp_path):
        _running_run(tmp_path, "run-running")
        result = scan_approval_timeouts(tmp_path, now="2026-08-10T00:00:00Z")
        assert result["due_count"] == 0
        assert result["expired_count"] == 0
