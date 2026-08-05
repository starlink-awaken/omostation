"""ADR-0374 G4: convergence_provenance symmetry detector tests.

Covers the bilateral link requirement between parent (supercedes) and
child (superseded_by) in governance-evolution-roadmap initiatives.
Locks the behavior of `_collect_convergence_provenance_errors` so
future refactors don't break the symmetry contract.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "governance-evolution.py"


def _load_governance_evolution():
    """Late-bind import so a stale .pyc never shadows the live script."""
    spec = importlib.util.spec_from_file_location("ge_test_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ge():
    return _load_governance_evolution()


def _seen(initiative_ids: list[str]) -> set[str]:
    return set(initiative_ids)


def test_bilateral_link_passes(ge) -> None:
    """G4 happy path: parent↔child both sides declared → no errors."""
    initiatives = [
        {
            "id": "sweep-tooling-scaling",
            "convergence_provenance": {"superseded_by": "sweep-tooling-convergence"},
        },
        {
            "id": "sweep-tooling-convergence",
            "convergence_provenance": {"supersedes": "sweep-tooling-scaling"},
        },
    ]
    errors = ge._collect_convergence_provenance_errors(
        _seen(["sweep-tooling-scaling", "sweep-tooling-convergence"]), initiatives
    )
    assert errors == []


def test_orphan_supersedes_fails(ge) -> None:
    """G4: child declares supersedes=parent, but parent has no superseded_by."""
    initiatives = [
        {
            "id": "round-1",
            "convergence_provenance": {"supersedes": "round-0"},
        },
        {
            "id": "round-0",
            # parent has NO convergence_provenance
        },
    ]
    errors = ge._collect_convergence_provenance_errors(_seen(["round-1", "round-0"]), initiatives)
    assert any("supersedes=round-0" in e and "no superseded_by" in e for e in errors)


def test_orphan_superseded_by_fails(ge) -> None:
    """G4: child declares superseded_by=parent, but parent has no supersedes."""
    initiatives = [
        {
            "id": "round-0",
        },
        {
            "id": "round-1",
            "convergence_provenance": {"superseded_by": "round-0"},
        },
    ]
    errors = ge._collect_convergence_provenance_errors(_seen(["round-0", "round-1"]), initiatives)
    assert any("superseded_by=round-0" in e and "no supersedes" in e for e in errors)


def test_supersedes_parent_missing_in_seen_ids(ge) -> None:
    """G4: child points to a parent id not declared as an initiative at all."""
    initiatives = [
        {
            "id": "round-future",
            "convergence_provenance": {"supersedes": "round-ghost"},
        },
    ]
    errors = ge._collect_convergence_provenance_errors(_seen(["round-future"]), initiatives)
    assert any("supersedes=round-ghost" in e and "not found" in e for e in errors)


def test_non_dict_initiative_is_skipped(ge) -> None:
    """G4: garbage entries in the list don't crash the validator."""
    initiatives = [
        "not a dict",
        None,
        {
            "id": "valid",
            "convergence_provenance": {"supersedes": "other"},
        },
    ]
    # 'valid' → 'other' but 'other' missing → 1 error from supersedes; 'other' missing
    # from seen_ids → another error. Garbage rows must not crash.
    errors = ge._collect_convergence_provenance_errors(_seen(["valid"]), initiatives)
    assert all(isinstance(e, str) for e in errors)


def test_bad_provenance_shape_does_not_crash(ge) -> None:
    """G4: convergence_provenance not a mapping → skip, no error raised."""
    initiatives = [
        {
            "id": "x",
            "convergence_provenance": "not a mapping",
        },
        {
            "id": "y",
            "convergence_provenance": None,
        },
    ]
    errors = ge._collect_convergence_provenance_errors(_seen(["x", "y"]), initiatives)
    assert errors == []


def test_no_provenance_yields_no_errors(ge) -> None:
    """G4: missing convergence_provenance field on every entry → 0 errors."""
    initiatives = [
        {"id": "a"},
        {"id": "b"},
    ]
    errors = ge._collect_convergence_provenance_errors(_seen(["a", "b"]), initiatives)
    assert errors == []


def test_chain_three_rounds(ge) -> None:
    """G4: 3-round chain A→B→C with bilateral links passes."""
    initiatives = [
        {"id": "a", "convergence_provenance": {"superseded_by": "b"}},
        {
            "id": "b",
            "convergence_provenance": {
                "supersedes": "a",
                "superseded_by": "c",
            },
        },
        {"id": "c", "convergence_provenance": {"supersedes": "b"}},
    ]
    errors = ge._collect_convergence_provenance_errors(_seen(["a", "b", "c"]), initiatives)
    assert errors == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
