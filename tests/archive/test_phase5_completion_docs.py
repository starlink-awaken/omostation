from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase5_completion_is_recorded() -> None:
    system = _read("state/system.yaml")
    root_index = _read("INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")
    plans_readme = _read("plans/README.md")

    assert "phase5_status: completed" in system

    for rel_path in [
        "plans/phase5-wave1-execution-plan.md",
        "plans/phase5-wave2-execution-plan.md",
        "plans/phase5-wave3-execution-plan.md",
        "tasks/done/P5-w1-runtime-governance-packet.yaml",
        "tasks/done/P5-w2-discovery-template-packet.yaml",
        "tasks/done/P5-w3-skill-federation-packet.yaml",
        "summaries/phase5-wave1-retrospective.md",
        "summaries/phase5-wave2-retrospective.md",
        "summaries/phase5-wave3-retrospective.md",
        "summaries/phase5-closeout-retrospective.md",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path

    assert "phase5-closeout-retrospective.md" in root_index
    assert "phase5-wave3-retrospective.md" in process_index
    assert "phase5-closeout-retrospective.md" in process_index
    assert "phase5-wave1-execution-plan.md" in plans_readme
    assert "phase5-wave2-execution-plan.md" in plans_readme
    assert "phase5-wave3-execution-plan.md" in plans_readme
