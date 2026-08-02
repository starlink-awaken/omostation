import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from omo.workflow_mesh import (
    WorkflowMeshEventError,
    WorkflowMeshStore,
    new_workflow_event,
)


def _grant(run_id: str, step_run_ids: list[str]) -> dict:
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
        json.dumps(grant, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return grant


def _admit(run_id: str, step_run_ids: list[str]) -> dict:
    grant = _grant(run_id, step_run_ids)
    return new_workflow_event(
        "WorkflowAdmitted", run_id, payload={"admission": grant, **grant}
    )


def test_workflow_mesh_store_projects_lifecycle_and_is_idempotent(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    requested = new_workflow_event(
        "WorkflowRequested",
        "run-1",
        producer="ecos",
        payload={"workflow": "mesh-test", "task_id": "task-1"},
    )
    started = new_workflow_event(
        "StepStarted",
        "run-1",
        producer="runtime",
        payload={"step_run_id": "step-1", "admission_id": "adm-run-1"},
    )
    succeeded = new_workflow_event(
        "WorkflowSucceeded", "run-1", producer="runtime", payload={"step_count": 1}
    )

    store.append(requested)
    store.append(_admit("run-1", ["step-1"]))
    store.append(
        new_workflow_event(
            "StepDispatched",
            "run-1",
            producer="runtime",
            payload={"step_run_id": "step-1", "admission_id": "adm-run-1"},
        )
    )
    store.append(started)
    store.append(succeeded)
    assert store.append(succeeded) == succeeded
    assert store.snapshot("run-1")["state"] == "succeeded"
    assert store.snapshot("run-1")["event_count"] == 5
    assert store.snapshot("run-1")["metadata"]["workflow"] == "mesh-test"


def test_scene_binding_is_projected_and_immutable(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    run_id = "run-scene-binding"
    binding = {
        "scene_id": "official-document-review",
        "journey_id": "draft-to-approval",
        "outcome_metric": "review_cycle_time",
    }
    store.append(
        new_workflow_event("WorkflowRequested", run_id, scene_binding=binding)
    )

    assert store.snapshot(run_id)["scene_binding"] == binding

    changed_binding = {**binding, "outcome_metric": "unapproved-change"}
    with pytest.raises(WorkflowMeshEventError, match="cannot change"):
        store.append(
            new_workflow_event("WorkflowFailed", run_id, scene_binding=changed_binding)
        )


def test_scene_binding_requires_all_business_identifiers(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    with pytest.raises(WorkflowMeshEventError, match="missing fields"):
        store.append(
            new_workflow_event(
                "WorkflowRequested",
                "run-incomplete-scene",
                scene_binding={"scene_id": "official-document-review"},
            )
        )


def test_successful_run_can_be_verified_merged_and_closed(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    grant = _grant("run-lifecycle", ["step-1"])
    for event_type in (
        "WorkflowRequested",
        "WorkflowAdmitted",
        "StepDispatched",
        "StepStarted",
        "WorkflowSucceeded",
        "EvidenceRecorded",
        "WorkflowVerified",
        "PRMerged",
        "WorkflowClosed",
    ):
        payload = (
            {"evidence_id": "evidence-1", "kind": "test", "uri": "memory://evidence-1"}
            if event_type == "EvidenceRecorded"
            else (
                {"admission": grant, **grant}
                if event_type == "WorkflowAdmitted"
                else (
                    {
                        "step_run_id": "step-1",
                        "step_name": "compile",
                        "admission_id": grant["admission_id"],
                    }
                    if event_type in {"StepDispatched", "StepStarted"}
                    else {}
                )
            )
        )
        store.append(new_workflow_event(event_type, "run-lifecycle", payload=payload))

    snapshot = store.snapshot("run-lifecycle")
    assert snapshot["state"] == "closed"
    assert snapshot["last_event_type"] == "WorkflowClosed"
    assert snapshot["event_count"] == 9


def test_step_run_checkpoint_and_evidence_are_queryable(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    events = [
        ("WorkflowRequested", {}),
        ("WorkflowAdmitted", {}),
        ("StepDispatched", {"step_run_id": "step-1", "step_name": "compile"}),
        ("StepStarted", {"step_run_id": "step-1", "step_name": "compile", "attempt": 2}),
        (
            "CheckpointSaved",
            {
                "step_run_id": "step-1",
                "step_name": "compile",
                "checkpoint_id": "cp-1",
                "next_turn": 3,
                "attempt": 2,
            },
        ),
        ("WorkflowSucceeded", {}),
        ("EvidenceRecorded", {"evidence_id": "ev-1", "sha256": "abc"}),
    ]
    grant = _grant("run-query", ["step-1"])
    for event_type, payload in events:
        if event_type == "WorkflowAdmitted":
            payload = {"admission": grant, **grant}
        elif payload.get("step_run_id"):
            payload["admission_id"] = grant["admission_id"]
        store.append(new_workflow_event(event_type, "run-query", payload=payload))

    assert store.step_snapshot("run-query", "step-1")["checkpoint"]["checkpoint_id"] == "cp-1"
    assert store.evidence_snapshot("run-query", "ev-1")["sha256"] == "abc"


def test_verified_requires_evidence(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowRequested", "run-no-evidence"))
    grant = _grant("run-no-evidence", ["step-1"])
    store.append(_admit("run-no-evidence", ["step-1"]))
    store.append(
        new_workflow_event(
            "StepDispatched",
            "run-no-evidence",
            payload={"step_run_id": "step-1", "admission_id": grant["admission_id"]},
        )
    )
    store.append(
        new_workflow_event(
            "StepStarted",
            "run-no-evidence",
            payload={"step_run_id": "step-1", "admission_id": grant["admission_id"]},
        )
    )
    store.append(new_workflow_event("WorkflowSucceeded", "run-no-evidence"))
    with pytest.raises(WorkflowMeshEventError, match="EvidenceRecorded"):
        store.append(new_workflow_event("WorkflowVerified", "run-no-evidence"))


def test_failed_backend_can_recover_with_explicit_event(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowRequested", "run-recovery"))
    store.append(_admit("run-recovery", ["step-1"]))
    store.append(new_workflow_event("BackendUnavailable", "run-recovery"))
    store.append(new_workflow_event("WorkflowRecovered", "run-recovery"))
    store.append(new_workflow_event("WorkflowSucceeded", "run-recovery"))

    assert store.snapshot("run-recovery")["state"] == "succeeded"


def test_append_order_wins_over_late_timestamp(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    requested = new_workflow_event("WorkflowRequested", "run-order")
    grant = _grant("run-order", ["step-1"])
    admitted = _admit("run-order", ["step-1"])
    failed = new_workflow_event("WorkflowFailed", "run-order")
    late_step = new_workflow_event(
        "StepStarted",
        "run-order",
        payload={"step_run_id": "step-1", "admission_id": grant["admission_id"]},
    )
    late_step["occurred_at"] = "1970-01-01T00:00:00+00:00"
    store.append(requested)
    store.append(admitted)
    store.append(failed)
    with pytest.raises(WorkflowMeshEventError, match="terminal"):
        store.append(late_step)


def test_terminal_run_rejects_later_event(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowRequested", "run-2"))
    store.append(new_workflow_event("WorkflowFailed", "run-2"))
    with pytest.raises(WorkflowMeshEventError, match="terminal"):
        store.append(new_workflow_event("StepStarted", "run-2"))


def test_unadmitted_step_is_rejected(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowRequested", "run-unadmitted"))
    with pytest.raises(WorkflowMeshEventError, match="admitted StepRun"):
        store.append(
            new_workflow_event(
                "StepDispatched",
                "run-unadmitted",
                payload={"step_run_id": "run-unadmitted:step-1"},
            )
        )


def test_retry_and_compensation_events_preserve_step_truth(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    run_id = "run-compensation"
    step_id = f"{run_id}:step-1"
    grant = _grant(run_id, [step_id])
    store.append(new_workflow_event("WorkflowRequested", run_id))
    store.append(_admit(run_id, [step_id]))
    store.append(
        new_workflow_event(
            "StepDispatched",
            run_id,
            payload={"step_run_id": step_id, "admission_id": grant["admission_id"]},
        )
    )
    store.append(
        new_workflow_event(
            "StepStarted",
            run_id,
            payload={"step_run_id": step_id, "admission_id": grant["admission_id"]},
        )
    )
    store.append(
        new_workflow_event(
            "StepRetryScheduled",
            run_id,
            payload={"step_run_id": step_id, "admission_id": grant["admission_id"]},
        )
    )
    store.append(
        new_workflow_event(
            "CompensationStarted",
            run_id,
            payload={"step_run_id": step_id, "admission_id": grant["admission_id"]},
        )
    )
    store.append(
        new_workflow_event(
            "StepFailed",
            run_id,
            payload={"step_run_id": step_id, "admission_id": grant["admission_id"]},
        )
    )
    store.append(new_workflow_event("WorkflowFailed", run_id))
    snapshot = store.snapshot(run_id)
    assert snapshot["state"] == "failed"
    assert snapshot["step_runs"][step_id]["last_event_type"] == "StepFailed"


def test_unknown_event_is_rejected(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    with pytest.raises(WorkflowMeshEventError, match="Unknown"):
        store.append(new_workflow_event("NotARealEvent", "run-3"))


def test_idempotency_key_is_authoritative_across_event_ids(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    first = new_workflow_event(
        "WorkflowRequested", "run-idempotent", idempotency_key="run-idempotent:requested"
    )
    duplicate = new_workflow_event(
        "WorkflowRequested", "run-idempotent", idempotency_key="run-idempotent:requested"
    )
    store.append(first)
    with pytest.raises(WorkflowMeshEventError, match="Conflicting duplicate"):
        store.append(duplicate)


def test_agent_workflow_mesh_bridge_start_event(tmp_path, monkeypatch):
    """Phase 1b: Agent Workflow start emits Mesh event."""
    from pathlib import Path
    from omo.workflow.mesh_agent_events import emit_workflow_mesh_event
    import os

    # Simulate workspace with minimal OMO structure
    omo_dir = tmp_path / ".omo"
    omo_dir.mkdir()

    # Test direct emission
    result = emit_workflow_mesh_event(
        "AgentWorkflowStarted",
        "test-run-123",
        {"workflow_id": "test-wf", "actor": "test-user"},
        workspace=tmp_path,
    )
    assert result is True, "Should succeed in emitting event"

    # Verify event was stored
    event_file = omo_dir / "_knowledge" / "workflow-mesh" / "events.jsonl"
    assert event_file.exists()
    content = event_file.read_text()
    assert "AgentWorkflowStarted" in content
    assert "test-run-123" in content
