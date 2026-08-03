from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from omo.omo_promotion_approval import build_promotion_approval_history


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def test_build_promotion_approval_history_returns_empty_surface_when_no_approvals_exist(
    tmp_path: Path,
):
    result = build_promotion_approval_history(
        tmp_path, omo_dir=".omo", now="2026-06-03T00:15:00Z"
    )

    assert result["yaml"]["approval_count"] == 0
    assert result["yaml"]["latest_approval_id"] is None
    assert result["yaml"]["approvals"] == []
    assert "Latest approval: none" in result["markdown"]


def test_build_promotion_approval_history_sorts_latest_requested_first(tmp_path: Path):
    _write_yaml(
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "TASK-A-promotion-approval-2026-06-02T00-00-00Z.yaml",
        {
            "approval_id": "TASK-A-promotion-approval-2026-06-02T00-00-00Z",
            "task_id": "TASK-A",
            "approval_status": "requested",
            "requested_at": "2026-06-02T00:00:00Z",
            "approved_at": None,
            "approver": None,
            "refs": {
                "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
        },
    )
    _write_yaml(
        tmp_path
        / ".omo"
        / "_truth"
        / "task-center"
        / "proposals"
        / "TASK-A-promotion-approval-2026-06-02T00-00-00Z-proposal.yaml",
        {
            "id": "TASK-A-promotion-approval-2026-06-02T00-00-00Z-proposal",
            "status": "proposed",
        },
    )
    _write_yaml(
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "TASK-B-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "approval_id": "TASK-B-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "TASK-B",
            "approval_status": "granted",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": "2026-06-03T00:10:00Z",
            "approver": "copilot-cli",
            "refs": {
                "task_ref": ".omo/tasks/planned/TASK-B.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
        },
    )
    _write_yaml(
        tmp_path
        / ".omo"
        / "_truth"
        / "task-center"
        / "proposals"
        / "TASK-B-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
        {
            "id": "TASK-B-promotion-approval-2026-06-03T00-00-00Z-proposal",
            "status": "verified",
        },
    )

    result = build_promotion_approval_history(
        tmp_path, omo_dir=".omo", now="2026-06-03T00:15:00Z"
    )

    assert (
        result["yaml"]["latest_approval_id"]
        == "TASK-B-promotion-approval-2026-06-03T00-00-00Z"
    )
    assert (
        result["yaml"]["prior_approval_id"]
        == "TASK-A-promotion-approval-2026-06-02T00-00-00Z"
    )
    assert [entry["task_id"] for entry in result["yaml"]["approvals"]] == [
        "TASK-B",
        "TASK-A",
    ]
    assert result["yaml"]["requested_count"] == 1
    assert result["yaml"]["granted_count"] == 1


def test_build_promotion_approval_history_keeps_entry_when_proposal_missing(
    tmp_path: Path,
):
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
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": None,
            "approver": None,
            "refs": {
                "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
        },
    )

    result = build_promotion_approval_history(
        tmp_path, omo_dir=".omo", now="2026-06-03T00:15:00Z"
    )

    assert result["yaml"]["approvals"][0]["proposal_status"] == "missing"


def test_build_promotion_approval_history_rejects_missing_required_fields(
    tmp_path: Path,
):
    _write_yaml(
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "BROKEN-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "approval_id": "BROKEN-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "BROKEN",
        },
    )

    with pytest.raises(ValueError, match="missing required promotion approval field"):
        build_promotion_approval_history(
            tmp_path, omo_dir=".omo", now="2026-06-03T00:15:00Z"
        )


def test_build_promotion_approval_history_accepts_multi_document_yaml(tmp_path: Path):
    (tmp_path / ".omo" / "workers" / "runs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".omo" / "_truth" / "task-center" / "proposals").mkdir(
        parents=True, exist_ok=True
    )
    (
        tmp_path
        / ".omo"
        / "workers"
        / "runs"
        / "TASK-A-promotion-approval-2026-06-03T00-00-00Z.yaml"
    ).write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "approval_id: TASK-A-promotion-approval-2026-06-03T00-00-00Z\n"
        "task_id: TASK-A\n"
        "approval_status: requested\n"
        "requested_at: 2026-06-03T00:00:00Z\n"
        "approved_at: null\n"
        "approver: null\n"
        "refs:\n"
        "  task_ref: .omo/tasks/planned/TASK-A.yaml\n"
        "  readiness_ref: .omo/workers/promotion/readiness.yaml\n",
        encoding="utf-8",
    )
    (
        tmp_path
        / ".omo"
        / "_truth"
        / "task-center"
        / "proposals"
        / "TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml"
    ).write_text(
        "---\nstatus: active\n---\n---\nid: TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal\nstatus: proposed\n",
        encoding="utf-8",
    )

    result = build_promotion_approval_history(
        tmp_path, omo_dir=".omo", now="2026-06-03T00:15:00Z"
    )

    assert result["yaml"]["approval_count"] == 1
    assert (
        result["yaml"]["latest_approval_id"]
        == "TASK-A-promotion-approval-2026-06-03T00-00-00Z"
    )
