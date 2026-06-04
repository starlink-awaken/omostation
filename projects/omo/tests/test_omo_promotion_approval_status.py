from __future__ import annotations

from scripts.omo_promotion_approval_status import (
    build_promotion_approval_status_packet,
    render_promotion_approval_status_markdown,
)


def test_build_status_packet_counts_requested_approved_and_granted_states():
    packet = build_promotion_approval_status_packet(
        generated_at="2026-06-03T00:00:00Z",
        tasks=[
            {
                "task_id": "TASK-REQ",
                "task_ref": ".omo/tasks/planned/TASK-REQ.yaml",
                "approval_ref": ".omo/workers/runs/TASK-REQ-promotion-approval-2026-06-03T00-00-00Z.yaml",
                "approval_id": "TASK-REQ-promotion-approval-2026-06-03T00-00-00Z",
                "approval_status": "requested",
                "proposal_id": "TASK-REQ-promotion-approval-2026-06-03T00-00-00Z-proposal",
                "proposal_ref": ".omo/_truth/task-center/proposals/TASK-REQ-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                "proposal_status": "proposed",
                "human_approval_required": True,
                "eligible": False,
                "blockers": ["approval_invalid"],
            },
            {
                "task_id": "TASK-APPROVED",
                "task_ref": ".omo/tasks/planned/TASK-APPROVED.yaml",
                "approval_ref": ".omo/workers/runs/TASK-APPROVED-promotion-approval-2026-06-03T00-00-00Z.yaml",
                "approval_id": "TASK-APPROVED-promotion-approval-2026-06-03T00-00-00Z",
                "approval_status": "requested",
                "proposal_id": "TASK-APPROVED-promotion-approval-2026-06-03T00-00-00Z-proposal",
                "proposal_ref": ".omo/_truth/task-center/proposals/TASK-APPROVED-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                "proposal_status": "approved",
                "human_approval_required": True,
                "eligible": False,
                "blockers": ["approval_invalid"],
            },
            {
                "task_id": "TASK-GRANTED",
                "task_ref": ".omo/tasks/planned/TASK-GRANTED.yaml",
                "approval_ref": ".omo/workers/runs/TASK-GRANTED-promotion-approval-2026-06-03T00-00-00Z.yaml",
                "approval_id": "TASK-GRANTED-promotion-approval-2026-06-03T00-00-00Z",
                "approval_status": "granted",
                "proposal_id": "TASK-GRANTED-promotion-approval-2026-06-03T00-00-00Z-proposal",
                "proposal_ref": ".omo/_truth/task-center/proposals/TASK-GRANTED-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                "proposal_status": "verified",
                "human_approval_required": True,
                "eligible": False,
                "blockers": ["phase_mismatch"],
            },
        ],
    )

    assert packet["approval_task_count"] == 3
    assert packet["requested_count"] == 1
    assert packet["approved_pending_apply_count"] == 1
    assert packet["granted_count"] == 1


def test_build_status_packet_orders_blocked_then_lifecycle_then_task_id():
    packet = build_promotion_approval_status_packet(
        generated_at="2026-06-03T00:00:00Z",
        tasks=[
            {
                "task_id": "TASK-C",
                "task_ref": ".omo/tasks/planned/TASK-C.yaml",
                "approval_ref": ".omo/workers/runs/TASK-C-promotion-approval-2026-06-03T00-00-00Z.yaml",
                "approval_id": "TASK-C-promotion-approval-2026-06-03T00-00-00Z",
                "approval_status": "granted",
                "proposal_id": "TASK-C-promotion-approval-2026-06-03T00-00-00Z-proposal",
                "proposal_ref": ".omo/_truth/task-center/proposals/TASK-C-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                "proposal_status": "verified",
                "human_approval_required": True,
                "eligible": True,
                "blockers": [],
            },
            {
                "task_id": "TASK-A",
                "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                "approval_ref": ".omo/workers/runs/TASK-A-promotion-approval-2026-06-03T00-00-00Z.yaml",
                "approval_id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z",
                "approval_status": "requested",
                "proposal_id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal",
                "proposal_ref": ".omo/_truth/task-center/proposals/TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                "proposal_status": "approved",
                "human_approval_required": True,
                "eligible": False,
                "blockers": ["approval_invalid"],
            },
            {
                "task_id": "TASK-B",
                "task_ref": ".omo/tasks/planned/TASK-B.yaml",
                "approval_ref": ".omo/workers/runs/TASK-B-promotion-approval-2026-06-03T00-00-00Z.yaml",
                "approval_id": "TASK-B-promotion-approval-2026-06-03T00-00-00Z",
                "approval_status": "requested",
                "proposal_id": "TASK-B-promotion-approval-2026-06-03T00-00-00Z-proposal",
                "proposal_ref": ".omo/_truth/task-center/proposals/TASK-B-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                "proposal_status": "proposed",
                "human_approval_required": True,
                "eligible": False,
                "blockers": ["approval_invalid"],
            },
        ],
    )

    assert [entry["task_id"] for entry in packet["tasks"]] == ["TASK-B", "TASK-A", "TASK-C"]


def test_render_status_markdown_emits_operator_action_hints():
    markdown = render_promotion_approval_status_markdown(
        {
            "generated_at": "2026-06-03T00:00:00Z",
            "approval_task_count": 2,
            "requested_count": 1,
            "approved_pending_apply_count": 0,
            "granted_count": 1,
            "tasks": [
                {
                    "task_id": "TASK-A",
                    "task_ref": ".omo/tasks/planned/TASK-A.yaml",
                    "approval_ref": ".omo/workers/runs/TASK-A-promotion-approval-2026-06-03T00-00-00Z.yaml",
                    "approval_id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z",
                    "approval_status": "requested",
                    "proposal_id": "TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal",
                    "proposal_ref": ".omo/_truth/task-center/proposals/TASK-A-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                    "proposal_status": "proposed",
                    "human_approval_required": True,
                    "eligible": False,
                    "blockers": ["approval_invalid"],
                },
                {
                    "task_id": "TASK-B",
                    "task_ref": ".omo/tasks/planned/TASK-B.yaml",
                    "approval_ref": ".omo/workers/runs/TASK-B-promotion-approval-2026-06-03T00-00-00Z.yaml",
                    "approval_id": "TASK-B-promotion-approval-2026-06-03T00-00-00Z",
                    "approval_status": "granted",
                    "proposal_id": "TASK-B-promotion-approval-2026-06-03T00-00-00Z-proposal",
                    "proposal_ref": ".omo/_truth/task-center/proposals/TASK-B-promotion-approval-2026-06-03T00-00-00Z-proposal.yaml",
                    "proposal_status": "verified",
                    "human_approval_required": True,
                    "eligible": False,
                    "blockers": ["phase_mismatch"],
                },
            ],
        }
    )

    assert "action=run governance approve" in markdown
    assert "action=approval blocker cleared; check readiness" in markdown
