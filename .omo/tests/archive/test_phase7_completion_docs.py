from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase7_completion_remains_recorded_as_historical_baseline() -> None:
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    control_index = _read("_control/INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")

    assert "phase7_status: completed" in system
    assert "orphaned_tasks:" not in system

    for rel_path in [
        "plans/phase7-planning-gate.md",
        "plans/phase7-program-plan.md",
        "plans/phase7-starter-packet-spec.md",
        "plans/phase7-wave1-execution-plan.md",
        "plans/phase7-wave2-execution-plan.md",
        "plans/phase7-wave3-execution-plan.md",
        "summaries/phase7-planning-ratification.md",
        "summaries/phase7-wave1-closeout.md",
        "summaries/phase7-wave2-closeout.md",
        "summaries/phase7-wave3-closeout.md",
        "summaries/phase7-closeout-retrospective.md",
        "tasks/done/P7-w1-user-journey-enablement.yaml",
        "tasks/done/P7-w2-resource-accounting-visibility.yaml",
        "tasks/done/P7-w3-freshness-entropy-automation.yaml",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path

    assert "phase7-closeout-retrospective.md" in root_index
    assert "phase10-program-plan.md" in control_index
    assert "phase7-wave3-execution-plan.md" in design_index
    assert "phase7-wave3-closeout.md" in process_index
    assert "phase7-wave3-execution-plan.md" in plans_readme


def test_phase7_planning_gate_remains_as_historical_artifact() -> None:
    assert (OMO_ROOT / "plans/phase7-planning-gate.md").exists()
    assert (OMO_ROOT / "summaries/phase7-planning-ratification.md").exists()
