"""Tests for the governed KEMS task ingress boundary."""

from pathlib import Path

import pytest

from omo.omo_ingress_kems import create_kems_planned_task


def payload(task_id="TASK-KEMS-1"):
    return {
        "id": task_id,
        "title": "补齐台账",
        "description": "提交已审核台账",
        "status": "candidate",
        "task_type": "kems_evidence_action",
        "risk_level": "L1",
        "allowed_operation_level": "L1",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": ["ent-1"],
        "handoff_refs": [],
        "source_docs": ["doc-1#page=2"],
        "entry_gate": ["evidence_bound"],
        "evidence_required": ["doc-1#page=2"],
        "test_plan": ["提交已审核台账"],
        "deliverables": ["提交已审核台账"],
        "human_approval_required": True,
        "depends_on": [],
        "metadata": {"source_run_id": "run-1", "proposed_owner": "单位 B"},
    }


def setup_omo(tmp_path: Path) -> Path:
    omo_dir = tmp_path / ".omo"
    (omo_dir / "tasks" / "planned").mkdir(parents=True)
    return omo_dir


def test_kems_ingress_is_idempotent_and_stays_planned(tmp_path):
    omo_dir = setup_omo(tmp_path)
    first = create_kems_planned_task(
        omo_dir, task_payload=payload(), source_ref="kems:run-1:task-1", now="2026-07-31T08:00:00Z"
    )
    second = create_kems_planned_task(
        omo_dir, task_payload=payload(), source_ref="kems:run-1:task-1", now="2026-07-31T08:01:00Z"
    )
    assert first == second
    assert first["status"] == "candidate"
    assert first["assigned_to"] is None
    assert (omo_dir / "tasks" / "planned" / "TASK-KEMS-1.yaml").exists()


def test_kems_ingress_rejects_missing_evidence_or_source_ref(tmp_path):
    omo_dir = setup_omo(tmp_path)
    bad = payload()
    bad["source_docs"] = []
    with pytest.raises(ValueError, match="source_docs"):
        create_kems_planned_task(omo_dir, task_payload=bad, source_ref="kems:bad")
    with pytest.raises(ValueError, match="source_ref"):
        create_kems_planned_task(omo_dir, task_payload=payload(), source_ref="")
