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
