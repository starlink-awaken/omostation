from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from omo.workflow_mesh import WorkflowMeshStore
from omo.workflow_promotion import WorkflowPromotionError, request_workflow_from_task


def _task(
    root: Path, *, knowledge_refs: list[str] | None = None, risk_level: str = "L1"
) -> None:
    task_dir = root / ".omo" / "tasks" / "planned"
    task_dir.mkdir(parents=True)
    payload = {
        "id": "TASK-KNOWLEDGE-1",
        "title": "知识行动请求",
        "description": "把引用的知识转成可审计的下一步工作流请求。",
        "status": "pending",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": knowledge_refs
        if knowledge_refs is not None
        else ["kos:article-1"],
        "handoff_refs": [],
        "risk_level": risk_level,
        "allowed_operation_level": risk_level,
        "human_approval_required": risk_level in {"L2", "L3"},
        "source_docs": ["cockpit:knowledge-action"],
        "entry_gate": ["确认场景与证据计划"],
        "evidence_required": ["工作流结果"],
        "deliverables": ["Workflow Mesh 请求"],
        "test_plan": ["验证请求可幂等回放"],
    }
    (task_dir / "TASK-KNOWLEDGE-1.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
    )


def _request(root: Path, **overrides):
    request = {
        "task_id": "TASK-KNOWLEDGE-1",
        "workflow_name": "knowledge-to-action",
        "scene_binding": {
            "scene_id": "engineering-delivery",
            "journey_id": "knowledge-to-action",
            "outcome_metric": "task_adoption_rate",
        },
        "evidence_plan": ["结果摘要", "人工复核回执"],
        "actor": "pytest",
        "now": "2026-08-02T16:00:00+00:00",
    }
    request.update(overrides)
    return request_workflow_from_task(root, **request)


def test_request_records_mesh_event_and_knowledge_receipt(tmp_path: Path) -> None:
    _task(tmp_path)

    result = _request(tmp_path)

    assert result["status"] == "requested"
    assert result["request_state"] == "ready_for_admission"
    assert result["external_side_effects"] == "disabled"
    assert result["worker_launch"] is False
    assert result["knowledge_action"]["status"] == "recorded"
    snapshot = WorkflowMeshStore(tmp_path / ".omo").snapshot(result["workflow_run_id"])
    assert snapshot["state"] == "planned"
    assert snapshot["scene_binding"]["scene_id"] == "engineering-delivery"
    assert snapshot["last_event_type"] == "WorkflowRequested"


def test_request_is_idempotent_and_does_not_duplicate_evidence(tmp_path: Path) -> None:
    _task(tmp_path)

    first = _request(tmp_path)
    second = _request(tmp_path)

    assert second["status"] == "deduplicated"
    assert second["workflow_run_id"] == first["workflow_run_id"]
    assert len(WorkflowMeshStore(tmp_path / ".omo").events()) == 1
    action_log = tmp_path / ".omo" / "_knowledge" / "knowledge-mesh" / "actions.jsonl"
    assert len(action_log.read_text(encoding="utf-8").splitlines()) == 1


def test_request_requires_knowledge_refs(tmp_path: Path) -> None:
    _task(tmp_path, knowledge_refs=[])

    with pytest.raises(WorkflowPromotionError, match="knowledge_refs"):
        _request(tmp_path)


def test_request_requires_approval_for_high_risk_without_admitting(
    tmp_path: Path,
) -> None:
    _task(tmp_path, risk_level="L2")

    result = _request(tmp_path)

    assert result["request_state"] == "approval_required"
    assert result["approval"] == {"required": True, "state": "pending"}
    assert (
        WorkflowMeshStore(tmp_path / ".omo").snapshot(result["workflow_run_id"])[
            "state"
        ]
        == "planned"
    )


def test_request_cannot_exceed_task_operation_level(tmp_path: Path) -> None:
    _task(tmp_path, risk_level="L1")

    with pytest.raises(WorkflowPromotionError, match="exceeds task allowance"):
        _request(tmp_path, operation_level="L2")
