from __future__ import annotations

from pathlib import Path

import pytest

from omo.omo_task_policy import (
    OPC_P6_SELF_EVOLUTION_POLICY,
    TASK_POLICIES,
    check_task_policy,
    get_task_policy,
)


def test_check_task_policy_passes_for_self_evolution_planned_only(tmp_path: Path) -> None:
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    planned_dir.mkdir(parents=True)
    active_dir.mkdir(parents=True)
    (planned_dir / "OPC-P6-SELF-EVOLUTION-good.yaml").write_text(
        "id: OPC-P6-SELF-EVOLUTION-good\n"
        "status: planned\n"
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
        "status: active\n"
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
    assert any("status must remain planned" in issue for issue in issues)
    assert any("leaked into active/" in issue for issue in issues)


def test_get_task_policy_resolves_registered_policy() -> None:
    policy = get_task_policy("self-evolution-approval")

    assert policy == OPC_P6_SELF_EVOLUTION_POLICY
    assert TASK_POLICIES[policy.name] is policy


def test_get_task_policy_rejects_unknown_policy() -> None:
    with pytest.raises(KeyError, match="unknown task policy"):
        get_task_policy("does-not-exist")
