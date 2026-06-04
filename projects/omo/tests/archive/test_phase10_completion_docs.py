from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase10_completion_is_recorded_with_wave4_closeout_and_retrospective() -> None:
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")
    tasks_readme = _read("tasks/README.md")
    program_plan = _read("plans/phase10-program-plan.md")

    assert "phase10_status: completed" in system
    assert "phase10_completed_at:" in system
    assert "phase11_entry_gate: phase10_completed" in system

    for rel_path in [
        "plans/phase10-wave4-execution-plan.md",
        "summaries/phase10-wave4-closeout.md",
        "summaries/phase10-closeout-retrospective.md",
        "tasks/done/P10-W3-ACTION-FIRST-MATRIX.yaml",
        "tasks/done/P10-W4-CROSS-SPACE-CLOSEOUT.yaml",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path

    assert "Wave 4 closes only after historical debt is moved out of current-phase assumptions" in program_plan
    assert "phase10-wave4-execution-plan.md" in root_index
    assert "phase10-wave4-closeout.md" in root_index
    assert "phase10-closeout-retrospective.md" in root_index
    assert "phase10-wave4-closeout.md" in process_index
    assert "phase10-closeout-retrospective.md" in process_index
    assert "phase10-wave4-execution-plan.md" in design_index
    assert "phase10-wave4-execution-plan.md" in plans_readme
    assert "Phase 10 已完成" in tasks_readme
