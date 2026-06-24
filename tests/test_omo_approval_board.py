from __future__ import annotations

import json
from pathlib import Path

import yaml

from omo.omo_approval_board import build_approval_board, write_approval_board


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_approval_board_joins_queue_status_and_blockers(tmp_path: Path) -> None:
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    _write_yaml(
        planned_dir / "OPC-P6-SELF-EVOLUTION-doc-gate-e.yaml",
        {
            "id": "OPC-P6-SELF-EVOLUTION-doc-gate-e",
            "title": "Self evolution",
            "status": "candidate",
            "approval_required": True,
            "approval_state": "awaiting_human",
            "latest_week": "2026-W25",
            "loop_history_ref": ".omo/_control/evolution/loop/history.json",
        },
    )
    _write_yaml(
        planned_dir / "OPC-P6-SELF-EVOLUTION-followup.yaml",
        {
            "id": "OPC-P6-SELF-EVOLUTION-followup",
            "title": "Follow up",
            "status": "candidate",
            "approval_required": True,
            "approval_state": "awaiting_human",
            "latest_week": "2026-W25",
            "loop_history_ref": ".omo/_control/evolution/loop/history.json",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_control" / "evolution" / "loop" / "history.json",
        {"summary": {"latest_week": "2026-W29"}},
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "promotion" / "approval-queue" / "current.yaml",
        {
            "tasks": [
                {
                    "task_id": "OPC-P6-SELF-EVOLUTION-doc-gate-e",
                    "approval_status": "granted",
                    "proposal_status": "verified",
                    "eligible": False,
                    "blockers": ["task_policy_blocked"],
                    "next_action": "resolve_blockers",
                },
                {
                    "task_id": "OPC-P6-SELF-EVOLUTION-followup",
                    "approval_status": "granted",
                    "proposal_status": "verified",
                    "eligible": False,
                    "blockers": ["phase_mismatch"],
                    "next_action": "wait_phase",
                },
            ]
        },
    )

    board = build_approval_board(tmp_path)

    assert board["summary"]["task_count"] == 2
    assert board["summary"]["approval_pending_count"] == 0
    assert board["summary"]["approval_granted_blocked_count"] == 2
    assert board["summary"]["task_policy_blocked_count"] == 1
    assert board["summary"]["phase_blocked_count"] == 1
    assert board["summary"]["latest_week"] == "2026-W29"
    assert board["summary"]["latest_week_source"] == "loop_history"
    by_id = {item["task_id"]: item for item in board["tasks"]}
    assert by_id["OPC-P6-SELF-EVOLUTION-doc-gate-e"]["blockers"] == ["task_policy_blocked"]
    assert by_id["OPC-P6-SELF-EVOLUTION-followup"]["blockers"] == ["phase_mismatch"]


def test_approval_board_accepts_multi_document_queue_yaml(tmp_path: Path) -> None:
    planned_dir = tmp_path / ".omo" / "tasks" / "planned"
    _write_yaml(
        planned_dir / "OPC-P6-SELF-EVOLUTION-doc-gate-e.yaml",
        {
            "id": "OPC-P6-SELF-EVOLUTION-doc-gate-e",
            "title": "Self evolution",
            "status": "candidate",
            "approval_required": True,
            "approval_state": "awaiting_human",
            "latest_week": "2026-W25",
            "loop_history_ref": ".omo/_control/evolution/loop/history.json",
        },
    )
    queue_path = tmp_path / ".omo" / "workers" / "promotion" / "approval-queue" / "current.yaml"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(
        "---\nstatus: active\nowner: governance\n---\n---\ntasks:\n"
        "  - task_id: OPC-P6-SELF-EVOLUTION-doc-gate-e\n"
        "    approval_status: granted\n"
        "    proposal_status: verified\n"
        "    eligible: false\n"
        "    blockers:\n      - task_policy_blocked\n"
        "    next_action: resolve_blockers\n",
        encoding="utf-8",
    )

    board = build_approval_board(tmp_path)

    assert board["summary"]["task_count"] == 1
    assert board["tasks"][0]["approval_status"] == "granted"


def test_write_approval_board_renders_queue_status_columns(tmp_path: Path) -> None:
    board = {
        "generated_at": "2026-06-21T00:00:00Z",
        "tasks": [
            {
                "task_id": "OPC-P6-SELF-EVOLUTION-doc-gate-e",
                "task_ref": ".omo/tasks/planned/OPC-P6-SELF-EVOLUTION-doc-gate-e.yaml",
                "task_root": "planned",
                "status": "candidate",
                "approval_required": True,
                "approval_state": "awaiting_human",
                "approval_status": "granted",
                "blockers": ["task_policy_blocked"],
                "next_action": "resolve_blockers",
                "latest_week": "2026-W25",
            }
        ],
        "summary": {
            "task_count": 1,
            "awaiting_human_count": 1,
            "approval_pending_count": 0,
            "approval_granted_blocked_count": 1,
            "approval_ready_count": 0,
            "task_policy_blocked_count": 1,
            "phase_blocked_count": 0,
            "remediation_count": 0,
            "review_lane_count": 0,
            "approval_required_count": 1,
            "latest_week": "2026-W25",
            "latest_week_source": "loop_history",
            "approval_queue_ref": ".omo/workers/promotion/approval-queue/current.yaml",
        },
    }

    json_path, md_path = write_approval_board(tmp_path, board)

    assert json.loads(json_path.read_text(encoding="utf-8"))["summary"]["approval_granted_blocked_count"] == 1
    text = md_path.read_text(encoding="utf-8")
    assert "approval_granted_blocked_count: 1" in text
    assert "task_policy_blocked" in text
    assert "| Task | Root | Status | Approval | Queue Status | Blockers | Next Action | Latest Week | Ref |" in text
