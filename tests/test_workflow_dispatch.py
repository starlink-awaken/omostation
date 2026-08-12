from __future__ import annotations

# ruff: noqa: I001

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from omo.workflow_dispatch import (
    WorkflowDispatchError,
    admit_workflow,
    consume_pending_workflow_requests,
    dispatch_admitted_workflow,
)
from omo.workflow_mesh import WorkflowMeshStore


def _task(tmp_path: Path, *, approval_ref: str | None = None) -> None:
    task_dir = tmp_path / ".omo" / "tasks" / "active"
    task_dir.mkdir(parents=True)
    registry_dir = tmp_path / ".omo" / "_truth" / "registry"
    registry_dir.mkdir(parents=True)
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
        "id": "TASK-MESH-1",
        "title": "Mesh dispatch",
        "status": "pending",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": approval_ref,
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
    (task_dir / "TASK-MESH-1.yaml").write_text(
        yaml.safe_dump(task, sort_keys=False), encoding="utf-8"
    )


def _health() -> dict:
    return {
        "status": "healthy",
        "source": "agora",
        "observed_at": datetime.now(UTC).isoformat(),
        "capabilities": {
            "workflow.execute": {"available": True, "health": "green"},
            "runtime": {"available": True, "health": "green"},
        },
    }


def test_admit_workflow_records_request_and_grant(tmp_path: Path) -> None:
    _task(tmp_path)
    packet = admit_workflow(
        tmp_path,
        task_id="TASK-MESH-1",
        backend="runtime",
        required_capabilities=["workflow.execute", "runtime"],
        capability_health=_health(),
        workflow_run_id="run-mesh-1",
        now="2026-08-01T10:00:00+00:00",
    )

    grant = packet["admission"]
    assert grant["workflow_run_id"] == "run-mesh-1"
    assert grant["proof"]
    snapshot = WorkflowMeshStore(tmp_path / ".omo").snapshot("run-mesh-1")
    assert snapshot["state"] == "admitted"
    assert snapshot["admission"]["admission_id"] == grant["admission_id"]


def test_admit_workflow_fails_closed_for_unhealthy_capability(tmp_path: Path) -> None:
    _task(tmp_path)
    health = _health()
    health["capabilities"]["runtime"]["available"] = False
    with pytest.raises(WorkflowDispatchError, match="unavailable"):
        admit_workflow(
            tmp_path,
            task_id="TASK-MESH-1",
            backend="runtime",
            required_capabilities=["runtime"],
            capability_health=health,
        )


def test_dispatch_bridge_records_step_dispatch_worker_context(tmp_path: Path) -> None:
    _task(tmp_path)
    packet = dispatch_admitted_workflow(
        tmp_path,
        task_id="TASK-MESH-1",
        worker_id="worker-a",
        allowed_write_paths=["docs/"],
        backend="runtime",
        required_capabilities=["workflow.execute", "runtime"],
        capability_health=_health(),
        workflow_run_id="run-dispatch-bridge",
        now="2026-08-01T10:00:00+00:00",
    )

    snapshot = WorkflowMeshStore(tmp_path / ".omo").snapshot("run-dispatch-bridge")
    assert snapshot["state"] == "dispatched"
    assert snapshot["worker"]["dispatch_id"] == packet["worker_dispatch"]["dispatch_id"]
    assert snapshot["worker"]["worker_id"] == "worker-a"


def test_admit_workflow_requires_granted_approval(tmp_path: Path) -> None:
    approval_ref = ".omo/workers/runs/approval.yaml"
    _task(tmp_path, approval_ref=approval_ref)
    task_path = tmp_path / ".omo" / "tasks" / "active" / "TASK-MESH-1.yaml"
    task = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    task["risk_level"] = "L2"
    task["allowed_operation_level"] = "L2"
    task["human_approval_required"] = True
    task_path.write_text(yaml.safe_dump(task, sort_keys=False), encoding="utf-8")
    with pytest.raises(WorkflowDispatchError, match="approval"):
        admit_workflow(
            tmp_path,
            task_id="TASK-MESH-1",
            backend="runtime",
            required_capabilities=["runtime"],
            capability_health=_health(),
        )


def test_admit_workflow_rejects_budget_overrun(tmp_path: Path) -> None:
    _task(tmp_path)
    with pytest.raises(WorkflowDispatchError, match="budget"):
        admit_workflow(
            tmp_path,
            task_id="TASK-MESH-1",
            backend="runtime",
            required_capabilities=["runtime"],
            capability_health=_health(),
            requested_budget=2,
            remaining_budget=1,
        )


def test_legacy_dispatch_without_packet_emits_mesh_events(tmp_path: Path) -> None:
    """Phase 2: dispatch_task without workflow_packet should emit Mesh events."""
    _task(tmp_path)
    from omo.omo_worker_dispatch import dispatch_task
    from omo.workflow_mesh import WorkflowMeshStore

    result = dispatch_task(
        tmp_path,
        task_id="TASK-MESH-1",
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
    assert snapshot["worker"]["dispatch_id"] == result["dispatch_id"]


def test_dispatch_with_packet_emits_step_dispatched(tmp_path: Path) -> None:
    """Phase 2: dispatch_task with workflow_packet should emit StepDispatched only."""
    _task(tmp_path)
    from omo.omo_worker_dispatch import dispatch_task
    from omo.workflow_mesh import WorkflowMeshStore

    packet = admit_workflow(
        tmp_path,
        task_id="TASK-MESH-1",
        backend="runtime",
        required_capabilities=["workflow.execute", "runtime"],
        capability_health=_health(),
        workflow_run_id="run-packet-test",
        now="2026-08-02T10:00:00+00:00",
    )

    dispatch_task(
        tmp_path,
        task_id="TASK-MESH-1",
        worker_id="worker-a",
        allowed_write_paths=["docs/"],
        launch=False,
        transport="cli_prompt",
        workflow_packet=packet,
        now="2026-08-02T10:00:00+00:00",
    )

    store = WorkflowMeshStore(tmp_path / ".omo")
    events = store.events()
    step_dispatched = [e for e in events if e["event_type"] == "StepDispatched"]

    assert len(step_dispatched) == 1, "Should emit exactly one StepDispatched"
    assert step_dispatched[0]["workflow_run_id"] == "run-packet-test"
    assert step_dispatched[0]["payload"]["worker_id"] == "worker-a"

    snapshot = store.snapshot("run-packet-test")
    assert snapshot["state"] == "dispatched"


def test_dispatch_admitted_workflow_no_double_step_dispatched(tmp_path: Path) -> None:
    """Phase 2: dispatch_admitted_workflow should not double-emit StepDispatched."""
    _task(tmp_path)
    from omo.workflow_mesh import WorkflowMeshStore

    dispatch_admitted_workflow(
        tmp_path,
        task_id="TASK-MESH-1",
        worker_id="worker-a",
        allowed_write_paths=["docs/"],
        backend="runtime",
        required_capabilities=["workflow.execute", "runtime"],
        capability_health=_health(),
        workflow_run_id="run-no-double",
        now="2026-08-02T10:00:00+00:00",
    )

    store = WorkflowMeshStore(tmp_path / ".omo")
    events = store.events()
    step_dispatched = [e for e in events if e["event_type"] == "StepDispatched"]

    assert len(step_dispatched) == 1, "Should not double-emit StepDispatched"


def test_consume_pending_workflow_requests_iris_fast_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P0 完整第三块: consume 闭环 - planned run → admit → iris 快速路径."""
    import omo.workflow_dispatch as wd
    from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event

    _task(tmp_path)  # active task TASK-MESH-1

    # 手动发 WorkflowRequested event (planned state, 声明 iris capability)
    store = WorkflowMeshStore(tmp_path / ".omo")
    run_id = "run-consume-iris"
    store.append(
        new_workflow_event(
            "WorkflowRequested",
            run_id,
            trace_id=run_id,
            producer="test",
            idempotency_key=f"{run_id}:requested",
            payload={
                "task_id": "TASK-MESH-1",
                "task_ref": ".omo/tasks/active/TASK-MESH-1.yaml",
                "required_capabilities": ["iris:apple_mail"],
            },
        )
    )

    # mock iris 快速路径 (避免 subprocess)
    dispatched: list[dict] = []

    def fake_iris_dispatch(root, packet, iris_caps, omo_dir=".omo"):  # noqa: ANN001
        dispatched.append(
            {"run_id": packet["workflow_run_id"], "caps": list(iris_caps)}
        )
        return {**packet, "iris_dispatch": [], "dispatch_state": "dispatched"}

    monkeypatch.setattr(wd, "_dispatch_iris_via_executor", fake_iris_dispatch)

    health = {
        "status": "healthy",
        "source": "iris-entry-points",
        "observed_at": datetime.now(UTC).isoformat(),
        "capabilities": {"iris:apple_mail": {"available": True, "health": "green"}},
    }

    result = consume_pending_workflow_requests(
        tmp_path, capability_health=health, omo_dir=".omo"
    )

    assert result["total_planned"] == 1
    assert len(result["consumed"]) == 1
    assert result["consumed"][0]["workflow_run_id"] == run_id
    assert result["consumed"][0]["iris"] is True
    assert len(dispatched) == 1
    assert dispatched[0]["caps"] == ["iris:apple_mail"]
    assert result["failed"] == []

    # verify mesh 状态机推进 (admitted 之后)
    snap = store.snapshot(run_id)
    assert snap["state"] in {"admitted", "dispatched", "running"}


def test_consume_pending_workflow_requests_skips_non_planned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """consume 跳过 non-planned run (不重复消费 admitted/succeeded)."""
    import omo.workflow_dispatch as wd

    _task(tmp_path)

    # 先 admit 一个 run (state → admitted, 非 planned)
    admit_workflow(
        tmp_path,
        task_id="TASK-MESH-1",
        backend="runtime",
        required_capabilities=["workflow.execute", "runtime"],
        capability_health=_health(),
        workflow_run_id="run-already-admitted",
        now="2026-08-02T10:00:00+00:00",
    )

    dispatched: list[int] = []
    monkeypatch.setattr(
        wd,
        "_dispatch_iris_via_executor",
        lambda *a, **k: dispatched.append(1) or {},
    )

    result = consume_pending_workflow_requests(
        tmp_path, capability_health=_health(), omo_dir=".omo"
    )

    # 没 planned run → 0 consumed, 0 skipped, 0 failed
    assert result["total_planned"] == 0
    assert result["consumed"] == []
    assert result["skipped"] == []
    assert result["failed"] == []
    assert dispatched == []
