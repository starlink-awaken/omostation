from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
OMO_ROOT = REPO_ROOT / ".omo"


def _read_yaml(rel_path: str) -> dict:
    return yaml.safe_load((OMO_ROOT / rel_path).read_text(encoding="utf-8"))


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase13_metacognition_outputs_are_supervised_and_read_only() -> None:
    baseline = _read_yaml("evidence/phase13/metacognition-baseline.yaml")
    proposals = _read_yaml("evidence/phase13/bottleneck-proposals.yaml")
    collaboration = _read_yaml("evidence/phase13/supervised-collaboration.yaml")
    rehearsal = _read_yaml("evidence/phase13/self-healing-rehearsal.yaml")

    assert baseline["mode"] == "read-only"
    assert baseline["auto_apply"] == "disabled"
    assert baseline["capability_count"] >= 79
    assert len(baseline["blind_spots"]) >= 3
    assert "confidence" in baseline

    assert proposals["mode"] == "proposal-only"
    assert proposals["auto_apply"] == "disabled"
    assert len(proposals["proposals"]) == 3
    for proposal in proposals["proposals"]:
        assert proposal["evidence_refs"]
        assert proposal["rollback"]
        assert proposal["verification"]
        assert proposal["operation_level"] in {"L0", "L1", "L2", "L3"}

    assert collaboration["mode"] == "draft-only"
    assert collaboration["auto_execute"] == "disabled"
    assert collaboration["execution_envelope"]["may_create_active_task"] is False

    assert rehearsal["mode"] == "dry-run"
    assert rehearsal["auto_apply"] == "disabled"
    assert rehearsal["recommended_action"]["live_mutation_allowed"] is False
    assert rehearsal["result"] == "pass"


def test_phase13_closeout_and_tasks_are_recorded() -> None:
    closeout = _read("summaries/phase13-closeout.md")
    retrospective = _read("summaries/phase13-retrospective.md")
    plan = _read("plans/phase13-metacognition-preplanning.md")
    standard = _read("standards/mutation-proposal-envelope.md")

    assert "Status: GO" in closeout
    assert "Phase 13 is complete" in closeout
    assert "Phase 13 converted Phase 12 capability evidence" in retrospective
    assert "Status: completed" in plan
    assert "Auto-apply remains disabled by default" in plan
    assert "Proposal generation is not approval" in standard

    for task_id in [
        "P13-W1-READONLY-METACOGNITION",
        "P13-W2-BOTTLENECK-PROPOSALS",
        "P13-W3-SUPERVISED-COLLABORATION",
        "P13-W4-SELF-HEALING-REHEARSAL",
    ]:
        task_text = _read(f"tasks/done/{task_id}.yaml")
        assert "status: done" in task_text
        assert "phase: 13" in task_text


def test_phase13_remains_completed_after_phase16_completion_allowing_only_authorized_active_tasks() -> None:
    goals = _read_yaml("goals/current.yaml")
    state = _read_yaml("state/system.yaml")
    active_tasks = list((OMO_ROOT / "tasks" / "active").glob("*.yaml"))
    active_payloads = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in active_tasks]
    stale_active = [
        task for task in active_payloads
        if task.get("phase", 0) <= goals["phase"]
    ]
    unauthorized_active = [task["id"] for task in active_payloads if task.get("status") == "pending"]

    assert goals["phase"] == 16
    assert goals["status"] == "completed"
    assert state["current_phase"] == 16
    assert state["phase_status"] == "completed"
    assert state["phase13_status"] == "completed"
    assert state["phase14_status"] == "completed"
    assert state["phase15_status"] == "completed"
    assert state["phase16_status"] == "completed"
    assert state["active_tasks"] == len(active_tasks)
    assert stale_active == [], f"Unexpected non-future active tasks: {stale_active}"
    assert unauthorized_active == [], f"Unexpected non-authorized active tasks: {unauthorized_active}"
