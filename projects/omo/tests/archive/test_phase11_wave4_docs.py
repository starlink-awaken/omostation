from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase11_wave4_is_preserved_after_phase16_completion() -> None:
    goals = _read("goals/current.yaml")
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    control_index = _read("_control/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")
    plans_readme = _read("plans/README.md")
    tasks_readme = _read("tasks/README.md")
    program_plan = _read("plans/phase11-program-plan.md")
    wave4_plan = _read("plans/phase11-wave4-execution-plan.md")
    wave4_review = _read("workers/runs/phase11-wave4-evolution-bridge-review.md")
    wave4_closeout = _read("summaries/phase11-wave4-closeout.md")
    retrospective = _read("summaries/phase11-retrospective.md")
    done_task_path = OMO_ROOT / "tasks/done/P11-W4-EVOLUTION-BRIDGE.yaml"
    run_dir = OMO_ROOT / "workers/runs"

    assert "phase: 16" in goals
    assert "status: completed" in goals
    assert "P16-W4-ADOPTION-CLOSEOUT" in goals

    assert "current_phase: 16" in system
    assert "current_wave: null" in system
    assert "phase_status: completed" in system
    assert "phase11_status: completed" in system
    assert "phase15_status: completed" in system
    assert "phase16_status: completed" in system

    assert "Status: completed" in program_plan
    assert "Status: completed" in wave4_plan
    assert "Deep hardening + evolution alignment" in wave4_plan
    assert "| T4.2 | completed |" in wave4_plan
    assert "TestPyPI publish succeeded" in wave4_plan
    assert "PyPI publish succeeded" in wave4_plan
    assert "pip install kairon==0.1.0" in wave4_plan

    assert "T4.2 — **completed**" in wave4_review
    assert "TestPyPI publish workflow succeeded" in wave4_review
    assert "PyPI publish workflow succeeded" in wave4_review
    assert "pip install kairon==0.1.0" in wave4_review

    assert "TestPyPI publish" in wave4_closeout
    assert "PyPI publish" in wave4_closeout
    assert "pip install kairon==0.1.0" in wave4_closeout
    assert "Public `pip install kairon` is now verified" in wave4_closeout

    assert "trusted publishing" in retrospective
    assert "TestPyPI and PyPI release path is now real" in retrospective

    assert done_task_path.exists()
    done_task = done_task_path.read_text(encoding="utf-8")
    assert "phase: 11" in done_task
    assert "P11-W4-EVOLUTION-BRIDGE" in done_task
    assert ".omo/plans/phase11-wave4-execution-plan.md" in done_task
    assert "status: done" in done_task

    assert any(run_dir.glob("phase11-wave4-evolution-bridge-*.md"))

    assert "phase11-program-plan.md" in root_index
    assert "phase11-wave4-execution-plan.md" in root_index
    assert "phase11-program-plan.md" in control_index
    assert "phase11-wave4-closeout.md" in control_index
    assert "phase11-program-plan.md" in design_index
    assert "phase11-wave4-execution-plan.md" in design_index
    assert "phase11-wave3-closeout.md" in process_index
    assert "phase11-wave4-closeout.md" in process_index
    assert "phase11-program-plan.md" in plans_readme
    assert "phase11-wave4-execution-plan.md" in plans_readme
    assert "P11-W4-EVOLUTION-BRIDGE" in tasks_readme
