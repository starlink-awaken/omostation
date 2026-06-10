from __future__ import annotations

from pathlib import Path

import yaml

from omo.omo_rules import evaluate_rule_bundle


ROOT = Path(__file__).resolve().parents[2]


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_phase10_wave3_live_runtime_observe_bundle_uses_normalized_contracts() -> None:
    bundle = evaluate_rule_bundle(
        ROOT,
        Path(".omo/workers/runs/phase10-wave3-action-matrix-envelope.yaml"),
    )

    assert bundle["action"] == "runtime.observe"
    assert bundle["delivery_contract_ref"] == ".omo/_delivery/task-center/contracts/runtime-observe-delivery-contract.yaml"
    assert bundle["delivery_contract"] == {
        "proposal_ref": ".omo/workers/runs/phase9-wave3-identity-admission-approval.yaml",
        "apply_ref": ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/apply.yaml",
        "verify_ref": ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/verify.yaml",
        "acceptance_ref": ".omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml",
    }
    assert bundle["data_contract"] == {
        "policy_ref": "data/system-data-access-policy.yaml",
        "allowed_roots": [],
    }


def test_phase10_wave3_project_dispatch_bundle_uses_normalized_contracts_without_wave2_task_prefix(
    tmp_path: Path,
) -> None:
    _write_yaml(
        tmp_path / "spaces" / "cross-root-rules.yaml",
        {
            "rules": [
                {
                    "space_ref": "spaces/system-space.yaml",
                    "action": "project.dispatch",
                    "governance": {
                        "admission_contract_ref": "spaces/admission.yaml",
                        "rollout_policy_ref": "spaces/rollout.yaml",
                    },
                    "data": {"policy_ref": "data/data-policy.yaml"},
                    "runtime": {"boundary_ref": "runtime/runtime-boundary.yaml"},
                    "delivery": {
                        "contract_ref": ".omo/_delivery/task-center/contracts/delivery.yaml"
                    },
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / "data" / "data-policy.yaml",
        {
            "rules": [
                {
                    "action": "project.dispatch",
                    "allowed_roots": ["data"],
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "_delivery" / "task-center" / "contracts" / "delivery.yaml",
        {
            "proposal_ref": ".omo/workers/runs/example-approval.yaml",
            "apply_ref": ".omo/_delivery/task-center/proposals/example/apply.yaml",
            "verify_ref": ".omo/_delivery/task-center/proposals/example/verify.yaml",
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "P10-W3-TASK-1",
            "gates": {
                "approval_ref": ".omo/workers/runs/example-approval.yaml",
                "acceptance_ref": ".omo/workers/runs/example-acceptance.yaml",
            },
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "system-governor-membership",
                "action": "project.dispatch",
            },
            "rules_context": {
                "registry_ref": "spaces/cross-root-rules.yaml",
            },
        },
    )

    bundle = evaluate_rule_bundle(
        tmp_path,
        Path(".omo/workers/runs/example-envelope.yaml"),
    )

    assert bundle["delivery_contract_ref"] == ".omo/_delivery/task-center/contracts/delivery.yaml"
    assert bundle["delivery_contract"] == {
        "proposal_ref": ".omo/workers/runs/example-approval.yaml",
        "apply_ref": ".omo/_delivery/task-center/proposals/example/apply.yaml",
        "verify_ref": ".omo/_delivery/task-center/proposals/example/verify.yaml",
        "acceptance_ref": ".omo/workers/runs/example-acceptance.yaml",
    }
    assert bundle["data_contract"] == {
        "policy_ref": "data/data-policy.yaml",
        "allowed_roots": ["data"],
    }
