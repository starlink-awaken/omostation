from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.omo_governance_overlay import build_governance_overlay_status


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_build_governance_overlay_status_reports_candidate_and_blocked_items(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1",
            "next_milestone": "GOV-M2",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T06:30:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {
            "autopilot_mode": "full_omo_autopilot",
            "auto_select": True,
            "auto_promote_when_safe": True,
            "human_gate_on_high_risk": True,
            "retry_on_blocked": "explicit",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-ROADMAP-E2E",
                    "type": "task-bundle",
                    "title": "E2E and pricing debt closure",
                    "priority": "P0",
                    "status": "pending",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [
                        ".omo/tasks/planned/D2-CI-E2E-TEST-ENV.yaml",
                        ".omo/tasks/planned/D3-EU-PRICING-TEST.yaml",
                    ],
                    "success_criteria": ["D2 and D3 promoted and closed"],
                },
                {
                    "id": "GOV-M2-BRIDGE",
                    "type": "debt-bundle",
                    "title": "SharedBrain bridge recovery",
                    "priority": "P1",
                    "status": "pending",
                    "depends_on": ["GOV-M1-ROADMAP-E2E"],
                    "source_refs": [".omo/debt/registry.yaml"],
                    "target_refs": [".omo/debt/dashboard/current.yaml"],
                    "success_criteria": ["bridge debt no longer blocks roadmap"],
                },
            ]
        },
    )
    _write_yaml(tmp_path / ".omo" / "tasks" / "planned" / "D2-CI-E2E-TEST-ENV.yaml", {"id": "D2-CI-E2E-TEST-ENV"})
    _write_yaml(tmp_path / ".omo" / "tasks" / "planned" / "D3-EU-PRICING-TEST.yaml", {"id": "D3-EU-PRICING-TEST"})
    _write_yaml(tmp_path / ".omo" / "debt" / "dashboard" / "current.yaml", {"items": []})

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T06:35:00Z")

    assert result["yaml"]["eligible_count"] == 1
    assert result["yaml"]["blocked_count"] == 1
    assert result["yaml"]["autopilot_candidates"][0]["id"] == "GOV-M1-ROADMAP-E2E"
    assert result["yaml"]["blocked_items"][0]["id"] == "GOV-M2-BRIDGE"
    assert result["yaml"]["next_action"] == "advance:GOV-M1-ROADMAP-E2E"


def test_build_governance_overlay_status_marks_missing_target_refs_invalid(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1",
            "next_milestone": None,
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T06:30:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {
            "autopilot_mode": "full_omo_autopilot",
            "auto_select": True,
            "auto_promote_when_safe": True,
            "human_gate_on_high_risk": True,
            "retry_on_blocked": "explicit",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-MISSING",
                    "type": "task-bundle",
                    "title": "Missing target ref bundle",
                    "priority": "P0",
                    "status": "pending",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/DOES-NOT-EXIST.yaml"],
                    "success_criteria": ["missing ref repaired"],
                }
            ]
        },
    )

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T06:35:00Z")

    assert result["yaml"]["eligible_count"] == 0
    assert result["yaml"]["blocked_count"] == 1
    assert result["yaml"]["blocked_items"][0]["reason"] == "missing_target_refs"
    assert result["yaml"]["next_action"] == "repair_refs"


def test_build_governance_overlay_status_requires_overlay_inputs(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="governance-overlay/current.yaml"):
        build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T06:35:00Z")


def test_build_governance_overlay_status_reports_active_roadmap_item_and_target_states(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1-EXECUTION-HARDENING",
            "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T06:35:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {"autopilot_mode": "full_omo_autopilot", "auto_select": True},
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-EXECUTION-HARDENING",
                    "type": "task-bundle",
                    "title": "Execution hardening",
                    "priority": "P0",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml", ".omo/tasks/planned/TASK-B.yaml"],
                    "success_criteria": ["execution hardening closed"],
                }
            ]
        },
    )
    _write_yaml(tmp_path / ".omo" / "tasks" / "active" / "TASK-A.yaml", {"id": "TASK-A", "status": "pending"})
    _write_yaml(tmp_path / ".omo" / "tasks" / "done" / "TASK-B.yaml", {"id": "TASK-B", "status": "done"})

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T06:50:00Z")

    assert result["yaml"]["active_roadmap_item"]["id"] == "GOV-M1-EXECUTION-HARDENING"
    assert result["yaml"]["active_target_states"][0]["state"] == "active_pending"
    assert result["yaml"]["active_target_states"][1]["state"] == "done"
    assert result["yaml"]["next_action"] == "dispatch:TASK-A"


def test_build_governance_overlay_status_prefers_verify_for_active_review_target(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1-EXECUTION-HARDENING",
            "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T06:35:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {"autopilot_mode": "full_omo_autopilot", "auto_select": True},
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-EXECUTION-HARDENING",
                    "type": "task-bundle",
                    "title": "Execution hardening",
                    "priority": "P0",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                    "success_criteria": ["execution hardening closed"],
                }
            ]
        },
    )
    _write_yaml(tmp_path / ".omo" / "tasks" / "active" / "TASK-A.yaml", {"id": "TASK-A", "status": "review"})

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T07:00:00Z")

    assert result["yaml"]["active_target_states"][0]["state"] == "active_review"
    assert result["yaml"]["next_action"] == "verify:TASK-A"


def test_build_governance_overlay_status_surfaces_contract_gap_for_dispatched_empty_scope(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1-EXECUTION-HARDENING",
            "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T07:10:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {"autopilot_mode": "full_omo_autopilot", "auto_select": True},
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-EXECUTION-HARDENING",
                    "type": "task-bundle",
                    "title": "Execution hardening",
                    "priority": "P0",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                    "success_criteria": ["execution hardening closed"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "active" / "TASK-A.yaml",
        {
            "id": "TASK-A",
            "status": "in_progress",
            "deliverables": [],
            "run_ref": ".omo/workers/runs/task-a-dispatch.yaml",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "task-a-dispatch.yaml",
        {"dispatch_state": "dispatched"},
    )

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T07:12:00Z")

    assert result["yaml"]["active_target_states"][0]["state"] == "active_dispatch_blocked"
    assert result["yaml"]["active_target_states"][0]["detail"] == "dispatch exists but task has no launch-ready write scope"
    assert result["yaml"]["next_action"] == "contract:TASK-A"


def test_build_governance_overlay_status_surfaces_launch_for_dispatched_ready_scope(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M1-EXECUTION-HARDENING",
            "next_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T07:10:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {"autopilot_mode": "full_omo_autopilot", "auto_select": True},
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M1-EXECUTION-HARDENING",
                    "type": "task-bundle",
                    "title": "Execution hardening",
                    "priority": "P0",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                    "success_criteria": ["execution hardening closed"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "active" / "TASK-A.yaml",
        {
            "id": "TASK-A",
            "status": "in_progress",
            "deliverables": ["src/app.py"],
            "run_ref": ".omo/workers/runs/task-a-dispatch.yaml",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "task-a-dispatch.yaml",
        {"dispatch_state": "dispatched"},
    )

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T07:13:00Z")

    assert result["yaml"]["active_target_states"][0]["state"] == "active_dispatched"
    assert result["yaml"]["next_action"] == "launch:TASK-A"


def test_build_governance_overlay_status_surfaces_planned_approval_pending_for_active_item(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M3-FUTURE-PROMOTION-OPERATIONS",
            "next_milestone": None,
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T01:49:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {"autopilot_mode": "full_omo_autopilot", "auto_select": True},
    )
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 23})
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M3-FUTURE-PROMOTION-OPERATIONS",
                    "type": "phase-bridge",
                    "title": "Future promotion bridge",
                    "priority": "P1",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/P24-W2-NUCLEUS-REPLACE.yaml"],
                    "success_criteria": ["future packet promoted safely"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P24-W2-NUCLEUS-REPLACE.yaml",
        {
            "id": "P24-W2-NUCLEUS-REPLACE",
            "phase": 24,
            "milestone": "M24.2",
            "priority": "P0",
            "title": "Nucleus replace",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/P24-W2-NUCLEUS-REPLACE-promotion-approval-2026-06-03T01-49-00Z.yaml",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/MASTER-BLUEPRINT.md"],
            "depends_on": [],
            "entry_gate": ["phase23_completed"],
            "risk_level": "L3",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "evidence_required": ["approval granted"],
            "test_plan": [".omo/tests/test_omo_governance_overlay.py"],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "P24-W2-NUCLEUS-REPLACE-promotion-approval-2026-06-03T01-49-00Z.yaml",
        {
            "task_id": "P24-W2-NUCLEUS-REPLACE",
            "approval_status": "requested",
            "approval_scope": "task.promote_apply",
            "refs": {"task_ref": ".omo/tasks/planned/P24-W2-NUCLEUS-REPLACE.yaml"},
        },
    )

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T01:49:10Z")

    assert result["yaml"]["active_target_states"][0]["state"] == "planned_approval_pending"
    assert result["yaml"]["active_target_states"][0]["task_id"] == "P24-W2-NUCLEUS-REPLACE"
    assert result["yaml"]["next_action"] == "monitor:GOV-M3-FUTURE-PROMOTION-OPERATIONS"


def test_build_governance_overlay_status_surfaces_planned_promotion_blocked_for_phase_mismatch(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M3-FUTURE-PROMOTION-OPERATIONS",
            "next_milestone": None,
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T01:49:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {"autopilot_mode": "full_omo_autopilot", "auto_select": True},
    )
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M3-FUTURE-PROMOTION-OPERATIONS",
                    "type": "phase-bridge",
                    "title": "Future promotion bridge",
                    "priority": "P1",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/P25-W1-E2E-INTEGRATION.yaml"],
                    "success_criteria": ["future packet promoted safely"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P25-W1-E2E-INTEGRATION.yaml",
        {
            "id": "P25-W1-E2E-INTEGRATION",
            "phase": 25,
            "milestone": "M25.1",
            "priority": "P0",
            "title": "E2E integration",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/P24-W2-NUCLEUS-REPLACE-promotion-approval-2026-06-03T02-27-00Z.yaml",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/MASTER-BLUEPRINT.md"],
            "depends_on": [],
            "entry_gate": ["phase24_completed"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["promotion gates clear"],
            "test_plan": [".omo/tests/test_omo_governance_overlay.py"],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "P24-W2-NUCLEUS-REPLACE-promotion-approval-2026-06-03T02-27-00Z.yaml",
        {
            "task_id": "P24-W2-NUCLEUS-REPLACE",
            "approval_status": "requested",
            "approval_scope": "task.promote_apply",
            "refs": {"task_ref": ".omo/tasks/planned/P24-W2-NUCLEUS-REPLACE.yaml"},
        },
    )

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T01:49:10Z")

    assert result["yaml"]["active_target_states"][0]["state"] == "planned_promotion_blocked"
    assert result["yaml"]["active_target_states"][0]["blockers"] == ["phase_mismatch"]
    assert result["yaml"]["next_action"] == "monitor:GOV-M3-FUTURE-PROMOTION-OPERATIONS"


def test_build_governance_overlay_status_summarizes_monitor_blockers_for_active_phase_bridge(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M3-FUTURE-PROMOTION-OPERATIONS",
            "next_milestone": None,
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T02:27:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {"autopilot_mode": "full_omo_autopilot", "auto_select": True},
    )
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M3-FUTURE-PROMOTION-OPERATIONS",
                    "type": "phase-bridge",
                    "title": "Future promotion bridge",
                    "priority": "P1",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [
                        ".omo/tasks/planned/P24-W2-NUCLEUS-REPLACE.yaml",
                        ".omo/tasks/planned/P25-W1-E2E-INTEGRATION.yaml",
                    ],
                    "success_criteria": ["future packets promoted safely"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P24-W2-NUCLEUS-REPLACE.yaml",
        {
            "id": "P24-W2-NUCLEUS-REPLACE",
            "phase": 24,
            "milestone": "M24.2",
            "priority": "P0",
            "title": "Nucleus replace",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": ".omo/workers/runs/P24-W2-NUCLEUS-REPLACE-promotion-approval-2026-06-03T02-27-00Z.yaml",
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/MASTER-BLUEPRINT.md"],
            "depends_on": [],
            "entry_gate": ["phase23_completed"],
            "risk_level": "L3",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "evidence_required": ["approval granted"],
            "test_plan": [".omo/tests/test_omo_governance_overlay.py"],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "P24-W2-NUCLEUS-REPLACE-promotion-approval-2026-06-03T02-27-00Z.yaml",
        {
            "task_id": "P24-W2-NUCLEUS-REPLACE",
            "approval_status": "requested",
            "approval_scope": "task.promote_apply",
            "refs": {"task_ref": ".omo/tasks/planned/P24-W2-NUCLEUS-REPLACE.yaml"},
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P25-W1-E2E-INTEGRATION.yaml",
        {
            "id": "P25-W1-E2E-INTEGRATION",
            "phase": 25,
            "milestone": "M25.1",
            "priority": "P0",
            "title": "E2E integration",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/MASTER-BLUEPRINT.md"],
            "depends_on": [],
            "entry_gate": ["phase24_completed"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
            "human_approval_required": False,
            "evidence_required": ["promotion gates clear"],
            "test_plan": [".omo/tests/test_omo_governance_overlay.py"],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "governance-overlay" / "approval-prep" / "current.yaml",
        {
            "generated_at": "2026-06-03T02:35:00Z",
            "prep_task_count": 1,
            "request_now_count": 0,
            "awaiting_approval_count": 1,
            "tasks": [{"task_id": "P24-W2-NUCLEUS-REPLACE"}],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "governance-overlay" / "approval-prep" / "trend" / "current.yaml",
        {
            "generated_at": "2026-06-03T02:43:00Z",
            "trend_status": "trend_available",
            "window_event_count": 2,
            "burndown": {"current_backlog": 1, "peak_backlog_estimate": 1, "resolved_estimate": 0, "net_change_from_peak": 0},
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "governance-overlay" / "approval-prep" / "diff" / "current.yaml",
        {
            "generated_at": "2026-06-03T10:55:00Z",
            "diff_status": "diff_available",
            "new_current_task_ids": [],
            "changed_current_task_ids": ["P24-W2-NUCLEUS-REPLACE"],
            "no_longer_current_task_ids": [],
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "governance-overlay" / "approval-prep" / "aging" / "current.yaml",
        {
            "generated_at": "2026-06-03T11:01:00Z",
            "aging_status": "aging_available",
            "attention_summary": {"fresh_count": 1, "watch_count": 0, "escalate_count": 0},
            "followup_task_ids": [],
            "escalation_task_ids": [],
        },
    )

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T02:27:56Z")

    assert result["yaml"]["next_action"] == "monitor:GOV-M3-FUTURE-PROMOTION-OPERATIONS"
    assert result["yaml"]["monitor_summary"] == {
        "blocked_target_count": 2,
        "state_histogram": {"planned_approval_prep_pending": 1, "planned_promotion_blocked": 1},
        "blocker_histogram": {"phase_mismatch": 2, "approval_invalid": 1},
        "approval_blocked_task_ids": ["P24-W2-NUCLEUS-REPLACE"],
        "phase_blocked_task_ids": [
            "P24-W2-NUCLEUS-REPLACE",
            "P25-W1-E2E-INTEGRATION",
        ],
        "approval_prep": {
            "prep_task_count": 1,
            "request_now_count": 0,
            "awaiting_approval_count": 1,
            "trend_status": "trend_available",
            "window_event_count": 2,
            "changed_current_task_ids": ["P24-W2-NUCLEUS-REPLACE"],
            "no_longer_current_task_ids": [],
            "attention_summary": {"fresh_count": 1, "watch_count": 0, "escalate_count": 0},
            "followup_task_ids": [],
            "escalation_task_ids": [],
        },
    }
    assert "## Active monitor summary" in result["markdown"]
    assert "approval_blocked=P24-W2-NUCLEUS-REPLACE" in result["markdown"]
    assert "prep_awaiting_approval=1" in result["markdown"]
    assert "prep_changed=P24-W2-NUCLEUS-REPLACE" in result["markdown"]


def test_build_governance_overlay_status_advances_phase_blocked_target_into_approval_prep(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M3-FUTURE-PROMOTION-OPERATIONS",
            "next_milestone": None,
            "success_target": "future roadmap governed through overlay lane",
            "updated_at": "2026-06-03T02:30:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {"autopilot_mode": "full_omo_autopilot", "auto_select": True},
    )
    _write_yaml(tmp_path / ".omo" / "goals" / "current.yaml", {"phase": 16})
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml",
        {
            "items": [
                {
                    "id": "GOV-M3-FUTURE-PROMOTION-OPERATIONS",
                    "type": "phase-bridge",
                    "title": "Future promotion bridge",
                    "priority": "P1",
                    "status": "in_progress",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/P24-W2-NUCLEUS-REPLACE.yaml"],
                    "success_criteria": ["future packets promoted safely"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "P24-W2-NUCLEUS-REPLACE.yaml",
        {
            "id": "P24-W2-NUCLEUS-REPLACE",
            "phase": 24,
            "milestone": "M24.2",
            "priority": "P0",
            "title": "Nucleus replace",
            "status": "pending",
            "assigned_to": None,
            "dispatch_id": None,
            "run_ref": None,
            "approval_ref": None,
            "review_ref": None,
            "knowledge_refs": [],
            "handoff_refs": [],
            "source_docs": [".omo/MASTER-BLUEPRINT.md"],
            "depends_on": [],
            "entry_gate": ["phase23_completed"],
            "risk_level": "L3",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "evidence_required": ["approval granted"],
            "test_plan": [".omo/tests/test_omo_governance_overlay.py"],
        },
    )

    result = build_governance_overlay_status(tmp_path, omo_dir=".omo", now="2026-06-03T02:30:30Z")

    assert result["yaml"]["active_target_states"][0]["state"] == "planned_approval_prep_needed"
    assert result["yaml"]["active_target_states"][0]["action"] == "request_approval"
    assert result["yaml"]["active_target_states"][0]["blockers"] == ["phase_mismatch", "approval_missing"]
    assert result["yaml"]["next_action"] == "advance:GOV-M3-FUTURE-PROMOTION-OPERATIONS"
