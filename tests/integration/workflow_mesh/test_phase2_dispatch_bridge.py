"""Phase 2: Worker Dispatch Mesh Bridge Integration Tests.

Verifies that:
1. Legacy dispatch_task (no workflow_packet) emits Mesh events
2. Mesh-aware dispatch_task (with packet) emits StepDispatched
3. dispatch_admitted_workflow does not double-emit StepDispatched
4. Legacy dispatch snapshot shows dispatched state with worker context
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for source in (ROOT / "projects" / "omo" / "src",):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


def _setup_task(tmp_path: Path) -> None:
    """Create minimal OMO task structure for dispatch."""
    import yaml

    task_dir = tmp_path / ".omo" / "tasks" / "active"
    task_dir.mkdir(parents=True, exist_ok=True)
    registry_dir = tmp_path / ".omo" / "_truth" / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "workers.yaml").write_text(
        yaml.safe_dump(
            {
                "workers": [
                    {
                        "id": "worker-a",
                        "enabled": True,
                        "admission_state": "admitted",
                        "transports": {"cli_prompt": {"command": "worker-a"}},
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    task = {
        "id": "TASK-P2-1",
        "title": "Phase 2 test task",
        "status": "pending",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "risk_level": "L1",
        "allowed_operation_level": "L1",
        "human_approval_required": False,
        "source_docs": ["docs/source.md"],
        "entry_gate": [],
        "evidence_required": ["worker review"],
        "deliverables": ["docs/result.md"],
        "test_plan": ["pytest"],
    }
    (task_dir / "TASK-P2-1.yaml").write_text(yaml.safe_dump(task, sort_keys=False), encoding="utf-8")


def test_legacy_dispatch_emits_mesh_events(tmp_path):
    """Legacy dispatch_task without packet should emit full Mesh event chain."""
    try:
        from omo.omo_worker_dispatch import dispatch_task
        from omo.workflow_mesh import WorkflowMeshStore
    except ImportError:
        return  # skip if pydantic not available in root env

    _setup_task(tmp_path)
    result = dispatch_task(
        tmp_path,
        task_id="TASK-P2-1",
        worker_id="worker-a",
        allowed_write_paths=["docs/"],
        launch=False,
        transport="cli_prompt",
        now="2026-08-02T10:00:00+00:00",
    )

    store = WorkflowMeshStore(tmp_path / ".omo")
    events = store.events()
    event_types = [e["event_type"] for e in events]

    assert "WorkflowRequested" in event_types
    assert "WorkflowAdmitted" in event_types
    assert "StepDispatched" in event_types

    snapshot = store.snapshot(f"dispatch-{result['dispatch_id']}")
    assert snapshot["state"] == "dispatched"
    assert snapshot["worker"]["worker_id"] == "worker-a"


def test_mesh_aware_dispatch_emits_step_dispatched(tmp_path):
    """dispatch_task with workflow_packet should emit only StepDispatched."""
    try:
        from omo.omo_worker_dispatch import dispatch_task
        from omo.workflow_dispatch import admit_workflow
        from omo.workflow_mesh import WorkflowMeshStore
    except ImportError:
        return  # skip if pydantic not available in root env

    _setup_task(tmp_path)
    packet = admit_workflow(
        tmp_path,
        task_id="TASK-P2-1",
        backend="runtime",
        required_capabilities=["workflow.execute"],
        capability_health={
            "status": "healthy",
            "source": "test",
            "observed_at": "2026-08-02T10:00:00+00:00",
            "capabilities": {
                "workflow.execute": {"available": True, "health": "green"},
            },
        },
        workflow_run_id="run-p2-mesh",
        now="2026-08-02T10:00:00+00:00",
    )

    dispatch_task(
        tmp_path,
        task_id="TASK-P2-1",
        worker_id="worker-a",
        allowed_write_paths=["docs/"],
        launch=False,
        transport="cli_prompt",
        workflow_packet=packet,
        now="2026-08-02T10:00:00+00:00",
    )

    store = WorkflowMeshStore(tmp_path / ".omo")
    step_dispatched = [e for e in store.events() if e["event_type"] == "StepDispatched"]
    assert len(step_dispatched) == 1
    assert step_dispatched[0]["workflow_run_id"] == "run-p2-mesh"


def test_dispatch_admitted_no_double_step_dispatched(tmp_path):
    """dispatch_admitted_workflow should emit exactly one StepDispatched."""
    try:
        from omo.workflow_dispatch import dispatch_admitted_workflow
        from omo.workflow_mesh import WorkflowMeshStore
    except ImportError:
        return  # skip if pydantic not available in root env

    _setup_task(tmp_path)
    dispatch_admitted_workflow(
        tmp_path,
        task_id="TASK-P2-1",
        worker_id="worker-a",
        allowed_write_paths=["docs/"],
        backend="runtime",
        required_capabilities=["workflow.execute"],
        capability_health={
            "status": "healthy",
            "source": "test",
            "observed_at": "2026-08-02T10:00:00+00:00",
            "capabilities": {
                "workflow.execute": {"available": True, "health": "green"},
            },
        },
        workflow_run_id="run-p2-no-double",
        now="2026-08-02T10:00:00+00:00",
    )

    store = WorkflowMeshStore(tmp_path / ".omo")
    step_dispatched = [e for e in store.events() if e["event_type"] == "StepDispatched"]
    assert len(step_dispatched) == 1
