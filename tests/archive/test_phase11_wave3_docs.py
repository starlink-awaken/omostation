from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase11_wave3_is_recorded_as_history_after_phase16_completion() -> None:
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")
    tasks_readme = _read("tasks/README.md")
    wave3_plan = _read("plans/phase11-wave3-execution-plan.md")
    done_wave3_task = _read("tasks/done/P11-W3-USER-MVP.yaml")

    assert "current_phase: 16" in system
    assert "current_wave: null" in system
    assert "phase_status: completed" in system
    assert "phase11_status: completed" in system
    assert "phase15_status: completed" in system
    assert "phase16_status: completed" in system

    assert "Status: completed" in wave3_plan
    assert "User layer MVP" in wave3_plan
    assert "phase11-wave3-execution-plan.md" in root_index
    assert "phase11-program-plan.md" in design_index
    assert "phase11-wave3-execution-plan.md" in design_index
    assert "phase11-wave3-execution-plan.md" in plans_readme
    assert "status: done" in done_wave3_task
    assert ".omo/plans/phase11-wave3-execution-plan.md" in done_wave3_task
    assert "P11-W4-EVOLUTION-BRIDGE" in tasks_readme
    assert "P14-W4-ECOSYSTEM-PREVIEW" in tasks_readme
