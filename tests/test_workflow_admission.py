from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from omo.omo_ingress_task_promotion import promote_task_to_active
from omo.workflow_dispatch import (
    WorkflowDispatchError,
    admit_requested_workflow,
    preview_requested_workflow,
)
from omo.workflow_mesh import WorkflowMeshStore
from omo.workflow_promotion import request_workflow_from_task


SCENE = {
    "scene_id": "engineering-delivery",
    "journey_id": "knowledge-to-action",
    "outcome_metric": "task_adoption_rate",
}


def _task(root: Path, *, risk_level: str = "L1") -> None:
    task_dir = root / ".omo" / "tasks" / "planned"
    task_dir.mkdir(parents=True)
    payload = {
        "id": "TASK-ADMISSION-1",
        "title": "Workflow admission",
        "description": "Request a governed workflow admission.",
        "status": "pending",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": ["kos:article-1"],
        "handoff_refs": [],
        "risk_level": risk_level,
        "allowed_operation_level": risk_level,
        "human_approval_required": risk_level in {"L2", "L3"},
        "source_docs": ["docs/source.md"],
        "entry_gate": ["confirm scene"],
        "evidence_required": ["result summary"],
        "deliverables": ["docs/result.md"],
        "test_plan": ["pytest"],
    }
    task_dir.joinpath("TASK-ADMISSION-1.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
    )


def _request(root: Path) -> dict:
    return request_workflow_from_task(
        root,
        task_id="TASK-ADMISSION-1",
        workflow_name="knowledge-to-action",
        scene_binding=SCENE,
        evidence_plan=["result summary"],
        actor="pytest",
        now="2026-08-03T10:00:00+00:00",
    )


def _health(*, available: bool = True) -> dict:
    return {
        "status": "healthy" if available else "unhealthy",
        "source": "agora.workflow_health",
        "observed_at": "2026-08-03T10:00:00+00:00",
        "capabilities": {
            "runtime": {"available": available, "health": "green" if available else "red"}
        },
    }


def _admission_args(run_id: str) -> dict:
    return {
        "workflow_run_id": run_id,
        "backend": "runtime",
        "required_capabilities": ["runtime"],
        "capability_health": _health(),
        "scene_binding": SCENE,
    }


def test_preview_is_read_only_and_reports_eligible_request(tmp_path: Path) -> None:
    _task(tmp_path)
    requested = _request(tmp_path)

    preview = preview_requested_workflow(tmp_path, **_admission_args(requested["workflow_run_id"]))

    assert preview["status"] == "eligible"
    assert preview["dispatch_state"] == "preview"
    assert preview["worker_launch"] is False
    assert len(WorkflowMeshStore(tmp_path / ".omo").events()) == 1
    assert WorkflowMeshStore(tmp_path / ".omo").snapshot(requested["workflow_run_id"])["state"] == "planned"


def test_preview_is_blocked_for_health_or_approval_gates(tmp_path: Path) -> None:
    _task(tmp_path)
    requested = _request(tmp_path)
    args = _admission_args(requested["workflow_run_id"])
    args["capability_health"] = _health(available=False)

    preview = preview_requested_workflow(tmp_path, **args)

    assert preview["status"] == "blocked"
    assert "unavailable" in preview["blocker"] or "unhealthy" in preview["blocker"]

    _task(tmp_path / "high-risk", risk_level="L2")
    high_risk = _request(tmp_path / "high-risk")
    approval_preview = preview_requested_workflow(
        tmp_path / "high-risk", **_admission_args(high_risk["workflow_run_id"])
    )
    assert approval_preview["status"] == "blocked"
    assert "approval" in approval_preview["blocker"]


def test_apply_requires_active_task_and_admits_existing_request_once(tmp_path: Path) -> None:
    _task(tmp_path)
    requested = _request(tmp_path)
    args = _admission_args(requested["workflow_run_id"])
    args["now"] = "2026-08-03T10:01:00+00:00"

    with pytest.raises(WorkflowDispatchError, match="active"):
        admit_requested_workflow(tmp_path, **args)

    promote_task_to_active(
        tmp_path / ".omo", task_id="TASK-ADMISSION-1", actor="pytest", now="2026-08-03T10:00:30Z"
    )
    first = admit_requested_workflow(tmp_path, **args)
    second = admit_requested_workflow(tmp_path, **args)

    assert first["status"] == "admitted"
    assert second["status"] == "deduplicated"
    assert first["external_side_effects"] == "disabled"
    assert first["worker_launch"] is False
    events = WorkflowMeshStore(tmp_path / ".omo").events()
    assert [event["event_type"] for event in events].count("WorkflowRequested") == 1
    assert [event["event_type"] for event in events].count("WorkflowAdmitted") == 1


def test_apply_rejects_scene_binding_mismatch(tmp_path: Path) -> None:
    _task(tmp_path)
    requested = _request(tmp_path)
    args = _admission_args(requested["workflow_run_id"])
    args["scene_binding"] = {**SCENE, "outcome_metric": "other_metric"}

    with pytest.raises(WorkflowDispatchError, match="scene binding"):
        preview_requested_workflow(tmp_path, **args)
