from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase8_completion_is_recorded_with_retrospective_and_review() -> None:
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    control_index = _read("_control/INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")

    assert "phase8_status: completed" in system
    assert "active_tasks:" in system

    for rel_path in [
        "plans/phase8-wave3-execution-plan.md",
        "summaries/phase8-wave3-closeout.md",
        "summaries/phase8-closeout-retrospective.md",
        "summaries/phase8-review.md",
        "tasks/done/P8-w3-cross-repo-governance.yaml",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path
    assert "phase8-closeout-retrospective.md" in root_index
    assert "phase8-closeout-retrospective.md" in root_index
    assert "phase10-program-plan.md" in control_index
    assert "phase8-wave3-closeout.md" in process_index
    assert "phase8-review.md" in process_index
    assert "phase8-wave3-execution-plan.md" in design_index
    assert "phase8-wave3-execution-plan.md" in plans_readme
