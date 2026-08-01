import pytest

from omo.workflow_mesh import (
    WorkflowMeshEventError,
    WorkflowMeshStore,
    new_workflow_event,
)


def test_workflow_mesh_store_projects_lifecycle_and_is_idempotent(tmp_path):
    store = WorkflowMeshStore(tmp_path)
    requested = new_workflow_event("WorkflowRequested", "run-1", producer="ecos")
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
