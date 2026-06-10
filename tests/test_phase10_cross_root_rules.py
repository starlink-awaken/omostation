from __future__ import annotations

from pathlib import Path

import yaml

from omo.omo_rules import evaluate_rule_bundle


ROOT = Path(__file__).resolve().parents[2]


def _read_yaml(rel_path: str) -> dict:
    return yaml.safe_load((ROOT / rel_path).read_text(encoding="utf-8"))


def test_phase10_rule_registry_is_linked_from_system_space_surfaces() -> None:
    system_space = _read_yaml("spaces/system-space.yaml")
    registry = _read_yaml("spaces/registry.yaml")
    system_entry = next(space for space in registry["spaces"] if space["id"] == "system-space")

    assert (ROOT / "spaces/system-space-cross-root-rule-registry.yaml").exists()
    assert (ROOT / "data/system-data-access-policy.yaml").exists()
    assert "spaces/system-space-cross-root-rule-registry.yaml" in system_space["policy_refs"]
    assert "spaces/system-space-cross-root-rule-registry.yaml" in system_entry["policy_refs"]
    assert "data/system-data-access-policy.yaml" in system_space["policy_refs"]
    assert "data/system-data-access-policy.yaml" in system_entry["policy_refs"]


def test_phase10_live_envelope_resolves_cross_root_rule_bundle() -> None:
    result = evaluate_rule_bundle(
        ROOT,
        Path(".omo/workers/runs/phase10-wave1-cross-root-rules-envelope.yaml"),
    )

    assert result == {
        "space_ref": "spaces/system-space.yaml",
        "membership_ref": "system-governor-membership",
        "action": "project.dispatch",
        "registry_ref": "spaces/system-space-cross-root-rule-registry.yaml",
        "data_policy_ref": "data/system-data-access-policy.yaml",
        "runtime_boundary_ref": "runtime/system-runtime-boundary.yaml",
        "admission_contract_ref": "spaces/system-space-identity-admission.yaml",
        "rollout_policy_ref": "spaces/system-space-rollout-policy.yaml",
        "delivery_evidence_refs": [
            ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/apply.yaml",
            ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/verify.yaml",
        ],
        "approval_ref": ".omo/workers/runs/phase9-wave3-identity-admission-approval.yaml",
        "acceptance_ref": ".omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml",
    }
