from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase10_wave2_is_recorded_as_history_after_phase10_completion() -> None:
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")
    tasks_readme = _read("tasks/README.md")
    wave2_plan = _read("plans/phase10-wave2-execution-plan.md")
    done_wave2_task = _read("tasks/done/P10-W2-NORMALIZED-RULE-BUNDLE.yaml")
    done_task = _read("tasks/done/P10-W1-CROSS-ROOT-RULE-REGISTRY.yaml")

    assert "phase10_status: completed" in system
    assert "phase10_completed_at:" in system

    assert "typed delivery contract" in wave2_plan
    assert "Normalize the cross-root bundle" in wave2_plan
    assert "status: done" in done_wave2_task
    assert ".omo/plans/phase10-wave2-execution-plan.md" in done_wave2_task
    assert "status: done" in done_task

    assert "phase10-wave2-execution-plan.md" in root_index
    assert "phase10-wave2-execution-plan.md" in design_index
    assert "phase10-wave2-execution-plan.md" in plans_readme
    assert "Phase 10 已完成" in tasks_readme
