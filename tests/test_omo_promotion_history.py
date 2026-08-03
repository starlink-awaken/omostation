from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from omo.omo_promotion_history import build_promotion_history


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def test_build_promotion_history_returns_empty_surface_when_no_promotions_exist(
    tmp_path: Path,
):
    result = build_promotion_history(
        tmp_path, omo_dir=".omo", now="2026-06-03T00:00:00Z"
    )

    assert result["yaml"]["promotion_count"] == 0
    assert result["yaml"]["latest_promotion_id"] is None
    assert result["yaml"]["promotions"] == []
    assert "Latest promotion: none" in result["markdown"]


def test_build_promotion_history_sorts_promotions_newest_first(tmp_path: Path):
    _write_yaml(
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "TASK-A-promotion-2026-06-02T00-00-00Z.yaml",
        {
            "promotion_id": "TASK-A-promotion-2026-06-02T00-00-00Z",
            "task_id": "TASK-A",
            "promoted_at": "2026-06-02T00:00:00Z",
            "promoted_by": "copilot-cli",
            "task_ref_before": ".omo/tasks/planned/TASK-A.yaml",
            "task_ref_after": ".omo/tasks/active/TASK-A.yaml",
            "approval": {"required": False, "approval_ref": None},
            "phase_gate": {"target_phase": 17},
        },
    )
    _write_yaml(
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "TASK-B-promotion-2026-06-03T00-00-00Z.yaml",
        {
            "promotion_id": "TASK-B-promotion-2026-06-03T00-00-00Z",
            "task_id": "TASK-B",
            "promoted_at": "2026-06-03T00:00:00Z",
            "promoted_by": "copilot-cli",
            "task_ref_before": ".omo/tasks/planned/TASK-B.yaml",
            "task_ref_after": ".omo/tasks/active/TASK-B.yaml",
            "approval": {"required": False, "approval_ref": None},
            "phase_gate": {"target_phase": 17},
        },
    )

    result = build_promotion_history(
        tmp_path, omo_dir=".omo", now="2026-06-03T00:10:00Z"
    )

    assert (
        result["yaml"]["latest_promotion_id"] == "TASK-B-promotion-2026-06-03T00-00-00Z"
    )
    assert (
        result["yaml"]["prior_promotion_id"] == "TASK-A-promotion-2026-06-02T00-00-00Z"
    )
    assert [entry["task_id"] for entry in result["yaml"]["promotions"]] == [
        "TASK-B",
        "TASK-A",
    ]


def test_build_promotion_history_accepts_unphased_promotions(tmp_path: Path):
    _write_yaml(
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "OPT-BOS-GATEWAY-promotion-2026-06-03T00-00-00Z.yaml",
        {
            "promotion_id": "OPT-BOS-GATEWAY-promotion-2026-06-03T00-00-00Z",
            "task_id": "OPT-BOS-GATEWAY",
            "promoted_at": "2026-06-03T00:00:00Z",
            "promoted_by": "copilot-cli",
            "task_ref_before": ".omo/tasks/planned/OPT-BOS-GATEWAY.yaml",
            "task_ref_after": ".omo/tasks/active/OPT-BOS-GATEWAY.yaml",
            "approval": {"required": False, "approval_ref": None},
            "phase_gate": {"target_phase": None},
        },
    )

    result = build_promotion_history(
        tmp_path, omo_dir=".omo", now="2026-06-03T00:10:00Z"
    )

    assert result["yaml"]["promotion_count"] == 1
    assert result["yaml"]["promotions"][0]["target_phase"] is None
    assert "target_phase=unphased" in result["markdown"]


def test_build_promotion_history_rejects_missing_required_fields(tmp_path: Path):
    _write_yaml(
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "BROKEN-promotion-2026-06-03T00-00-00Z.yaml",
        {
            "promotion_id": "BROKEN-promotion-2026-06-03T00-00-00Z",
            "task_id": "BROKEN",
            "promoted_at": "2026-06-03T00:00:00Z",
        },
    )

    with pytest.raises(ValueError, match="missing required promotion field"):
        build_promotion_history(tmp_path, omo_dir=".omo", now="2026-06-03T00:00:00Z")


def test_build_promotion_history_ignores_promotion_approval_request_artifacts(
    tmp_path: Path,
):
    _write_yaml(
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "TASK-A-promotion-2026-06-03T00-00-00Z.yaml",
        {
            "promotion_id": "TASK-A-promotion-2026-06-03T00-00-00Z",
            "task_id": "TASK-A",
            "promoted_at": "2026-06-03T00:00:00Z",
            "promoted_by": "copilot-cli",
            "task_ref_before": ".omo/tasks/planned/TASK-A.yaml",
            "task_ref_after": ".omo/tasks/active/TASK-A.yaml",
            "approval": {"required": False, "approval_ref": None},
            "phase_gate": {"target_phase": 17},
        },
    )
    _write_yaml(
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "TASK-A-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "approval_id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "TASK-A",
            "approval_status": "requested",
        },
    )

    result = build_promotion_history(
        tmp_path, omo_dir=".omo", now="2026-06-03T00:10:00Z"
    )

    assert result["yaml"]["promotion_count"] == 1
    assert (
        result["yaml"]["latest_promotion_id"] == "TASK-A-promotion-2026-06-03T00-00-00Z"
    )


def test_build_promotion_history_accepts_multi_document_promotion_yaml(tmp_path: Path):
    (tmp_path / ".omo" / "workers" / "runs").mkdir(parents=True, exist_ok=True)
    (
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "TASK-A-promotion-2026-06-03T00-00-00Z.yaml"
    ).write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "promotion_id: TASK-A-promotion-2026-06-03T00-00-00Z\n"
        "task_id: TASK-A\n"
        "promoted_at: 2026-06-03T00:00:00Z\n"
        "promoted_by: copilot-cli\n"
        "task_ref_before: .omo/tasks/planned/TASK-A.yaml\n"
        "task_ref_after: .omo/tasks/active/TASK-A.yaml\n"
        "approval:\n"
        "  required: false\n"
        "  approval_ref: null\n"
        "phase_gate:\n"
        "  target_phase: 17\n",
        encoding="utf-8",
    )

    result = build_promotion_history(
        tmp_path, omo_dir=".omo", now="2026-06-03T00:10:00Z"
    )

    assert result["yaml"]["promotion_count"] == 1
    assert (
        result["yaml"]["latest_promotion_id"] == "TASK-A-promotion-2026-06-03T00-00-00Z"
    )
