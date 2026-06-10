from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase6_ratification_is_recorded() -> None:
    root_index = _read("INDEX.md")
    _read("_control/INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")

    for rel_path in [
        "plans/phase6-program-plan.md",
        "plans/phase6-wave1-execution-plan.md",
        "plans/phase6-wave1-task-specs.md",
        "tasks/done/P6-r0-phase-ratification-packet.yaml",
        "summaries/phase6-ratification-kickoff.md",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path

    assert "phase6-program-plan.md" in root_index
    assert "phase6-wave1-execution-plan.md" in root_index
    assert "phase6-wave1-task-specs.md" in root_index
    assert "phase6-ratification-kickoff.md" in process_index
    assert "phase6-program-plan.md" in design_index
    assert "phase6-wave1-execution-plan.md" in design_index
    assert "phase6-wave1-task-specs.md" in plans_readme
