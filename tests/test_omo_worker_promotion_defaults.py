from __future__ import annotations

from pathlib import Path

import pytest
from omo.omo_worker_promotion import _promotion_readiness_entry


@pytest.fixture
def minimal_workspace(tmp_path: Path) -> Path:
    """创建最小 workspace: .omo/tasks/planned/TASK-001.yaml 只含 id."""
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    planned_dir.mkdir(parents=True)
    task_path = planned_dir / "TASK-001.yaml"
    task_path.write_text("id: TASK-001\n", encoding="utf-8")
    return tmp_path


def test_promotion_readiness_entry_defaults_for_missing_optional_fields(
    minimal_workspace: Path,
) -> None:
    """锁死缺失可选字段时的缺省值, 防止后台 agent 反复改动 phase/status/risk_level."""
    task_path = minimal_workspace / ".omo" / "tasks" / "planned" / "TASK-001.yaml"
    entry = _promotion_readiness_entry(minimal_workspace, task_path)

    assert entry["task_id"] == "TASK-001"
    assert entry["phase"] is None
    assert entry["status"] == "candidate"
    assert entry["risk_level"] == "L1"
    assert entry["allowed_operation_level"] == "L1"
    assert entry["human_approval_required"] is False
    assert entry["approval_ref"] is None
