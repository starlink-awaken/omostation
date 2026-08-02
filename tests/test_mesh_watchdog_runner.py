from __future__ import annotations

import hashlib
import json

import pytest
from omo.cli import main as cli_main
from omo.mesh_watchdog_runner import (
    _exclusive_run_lock,
    _paths,
    read_latest_mesh_watchdog_run,
    run_once,
)
from omo.worker_lifecycle import acknowledge_worker, record_step_dispatch
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


def _context(tmp_path, run_id: str = "run-runner") -> dict[str, str]:
    step_run_id = f"{run_id}:execute"
    grant = _grant(run_id, step_run_id)
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowRequested", run_id))
    store.append(
        new_workflow_event(
            "WorkflowAdmitted", run_id, payload={"admission": grant, **grant}
        )
    )
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


def test_runner_dry_run_is_durable_and_does_not_mutate_mesh(tmp_path):
    context = _context(tmp_path)
    acknowledge_worker(
        tmp_path, **context, lease_seconds=60, now="2026-08-02T00:00:00Z"
    )
    before = len(WorkflowMeshStore(tmp_path).events())

    result = run_once(tmp_path, now="2026-08-02T00:01:00Z")

    assert result["status"] == "completed"
    assert result["mode"] == "dry_run"
    assert result["scan"]["due_count"] == 1
    assert result["scan"]["expired_count"] == 0
    assert len(WorkflowMeshStore(tmp_path).events()) == before
    assert result["ledger_recorded"] is True

    latest = read_latest_mesh_watchdog_run(tmp_path)
    assert latest is not None
    assert latest["run_id"] == result["run_id"]
    assert latest["scan"]["due_workflow_run_ids"] == [context["workflow_run_id"]]
    assert "worker_id" not in latest


def test_runner_apply_expires_once_and_never_reclaims(tmp_path):
    context = _context(tmp_path, "run-apply")
    acknowledge_worker(
        tmp_path, **context, lease_seconds=60, now="2026-08-02T00:00:00Z"
    )

    applied = run_once(
        tmp_path, now="2026-08-02T00:01:00Z", apply=True, reason="runner_timeout"
    )
    repeated = run_once(tmp_path, now="2026-08-02T00:02:00Z", apply=True)

    assert applied["status"] == "completed"
    assert applied["scan"]["expired_count"] == 1
    assert repeated["status"] == "completed"
    assert repeated["scan"]["expired_count"] == 0
    assert (
        WorkflowMeshStore(tmp_path).snapshot(context["workflow_run_id"])["worker"][
            "state"
        ]
        == "lease_expired"
    )
    assert not any(
        event["event_type"] == "WorkerReclaimed"
        for event in WorkflowMeshStore(tmp_path).events()
    )


def test_runner_skips_overlapping_tick(tmp_path):
    _, _, lock_path = _paths(tmp_path)
    with _exclusive_run_lock(lock_path) as acquired:
        assert acquired is True
        result = run_once(tmp_path, now="2026-08-02T00:01:00Z")

    assert result["status"] == "skipped"
    assert result["skip_reason"] == "already_running"
    assert result["ledger_recorded"] is True


def test_public_cli_runs_governed_runner(tmp_path, capsys):
    assert (
        cli_main(["worker", "mesh-watchdog-run", "--json", "--omo-dir", str(tmp_path)])
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "workflow-mesh-watchdog-run/v1"
    assert payload["status"] == "completed"


@pytest.mark.parametrize("bad_reason", ["", "   "])
def test_runner_rejects_empty_reason_without_mesh_mutation(tmp_path, bad_reason):
    result = run_once(tmp_path, reason=bad_reason)
    assert result["status"] == "failed"
    assert result["scan"]["expired_count"] == 0
    assert result["errors"]
