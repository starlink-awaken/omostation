from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase11_wave1_kickoff_is_preserved_as_history() -> None:
    goals = _read("goals/current.yaml")
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    control_index = _read("_control/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")
    plans_readme = _read("plans/README.md")
    tasks_readme = _read("tasks/README.md")
    program_plan = _read("plans/phase11-program-plan.md")
    wave1_plan = _read("plans/phase11-wave1-execution-plan.md")
    closeout = _read("summaries/phase11-wave1-closeout.md")
    archived_task_path = OMO_ROOT / "tasks/done/P11-W1-SSOT-BASELINE.yaml"

    assert "phase: 16" in goals
    assert "status: completed" in goals
    assert "P16-W4-ADOPTION-CLOSEOUT" in goals

    assert "current_phase: 16" in system
    assert "current_wave: null" in system
    assert "phase_status: completed" in system
    assert "phase11_status: completed" in system
    assert "phase15_status: completed" in system
    assert "phase16_status: completed" in system
    assert "phase10_status: completed" in system

    assert "Status: completed" in program_plan
    assert "Status: completed" in wave1_plan
    assert "SSOT repair + baseline inventory" in wave1_plan

    assert archived_task_path.exists()
    archived_task = archived_task_path.read_text(encoding="utf-8")
    assert "status: done" in archived_task
    assert ".omo/summaries/phase11-wave1-closeout.md" in archived_task
    assert "completed_at:" in archived_task
    assert "Wave 1 is closed" in closeout

    assert "phase11-program-plan.md" in root_index
    assert "phase11-wave1-closeout.md" in root_index
    assert "phase11-program-plan.md" in control_index
    assert "phase11-wave1-execution-plan.md" in design_index
    assert "phase11-wave2-execution-plan.md" in design_index
    assert "phase11-wave3-execution-plan.md" in design_index
    assert "phase11-wave1-closeout.md" in process_index
    assert "phase11-program-plan.md" in plans_readme
    assert "phase11-wave1-execution-plan.md" in plans_readme
    assert "P11-W4-EVOLUTION-BRIDGE" in tasks_readme
    assert "P14-W4-ECOSYSTEM-PREVIEW" in tasks_readme
