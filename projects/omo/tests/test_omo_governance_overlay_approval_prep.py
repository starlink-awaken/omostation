from __future__ import annotations

from pathlib import Path

import yaml

from omo.omo_governance_overlay_approval_prep import (
    build_governance_overlay_approval_prep_history,
    build_governance_overlay_approval_prep_status,
)
from omo.omo_governance_overlay_approval_prep_analytics import build_governance_overlay_approval_prep_analytics
from omo.omo_governance_overlay_approval_prep_aging import build_governance_overlay_approval_prep_aging
from omo.omo_governance_overlay_approval_prep_diff import build_governance_overlay_approval_prep_diff
from omo.omo_governance_overlay_approval_prep_trend import build_governance_overlay_approval_prep_trend


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_build_governance_overlay_approval_prep_status_collects_current_prep_targets(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "governance-overlay" / "current.yaml",
        {
            "generated_at": "2026-06-03T02:34:21Z",
            "current_milestone": "GOV-M3-FUTURE-PROMOTION-OPERATIONS",
            "active_target_states": [
                {
                    "target_ref": ".omo/tasks/planned/P24-W2-NUCLEUS-REPLACE.yaml",
                    "task_id": "P24-W2-NUCLEUS-REPLACE",
                    "state": "planned_approval_prep_pending",
                    "action": "await_approval",
                    "result": "approval_prep_pending",
                    "blockers": ["phase_mismatch", "approval_invalid"],
                    "detail": "phase gate is still closed and task-specific promotion approval is not granted yet",
                },
                {
                    "target_ref": ".omo/tasks/planned/P26-W1-FUTURE-APPROVAL.yaml",
                    "task_id": "P26-W1-FUTURE-APPROVAL",
                    "state": "planned_approval_prep_needed",
                    "action": "request_approval",
                    "result": "approval_prep_needed",
                    "blockers": ["phase_mismatch", "approval_missing"],
                    "detail": "phase gate is still closed, but task-specific promotion approval can be prepared now",
                },
                {
                    "target_ref": ".omo/tasks/planned/P25-W1-E2E-INTEGRATION.yaml",
                    "task_id": "P25-W1-E2E-INTEGRATION",
                    "state": "planned_promotion_blocked",
                    "action": "promote_apply",
                    "result": "promotion_blocked",
                    "blockers": ["phase_mismatch"],
                    "detail": "planned task is blocked by existing promotion gates",
                },
            ],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P24-W2-NUCLEUS-REPLACE.yaml",
        {
            "id": "P24-W2-NUCLEUS-REPLACE",
            "approval_ref": ".omo/workers/runs/P24-W2-NUCLEUS-REPLACE-promotion-approval-2026-06-03T01-49-00Z.yaml",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P26-W1-FUTURE-APPROVAL.yaml",
        {
            "id": "P26-W1-FUTURE-APPROVAL",
            "approval_ref": None,
        },
    )

    result = build_governance_overlay_approval_prep_status(tmp_path, omo_dir=".omo", now="2026-06-03T02:35:00Z")

    assert result["yaml"]["prep_task_count"] == 2
    assert result["yaml"]["request_now_count"] == 1
    assert result["yaml"]["awaiting_approval_count"] == 1
    assert [entry["task_id"] for entry in result["yaml"]["tasks"]] == [
        "P26-W1-FUTURE-APPROVAL",
        "P24-W2-NUCLEUS-REPLACE",
    ]
    assert result["yaml"]["tasks"][1]["approval_ref"] == (
        ".omo/workers/runs/P24-W2-NUCLEUS-REPLACE-promotion-approval-2026-06-03T01-49-00Z.yaml"
    )
    assert "## Task: P26-W1-FUTURE-APPROVAL" in result["markdown"]


def test_build_governance_overlay_approval_prep_history_collects_prep_events_from_overlay_runs(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "governance-overlay-2026-06-03T02-31-00Z.yaml",
        {
            "run_id": "governance-overlay-2026-06-03T02-31-00Z",
            "started_at": "2026-06-03T02:31:00Z",
            "completed_at": "2026-06-03T02:31:00Z",
            "target_results": [
                {
                    "target_ref": ".omo/tasks/planned/P26-W1-FUTURE-APPROVAL.yaml",
                    "task_id": "P26-W1-FUTURE-APPROVAL",
                    "state": "planned_approval_prep_needed",
                    "action": "request_approval",
                    "result": "approval_requested",
                    "approval_ref": ".omo/workers/runs/P26-W1-FUTURE-APPROVAL-promotion-approval-2026-06-03T02-31-00Z.yaml",
                    "proposal_ref": ".omo/_truth/task-center/proposals/P26-W1-FUTURE-APPROVAL-promotion-approval-2026-06-03T02-31-00Z-proposal.yaml",
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "governance-overlay-2026-06-03T02-34-21Z.yaml",
        {
            "run_id": "governance-overlay-2026-06-03T02-34-21Z",
            "started_at": "2026-06-03T02:34:21Z",
            "completed_at": "2026-06-03T02:34:21Z",
            "target_results": [
                {
                    "target_ref": ".omo/tasks/planned/P24-W2-NUCLEUS-REPLACE.yaml",
                    "task_id": "P24-W2-NUCLEUS-REPLACE",
                    "state": "planned_approval_prep_pending",
                    "action": "await_approval",
                    "result": "approval_prep_pending",
                    "blockers": ["phase_mismatch", "approval_invalid"],
                }
            ],
        },
    )

    result = build_governance_overlay_approval_prep_history(tmp_path, omo_dir=".omo", now="2026-06-03T02:35:00Z")

    assert result["yaml"]["event_count"] == 2
    assert result["yaml"]["latest_run_id"] == "governance-overlay-2026-06-03T02-34-21Z"
    assert [entry["task_id"] for entry in result["yaml"]["events"]] == [
        "P24-W2-NUCLEUS-REPLACE",
        "P26-W1-FUTURE-APPROVAL",
    ]
    assert result["yaml"]["events"][1]["proposal_ref"] == (
        ".omo/_truth/task-center/proposals/P26-W1-FUTURE-APPROVAL-promotion-approval-2026-06-03T02-31-00Z-proposal.yaml"
    )
    assert "## Event: governance-overlay-2026-06-03T02-31-00Z:P26-W1-FUTURE-APPROVAL" in result["markdown"]


def test_build_governance_overlay_approval_prep_analytics_summarizes_current_and_history(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "governance-overlay" / "approval-prep" / "current.yaml",
        {
            "generated_at": "2026-06-03T02:38:16Z",
            "prep_task_count": 2,
            "request_now_count": 1,
            "awaiting_approval_count": 1,
            "tasks": [
                {
                    "task_id": "P26-W1-FUTURE-APPROVAL",
                    "state": "planned_approval_prep_needed",
                    "action": "request_approval",
                    "blockers": ["phase_mismatch", "approval_missing"],
                    "approval_ref": None,
                },
                {
                    "task_id": "P24-W2-NUCLEUS-REPLACE",
                    "state": "planned_approval_prep_pending",
                    "action": "await_approval",
                    "blockers": ["phase_mismatch", "approval_invalid"],
                    "approval_ref": ".omo/workers/runs/P24-W2-NUCLEUS-REPLACE-promotion-approval-2026-06-03T01-49-00Z.yaml",
                },
            ],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "governance-overlay" / "approval-prep" / "history" / "current.yaml",
        {
            "generated_at": "2026-06-03T02:38:46Z",
            "event_count": 2,
            "events": [
                {
                    "event_id": "governance-overlay-2026-06-03T02-34-21Z:P24-W2-NUCLEUS-REPLACE",
                    "run_id": "governance-overlay-2026-06-03T02-34-21Z",
                    "task_id": "P24-W2-NUCLEUS-REPLACE",
                    "started_at": "2026-06-03T02:34:21Z",
                },
                {
                    "event_id": "governance-overlay-2026-06-01T02-31-00Z:P26-W1-FUTURE-APPROVAL",
                    "run_id": "governance-overlay-2026-06-01T02-31-00Z",
                    "task_id": "P26-W1-FUTURE-APPROVAL",
                    "started_at": "2026-06-01T02:31:00Z",
                },
            ],
        },
    )

    result = build_governance_overlay_approval_prep_analytics(tmp_path, omo_dir=".omo", now="2026-06-03T02:39:00Z")

    assert result["yaml"]["prep_task_count"] == 2
    assert result["yaml"]["history_event_count"] == 2
    assert result["yaml"]["action_queues"]["request_now"][0]["task_id"] == "P26-W1-FUTURE-APPROVAL"
    assert result["yaml"]["blocker_histogram"] == {"phase_mismatch": 2, "approval_missing": 1, "approval_invalid": 1}
    assert result["yaml"]["age_buckets"] == {"lt_1d": 1, "d1_to_d3": 1, "d3_plus": 0}
    assert result["yaml"]["tasks"][0]["task_id"] == "P26-W1-FUTURE-APPROVAL"
    assert "## Task: P24-W2-NUCLEUS-REPLACE" in result["markdown"]


def test_build_governance_overlay_approval_prep_trend_summarizes_event_window_and_burndown(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "governance-overlay" / "approval-prep" / "analytics" / "current.yaml",
        {
            "generated_at": "2026-06-03T02:42:32Z",
            "prep_task_count": 1,
            "history_event_count": 3,
            "request_now_count": 0,
            "awaiting_approval_count": 1,
            "blocker_histogram": {"phase_mismatch": 1, "approval_invalid": 1},
            "age_buckets": {"lt_1d": 1, "d1_to_d3": 0, "d3_plus": 0},
            "action_queues": {"request_now": [], "awaiting_approval": [{"task_id": "P24-W2-NUCLEUS-REPLACE"}]},
            "tasks": [
                {
                    "task_id": "P24-W2-NUCLEUS-REPLACE",
                    "state": "planned_approval_prep_pending",
                    "action": "await_approval",
                    "age_bucket": "lt_1d",
                    "latest_started_at": "2026-06-03T02:34:21Z",
                    "blockers": ["phase_mismatch", "approval_invalid"],
                    "approval_ref": ".omo/workers/runs/P24-W2-NUCLEUS-REPLACE-promotion-approval-2026-06-03T01-49-00Z.yaml",
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "governance-overlay" / "approval-prep" / "history" / "current.yaml",
        {
            "generated_at": "2026-06-03T02:38:46Z",
            "event_count": 3,
            "events": [
                {
                    "event_id": "governance-overlay-2026-06-03T02-34-21Z:P24-W2-NUCLEUS-REPLACE",
                    "run_id": "governance-overlay-2026-06-03T02-34-21Z",
                    "task_id": "P24-W2-NUCLEUS-REPLACE",
                    "state": "planned_approval_prep_pending",
                    "action": "await_approval",
                    "result": "approval_prep_pending",
                    "started_at": "2026-06-03T02:34:21Z",
                },
                {
                    "event_id": "governance-overlay-2026-06-02T02-31-00Z:P26-W1-FUTURE-APPROVAL",
                    "run_id": "governance-overlay-2026-06-02T02-31-00Z",
                    "task_id": "P26-W1-FUTURE-APPROVAL",
                    "state": "planned_approval_prep_needed",
                    "action": "request_approval",
                    "result": "approval_requested",
                    "started_at": "2026-06-02T02:31:00Z",
                },
                {
                    "event_id": "governance-overlay-2026-06-01T02-00-00Z:P25-W1-DOCS-DEBT-CLOSURE",
                    "run_id": "governance-overlay-2026-06-01T02-00-00Z",
                    "task_id": "P25-W1-DOCS-DEBT-CLOSURE",
                    "state": "planned_approval_prep_needed",
                    "action": "request_approval",
                    "result": "approval_requested",
                    "started_at": "2026-06-01T02:00:00Z",
                },
            ],
        },
    )

    result = build_governance_overlay_approval_prep_trend(tmp_path, omo_dir=".omo", now="2026-06-03T02:43:00Z")

    assert result["yaml"]["trend_status"] == "trend_available"
    assert result["yaml"]["window_event_count"] == 3
    assert result["yaml"]["oldest_started_at"] == "2026-06-01T02:00:00Z"
    assert result["yaml"]["latest_started_at"] == "2026-06-03T02:34:21Z"
    assert result["yaml"]["burndown"] == {
        "current_backlog": 1,
        "peak_backlog_estimate": 3,
        "resolved_estimate": 2,
        "net_change_from_peak": -2,
    }
    assert result["yaml"]["action_histogram"] == {"await_approval": 1, "request_approval": 2}
    assert len(result["yaml"]["intervals"]) == 2
    assert result["yaml"]["points"][-1]["task_id"] == "P24-W2-NUCLEUS-REPLACE"
    assert "## Burndown" in result["markdown"]


def test_build_governance_overlay_approval_prep_diff_classifies_entered_transitioned_and_exited_tasks(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "governance-overlay" / "approval-prep" / "current.yaml",
        {
            "generated_at": "2026-06-03T02:35:00Z",
            "prep_task_count": 2,
            "request_now_count": 1,
            "awaiting_approval_count": 1,
            "tasks": [
                {
                    "task_id": "P26-W1-FUTURE-APPROVAL",
                    "state": "planned_approval_prep_needed",
                    "action": "request_approval",
                    "result": "approval_prep_needed",
                    "blockers": ["phase_mismatch", "approval_missing"],
                    "approval_ref": None,
                },
                {
                    "task_id": "P24-W2-NUCLEUS-REPLACE",
                    "state": "planned_approval_prep_pending",
                    "action": "await_approval",
                    "result": "approval_prep_pending",
                    "blockers": ["phase_mismatch", "approval_invalid"],
                    "approval_ref": ".omo/workers/runs/P24-W2-NUCLEUS-REPLACE-promotion-approval-2026-06-03T01-49-00Z.yaml",
                },
            ],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "governance-overlay" / "approval-prep" / "history" / "current.yaml",
        {
            "generated_at": "2026-06-03T02:38:46Z",
            "event_count": 4,
            "events": [
                {
                    "event_id": "governance-overlay-2026-06-03T02-34-21Z:P24-W2-NUCLEUS-REPLACE",
                    "run_id": "governance-overlay-2026-06-03T02-34-21Z",
                    "task_id": "P24-W2-NUCLEUS-REPLACE",
                    "state": "planned_approval_prep_pending",
                    "action": "await_approval",
                    "result": "approval_prep_pending",
                    "started_at": "2026-06-03T02:34:21Z",
                },
                {
                    "event_id": "governance-overlay-2026-06-03T02-32-00Z:P26-W1-FUTURE-APPROVAL",
                    "run_id": "governance-overlay-2026-06-03T02-32-00Z",
                    "task_id": "P26-W1-FUTURE-APPROVAL",
                    "state": "planned_approval_prep_needed",
                    "action": "request_approval",
                    "result": "approval_requested",
                    "started_at": "2026-06-03T02:32:00Z",
                },
                {
                    "event_id": "governance-overlay-2026-06-03T01-49-00Z:P24-W2-NUCLEUS-REPLACE",
                    "run_id": "governance-overlay-2026-06-03T01-49-00Z",
                    "task_id": "P24-W2-NUCLEUS-REPLACE",
                    "state": "planned_approval_prep_needed",
                    "action": "request_approval",
                    "result": "approval_requested",
                    "started_at": "2026-06-03T01:49:00Z",
                },
                {
                    "event_id": "governance-overlay-2026-06-02T02-00-00Z:P25-W1-DOCS-DEBT-CLOSURE",
                    "run_id": "governance-overlay-2026-06-02T02-00-00Z",
                    "task_id": "P25-W1-DOCS-DEBT-CLOSURE",
                    "state": "planned_approval_prep_needed",
                    "action": "request_approval",
                    "result": "approval_requested",
                    "started_at": "2026-06-02T02:00:00Z",
                },
            ],
        },
    )

    result = build_governance_overlay_approval_prep_diff(tmp_path, omo_dir=".omo", now="2026-06-03T02:43:00Z")

    assert result["yaml"]["diff_status"] == "diff_available"
    assert result["yaml"]["current_task_count"] == 2
    assert result["yaml"]["new_current_task_ids"] == ["P26-W1-FUTURE-APPROVAL"]
    assert result["yaml"]["changed_current_task_ids"] == ["P24-W2-NUCLEUS-REPLACE"]
    assert result["yaml"]["no_longer_current_task_ids"] == ["P25-W1-DOCS-DEBT-CLOSURE"]
    changes = {entry["task_id"]: entry for entry in result["yaml"]["task_changes"]}
    assert changes["P24-W2-NUCLEUS-REPLACE"]["change_kind"] == "transitioned"
    assert changes["P24-W2-NUCLEUS-REPLACE"]["previous_action"] == "request_approval"
    assert changes["P26-W1-FUTURE-APPROVAL"]["change_kind"] == "entered"
    assert "## Exited" in result["markdown"]


def test_build_governance_overlay_approval_prep_aging_prioritizes_followups_and_escalations(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "workers" / "governance-overlay" / "approval-prep" / "analytics" / "current.yaml",
        {
            "generated_at": "2026-06-03T10:58:00Z",
            "prep_task_count": 3,
            "history_event_count": 4,
            "request_now_count": 1,
            "awaiting_approval_count": 2,
            "blocker_histogram": {"phase_mismatch": 3, "approval_invalid": 2, "approval_missing": 1},
            "age_buckets": {"lt_1d": 1, "d1_to_d3": 1, "d3_plus": 1},
            "action_queues": {
                "request_now": [{"task_id": "P30-W1-REQUEST-LONGTAIL"}],
                "awaiting_approval": [
                    {"task_id": "P31-W1-PENDING-FOLLOWUP"},
                    {"task_id": "P32-W1-FRESH-PREP"},
                ],
            },
            "tasks": [
                {
                    "task_id": "P30-W1-REQUEST-LONGTAIL",
                    "state": "planned_approval_prep_needed",
                    "action": "request_approval",
                    "age_bucket": "d3_plus",
                    "latest_started_at": "2026-05-29T10:00:00Z",
                    "blockers": ["phase_mismatch", "approval_missing"],
                    "approval_ref": None,
                },
                {
                    "task_id": "P31-W1-PENDING-FOLLOWUP",
                    "state": "planned_approval_prep_pending",
                    "action": "await_approval",
                    "age_bucket": "d1_to_d3",
                    "latest_started_at": "2026-06-01T10:00:00Z",
                    "blockers": ["phase_mismatch", "approval_invalid"],
                    "approval_ref": ".omo/workers/runs/P31-W1-PENDING-FOLLOWUP-promotion-approval.yaml",
                },
                {
                    "task_id": "P32-W1-FRESH-PREP",
                    "state": "planned_approval_prep_pending",
                    "action": "await_approval",
                    "age_bucket": "lt_1d",
                    "latest_started_at": "2026-06-03T06:00:00Z",
                    "blockers": ["phase_mismatch", "approval_invalid"],
                    "approval_ref": ".omo/workers/runs/P32-W1-FRESH-PREP-promotion-approval.yaml",
                },
            ],
        },
    )

    result = build_governance_overlay_approval_prep_aging(tmp_path, omo_dir=".omo", now="2026-06-03T11:00:00Z")

    assert result["yaml"]["aging_status"] == "aging_available"
    assert result["yaml"]["attention_summary"] == {"fresh_count": 1, "watch_count": 1, "escalate_count": 1}
    assert result["yaml"]["followup_task_ids"] == ["P30-W1-REQUEST-LONGTAIL", "P31-W1-PENDING-FOLLOWUP"]
    assert result["yaml"]["escalation_task_ids"] == ["P30-W1-REQUEST-LONGTAIL"]
    assert result["yaml"]["tasks"][0]["task_id"] == "P30-W1-REQUEST-LONGTAIL"
    assert result["yaml"]["tasks"][0]["attention_level"] == "escalate"
    assert result["yaml"]["tasks"][1]["attention_reason"] == "approval follow-up aging past 1 day"
    assert "## Escalation Candidates" in result["markdown"]
