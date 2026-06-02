from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.omo_promotion_approval_analytics import build_promotion_approval_analytics_packet


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_build_promotion_approval_analytics_packet_returns_zero_rollup_when_no_tasks_exist(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "current.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "approval_task_count": 0,
            "requested_count": 0,
            "approved_pending_apply_count": 0,
            "granted_count": 0,
            "tasks": [],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "history" / "current.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "approval_count": 0,
            "approvals": [],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "blocked_count": 0,
            "ready_count": 0,
            "tasks": [],
        },
    )

    packet = build_promotion_approval_analytics_packet(tmp_path, omo_dir=".omo", now="2026-06-03T06:00:00Z")

    assert packet["yaml"]["approval_task_count"] == 0
    assert packet["yaml"]["history_approval_count"] == 0
    assert packet["yaml"]["action_queues"]["approve_now"] == []
    assert packet["yaml"]["blocker_histogram"] == {}
    assert packet["yaml"]["approval_age_buckets"] == {"lt_1d": 0, "d1_to_d3": 0, "d3_plus": 0}


def test_build_promotion_approval_analytics_packet_classifies_action_queues_and_histograms(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "current.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "approval_task_count": 3,
            "requested_count": 2,
            "approved_pending_apply_count": 1,
            "granted_count": 1,
            "tasks": [
                {
                    "task_id": "TASK-A",
                    "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                    "approval_ref": ".omo/workers/runs/TASK-A-promotion-approval-2026-06-03T05-00-00Z.yaml",
                    "approval_id": "TASK-A-promotion-approval-2026-06-03T05-00-00Z",
                    "approval_status": "requested",
                    "proposal_id": "TASK-A-promotion-approval-2026-06-03T05-00-00Z-proposal",
                    "proposal_status": "proposed",
                    "eligible": False,
                    "blockers": ["approval_invalid", "phase_mismatch"],
                },
                {
                    "task_id": "TASK-B",
                    "task_ref": ".omo/tasks/planned/TASK-B.yaml",
                    "approval_ref": ".omo/workers/runs/TASK-B-promotion-approval-2026-06-02T06-00-00Z.yaml",
                    "approval_id": "TASK-B-promotion-approval-2026-06-02T06-00-00Z",
                    "approval_status": "requested",
                    "proposal_id": "TASK-B-promotion-approval-2026-06-02T06-00-00Z-proposal",
                    "proposal_status": "approved",
                    "eligible": False,
                    "blockers": ["approval_invalid"],
                },
                {
                    "task_id": "TASK-C",
                    "task_ref": ".omo/tasks/planned/TASK-C.yaml",
                    "approval_ref": ".omo/workers/runs/TASK-C-promotion-approval-2026-06-01T06-00-00Z.yaml",
                    "approval_id": "TASK-C-promotion-approval-2026-06-01T06-00-00Z",
                    "approval_status": "granted",
                    "proposal_id": "TASK-C-promotion-approval-2026-06-01T06-00-00Z-proposal",
                    "proposal_status": "verified",
                    "eligible": False,
                    "blockers": ["phase_mismatch"],
                },
            ],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "history" / "current.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "approval_count": 3,
            "approvals": [
                {
                    "approval_id": "TASK-A-promotion-approval-2026-06-03T05-00-00Z",
                    "task_id": "TASK-A",
                    "requested_at": "2026-06-03T05:00:00Z",
                    "approval_status": "requested",
                    "proposal_status": "proposed",
                },
                {
                    "approval_id": "TASK-B-promotion-approval-2026-06-02T06-00-00Z",
                    "task_id": "TASK-B",
                    "requested_at": "2026-06-02T06:00:00Z",
                    "approval_status": "requested",
                    "proposal_status": "approved",
                },
                {
                    "approval_id": "TASK-C-promotion-approval-2026-06-01T06-00-00Z",
                    "task_id": "TASK-C",
                    "requested_at": "2026-06-01T06:00:00Z",
                    "approval_status": "granted",
                    "proposal_status": "verified",
                },
            ],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "blocked_count": 3,
            "ready_count": 0,
            "tasks": [
                {"task_id": "TASK-A", "blockers": ["approval_invalid", "phase_mismatch"]},
                {"task_id": "TASK-B", "blockers": ["approval_invalid"]},
                {"task_id": "TASK-C", "blockers": ["phase_mismatch"]},
            ],
        },
    )

    packet = build_promotion_approval_analytics_packet(tmp_path, omo_dir=".omo", now="2026-06-03T06:00:00Z")

    assert [item["task_id"] for item in packet["yaml"]["action_queues"]["approve_now"]] == ["TASK-A"]
    assert [item["task_id"] for item in packet["yaml"]["action_queues"]["apply_now"]] == ["TASK-B"]
    assert [item["task_id"] for item in packet["yaml"]["action_queues"]["check_readiness"]] == ["TASK-C"]
    assert packet["yaml"]["blocker_histogram"] == {"approval_invalid": 2, "phase_mismatch": 2}
    assert packet["yaml"]["proposal_status_histogram"] == {
        "proposed": 1,
        "approved": 1,
        "verified": 1,
        "missing": 0,
        "invalid": 0,
    }


def test_build_promotion_approval_analytics_packet_assigns_age_buckets_for_open_requests(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "current.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "approval_task_count": 3,
            "requested_count": 3,
            "approved_pending_apply_count": 0,
            "granted_count": 0,
            "tasks": [
                {
                    "task_id": "TASK-A",
                    "approval_id": "A",
                    "approval_status": "requested",
                    "proposal_id": "A-proposal",
                    "proposal_status": "proposed",
                    "eligible": False,
                    "blockers": ["approval_invalid"],
                },
                {
                    "task_id": "TASK-B",
                    "approval_id": "B",
                    "approval_status": "requested",
                    "proposal_id": "B-proposal",
                    "proposal_status": "proposed",
                    "eligible": False,
                    "blockers": ["approval_invalid"],
                },
                {
                    "task_id": "TASK-C",
                    "approval_id": "C",
                    "approval_status": "requested",
                    "proposal_id": "C-proposal",
                    "proposal_status": "proposed",
                    "eligible": False,
                    "blockers": ["approval_invalid"],
                },
            ],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "approvals" / "history" / "current.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "approval_count": 3,
            "approvals": [
                {
                    "approval_id": "A",
                    "task_id": "TASK-A",
                    "requested_at": "2026-06-03T05:30:00Z",
                    "approval_status": "requested",
                    "proposal_status": "proposed",
                },
                {
                    "approval_id": "B",
                    "task_id": "TASK-B",
                    "requested_at": "2026-06-02T05:00:00Z",
                    "approval_status": "requested",
                    "proposal_status": "proposed",
                },
                {
                    "approval_id": "C",
                    "task_id": "TASK-C",
                    "requested_at": "2026-05-30T06:00:00Z",
                    "approval_status": "requested",
                    "proposal_status": "proposed",
                },
            ],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "readiness.yaml",
        {
            "generated_at": "2026-06-03T06:00:00Z",
            "blocked_count": 3,
            "ready_count": 0,
            "tasks": [
                {"task_id": "TASK-A", "blockers": ["approval_invalid"]},
                {"task_id": "TASK-B", "blockers": ["approval_invalid"]},
                {"task_id": "TASK-C", "blockers": ["approval_invalid"]},
            ],
        },
    )

    packet = build_promotion_approval_analytics_packet(tmp_path, omo_dir=".omo", now="2026-06-03T06:00:00Z")

    assert packet["yaml"]["approval_age_buckets"] == {"lt_1d": 1, "d1_to_d3": 1, "d3_plus": 1}
    assert [item["task_id"] for item in packet["yaml"]["tasks"]] == ["TASK-C", "TASK-B", "TASK-A"]


def test_build_promotion_approval_analytics_packet_requires_all_canonical_inputs(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="approvals/current.yaml"):
        build_promotion_approval_analytics_packet(tmp_path, omo_dir=".omo", now="2026-06-03T06:00:00Z")
