"""Tests for ``./omo/debt/registry.yaml`` using a fixture-backed .omo."""

from __future__ import annotations

from pathlib import Path

import yaml
from omo.omo_debt_registry import load_debt_ledger

# ── helpers ─────────────────────────────────────────────────────────────────


def _load_yaml(omo_test_dir: Path, rel_path: str) -> dict:
    """Load YAML from ``omo_test_dir / rel_path``."""
    return yaml.safe_load((omo_test_dir / rel_path).read_text(encoding="utf-8"))


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


def test_load_debt_ledger_accepts_multi_document_truth_registry(tmp_path: Path) -> None:
    omo_dir = tmp_path / ".omo"
    (omo_dir / "_truth" / "registry").mkdir(parents=True, exist_ok=True)
    (omo_dir / "debt" / "items").mkdir(parents=True, exist_ok=True)
    (omo_dir / "_truth" / "registry" / "debt.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "dashboard_ref: .omo/debt/dashboard/current.yaml\n"
        "review_pack_ref: .omo/debt/reviews/current.md\n"
        "review_queue_ref: .omo/debt/review-queue/current.yaml\n"
        "action_packet_ref: .omo/debt/action-packet/current.yaml\n"
        "owner_routing_ref: .omo/debt/owner-routing/current.yaml\n"
        "dispatch_ref: .omo/debt/dispatch/current.yaml\n"
        "campaign_ref: .omo/debt/campaign/current.yaml\n"
        "reporting_ref: .omo/debt/reporting/current.yaml\n"
        "seed_items:\n"
        "  - .omo/debt/items/DEBT-1.yaml\n",
        encoding="utf-8",
    )
    (omo_dir / "debt" / "items" / "DEBT-1.yaml").write_text(
        "---\nstatus: active\n---\n---\n"
        "id: DEBT-1\n"
        "title: test debt\n"
        "dimension: governance\n"
        "subdimension: boundary\n"
        "domain: workspace\n"
        "scope: cross_project\n"
        "severity: medium\n"
        "weight: 0.3\n"
        "entropy_class: pointer\n"
        "lifecycle_state: identified\n"
        "owner: platform-governance\n"
        "affected_roots:\n"
        "  - projects/omo\n"
        "evidence_refs: []\n"
        "mitigation_refs: []\n"
        "opened_at: 2026-06-01T00:00:00Z\n"
        "last_reviewed_at: null\n"
        "next_review_at: null\n"
        "gate_level: none\n"
        "history: []\n",
        encoding="utf-8",
    )

    ledger = load_debt_ledger(omo_dir)

    assert ledger.registry_ref == ".omo/_truth/registry/debt.yaml"
    assert [item.id for item in ledger.items] == ["DEBT-1"]
