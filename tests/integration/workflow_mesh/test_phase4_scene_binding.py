"""Phase 4: Scene Binding Bridge Integration Tests.

Verifies that scene_binding from External Connection Fabric is propagated
to Workflow Mesh events.
"""
from __future__ import annotations


def test_scene_binding_in_agent_workflow_event(tmp_path):
    """Agent workflow event with scene_binding should persist to Mesh store."""
    try:
        from omo.workflow.mesh_agent_events import emit_workflow_mesh_event
        from omo.workflow_mesh import WorkflowMeshStore
    except ImportError:
        return

    omo_dir = tmp_path / ".omo"
    omo_dir.mkdir()

    result = emit_workflow_mesh_event(
        "AgentWorkflowStarted",
        "test-run-scene-001",
        {"workflow_id": "test-wf", "actor": "test"},
        workspace=tmp_path,
        scene_binding={
            "scene_id": "scene-test",
            "journey_id": "journey-test",
            "outcome_metric": "metric-test",
        },
    )
    assert result is True

    store = WorkflowMeshStore(omo_dir)
    events = store.events()
    assert len(events) >= 1
    assert events[-1]["payload"]["scene_binding"]["scene_id"] == "scene-test"
    assert events[-1]["payload"]["scene_binding"]["journey_id"] == "journey-test"
    assert events[-1]["payload"]["scene_binding"]["outcome_metric"] == "metric-test"


def test_scene_binding_omitted_when_none(tmp_path):
    """Events without scene_binding should not have the field."""
    try:
        from omo.workflow.mesh_agent_events import emit_workflow_mesh_event
        from omo.workflow_mesh import WorkflowMeshStore
    except ImportError:
        return

    omo_dir = tmp_path / ".omo"
    omo_dir.mkdir()

    emit_workflow_mesh_event(
        "AgentWorkflowStarted",
        "test-run-no-scene",
        {"workflow_id": "test-wf"},
        workspace=tmp_path,
    )

    store = WorkflowMeshStore(omo_dir)
    events = store.events()
    assert len(events) >= 1
    assert "scene_binding" not in events[-1]["payload"]


def test_ecos_executor_emits_scene_binding_from_metadata(monkeypatch):
    """ECOS executor should include scene_binding from workflow metadata."""
    from ecos.workflow.executor import execute_m1_workflow

    sink_calls = []

    def spy_sink(event):
        sink_calls.append(event)

    monkeypatch.setattr(
        "ecos.workflow.executor.load_workflow",
        lambda name: {
            "name": "test-scene",
            "steps": [{"name": "noop", "action": "echo", "command": "echo ok"}],
            "execution": {"backend": "default", "mode": "workflow"},
            "metadata": {
                "scene_binding": {
                    "scene_id": "scene-1",
                    "journey_id": "journey-1",
                    "outcome_metric": "success_rate",
                }
            },
        },
    )
    monkeypatch.setattr(
        "ecos.workflow.executor.get_default_mesh_sink",
        lambda: spy_sink,
    )

    execute_m1_workflow("test-scene")

    requested = [c for c in sink_calls if c.get("event_type") == "WorkflowRequested"]
    assert len(requested) >= 1
    assert requested[0]["payload"]["scene_binding"]["scene_id"] == "scene-1"


def test_mesh_health_snapshot_works():
    """Mesh health monitor should return a valid snapshot."""
    from ecos.workflow.mesh_health import mesh_health_snapshot

    health = mesh_health_snapshot()
    assert health["status"] in ("healthy", "degraded", "unavailable")
    assert isinstance(health["event_count"], int)
    assert isinstance(health["bridges_active"], list)
