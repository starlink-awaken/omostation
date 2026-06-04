from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase8_wave2_closeout_remains_recorded_as_historical_baseline() -> None:
    root_index = _read("INDEX.md")
    control_index = _read("_control/INDEX.md")
    process_index = _read("_knowledge/process/INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")

    for rel_path in [
        "plans/phase8-wave2-execution-plan.md",
        "summaries/phase8-wave2-closeout.md",
        "tasks/done/P8-w2-hermes-storage-convergence.yaml",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path

    assert "phase8-wave2-closeout.md" in root_index
    assert "phase8-wave2-closeout.md" in control_index
    assert "phase8-wave2-closeout.md" in process_index
    assert "phase8-wave2-execution-plan.md" in design_index
    assert "phase8-wave2-execution-plan.md" in plans_readme
