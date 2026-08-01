import pytest

from omo.workflow_mesh import (
    WorkflowMeshEventError,
    WorkflowMeshStore,
    new_workflow_event,
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
        "StepStarted", "run-1", producer="runtime", payload={"step_run_id": "step-1"}
    )
    succeeded = new_workflow_event(
        "WorkflowSucceeded", "run-1", producer="runtime", payload={"step_count": 1}
    )

    store.append(requested)
    store.append(started)
    store.append(succeeded)
    assert store.append(succeeded) == succeeded
    assert store.snapshot("run-1")["state"] == "succeeded"
    assert store.snapshot("run-1")["event_count"] == 3
    assert store.snapshot("run-1")["metadata"]["workflow"] == "mesh-test"


def test_successful_run_can_be_verified_merged_and_closed(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    for event_type in (
        "WorkflowRequested",
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
            else {}
        )
        store.append(new_workflow_event(event_type, "run-lifecycle", payload=payload))

    snapshot = store.snapshot("run-lifecycle")
    assert snapshot["state"] == "closed"
    assert snapshot["last_event_type"] == "WorkflowClosed"
    assert snapshot["event_count"] == 7


def test_step_run_checkpoint_and_evidence_are_queryable(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    events = [
        ("WorkflowRequested", {}),
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
    for event_type, payload in events:
        store.append(new_workflow_event(event_type, "run-query", payload=payload))

    assert store.step_snapshot("run-query", "step-1")["checkpoint"]["checkpoint_id"] == "cp-1"
    assert store.evidence_snapshot("run-query", "ev-1")["sha256"] == "abc"


def test_verified_requires_evidence(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowRequested", "run-no-evidence"))
    store.append(new_workflow_event("StepStarted", "run-no-evidence"))
    store.append(new_workflow_event("WorkflowSucceeded", "run-no-evidence"))
    with pytest.raises(WorkflowMeshEventError, match="EvidenceRecorded"):
        store.append(new_workflow_event("WorkflowVerified", "run-no-evidence"))


def test_failed_backend_can_recover_with_explicit_event(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowRequested", "run-recovery"))
    store.append(new_workflow_event("BackendUnavailable", "run-recovery"))
    store.append(new_workflow_event("WorkflowRecovered", "run-recovery"))
    store.append(new_workflow_event("WorkflowSucceeded", "run-recovery"))

    assert store.snapshot("run-recovery")["state"] == "succeeded"


def test_append_order_wins_over_late_timestamp(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    requested = new_workflow_event("WorkflowRequested", "run-order")
    failed = new_workflow_event("WorkflowFailed", "run-order")
    late_step = new_workflow_event("StepStarted", "run-order")
    late_step["occurred_at"] = "1970-01-01T00:00:00+00:00"
    store.append(requested)
    store.append(failed)
    with pytest.raises(WorkflowMeshEventError, match="terminal"):
        store.append(late_step)


def test_terminal_run_rejects_later_event(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    store.append(new_workflow_event("WorkflowRequested", "run-2"))
    store.append(new_workflow_event("WorkflowFailed", "run-2"))
    with pytest.raises(WorkflowMeshEventError, match="terminal"):
        store.append(new_workflow_event("StepStarted", "run-2"))


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
