"""Tests for ``./omo/debt/registry.yaml`` using a fixture-backed .omo."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


# ── helpers ─────────────────────────────────────────────────────────────────


def _load_yaml(omo_test_dir: Path, rel_path: str) -> dict:
    """Load YAML from ``omo_test_dir / rel_path``."""
    return yaml.safe_load(
        (omo_test_dir / rel_path).read_text(encoding="utf-8")
    )


# ── tests ───────────────────────────────────────────────────────────────────


def test_debt_registry_lists_seed_items_and_outputs(omo_test_dir: Path) -> None:
    """Verify the debt registry has all expected fields."""
    registry = _load_yaml(omo_test_dir, ".omo/debt/registry.yaml")

    assert registry["version"] == 1
    assert registry["items_dir"] == ".omo/debt/items"
    assert registry["dashboard_ref"] == ".omo/debt/dashboard/current.yaml"
    assert registry["review_pack_ref"] == ".omo/debt/reviews/current.md"
    assert registry["review_queue_ref"] == ".omo/debt/review-queue/current.yaml"
    assert registry["action_packet_ref"] == ".omo/debt/action-packet/current.yaml"
    assert registry["owner_routing_ref"] == ".omo/debt/owner-routing/current.yaml"
    assert registry["dispatch_ref"] == ".omo/debt/dispatch/current.yaml"
    assert registry["campaign_ref"] == ".omo/debt/campaign/current.yaml"
    assert registry["reporting_ref"] == ".omo/debt/reporting/current.yaml"
    assert registry["seed_items"] == [
        ".omo/debt/items/DEBT-TEST-001.yaml",
        ".omo/debt/items/DEBT-TEST-002.yaml",
        ".omo/debt/items/DEBT-TEST-003.yaml",
    ]


def test_debt_registry_campaign_and_reporting_refs_exist(
    omo_test_dir: Path,
) -> None:
    """Campaign and reporting placeholder files exist on disk."""
    registry = _load_yaml(omo_test_dir, ".omo/debt/registry.yaml")

    assert (omo_test_dir / registry["campaign_ref"]).exists()
    assert (omo_test_dir / registry["reporting_ref"]).exists()


def test_seed_items_keep_refs_to_existing_governance_surfaces(
    omo_test_dir: Path,
) -> None:
    """Inspect DEBT-TEST-002 (the richest synthetic item)."""
    item = _load_yaml(omo_test_dir, ".omo/debt/items/DEBT-TEST-002.yaml")

    assert item["lifecycle_state"] == "scheduled"
    assert item["gate_level"] == "none"
    assert ".omo/tasks/active/TEST-DECISION.yaml" in item["evidence_refs"]
    assert ".omo/_knowledge/design/test-plan.md" in item["mitigation_refs"]
    assert "scripts" in item["affected_roots"]


def test_new_seed_items_stay_pointer_based(omo_test_dir: Path) -> None:
    """Inspect DEBT-TEST-001 (the simplest synthetic item)."""
    item = _load_yaml(omo_test_dir, ".omo/debt/items/DEBT-TEST-001.yaml")

    assert item["weight"] == 0.05
    assert item["lifecycle_state"] == "deferred"
    assert item["x1_policy_ref"] == "X1-AUDIT-001"
    assert item["x2_freshness"] == "2026-06-05T06:00:00Z"
    assert item["x3_tier"] == "Framework"
