from __future__ import annotations

from pathlib import Path

from omo.omo_rules import evaluate_rule_bundle


ROOT = Path(__file__).resolve().parents[2]


def test_phase10_wave2_live_bundle_includes_typed_delivery_contract() -> None:
    bundle = evaluate_rule_bundle(
        ROOT,
        Path(".omo/workers/runs/phase10-wave2-normalized-rules-envelope.yaml"),
    )

    assert bundle["delivery_contract_ref"] == ".omo/_delivery/task-center/contracts/project-dispatch-delivery-contract.yaml"
    assert bundle["delivery_contract"] == {
        "proposal_ref": ".omo/workers/runs/phase9-wave3-identity-admission-approval.yaml",
        "apply_ref": ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/apply.yaml",
        "verify_ref": ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/verify.yaml",
        "acceptance_ref": ".omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml",
    }
    assert bundle["data_contract"] == {
        "policy_ref": "data/system-data-access-policy.yaml",
        "allowed_roots": ["data"],
    }
