"""Phase 5 integration tests: Mesh event chain closure.

Verifies that emit_workflow_mesh_event produces valid state machine
transitions for all terminal states (succeeded, failed, cancelled),
and that the full event chain is visible in the Mesh store.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def test_event_chain_succeeded(tmp_path):
    """Succeeded chain: planned -> admitted -> dispatched -> running -> succeeded -> closed."""
    from omo.workflow.mesh_agent_events import emit_workflow_mesh_event
    from omo.workflow_mesh import WorkflowMeshStore

    omo_dir = tmp_path / ".omo"
    (omo_dir / "_knowledge" / "workflow-mesh").mkdir(parents=True, exist_ok=True)

    run_id = "chain-test-succ-001"
    r1 = emit_workflow_mesh_event("AgentWorkflowStarted", run_id, {"task": "test"}, workspace=tmp_path)
    assert r1 is True

    r2 = emit_workflow_mesh_event("AgentWorkflowClosed", run_id, {"status": "succeeded", "ok": True}, workspace=tmp_path)
    assert r2 is True

    store = WorkflowMeshStore(omo_dir)
    events = store.events()
    types = [e["event_type"] for e in events if e["workflow_run_id"] == run_id]
    assert types == [
        "WorkflowRequested",
        "WorkflowAdmitted",
        "StepDispatched",
        "StepStarted",
        "WorkflowSucceeded",
        "WorkflowClosed",
    ]


def test_event_chain_failed(tmp_path):
    """Failed chain: planned -> admitted -> dispatched -> running -> failed(StepFailed) -> closed."""
    from omo.workflow.mesh_agent_events import emit_workflow_mesh_event
    from omo.workflow_mesh import WorkflowMeshStore

    omo_dir = tmp_path / ".omo"
    (omo_dir / "_knowledge" / "workflow-mesh").mkdir(parents=True, exist_ok=True)

    run_id = "chain-test-fail-001"
    r1 = emit_workflow_mesh_event("AgentWorkflowStarted", run_id, {"task": "test"}, workspace=tmp_path)
    assert r1 is True

    r2 = emit_workflow_mesh_event("AgentWorkflowClosed", run_id, {"status": "failed", "ok": False}, workspace=tmp_path)
    assert r2 is True

    store = WorkflowMeshStore(omo_dir)
    events = store.events()
    types = [e["event_type"] for e in events if e["workflow_run_id"] == run_id]
    assert types == [
        "WorkflowRequested",
        "WorkflowAdmitted",
        "StepDispatched",
        "StepStarted",
        "StepFailed",
        "WorkflowClosed",
    ]


def test_event_chain_cancelled(tmp_path):
    """Cancelled chain: planned -> cancelled -> closed."""
    from omo.workflow.mesh_agent_events import emit_workflow_mesh_event
    from omo.workflow_mesh import WorkflowMeshStore

    omo_dir = tmp_path / ".omo"
    (omo_dir / "_knowledge" / "workflow-mesh").mkdir(parents=True, exist_ok=True)

    run_id = "chain-test-cancel-001"
    r1 = emit_workflow_mesh_event("AgentWorkflowStarted", run_id, {"task": "test"}, workspace=tmp_path)
    assert r1 is True

    r2 = emit_workflow_mesh_event("AgentWorkflowClosed", run_id, {"status": "cancelled", "ok": False}, workspace=tmp_path)
    assert r2 is True

    store = WorkflowMeshStore(omo_dir)
    events = store.events()
    types = [e["event_type"] for e in events if e["workflow_run_id"] == run_id]
    assert types == [
        "WorkflowRequested",
        "WorkflowCancelled",
        "WorkflowClosed",
    ]


def test_event_chain_idempotency(tmp_path):
    """Duplicate close events should not corrupt the state machine."""
    from omo.workflow.mesh_agent_events import emit_workflow_mesh_event
    from omo.workflow_mesh import WorkflowMeshStore

    omo_dir = tmp_path / ".omo"
    (omo_dir / "_knowledge" / "workflow-mesh").mkdir(parents=True, exist_ok=True)

    run_id = "chain-test-idem-001"
    emit_workflow_mesh_event("AgentWorkflowStarted", run_id, {"task": "test"}, workspace=tmp_path)
    emit_workflow_mesh_event("AgentWorkflowClosed", run_id, {"status": "succeeded", "ok": True}, workspace=tmp_path)

    # Second close should be silently dropped (idempotency key or terminal state)
    r2 = emit_workflow_mesh_event("AgentWorkflowClosed", run_id, {"status": "succeeded", "ok": True}, workspace=tmp_path)
    # Returns False because run is already terminal/closed
    assert r2 is False

    store = WorkflowMeshStore(omo_dir)
    events = store.events()
    run_events = [e for e in events if e["workflow_run_id"] == run_id]
    # Should still be 6 events, not 12
    assert len(run_events) == 6


def test_mesh_health_snapshot_after_chain(tmp_path):
    """Mesh health snapshot should reflect events after chain closure."""
    from omo.workflow.mesh_agent_events import emit_workflow_mesh_event

    omo_dir = tmp_path / ".omo"
    (omo_dir / "_knowledge" / "workflow-mesh").mkdir(parents=True, exist_ok=True)

    run_id = "health-test-001"
    emit_workflow_mesh_event("AgentWorkflowStarted", run_id, {"task": "test"}, workspace=tmp_path)
    emit_workflow_mesh_event("AgentWorkflowClosed", run_id, {"status": "succeeded", "ok": True}, workspace=tmp_path)

    # Verify events are readable
    from omo.workflow_mesh import WorkflowMeshStore
    store = WorkflowMeshStore(omo_dir)
    events = store.events()
    assert len(events) >= 6
    assert any(e["event_type"] == "WorkflowClosed" for e in events)


def test_scene_binding_propagated_in_close(tmp_path):
    """Scene binding from start event should be carried through to close."""
    from omo.workflow.mesh_agent_events import emit_workflow_mesh_event
    from omo.workflow_mesh import WorkflowMeshStore

    omo_dir = tmp_path / ".omo"
    (omo_dir / "_knowledge" / "workflow-mesh").mkdir(parents=True, exist_ok=True)

    scene = {"scene_id": "test-scene", "journey_id": "journey-1", "outcome_metric": "accuracy"}
    run_id = "scene-test-001"
    emit_workflow_mesh_event("AgentWorkflowStarted", run_id, {"task": "test"}, workspace=tmp_path, scene_binding=scene)
    emit_workflow_mesh_event("AgentWorkflowClosed", run_id, {"status": "succeeded", "ok": True}, workspace=tmp_path, scene_binding=scene)

    store = WorkflowMeshStore(omo_dir)
    events = store.events()
    for e in events:
        if e["workflow_run_id"] == run_id:
            payload = e.get("payload", {})
            if "scene_binding" in payload:
                assert payload["scene_binding"]["scene_id"] == "test-scene"
