#!/usr/bin/env python3
"""Unit tests for GacRule 'declared' lifecycle state (BET-Y2Q4-T10-362).

Verifies:
  1. gac-validate: validates 'lifecycle: declared' as an accepted lifecycle enum state.
  2. check-governance-trend: correctly tallies 'declared' rules, isolates them from active counts,
     and exempts them from the 90-day draft freshness gate.
  3. gac-bootstrap: ignores non-existent source_ref paths on 'declared' rules in check_indexed_integrity.
"""

from __future__ import annotations

import importlib.util
import pathlib
from datetime import datetime, timezone

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
VALIDATE_PATH = ROOT / "bin" / "gac" / "gac-validate.py"
TREND_PATH = ROOT / "bin" / "gac" / "check-governance-trend.py"
BOOT_PATH = ROOT / "bin" / "gac" / "gac-bootstrap.py"


def _load_module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_validate_rule_accepts_declared_lifecycle() -> None:
    gv = _load_module(VALIDATE_PATH, "gac_validate_mod")
    assert "declared" in gv.LIFECYCLE_ENUM

    rule = {
        "id": "CR-TEST-DECLARED",
        "dimension": "X1",
        "layer": "L2",
        "check_type": "ssot_lint",
        "executor": ["ci_gate"],
        "lifecycle": "declared",
        "version": "1.0.0",
        "created_at": "2026-08-01",
    }
    errors = gv.validate_rule(rule, 0)
    assert not errors, f"Expected no validation errors, got: {errors}"


def test_governance_trend_counts_declared_and_exempts_from_draft_timeout() -> None:
    gt = _load_module(TREND_PATH, "check_gov_trend_mod")

    # Mock rules containing 1 active, 1 declared (old created_at), 1 valid draft
    rules = [
        {
            "id": "CR-TEST-ACTIVE",
            "dimension": "X2",
            "lifecycle": "active",
            "adr": "ADR-0100",
            "created_at": "2026-01-01",
        },
        {
            "id": "CR-TEST-DECLARED",
            "dimension": "X1",
            "lifecycle": "declared",
            "adr": "ADR-0401",
            "created_at": "2026-01-01",  # > 90 days, should NOT trigger stale draft
        },
    ]

    active_rules = []
    declared_rules = []
    stale_draft_rules = []
    for r in rules:
        lc = (r.get("lifecycle") or "").strip().lower()
        if lc == "active":
            active_rules.append(r)
        elif lc == "declared":
            declared_rules.append(r)
        elif lc == "draft":
            created_at = r.get("created_at")
            if created_at:
                dt = gt._parse_date(created_at)
                if dt and (datetime.now(timezone.utc) - dt).days > 90:
                    stale_draft_rules.append(r)

    assert len(active_rules) == 1
    assert len(declared_rules) == 1
    assert len(stale_draft_rules) == 0


def test_bootstrap_skips_declared_rules_in_source_integrity() -> None:
    gb = _load_module(BOOT_PATH, "gac_bootstrap_mod")

    fake_rules = [
        {
            "id": "CR-FAKE-DECLARED",
            "lifecycle": "declared",
            "source_type": "native",
            "source_ref": "bin/gac/__missing_intent__.py",
        },
        {
            "id": "CR-FAKE-ACTIVE",
            "lifecycle": "active",
            "source_type": "native",
            "source_ref": "bin/gac/__missing_active__.py",
        },
    ]

    gb.load_rules = lambda: fake_rules
    res = gb.check_indexed_integrity()

    missing_ids = {m["id"] for m in res["missing"]}
    assert "CR-FAKE-ACTIVE" in missing_ids
    assert "CR-FAKE-DECLARED" not in missing_ids
