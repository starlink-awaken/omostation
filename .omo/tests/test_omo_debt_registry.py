from __future__ import annotations

from pathlib import Path

import yaml


OMO_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(rel_path: str) -> dict:
    return yaml.safe_load((OMO_ROOT / rel_path).read_text(encoding="utf-8"))


def test_debt_registry_lists_seed_items_and_outputs() -> None:
    registry = _load_yaml("debt/registry.yaml")

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
        ".omo/debt/items/D2_CI_E2E.yaml",
        ".omo/debt/items/D3_EU_PRICING.yaml",
        ".omo/debt/items/SB_DECOMPOSITION.yaml",
        ".omo/debt/items/SB_UNTESTED_PKGS.yaml",
        ".omo/debt/items/SB_ORPHANED_TASKS.yaml",
        ".omo/debt/items/SB_ROOT_CLEANUP.yaml",
        ".omo/debt/items/SB_BRIDGE_FIX.yaml",
        ".omo/debt/items/SB_PROJECTS_YAML.yaml",
        ".omo/debt/items/SB_PHASE17_PLAN.yaml",
    ]


def test_debt_registry_campaign_and_reporting_refs_exist() -> None:
    registry = _load_yaml("debt/registry.yaml")

    assert (OMO_ROOT.parent / registry["campaign_ref"]).exists()
    assert (OMO_ROOT.parent / registry["reporting_ref"]).exists()


def test_seed_items_keep_refs_to_existing_governance_surfaces() -> None:
    item = _load_yaml("debt/items/SB_DECOMPOSITION.yaml")

    assert item["lifecycle_state"] == "resolved"
    assert item["gate_level"] == "none"
    assert ".omo/tasks/active/SHAREDBRAIN-FORMAL-DECISION.yaml" in item["evidence_refs"]
    assert ".omo/_knowledge/design/debt-cleanup-plan.md" in item["mitigation_refs"]
    assert "projects/SharedBrain" in item["affected_roots"]


def test_new_seed_items_stay_pointer_based() -> None:
    item = _load_yaml("debt/items/SB_UNTESTED_PKGS.yaml")

    assert item["weight"] == 0.15
    assert item["lifecycle_state"] == "scheduled"
    assert ".omo/_knowledge/design/debt-cleanup-plan.md" in item["evidence_refs"]
    assert ".omo/tasks/active/SHAREDBRAIN-FORMAL-DECISION.yaml" in item["mitigation_refs"]
    assert "projects/kairon" in item["affected_roots"]
