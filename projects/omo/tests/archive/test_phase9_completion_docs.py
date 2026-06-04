from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase9_completion_is_recorded_with_wave4_closeout_and_retrospective() -> None:
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")
    tasks_readme = _read("tasks/README.md")
    program_plan = _read("plans/phase9-program-plan.md")

    assert "phase9_status: completed" in system
    assert "phase9_completed_at:" in system

    for rel_path in [
        "plans/phase9-wave4-execution-plan.md",
        "summaries/phase9-wave4-closeout.md",
        "summaries/phase9-closeout-retrospective.md",
        "tasks/done/P9-W4-ROLLOUT-OPS-CLOSEOUT.yaml",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path
    assert "phase9-wave4-closeout.md" in root_index
    assert "phase9-closeout-retrospective.md" in root_index
    assert "phase9-closeout-retrospective.md" in root_index
    assert "phase9-wave4-closeout.md" in process_index
    assert "phase9-closeout-retrospective.md" in process_index
    assert "phase9-wave4-execution-plan.md" in design_index
    assert "phase9-wave4-execution-plan.md" in plans_readme
    assert "Phase 9 已完成" in tasks_readme
    assert "Wave 4" in program_plan
