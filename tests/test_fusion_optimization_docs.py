from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_fusion_optimization_blueprint_covers_strategy_tactics_and_execution():
    text = _read("plans/omo-fusion-optimization-blueprint.md")

    assert "# OMO fusion optimization blueprint" in text
    assert "## Strategic upgrades" in text
    assert "## Tactical operating model" in text
    assert "## Execution loop" in text
    assert "## Verification model" in text
    assert "_control" in text and "_truth" in text and "_knowledge" in text and "_delivery" in text


def test_meta_retrospective_covers_mechanism_and_phase1_to_phase3():
    text = _read("summaries/omo-mechanism-and-phase1-3-retrospective.md")

    assert "# OMO mechanism and Phase 1-3 retrospective" in text
    assert "## Mechanism retrospective" in text
    assert "## Phase 1 retrospective" in text
    assert "## Phase 2 retrospective" in text
    assert "## Phase 3 retrospective" in text
    assert "## Next evolution priorities" in text


def test_index_links_blueprint_and_meta_retrospective():
    index_text = _read("INDEX.md")
    process_text = _read("_knowledge/process/INDEX.md")
    design_text = _read("_knowledge/design/INDEX.md")

    assert "[omo-fusion-optimization-blueprint.md](plans/omo-fusion-optimization-blueprint.md)" in index_text
    assert "[omo-mechanism-and-phase1-3-retrospective.md](../../summaries/omo-mechanism-and-phase1-3-retrospective.md)" in process_text
    assert "[omo-fusion-optimization-blueprint.md](../../plans/omo-fusion-optimization-blueprint.md)" in design_text


def test_convergence_audit_is_indexed_and_live_indexes_do_not_copy_stale_counts():
    audit_text = _read("_knowledge/management/omo-convergence-audit-2026-05-31.md")
    index_text = _read("INDEX.md")
    control_text = _read("_control/INDEX.md")
    management_text = _read("_knowledge/management/INDEX.md")
    doc_arch_text = _read("DOC-ARCH.md")
    requirements_text = _read("_knowledge/design/task-center-requirements.md")

    assert "# OMO convergence audit" in audit_text
    assert "[omo-convergence-audit-2026-05-31.md](_knowledge/management/omo-convergence-audit-2026-05-31.md)" in index_text
    assert "[omo-convergence-audit-2026-05-31.md](omo-convergence-audit-2026-05-31.md)" in management_text
    assert "**活跃任务**: 4" not in index_text
    assert "**活跃任务**: 4" not in control_text
    assert "plane-native domain" in doc_arch_text
    assert "secret_ref" in requirements_text
    assert "secret: <SHA256-HMAC-SECRET>" not in requirements_text
    assert "deliver: local                  # local | notify" in requirements_text
