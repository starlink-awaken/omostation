from __future__ import annotations

from pathlib import Path

import pytest
from omo.omo_task_policy import (
    ACTIVE_EXECUTION_LINKS_POLICY,
    ACTIVE_REVIEW_REF_POLICY,
    DONE_DIRECTORY_STATUS_POLICY,
    MODERN_DONE_COMPLETION_MARKER_POLICY,
    MODERN_DONE_EVIDENCE_PATHS_POLICY,
    OPC_P6_SELF_EVOLUTION_POLICY,
    REMEDIATION_REVIEW_NOTE_POLICY,
    TASK_POLICIES,
    check_task_policy,
    get_task_policy,
    task_policy_registry_snapshot,
)


def test_check_task_policy_passes_for_self_evolution_planned_only(
    tmp_path: Path,
) -> None:
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    planned_dir.mkdir(parents=True)
    active_dir.mkdir(parents=True)
    (planned_dir / "OPC-P6-SELF-EVOLUTION-good.yaml").write_text(
        "id: OPC-P6-SELF-EVOLUTION-good\n"
        "status: candidate\n"
        "approval_required: true\n"
        "human_approval_required: true\n"
        "approval_state: awaiting_human\n",
        encoding="utf-8",
    )

    issues = check_task_policy(tmp_path, OPC_P6_SELF_EVOLUTION_POLICY)

    assert issues == []


def test_check_task_policy_accepts_multi_document_task_yaml(tmp_path: Path) -> None:
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    planned_dir.mkdir(parents=True)
    (planned_dir / "OPC-P6-SELF-EVOLUTION-good.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "id: OPC-P6-SELF-EVOLUTION-good\n"
        "status: candidate\n"
        "approval_required: true\n"
        "human_approval_required: true\n"
        "approval_state: awaiting_human\n",
        encoding="utf-8",
    )

    issues = check_task_policy(tmp_path, OPC_P6_SELF_EVOLUTION_POLICY)

    assert issues == []


def test_check_task_policy_flags_field_drift_and_active_leak(tmp_path: Path) -> None:
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    planned_dir.mkdir(parents=True)
    active_dir.mkdir(parents=True)
    (planned_dir / "OPC-P6-SELF-EVOLUTION-bad.yaml").write_text(
        "id: OPC-P6-SELF-EVOLUTION-bad\n"
        "status: planned\n"
        "approval_required: false\n"
        "human_approval_required: false\n"
        "approval_state: auto\n",
        encoding="utf-8",
    )
    (active_dir / "OPC-P6-SELF-EVOLUTION-leaked.yaml").write_text(
        "id: OPC-P6-SELF-EVOLUTION-leaked\nstatus: active\n",
        encoding="utf-8",
    )

    issues = check_task_policy(tmp_path, OPC_P6_SELF_EVOLUTION_POLICY)

    assert len(issues) == 5
    assert any("approval_required must be True" in issue for issue in issues)
    assert any("human_approval_required must be True" in issue for issue in issues)
    assert any("approval_state must be 'awaiting_human'" in issue for issue in issues)
    assert any("status must be one of ('candidate',)" in issue for issue in issues)
    assert any("leaked into active/" in issue for issue in issues)


def test_get_task_policy_resolves_registered_policy() -> None:
    policy = get_task_policy("self-evolution-approval")

    assert policy == OPC_P6_SELF_EVOLUTION_POLICY
    assert TASK_POLICIES[policy.name] is policy


def test_get_task_policy_rejects_unknown_policy() -> None:
    with pytest.raises(KeyError, match="unknown task policy"):
        get_task_policy("does-not-exist")


def test_task_policy_registry_snapshot_lists_registered_policies() -> None:
    snapshot = task_policy_registry_snapshot()

    assert [item["name"] for item in snapshot] == sorted(TASK_POLICIES)
    assert snapshot[0]["summary"]
    assert "target_roots" in snapshot[0]


def test_active_execution_links_policy_flags_missing_fields(tmp_path: Path) -> None:
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    active_dir.mkdir(parents=True)
    (active_dir / "TASK-A.yaml").write_text(
        "id: TASK-A\n"
        "status: review\n"
        "assigned_to: system\n"
        "dispatch_id: null\n"
        "run_ref: null\n"
        "review_ref: null\n",
        encoding="utf-8",
    )

    issues = check_task_policy(tmp_path, ACTIVE_EXECUTION_LINKS_POLICY)

    assert any(
        "dispatch_id must be set when status=review" in issue for issue in issues
    )
    assert any("run_ref must be set when status=review" in issue for issue in issues)
    assert any("review_ref must be set when status=review" in issue for issue in issues)


def test_active_review_ref_policy_flags_missing_artifact(tmp_path: Path) -> None:
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    active_dir.mkdir(parents=True)
    (active_dir / "TASK-RV.yaml").write_text(
        "id: TASK-RV\nstatus: review\nreview_ref: .omo/_delivery/reviews/missing.md\n",
        encoding="utf-8",
    )

    issues = check_task_policy(tmp_path, ACTIVE_REVIEW_REF_POLICY)

    assert issues == [
        "TASK-RV.yaml: review_ref target missing: .omo/_delivery/reviews/missing.md"
    ]


def test_done_directory_status_policy_flags_non_done_status(tmp_path: Path) -> None:
    done_dir = tmp_path / ".omo" / "tasks" / "done"
    done_dir.mkdir(parents=True)
    (done_dir / "TASK-D.yaml").write_text(
        "id: TASK-D\nstatus: review\n",
        encoding="utf-8",
    )

    issues = check_task_policy(tmp_path, DONE_DIRECTORY_STATUS_POLICY)

    assert issues == ["TASK-D.yaml: status must remain done"]


def test_modern_done_completion_marker_policy_flags_missing_marker(
    tmp_path: Path,
) -> None:
    done_dir = tmp_path / ".omo" / "tasks" / "done"
    done_dir.mkdir(parents=True)
    (done_dir / "TASK-M.yaml").write_text(
        "id: TASK-M\n"
        "status: done\n"
        "task_type: governance\n"
        "source_docs:\n- spec.md\n"
        "entry_gate:\n- gate-a\n"
        "evidence_required:\n- pytest\n"
        "test_plan:\n- uv run pytest\n"
        "allowed_operation_level: L0\n",
        encoding="utf-8",
    )

    issues = check_task_policy(tmp_path, MODERN_DONE_COMPLETION_MARKER_POLICY)

    assert issues == [
        "TASK-M.yaml: modern done packet must carry completed_at or completed marker"
    ]


def test_remediation_review_note_policy_flags_missing_note(tmp_path: Path) -> None:
    remediation_dir = tmp_path / ".omo" / "tasks" / "remediation"
    remediation_dir.mkdir(parents=True)
    (remediation_dir / "TASK-R.yaml").write_text(
        "id: TASK-R\nstatus: review\n",
        encoding="utf-8",
    )

    issues = check_task_policy(tmp_path, REMEDIATION_REVIEW_NOTE_POLICY)

    assert issues == ["TASK-R.yaml: remediation review task must carry review_note"]


def test_modern_done_evidence_paths_policy_flags_missing_artifact(
    tmp_path: Path,
) -> None:
    done_dir = tmp_path / ".omo" / "tasks" / "done"
    done_dir.mkdir(parents=True)
    (done_dir / "TASK-E.yaml").write_text(
        "id: TASK-E\n"
        "status: done\n"
        "task_type: governance\n"
        "source_docs:\n- spec.md\n"
        "entry_gate:\n- gate-a\n"
        "evidence_required:\n- pytest\n"
        "test_plan:\n- uv run pytest\n"
        "allowed_operation_level: L0\n"
        "evidence_paths:\n- .omo/_delivery/reports/missing.md\n",
        encoding="utf-8",
    )

    issues = check_task_policy(tmp_path, MODERN_DONE_EVIDENCE_PATHS_POLICY)

    assert issues == [
        "TASK-E.yaml: evidence_path target missing: .omo/_delivery/reports/missing.md"
    ]
