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

import pytest

ROOT = Path(__file__).resolve().parents[3]
for source in (ROOT / "projects" / "omo" / "src",):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))


def _request_identity(task_rel_path: str) -> dict:
    """构造绑定工作流派发所需的 request_identity。

    `admit_workflow` 现要求请求身份 (见 omo_worker_dispatch.py:92-94 —
    "bound workflow dispatch requires request_identity")，据此投影
    packet_id / packet_hash / instruction_binding 到 StepDispatched 事件。
    """
    import hashlib

    return {
        "bet_id": "BET-TEST",
        "packet_id": "WP-TEST-001",
        "packet_hash": "sha256:" + hashlib.sha256(b"test-packet").hexdigest(),
        "task_ref": task_rel_path,
        "instruction_binding": {
            "instruction_ref": "instr-ref-001",
            "instruction_version": "v1",
            "content_digest": "sha256:" + hashlib.sha256(b"test-instruction").hexdigest(),
            "instruction_profile": "executor",
        },
    }


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
                        "capabilities": ["workflow.execute"],
                        "transports": {
                            "cli_prompt": {"command": "worker-a", "worker_ack_protocol": "omo-worker-origin-ack/v1"}
                        },
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
    """Legacy dispatch_task without packet is observer-only (no worker state)."""
    try:
        from omo.omo_worker_dispatch import dispatch_task
        from omo.workflow_dispatch import admit_workflow
        from omo.workflow_mesh import WorkflowMeshStore
    except ImportError as exc:  # pragma: no cover - 环境相关
        pytest.skip(f"omo.workflow_dispatch 不可用: {exc}")

    _setup_task(tmp_path)

    # Legacy dispatch (no workflow_packet) is now observer-only and raises.
    with pytest.raises(ValueError, match="observer-only"):
        dispatch_task(
            tmp_path,
            task_id="TASK-P2-1",
            worker_id="worker-a",
            allowed_write_paths=["docs/"],
            launch=False,
            transport="cli_prompt",
            now="2026-08-02T10:00:00+00:00",
        )

    # Mesh-aware dispatch (with workflow_packet) still works.
    task_rel_path = ".omo/tasks/active/TASK-P2-1.yaml"
    identity = _request_identity(task_rel_path)
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
        workflow_run_id="run-p2-legacy",
        request_identity=identity,
        now="2026-08-02T10:00:00+00:00",
    )
    result = dispatch_task(
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
    events = store.events()
    event_types = [e["event_type"] for e in events]

    assert "WorkflowRequested" in event_types
    assert "WorkflowAdmitted" in event_types
    assert "StepDispatched" in event_types


def test_mesh_aware_dispatch_emits_step_dispatched(tmp_path):
    """dispatch_task with workflow_packet should emit only StepDispatched."""
    try:
        from omo.omo_worker_dispatch import dispatch_task
        from omo.workflow_dispatch import admit_workflow
        from omo.workflow_mesh import WorkflowMeshStore
    except ImportError as exc:  # pragma: no cover - 环境相关
        pytest.skip(f"omo.workflow_dispatch 不可用: {exc}")

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
        request_identity=_request_identity(".omo/tasks/active/TASK-P2-1.yaml"),
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
    except ImportError as exc:  # pragma: no cover - 环境相关
        pytest.skip(f"omo.workflow_dispatch 不可用: {exc}")

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
        request_identity=_request_identity(".omo/tasks/active/TASK-P2-1.yaml"),
        # worker-a 在 _setup_task 的 registry 中只注册了 cli_prompt 传输;
        # 不传则默认 acp_stdio → 准入拒绝 (reason=transport_missing)。
        transport="cli_prompt",
        now="2026-08-02T10:00:00+00:00",
    )

    store = WorkflowMeshStore(tmp_path / ".omo")
    step_dispatched = [e for e in store.events() if e["event_type"] == "StepDispatched"]
    assert len(step_dispatched) == 1
