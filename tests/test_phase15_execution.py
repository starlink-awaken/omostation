from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parent
OMO_ROOT = REPO_ROOT / ".omo"


def _read_yaml(rel_path: str) -> dict:
    return yaml.safe_load((OMO_ROOT / rel_path).read_text(encoding="utf-8"))


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def _resolve_workspace_ref(ref: str) -> Path:
    if ref.startswith(".omo/"):
        return WORKSPACE_ROOT / ref
    return WORKSPACE_ROOT / ref


def test_phase15_governance_evidence_ledger_is_complete_and_traceable() -> None:
    ledger = _read_yaml("_truth/governance-evidence/ledger.yaml")

    assert ledger["phase"] == 15
    assert ledger["status"] == "ready"
    assert ledger["live_ssot_mutation"] == "disabled"
    assert ledger["entry_gate"]["phase14_status"] == "completed"

    envelope_types = {entry["type"] for entry in ledger["entries"]}
    assert {
        "promotion",
        "deferred-scope",
        "scenario-trace",
        "mutation-proposal",
        "closeout",
        "recovery-drill",
        "project-health",
        "user-value-scenario",
    }.issubset(envelope_types)

    for entry in ledger["entries"]:
        assert entry["id"]
        assert entry["evidence_refs"]
        assert entry["verification"]
        assert entry["rollback"]
        for ref in entry["evidence_refs"]:
            assert _resolve_workspace_ref(ref).exists(), ref


def test_phase15_policy_report_blocks_governance_invariant_violations() -> None:
    report = _read_yaml("_delivery/evidence/phase15/policy-test-report.yaml")

    assert report["status"] == "pass"
    assert report["policy_test_pass_rate"] == 1.0
    assert report["live_mutations_applied"] == 0
    assert report["draft_activation_leak_count"] == 0

    blocked = {check["id"]: check for check in report["checks"]}
    for required in [
        "no-live-ssot-promotion-without-envelope",
        "one-active-packet",
        "no-hidden-deferred-scope",
        "mutation-proposal-requires-rollback",
        "drafts-never-enter-active",
        "user-value-evidence-required",
    ]:
        assert blocked[required]["result"] == "pass"
        assert blocked[required]["would_block"] is True


def test_phase15_proposal_compiler_outputs_inactive_task_drafts_only() -> None:
    compiler = _read_yaml("_delivery/evidence/phase15/proposal-to-task-dry-run.yaml")
    drafts = sorted((OMO_ROOT / "tasks" / "drafts").glob("P15-*.yaml"))
    active = sorted((OMO_ROOT / "tasks" / "active").glob("*.yaml"))
    p15_active = [
        task for task in active
        if yaml.safe_load(task.read_text(encoding="utf-8")).get("phase") == 15
    ]

    assert compiler["status"] == "ready"
    assert compiler["mode"] == "inactive-draft-only"
    assert compiler["created_active_tasks"] == 0
    assert len(compiler["drafts"]) >= 2
    assert drafts
    assert p15_active == []

    for draft in drafts:
        payload = yaml.safe_load(draft.read_text(encoding="utf-8"))
        assert payload["phase"] == 15
        assert payload["status"] == "draft"
        assert payload["activation_allowed"] is False
        assert payload["approval_required"] == "human"
        assert payload["source_evidence"]
        assert payload["rollback"]
        assert payload["verification"]


def test_phase15_dashboard_includes_projects_and_user_value_not_only_omo() -> None:
    dashboard = _read_yaml("_delivery/evidence/phase15/operating-dashboard-snapshot.yaml")

    assert dashboard["status"] == "ready"
    assert dashboard["ledger_authoritative"] is True
    assert dashboard["dashboard_mutation_allowed"] is False
    assert set(dashboard["project_health"]) == {"kairon", "gbrain", "agentmesh", "SharedBrain"}
    assert all(project["evidence_refs"] for project in dashboard["project_health"].values())
    assert dashboard["user_value"]["scenario_count"] >= 3
    assert dashboard["user_value"]["live_demo_candidates"] >= 2
    assert dashboard["user_value"]["risk"] == "governed-preview"


def test_phase15_recovery_and_user_value_evidence_are_rehearsed() -> None:
    recovery = _read_yaml("_delivery/evidence/phase15/recovery-drill-report.yaml")
    user_value = _read_yaml("_delivery/evidence/phase15/user-value-loop.yaml")

    assert recovery["status"] == "pass"
    assert recovery["rollback_drill_success_rate"] == 1.0
    assert recovery["mode"] == "fixture-and-dry-run"
    assert all(drill["result"] == "pass" for drill in recovery["drills"])

    assert user_value["status"] == "ready"
    assert user_value["mode"] == "governed-user-value-loop"
    assert len(user_value["scenarios"]) == 3
    for scenario in user_value["scenarios"]:
        assert scenario["user_goal"]
        assert scenario["projects_used"]
        assert scenario["evidence_refs"]
        assert scenario["current_limit"]
        assert scenario["next_improvement"]


def test_phase15_cli_commands_are_usable() -> None:
    commands = [
        ("ledger", '"status": "ready"'),
        ("policy", '"status": "pass"'),
        ("compile", '"created_active_tasks": 0'),
        ("dashboard", '"status": "ready"'),
        ("recovery", '"status": "pass"'),
        ("user-value", '"status": "ready"'),
    ]

    for command, expected in commands:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "omo"), "phase15", command],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        assert expected in result.stdout


def test_phase15_remains_completed_after_phase16_completion_allowing_only_authorized_active_tasks() -> None:
    goals = _read_yaml("_truth/goals/current.yaml")
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

    assert goals["phase"] >= 16
    assert goals["status"] in ("completed", "active", "done")
    assert all(s in ("completed", "active", "done") for s in [goal["status"] for goal in goals["goals"]])
    assert state["current_phase"] >= 16
    assert state["phase_status"] in ("completed", "active")
    assert state["phase15_status"] == "completed"
    assert state["phase16_status"] == "completed"
    assert state["active_tasks"] == len(active_tasks)
    assert stale_active == [], f"Unexpected non-future active tasks: {stale_active}"
    assert unauthorized_active == [], f"Unexpected non-authorized active tasks: {unauthorized_active}"

    assert "Phase 15 is complete" in _read("_knowledge/summaries/phase15/phase15-closeout.md")
    assert "Status: GO" in _read("_knowledge/summaries/phase15/phase15-closeout.md")
    assert "projects and user value loop" in _read("_knowledge/summaries/phase15/phase15-retrospective.md")
    assert "Status: pass" in _read("_knowledge/management/phase15-cross-audit.md")
