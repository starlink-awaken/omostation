from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase10_wave1_kickoff_is_recorded_as_history() -> None:
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")
    tasks_readme = _read("tasks/README.md")
    program_plan = _read("plans/phase10-program-plan.md")
    wave1_plan = _read("plans/phase10-wave1-execution-plan.md")
    done_task = _read("tasks/done/P10-W1-CROSS-ROOT-RULE-REGISTRY.yaml")

    assert "phase10_status: completed" in system
    assert "phase10_completed_at:" in system

    assert "cross-root operating rule unification" in program_plan
    assert "cross-root rule registry" in wave1_plan
    assert "status: done" in done_task
    assert ".omo/plans/phase10-wave1-execution-plan.md" in done_task

    assert "phase10-program-plan.md" in root_index
    assert "phase10-wave1-execution-plan.md" in root_index
    assert "phase10-wave1-execution-plan.md" in design_index
    assert "phase10-program-plan.md" in plans_readme
    assert "Phase 10 已完成" in tasks_readme
