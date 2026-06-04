from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase7_planning_gate_remains_recorded_as_historical_artifact() -> None:
    root_index = _read("INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")

    for rel_path in [
        "plans/phase7-planning-gate.md",
        "plans/phase7-program-plan.md",
        "plans/phase7-starter-packet-spec.md",
        "tasks/done/P7-r0-phase7-planning-gate.yaml",
        "summaries/phase7-planning-ratification.md",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path

    assert "phase7-planning-gate.md" in root_index
    assert "phase7-program-plan.md" in root_index
    assert "phase7-planning-ratification.md" in root_index
    assert "phase7-planning-ratification.md" in process_index
    assert "phase7-program-plan.md" in design_index
    assert "phase7-planning-gate.md" in plans_readme
    assert "phase7-starter-packet-spec.md" in plans_readme
