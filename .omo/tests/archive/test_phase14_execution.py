from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
OMO_ROOT = REPO_ROOT / ".omo"


def _read_yaml(rel_path: str) -> dict:
    return yaml.safe_load((OMO_ROOT / rel_path).read_text(encoding="utf-8"))


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase14_evidence_completes_deferred_ecosystem_scope() -> None:
    triage = _read_yaml("evidence/phase14/integration-triage.yaml")
    pilots = _read_yaml("evidence/phase14/deep-absorption-pilots.yaml")
    patterns = _read_yaml("evidence/phase14/architecture-patterns.yaml")
    ecosystem = _read_yaml("evidence/phase14/ecosystem-preview.yaml")
    security = _read_yaml("evidence/phase14/security-review.yaml")

    assert triage["mode"] == "governed-triage"
    assert len([item for item in triage["ranked_items"] if item["selected_for_phase14"]]) >= 3
    assert pilots["mode"] == "adapter-contract-only"
    assert pilots["mutation"] == "disabled"
    assert len(pilots["pilots"]) == 3
    assert all(pilot["rollback"] for pilot in pilots["pilots"])
    assert patterns["mode"] == "design-fixture"
    assert len(patterns["patterns"]) == 3
    assert ecosystem["mode"] == "preview-only"
    assert ecosystem["mutations_applied"] == 0
    assert ecosystem["marketplace_preview"]["install_enabled"] is False
    assert ecosystem["marketplace_preview"]["publish_enabled"] is False
    assert security["status"] == "pass-with-preview-only-controls"
    assert security["critical_findings"] == []


def test_phase14_closeout_and_tasks_are_recorded() -> None:
    assert "Status: GO" in _read("summaries/phase14-closeout.md")
    assert "Phase 14 is complete" in _read("summaries/phase14-closeout.md")
    assert "Phase 14 executed the deferred ecosystem backlog" in _read("summaries/phase14-retrospective.md")
    assert "Status: completed" in _read("plans/phase14-deferred-ecosystem-backlog.md")
    assert "Status: completed" in _read("plans/phase14-program-plan.md")
    assert "Status: pass" in _read("_knowledge/management/phase14-cross-audit.md")

    for task_id in [
        "P14-W1-INTEGRATION-TRIAGE",
        "P14-W2-DEEP-ABSORPTION-PILOTS",
        "P14-W3-PATTERN-LANDING",
        "P14-W4-ECOSYSTEM-PREVIEW",
    ]:
        task = _read(f"tasks/done/{task_id}.yaml")
        assert "phase: 14" in task
        assert "status: done" in task


def test_phase14_remains_completed_after_phase16_completion_allowing_only_authorized_active_tasks() -> None:
    goals = _read_yaml("goals/current.yaml")
    state = _read_yaml("state/system.yaml")
    active_tasks = list((OMO_ROOT / "tasks" / "active").glob("*.yaml"))
    active_payloads = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in active_tasks]
    stale_active = [
        task for task in active_payloads
        if task.get("phase", 0) <= goals["phase"]
    ]
    unauthorized_active = [
        task["id"]
        for task in active_payloads
        if task.get("status") == "pending"
        and not any("-promotion-" in ref for ref in task.get("handoff_refs", []))
    ]

    assert goals["phase"] == 16
    assert goals["status"] == "completed"
    assert [goal["status"] for goal in goals["goals"]] == ["completed", "completed", "completed", "completed"]
    assert state["current_phase"] == 16
    assert state["phase_status"] == "completed"
    assert state["phase14_status"] == "completed"
    assert state["phase15_status"] == "completed"
    assert state["phase16_status"] == "completed"
    assert state["active_tasks"] == len(active_tasks)
    assert stale_active == [], f"Unexpected non-future active tasks: {stale_active}"
    assert unauthorized_active == [], f"Unexpected non-authorized active tasks: {unauthorized_active}"
