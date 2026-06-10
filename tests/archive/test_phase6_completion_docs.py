from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase6_completion_is_recorded() -> None:
    root_index = _read("INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")

    for rel_path in [
        "plans/phase6-program-plan.md",
        "plans/phase6-wave1-execution-plan.md",
        "plans/phase6-wave1-task-specs.md",
        "plans/phase6-wave2-execution-plan.md",
        "plans/phase6-wave3-execution-plan.md",
        "tasks/done/P6-r0-phase-ratification-packet.yaml",
        "tasks/done/P6-g1-durable-governance-core.yaml",
        "tasks/done/P6-g2-discovery-templates-packet.yaml",
        "tasks/done/P6-g3-skill-federation-packet.yaml",
        "summaries/phase6-ratification-kickoff.md",
        "summaries/phase6-wave1-closeout.md",
        "summaries/phase6-wave2-closeout.md",
        "summaries/phase6-wave3-closeout.md",
        "summaries/phase6-closeout-retrospective.md",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path

    assert "phase6-closeout-retrospective.md" in root_index
    assert "phase6-wave3-closeout.md" in process_index
    assert "phase6-closeout-retrospective.md" in process_index
    assert "phase6-program-plan.md" in design_index
    assert "phase6-wave3-execution-plan.md" in design_index
    assert "phase6-wave1-execution-plan.md" in plans_readme
    assert "phase6-wave2-execution-plan.md" in plans_readme
    assert "phase6-wave3-execution-plan.md" in plans_readme
