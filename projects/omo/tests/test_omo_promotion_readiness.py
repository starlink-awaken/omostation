from __future__ import annotations

from omo.omo_promotion_readiness import (
    build_promotion_readiness_packet,
    render_promotion_readiness_markdown,
)


def test_build_promotion_readiness_packet_returns_zero_counts_for_empty_queue():
    packet = build_promotion_readiness_packet(
        generated_at="2026-06-03T00:00:00Z",
        current_phase=16,
        tasks=(),
    )

    assert packet["current_phase"] == 16
    assert packet["target_phase"] == 17
    assert packet["ready_count"] == 0
    assert packet["blocked_count"] == 0
    assert packet["tasks"] == []


def test_build_promotion_readiness_packet_orders_eligible_first_then_phase_then_task_id():
    packet = build_promotion_readiness_packet(
        generated_at="2026-06-03T00:00:00Z",
        current_phase=16,
        tasks=(
            {
                "task_id": "P18-W2-BLOCKED",
                "task_ref": ".omo/tasks/planned/P18-W2-BLOCKED.yaml",
                "phase": 18,
                "status": "pending",
                "risk_level": "L2",
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "approval_ref": None,
                "eligible": False,
                "blockers": ["phase_mismatch"],
                "checks": {"phase_ok": False},
                "errors": [],
            },
            {
                "task_id": "P17-W2-READY",
                "task_ref": ".omo/tasks/planned/P17-W2-READY.yaml",
                "phase": 17,
                "status": "pending",
                "risk_level": "L1",
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "approval_ref": None,
                "eligible": True,
                "blockers": [],
                "checks": {"phase_ok": True},
                "errors": [],
            },
            {
                "task_id": "P17-W1-READY",
                "task_ref": ".omo/tasks/planned/P17-W1-READY.yaml",
                "phase": 17,
                "status": "pending",
                "risk_level": "L1",
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "approval_ref": None,
                "eligible": True,
                "blockers": [],
                "checks": {"phase_ok": True},
                "errors": [],
            },
        ),
    )

    assert packet["ready_count"] == 2
    assert packet["blocked_count"] == 1
    assert [entry["task_id"] for entry in packet["tasks"]] == [
        "P17-W1-READY",
        "P17-W2-READY",
        "P18-W2-BLOCKED",
    ]


def test_render_promotion_readiness_markdown_labels_ready_and_blocked_entries():
    packet = build_promotion_readiness_packet(
        generated_at="2026-06-03T00:00:00Z",
        current_phase=16,
        tasks=(
            {
                "task_id": "P17-W1-READY",
                "task_ref": ".omo/tasks/planned/P17-W1-READY.yaml",
                "phase": 17,
                "status": "pending",
                "risk_level": "L1",
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "approval_ref": None,
                "eligible": True,
                "blockers": [],
                "checks": {"phase_ok": True},
                "errors": [],
            },
            {
                "task_id": "P18-W1-BLOCKED",
                "task_ref": ".omo/tasks/planned/P18-W1-BLOCKED.yaml",
                "phase": 18,
                "status": "pending",
                "risk_level": "L2",
                "allowed_operation_level": "L1",
                "human_approval_required": False,
                "approval_ref": None,
                "eligible": False,
                "blockers": ["phase_mismatch"],
                "checks": {"phase_ok": False},
                "errors": [],
            },
        ),
    )

    markdown = render_promotion_readiness_markdown(packet)

    assert "Ready tasks: 1" in markdown
    assert "Blocked tasks: 1" in markdown
    assert "## Ready: P17-W1-READY" in markdown
    assert "## Blocked: P18-W1-BLOCKED" in markdown
    assert "blockers=none" in markdown
    assert "blockers=phase_mismatch" in markdown
