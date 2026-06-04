from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OMO_ROOT = REPO_ROOT / ".omo"


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_architecture_baseline_registers_canonical_framework_and_boundaries() -> None:
    baseline = _read("_knowledge/design/system-design-baseline.md")

    assert "# OMO system design baseline" in baseline
    assert "OMO Baseline Framework (4P3V1L)" in baseline
    assert "P0 here means the product / user entry layer" in baseline
    assert "phase14-deferred-ecosystem-backlog.md" in baseline
    assert "The deferred-scope ledger remains" in baseline
    assert "Phase 15 — governance operating loop consolidation" in baseline
    assert "Phase 16 — product surface convergence" in baseline
    assert "Phase 17+" in baseline


def test_phase15_and_phase16_docs_preserve_sequence_and_non_goals() -> None:
    phase15 = _read("plans/phase15-autonomous-governance-preplanning.md")
    phase15_design = _read("_knowledge/design/phase15-autonomous-governance-design.md")
    phase16 = _read("plans/phase16-product-surface-convergence-preplanning.md")

    assert "system-design-baseline.md" in phase15
    assert "No P0 surface work during Phase 15." in phase15
    assert "P15-W1-EVIDENCE-LEDGER" in phase15
    assert "P15-W4-RECOVERY-DASHBOARD" in phase15

    assert "system-design-baseline.md" in phase15_design
    assert "Compilation is not activation." in phase15_design
    assert "Phase 15 does not deliver P0 product-surface convergence." in phase15_design

    assert "Status: completed" in phase16
    assert "Entry gate: Phase 15 closeout GO + explicit human approval" in phase16
    assert "P16-W1-JOURNEY-BASELINE" in phase16
    assert "Knowledge Capture/Search Product Surface Convergence" in phase16
    assert "knowledge-capture-search" in phase16


def test_indexes_and_plan_registry_include_baseline_and_phase16() -> None:
    root_index = _read("INDEX.md")
    design_index = _read("_knowledge/design/INDEX.md")
    plans_readme = _read("plans/README.md")

    assert "system-design-baseline.md" in root_index
    assert "system-design-baseline.md" in design_index
    assert "system-design-baseline.md" in plans_readme
    assert "phase16-product-surface-convergence-preplanning" in root_index
    assert "phase16-product-surface-convergence-preplanning" in design_index
    assert "phase16-product-surface-convergence-preplanning" in plans_readme
