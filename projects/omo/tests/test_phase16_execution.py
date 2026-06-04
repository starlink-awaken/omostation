from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
OMO_ROOT = REPO_ROOT / ".omo"
EXTERNAL_OMO_ROOT = Path("/Users/xiamingxing/Documents/学习进化/体系/OMO")


def _read_yaml(rel_path: str) -> dict:
    return yaml.safe_load((OMO_ROOT / rel_path).read_text(encoding="utf-8"))


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase16_plan_promotes_knowledge_capture_search_scope() -> None:
    plan = _read("plans/phase16-product-surface-convergence-preplanning.md")

    assert "Status: completed" in plan
    assert "Knowledge Capture/Search Product Surface Convergence" in plan
    assert "knowledge-capture-search" in plan
    assert "SharedBrain" in plan
    assert "gbrain" in plan
    assert "kairon" in plan
    assert "Phase 16 is not an ecosystem-expansion phase" in plan
    assert "repo `.omo/` stores live evidence" in plan
    assert "external OMO stores case, pattern, and playbook" in plan


def test_phase16_scenario_shell_defines_user_contract_and_boundaries() -> None:
    scenario = _read_yaml("scenarios/knowledge-capture-search.yaml")
    shell = _read_yaml("evidence/phase16/scenario-shell.yaml")

    assert scenario["id"] == "knowledge-capture-search"
    assert scenario["status"] == "ready"
    assert scenario["authorization"] == "scenario-contract-only"
    assert scenario["input_contract"] == ["text_or_markdown_file", "query"]
    assert scenario["output_contract"] == ["capture_receipt", "search_hits", "result_summary", "evidence_refs", "status"]
    assert set(scenario["status_enum"]) == {"ready", "needs_approval", "blocked", "failed_with_recovery", "completed"}
    assert scenario["project_boundaries"]["SharedBrain"] == "runtime-home and result-home"
    assert scenario["project_boundaries"]["gbrain"] == "capture, search, retrieval"
    assert scenario["project_boundaries"]["kairon"] == "capability binding and governance trace"
    assert scenario["project_boundaries"]["agentmesh"] == "future orchestration candidate only"

    assert shell["scenario_id"] == "knowledge-capture-search"
    assert shell["status"] == "ready"
    assert shell["binds"] == ["intent", "context", "policy", "execution", "verification", "recovery"]
    assert shell["does_not_authorize_live_mutation"] is True
    assert shell["phase15_guardrails_preserved"] is True


def test_phase16_baseline_and_walkthrough_tie_omo_back_to_projects_and_user_value() -> None:
    baseline = _read_yaml("evidence/phase16/journey-baseline.yaml")
    walkthrough = _read_yaml("evidence/phase16/capture-search-walkthrough.yaml")
    adoption = _read_yaml("evidence/phase16/adoption-closeout.yaml")

    assert baseline["status"] == "ready"
    assert baseline["primary_scenario"] == "knowledge-capture-search"
    assert baseline["gap"] == "control-plane-strong-user-entry-fragmented"
    assert set(baseline["project_roles"]) == {"SharedBrain", "gbrain", "kairon", "agentmesh"}
    assert baseline["phase15_inputs"]

    assert walkthrough["status"] in {"completed", "failed_with_recovery"}
    assert walkthrough["mode"] in {"fixture-backed", "low-risk-live"}
    assert walkthrough["user_visible_result"]["capture_receipt"]
    assert len(walkthrough["user_visible_result"]["search_hits"]) >= 1
    assert walkthrough["user_visible_result"]["result_summary"]
    assert walkthrough["evidence_refs"]
    if walkthrough["mode"] == "fixture-backed":
        assert walkthrough["blocked_reason"]
        assert walkthrough["next_live_demo_condition"]

    assert adoption["status"] == "ready"
    assert adoption["user_can_complete_task"] is True
    assert adoption["result_states"] == ["completed", "blocked", "needs_approval", "failed_with_recovery"]
    assert adoption["remaining_limits"]


def test_phase16_recovery_and_policy_keep_phase15_guardrails() -> None:
    recovery = _read_yaml("evidence/phase16/recovery-report.yaml")
    phase15_policy = _read_yaml("evidence/phase15/policy-test-report.yaml")

    assert recovery["status"] == "pass"
    assert recovery["mode"] == "fixture-backed-recovery"
    assert recovery["live_mutations_applied"] == 0
    assert recovery["marketplace_install_enabled"] is False
    assert recovery["auto_mutation_enabled"] is False
    assert all(item["result"] == "pass" for item in recovery["checks"])

    assert phase15_policy["status"] == "pass"
    assert phase15_policy["draft_activation_leak_count"] == 0


def test_phase16_external_omo_records_method_without_shadow_ssot() -> None:
    case = EXTERNAL_OMO_ROOT / "_delivery" / "cases" / "2026-06-01-phase16-knowledge-capture-search-retrospective.md"
    pattern = EXTERNAL_OMO_ROOT / "_delivery" / "patterns" / "03-控制面不能替代用户价值.md"
    playbook = EXTERNAL_OMO_ROOT / "_control" / "07-从OMO计划到项目能力升级Playbook.md"

    for path in [case, pattern, playbook]:
        assert path.exists(), path
        text = path.read_text(encoding="utf-8")
        assert "Pointer" in text
        assert "/Users/xiamingxing/Workspace/.omo/" in text
        assert "shadow SSOT" in text
        assert "current_phase:" not in text
        assert "active_tasks:" not in text

    assert "控制面不能替代用户价值" in pattern.read_text(encoding="utf-8")
    assert "知识捕获检索" in case.read_text(encoding="utf-8")
    assert "从 OMO 计划转项目能力升级" in playbook.read_text(encoding="utf-8")


def test_phase16_cli_commands_are_usable() -> None:
    commands = [
        ("baseline", '"status": "ready"'),
        ("scenario", '"status": "ready"'),
        ("walkthrough", '"status": "completed"'),
        ("recovery", '"status": "pass"'),
        ("closeout", '"status": "ready"'),
    ]

    for command, expected in commands:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "omo"), "phase16", command],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        assert expected in result.stdout


def test_phase16_closeout_and_live_state_are_completed_with_only_authorized_active_tasks() -> None:
    goals = _read_yaml("goals/current.yaml")
    state = _read_yaml("state/system.yaml")
    active_tasks = list((OMO_ROOT / "tasks" / "active").glob("*.yaml"))
    active_payloads = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in active_tasks]
    # After Phase 16 closeout, future backlog must live in planned/ unless the coordinator
    # explicitly promotes one packet and records that promotion in handoff_refs.
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
    assert goals["status"] in ("completed", "active")
    assert all(s in ("completed", "active") for s in [goal["status"] for goal in goals["goals"]])
    assert state["current_phase"] >= 16
    assert state["phase_status"] in ("completed", "active")
    assert state["phase15_status"] == "completed"
    assert state["phase16_status"] == "completed"
    assert stale_active == [], f"Unexpected non-future active tasks: {stale_active}"
    assert unauthorized_active == [], f"Unexpected non-authorized active tasks: {unauthorized_active}"

    assert "Phase 16 is complete" in _read("summaries/phase16/phase16-closeout.md")
    assert "Status: GO" in _read("summaries/phase16/phase16-closeout.md")
    assert "knowledge capture/search" in _read("summaries/phase16/phase16-retrospective.md")
    assert "Status: pass" in _read("_knowledge/management/phase16-cross-audit.md")
