from __future__ import annotations

from pathlib import Path

import yaml

from scripts.omo_governance_overlay_loop import plan_governance_overlay_cycle


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_plan_governance_overlay_cycle_returns_idle_when_no_candidates(tmp_path: Path):
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
            "updated_at": "2026-06-03T06:35:00Z",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_truth" / "governance-overlay" / "autopilot-policy.yaml",
        {"autopilot_mode": "full_omo_autopilot", "auto_select": True},
    )
    _write_yaml(tmp_path / ".omo" / "_truth" / "governance-overlay" / "roadmap.yaml", {"items": []})

    result = plan_governance_overlay_cycle(tmp_path, omo_dir=".omo", actor="copilot-cli", now="2026-06-03T06:40:00Z")

    assert result["run"]["summary"] == "idle"
    assert result["run"]["roadmap_item_id"] is None


def test_plan_governance_overlay_cycle_requests_approval_for_gated_planned_task(tmp_path: Path):
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
        {
            "autopilot_mode": "full_omo_autopilot",
            "auto_select": True,
            "auto_promote_when_safe": True,
        },
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
                    "status": "pending",
                    "depends_on": [],
                    "source_refs": [".omo/MASTER-BLUEPRINT.md"],
                    "target_refs": [".omo/tasks/planned/TASK-A.yaml"],
                    "success_criteria": ["TASK-A advanced"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "tasks" / "planned" / "TASK-A.yaml",
        {
            "id": "TASK-A",
            "phase": 17,
            "milestone": "GOV-M1",
            "priority": "P0",
            "title": "Task A",
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
            "risk_level": "L2",
            "allowed_operation_level": "L2",
            "human_approval_required": True,
            "entry_gate": ["governance overlay shell ready"],
            "evidence_required": ["approval request created"],
            "test_plan": [".omo/tests/test_omo_governance_overlay_loop.py"],
            "started_at": None,
            "completed_at": None,
            "blocked_by": None,
            "retry_count": 0,
        },
    )

    result = plan_governance_overlay_cycle(tmp_path, omo_dir=".omo", actor="copilot-cli", now="2026-06-03T06:40:00Z")

    assert result["run"]["target_results"][0]["action"] == "request_approval"
    assert result["run"]["target_results"][0]["result"] == "approval_request_needed"


def test_plan_governance_overlay_cycle_blocks_unsupported_target_ref(tmp_path: Path):
    _write_yaml(
        tmp_path / ".omo" / "_control" / "governance-overlay" / "current.yaml",
        {
            "overlay_id": "GOV-OVERLAY-2026-06",
            "status": "active",
            "autopilot_mode": "full_omo_autopilot",
            "intake_scope": "future_planned_debt",
            "current_milestone": "GOV-M2-SHAREDBRAIN-DEBT",
            "next_milestone": "GOV-M3",
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
                    "id": "GOV-M2-SHAREDBRAIN-DEBT",
                    "type": "debt-bundle",
                    "title": "SharedBrain debt",
                    "priority": "P1",
                    "status": "pending",
                    "depends_on": [],
                    "source_refs": [".omo/debt/registry.yaml"],
                    "target_refs": [".omo/debt/dashboard/current.yaml"],
                    "success_criteria": ["debt bundle processed"],
                }
            ]
        },
    )
    _write_yaml(tmp_path / ".omo" / "debt" / "dashboard" / "current.yaml", {"items": []})

    result = plan_governance_overlay_cycle(tmp_path, omo_dir=".omo", actor="copilot-cli", now="2026-06-03T06:40:00Z")

    assert result["run"]["target_results"][0]["action"] == "mark_blocked"
    assert result["run"]["target_results"][0]["result"] == "unsupported_target_ref"
    assert result["run"]["summary"] == "blocked"


def test_plan_governance_overlay_cycle_closes_done_active_item(tmp_path: Path):
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
        {
            "autopilot_mode": "full_omo_autopilot",
            "auto_select": True,
        },
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
                },
                {
                    "id": "GOV-M2-SHAREDBRAIN-DEBT",
                    "type": "debt-bundle",
                    "title": "SharedBrain debt",
                    "priority": "P1",
                    "status": "pending",
                    "depends_on": ["GOV-M1-EXECUTION-HARDENING"],
                    "source_refs": [".omo/debt/registry.yaml"],
                    "target_refs": [".omo/debt/dashboard/current.yaml"],
                    "success_criteria": ["debt closed"],
                },
            ]
        },
    )
    _write_yaml(tmp_path / ".omo" / "tasks" / "done" / "TASK-A.yaml", {"id": "TASK-A", "status": "done"})

    result = plan_governance_overlay_cycle(tmp_path, omo_dir=".omo", actor="copilot-cli", now="2026-06-03T06:50:00Z")

    assert result["run"]["mode"] == "continue_active"
    assert result["run"]["summary"] == "close_ready"
    assert result["run"]["roadmap_item_id"] == "GOV-M1-EXECUTION-HARDENING"
