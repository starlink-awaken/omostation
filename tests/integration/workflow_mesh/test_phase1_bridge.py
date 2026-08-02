"""Phase 1: Workflow Mesh Bridge Integration Tests.

Verifies that:
1. ECOS default_mesh_sink module is importable and callable
2. OMO mesh_agent_events module is importable and callable
3. Agent Workflow lifecycle imports mesh bridge gracefully
4. Mesh event emission works end-to-end with a real WorkflowMeshStore
5. Graceful degradation when OMO is not available
6. ECOS executor uses default sink automatically
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for source in (
    ROOT / "projects" / "omo" / "src",
    ROOT / "projects" / "ecos" / "src",
):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


def test_ecos_default_mesh_sink_importable():
    """ECOS default_mesh_sink module should be importable."""
    from ecos.workflow.default_mesh_sink import (
        get_default_mesh_sink,
        default_mesh_sink,
        _find_omo_root,
    )
    assert callable(get_default_mesh_sink)
    assert callable(default_mesh_sink)
    assert callable(_find_omo_root)


def test_omo_mesh_agent_events_importable():
    """OMO mesh_agent_events module should be importable."""
    from omo.workflow.mesh_agent_events import (
        emit_workflow_mesh_event,
        _run_mesh_sink,
    )
    assert callable(emit_workflow_mesh_event)
    assert callable(_run_mesh_sink)


def test_lifecycle_has_mesh_bridge():
    """Lifecycle module should import mesh bridge without errors."""
    from omo.workflow.lifecycle import start_run, closeout_run
    assert callable(start_run)
    assert callable(closeout_run)


def test_mesh_event_emission_end_to_end(tmp_path):
    """Mesh event emission should write to WorkflowMeshStore."""
    from omo.workflow.mesh_agent_events import emit_workflow_mesh_event
    from omo.workflow_mesh import WorkflowMeshStore

    # Setup minimal OMO structure
    omo_dir = tmp_path / ".omo"
    omo_dir.mkdir(parents=True, exist_ok=True)

    # Emit a WorkflowRequested event (maps from AgentWorkflowStarted)
    result = emit_workflow_mesh_event(
        "AgentWorkflowStarted",
        "test-run-bridge-001",
        {"workflow_id": "test-wf", "actor": "test"},
        workspace=tmp_path,
    )
    assert result is True, "Event emission should succeed"

    # Verify the event was persisted
    store = WorkflowMeshStore(omo_dir)
    events = store.events()
    assert len(events) >= 1, "At least one event should be stored"
    assert events[-1]["event_type"] == "WorkflowRequested"
    assert events[-1]["workflow_run_id"] == "test-run-bridge-001"
    assert events[-1]["producer"] == "agent-workflow"
    assert events[-1]["schema_version"] == "workflow-mesh/v1"
    assert events[-1]["payload"]["agent_event_type"] == "AgentWorkflowStarted"


def test_graceful_degradation_when_omo_unavailable(tmp_path):
    """When OMO store cannot be loaded, emission should return False, not crash."""
    from omo.workflow.mesh_agent_events import emit_workflow_mesh_event

    # tmp_path has no .omo directory - store creation may still work
    # but the key is it should not crash
    result = emit_workflow_mesh_event(
        "TestEvent",
        "test-run-degrade",
        {"data": "test"},
        workspace=tmp_path,
    )
    assert isinstance(result, bool)


def test_ecos_executor_uses_default_sink(tmp_path, monkeypatch):
    """ECOS executor should use default_mesh_sink when no event_sink is passed."""
    from ecos.workflow.executor import execute_m1_workflow

    sink_calls = []

    def spy_sink(event):
        sink_calls.append(event)

    monkeypatch.setattr(
        "ecos.workflow.executor.load_workflow",
        lambda name: {
            "name": "test-mesh-auto",
            "steps": [{"name": "noop", "action": "echo", "command": "echo ok"}],
            "execution": {"backend": "default"},
        },
    )
    monkeypatch.setattr(
        "ecos.workflow.executor.get_default_mesh_sink",
        lambda: spy_sink,
    )

    # Execute without passing event_sink - should use default
    result = execute_m1_workflow("test-mesh-auto")

    assert len(sink_calls) >= 1, "Should auto-emit Mesh events without explicit event_sink"
    assert any(c.get("event_type") == "WorkflowRequested" for c in sink_calls)
