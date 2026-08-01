from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from omo.workflow_dispatch import WorkflowDispatchError, admit_workflow
from omo.workflow_mesh import WorkflowMeshStore


def _task(tmp_path: Path, *, approval_ref: str | None = None) -> None:
    task_dir = tmp_path / ".omo" / "tasks" / "active"
    task_dir.mkdir(parents=True)
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
