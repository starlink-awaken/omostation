"""
``tests/fixtures/minimal_omo.py`` — generate a minimal .omo test directory.

This script creates an isolated ``.omo-test/`` directory under
``tests/fixtures/`` that mimics a real workspace layout:

::

    tests/fixtures/.omo-test/
    |-- .omo/
    |   |-- debt/
    |   |   |-- registry.yaml            ← debt ledger registry
    |   |   |-- items/DEBT-TEST-001.yaml  ← 3 synthetic debt items
    |   |   |-- items/DEBT-TEST-002.yaml
    |   |   |-- items/DEBT-TEST-003.yaml
    |   |   |-- dashboard/current.yaml
    |   |   |-- campaign/current.yaml
    |   |   |-- ... (other placeholder refs)
    |   |-- _truth/registry/debt.yaml    ← minimal truth registry

The ``omo_test_dir`` pytest fixture (defined in ``conftest.py``) returns the
path to ``.omo-test/`` (the workspace root).  Tests then resolve registry
refs like ``.omo/debt/items/...`` directly off that root.

Idempotent — safe to re-run any number of times.
"""

from __future__ import annotations

from pathlib import Path

import yaml

FIXTURE_DIR = Path(__file__).resolve().parent
OMO_TEST_DIR = FIXTURE_DIR / ".omo-test"
OMO_DIR = OMO_TEST_DIR / ".omo"  # the .omo/ inside the test workspace


# ── helper ──────────────────────────────────────────────────────────────────


def _write_yaml(rel_path: str, data: object) -> Path:
    """Write ``data`` as YAML under ``OMO_DIR / rel_path``."""
    full = OMO_DIR / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    )
    return full


# ── fixture data ────────────────────────────────────────────────────────────


def _registry() -> dict:
    """Return the content of ``.omo/debt/registry.yaml``."""
    return {
        "version": 1,
        "items_dir": ".omo/debt/items",
        "seed_items": [
            ".omo/debt/items/DEBT-TEST-001.yaml",
            ".omo/debt/items/DEBT-TEST-002.yaml",
            ".omo/debt/items/DEBT-TEST-003.yaml",
        ],
        "dashboard_ref": ".omo/debt/dashboard/current.yaml",
        "review_pack_ref": ".omo/debt/reviews/current.md",
        "review_queue_ref": ".omo/debt/review-queue/current.yaml",
        "action_packet_ref": ".omo/debt/action-packet/current.yaml",
        "owner_routing_ref": ".omo/debt/owner-routing/current.yaml",
        "dispatch_ref": ".omo/debt/dispatch/current.yaml",
        "campaign_ref": ".omo/debt/campaign/current.yaml",
        "reporting_ref": ".omo/debt/reporting/current.yaml",
    }


def _debt_item_001() -> dict:
    """DEBT-TEST-001 — a medium test-infrastructure item (Framework tier)."""
    return {
        "id": "DEBT-TEST-001",
        "title": "Test fixture debt item alpha",
        "dimension": "test-infrastructure",
        "subdimension": "fixtures",
        "domain": "workspace",
        "scope": "governance_kernel",
        "severity": "medium",
        "weight": 0.05,
        "entropy_class": "classification",
        "lifecycle_state": "deferred",
        "owner": "omo-engineer",
        "affected_roots": [".omo"],
        "evidence_refs": [],
        "mitigation_refs": [],
        "opened_at": "2026-06-01T00:00:00Z",
        "last_reviewed_at": None,
        "next_review_at": None,
        "gate_level": "none",
        "history": [
            {
                "at": "2026-06-01T00:00:00Z",
                "action": "register",
                "note": "Registered test item DEBT-TEST-001.",
            }
        ],
        "x1_policy_ref": "X1-AUDIT-001",
        "x2_freshness": "2026-06-05T06:00:00Z",
        "x3_tier": "Framework",
    }


def _debt_item_002() -> dict:
    """DEBT-TEST-002 — a high architecture item (Principle tier)."""
    return {
        "id": "DEBT-TEST-002",
        "title": "Test fixture debt item bravo",
        "dimension": "architecture",
        "subdimension": "consistency",
        "domain": "workspace",
        "scope": "governance_kernel",
        "severity": "high",
        "weight": 0.10,
        "entropy_class": "classification",
        "lifecycle_state": "scheduled",
        "owner": "omo-engineer",
        "affected_roots": [".omo", "scripts"],
        "evidence_refs": [".omo/tasks/active/TEST-DECISION.yaml"],
        "mitigation_refs": [".omo/_knowledge/design/test-plan.md"],
        "opened_at": "2026-06-02T00:00:00Z",
        "last_reviewed_at": "2026-06-03T00:00:00Z",
        "next_review_at": "2026-07-01T00:00:00Z",
        "gate_level": "none",
        "history": [
            {
                "at": "2026-06-02T00:00:00Z",
                "action": "register",
                "note": "Registered test item DEBT-TEST-002.",
            },
            {
                "at": "2026-06-03T00:00:00Z",
                "action": "review",
                "note": "Reviewed, scheduled for next sprint.",
            },
        ],
        "x1_policy_ref": "X1-AUDIT-002",
        "x2_freshness": "2026-06-05T06:00:00Z",
        "x3_tier": "Principle",
    }


def _debt_item_003() -> dict:
    """DEBT-TEST-003 — a low process item (Knowledge tier)."""
    return {
        "id": "DEBT-TEST-003",
        "title": "Test fixture debt item charlie",
        "dimension": "process",
        "subdimension": "documentation",
        "domain": "workspace",
        "scope": "governance_kernel",
        "severity": "low",
        "weight": 0.02,
        "entropy_class": "classification",
        "lifecycle_state": "open",
        "owner": "omo-engineer",
        "affected_roots": [".omo"],
        "evidence_refs": [],
        "mitigation_refs": [],
        "opened_at": "2026-06-04T00:00:00Z",
        "last_reviewed_at": None,
        "next_review_at": None,
        "gate_level": "none",
        "history": [
            {
                "at": "2026-06-04T00:00:00Z",
                "action": "register",
                "note": "Registered test item DEBT-TEST-003.",
            }
        ],
        "x1_policy_ref": "X1-AUDIT-003",
        "x2_freshness": "2026-06-05T06:00:00Z",
        "x3_tier": "Knowledge",
    }


def _truth_debt() -> dict:
    """Minimal ``_truth/registry/debt.yaml``."""
    return {
        "items": {},
        "seed_items": [
            ".omo/debt/items/DEBT-TEST-001.yaml",
            ".omo/debt/items/DEBT-TEST-002.yaml",
            ".omo/debt/items/DEBT-TEST-003.yaml",
        ],
        "dashboard_ref": ".omo/debt/dashboard/latest.yaml",
        "review_pack_ref": ".omo/debt/review/latest.yaml",
        "review_queue_ref": ".omo/debt/queue/latest.yaml",
        "action_packet_ref": ".omo/debt/action/latest.yaml",
        "owner_routing_ref": ".omo/debt/routing/latest.yaml",
        "dispatch_ref": ".omo/debt/dispatch/latest.yaml",
        "campaign_ref": ".omo/debt/campaign/latest.yaml",
        "reporting_ref": ".omo/debt/reporting/latest.yaml",
    }


# ── entry point ─────────────────────────────────────────────────────────────


def generate() -> Path:
    """Generate the full fixture tree under ``OMO_TEST_DIR``.

    Idempotent — overwrites existing files on each call.
    Returns the path to ``OMO_TEST_DIR`` (the workspace root containing
    ``.omo/``).
    """
    # -- scaffold directories ------------------------------------------------
    for sub in (
        ".omo/_control/governance-overlay",
        ".omo/_truth/governance-overlay",
        ".omo/_truth/registry",
        ".omo/debt/items",
        ".omo/debt/dashboard",
        ".omo/debt/reviews",
        ".omo/debt/review-queue",
        ".omo/debt/action-packet",
        ".omo/debt/owner-routing",
        ".omo/debt/dispatch",
        ".omo/debt/campaign",
        ".omo/debt/reporting",
    ):
        (OMO_TEST_DIR / sub).mkdir(parents=True, exist_ok=True)

    # -- debt registry -------------------------------------------------------
    _write_yaml("debt/registry.yaml", _registry())

    # -- debt items ----------------------------------------------------------
    _write_yaml("debt/items/DEBT-TEST-001.yaml", _debt_item_001())
    _write_yaml("debt/items/DEBT-TEST-002.yaml", _debt_item_002())
    _write_yaml("debt/items/DEBT-TEST-003.yaml", _debt_item_003())

    # -- truth registry ------------------------------------------------------
    _write_yaml("_truth/registry/debt.yaml", _truth_debt())

    # -- minimal placeholders for refs that tests check exist ----------------
    _write_yaml("debt/dashboard/current.yaml", {"dashboard": "placeholder"})
    OMO_DIR.joinpath("debt/reviews/current.md").write_text(
        "# Debt Reviews\n\nPlaceholder"
    )
    _write_yaml("debt/review-queue/current.yaml", {"queue": []})
    _write_yaml("debt/action-packet/current.yaml", {"actions": []})
    _write_yaml("debt/owner-routing/current.yaml", {"routes": []})
    _write_yaml("debt/dispatch/current.yaml", {"dispatches": []})
    _write_yaml("debt/campaign/current.yaml", {"campaigns": []})
    _write_yaml("debt/reporting/current.yaml", {"report": "placeholder"})

    return OMO_TEST_DIR


def clean() -> None:
    """Remove the entire generated fixture tree."""
    import shutil

    if OMO_TEST_DIR.is_dir():
        shutil.rmtree(OMO_TEST_DIR)


# ── CLI entry point ──────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean()
        print(f"Removed {OMO_TEST_DIR}")
    else:
        path = generate()
        print(f"Generated fixture workspace at {path}")
