from __future__ import annotations

from pathlib import Path

import yaml

from omo.omo_rules import evaluate_rule_bundle


ROOT = Path(__file__).resolve().parents[2]


def _read_yaml(rel_path: str) -> dict:
    return yaml.safe_load((ROOT / rel_path).read_text(encoding="utf-8")) or {}


def test_phase10_wave4_runtime_space_surfaces_are_registered() -> None:
    registry = _read_yaml("spaces/registry.yaml")
    runtime_space = _read_yaml("spaces/runtime-space.yaml")
    runtime_entry = next(space for space in registry["spaces"] if space["id"] == "runtime-space")

    assert runtime_space["space_kind"] == "runtime"
    assert runtime_space["routing"]["default_project"] == "projects/agentmesh"
    assert "spaces/runtime-space-identity-admission.yaml" in runtime_space["policy_refs"]
    assert "spaces/runtime-space-rollout-policy.yaml" in runtime_space["policy_refs"]
    assert "spaces/runtime-space-cross-root-rule-registry.yaml" in runtime_space["policy_refs"]
    assert "data/runtime-space-access-policy.yaml" in runtime_space["policy_refs"]
    assert runtime_entry["manifest"] == "spaces/runtime-space.yaml"
    assert runtime_entry["space_kind"] == "runtime"
    assert "spaces/runtime-space-cross-root-rule-registry.yaml" in runtime_entry["policy_refs"]
    assert "data/runtime-space-access-policy.yaml" in runtime_entry["policy_refs"]


def test_phase10_wave4_live_runtime_space_bundle_reuses_normalized_contracts() -> None:
    bundle = evaluate_rule_bundle(
        ROOT,
        Path(".omo/workers/runs/phase10-wave4-cross-space-closeout-envelope.yaml"),
    )

    assert bundle == {
        "space_ref": "spaces/runtime-space.yaml",
        "membership_ref": "runtime-space-observer-membership",
        "action": "runtime.observe",
        "registry_ref": "spaces/runtime-space-cross-root-rule-registry.yaml",
        "data_policy_ref": "data/runtime-space-access-policy.yaml",
        "runtime_boundary_ref": "runtime/runtime-space-boundary.yaml",
        "admission_contract_ref": "spaces/runtime-space-identity-admission.yaml",
        "rollout_policy_ref": "spaces/runtime-space-rollout-policy.yaml",
        "data_contract": {
            "policy_ref": "data/runtime-space-access-policy.yaml",
            "allowed_roots": [],
        },
        "delivery_contract_ref": ".omo/_delivery/task-center/contracts/runtime-space-runtime-observe-delivery-contract.yaml",
        "delivery_contract": {
            "proposal_ref": ".omo/workers/runs/phase9-wave3-identity-admission-approval.yaml",
            "apply_ref": ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/apply.yaml",
            "verify_ref": ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/verify.yaml",
            "acceptance_ref": ".omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml",
        },
        "approval_ref": ".omo/workers/runs/phase9-wave3-identity-admission-approval.yaml",
        "acceptance_ref": ".omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml",
    }


def test_phase10_wave4_runtime_mutate_bundle_reuses_same_normalized_surface() -> None:
    bundle = evaluate_rule_bundle(
        ROOT,
        Path(".omo/workers/runs/phase10-wave4-runtime-mutate-envelope.yaml"),
    )

    assert bundle == {
        "space_ref": "spaces/system-space.yaml",
        "membership_ref": "system-governor-membership",
        "action": "runtime.mutate",
        "registry_ref": "spaces/system-space-cross-root-rule-registry.yaml",
        "data_policy_ref": "data/system-data-access-policy.yaml",
        "runtime_boundary_ref": "runtime/system-runtime-boundary.yaml",
        "admission_contract_ref": "spaces/system-space-identity-admission.yaml",
        "rollout_policy_ref": "spaces/system-space-rollout-policy.yaml",
        "data_contract": {
            "policy_ref": "data/system-data-access-policy.yaml",
            "allowed_roots": [],
        },
        "delivery_contract_ref": ".omo/_delivery/task-center/contracts/runtime-mutate-delivery-contract.yaml",
        "delivery_contract": {
            "proposal_ref": ".omo/workers/runs/phase9-wave3-identity-admission-approval.yaml",
            "apply_ref": ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/apply.yaml",
            "verify_ref": ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/verify.yaml",
            "acceptance_ref": ".omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml",
        },
        "approval_ref": ".omo/workers/runs/phase9-wave3-identity-admission-approval.yaml",
        "acceptance_ref": ".omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml",
    }
