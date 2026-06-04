from __future__ import annotations

from pathlib import Path

import yaml

from omo.omo_promotion_approval import evaluate_promotion_approval


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_evaluate_promotion_approval_returns_missing_when_ref_absent(tmp_path: Path):
    result = evaluate_promotion_approval(
        tmp_path,
        approval_ref=None,
        task_id="P19-W3-ARCHIVE-TS",
        task_ref=".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
    )

    assert result["approval_ready"] is False
    assert result["blocker"] == "approval_missing"


def test_evaluate_promotion_approval_rejects_shared_markdown_baseline_ref(tmp_path: Path):
    _write_text(
        tmp_path / ".omo" / "workers" / "runs" / "future-active-l2l3-pending-approval-2026-06-02.md",
        "# planning backlog presence only\n",
    )

    result = evaluate_promotion_approval(
        tmp_path,
        approval_ref=".omo/workers/runs/future-active-l2l3-pending-approval-2026-06-02.md",
        task_id="P19-W3-ARCHIVE-TS",
        task_ref=".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
    )

    assert result["approval_ready"] is False
    assert result["blocker"] == "approval_invalid"


def test_evaluate_promotion_approval_rejects_yaml_for_different_task(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "OTHER-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "version": 1,
            "approval_id": "OTHER-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "OTHER",
            "approval_status": "granted",
            "requested_operation_level": "L2",
            "approval_scope": "task.promote_apply",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": "2026-06-03T00:05:00Z",
            "expires_at": None,
            "approver": "human",
            "refs": {
                "task_ref": ".omo/tasks/planned/OTHER.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
            "evidence": {"request_evidence": [], "approval_evidence": []},
        },
    )

    result = evaluate_promotion_approval(
        tmp_path,
        approval_ref=".omo/workers/runs/OTHER-promotion-approval-2026-06-03T00-00-00Z.yaml",
        task_id="P19-W3-ARCHIVE-TS",
        task_ref=".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
    )

    assert result["approval_ready"] is False
    assert result["blocker"] == "approval_invalid"


def test_evaluate_promotion_approval_accepts_valid_task_specific_yaml(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml",
        {
            "version": 1,
            "approval_id": "P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z",
            "task_id": "P19-W3-ARCHIVE-TS",
            "approval_status": "granted",
            "requested_operation_level": "L2",
            "approval_scope": "task.promote_apply",
            "requested_at": "2026-06-03T00:00:00Z",
            "approved_at": "2026-06-03T00:05:00Z",
            "expires_at": None,
            "approver": "human",
            "refs": {
                "task_ref": ".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
                "readiness_ref": ".omo/workers/promotion/readiness.yaml",
            },
            "evidence": {"request_evidence": [], "approval_evidence": []},
        },
    )

    result = evaluate_promotion_approval(
        tmp_path,
        approval_ref=".omo/workers/runs/P19-W3-ARCHIVE-TS-promotion-approval-2026-06-03T00-00-00Z.yaml",
        task_id="P19-W3-ARCHIVE-TS",
        task_ref=".omo/tasks/planned/P19-W3-ARCHIVE-TS.yaml",
    )

    assert result["approval_ready"] is True
    assert result["blocker"] is None
