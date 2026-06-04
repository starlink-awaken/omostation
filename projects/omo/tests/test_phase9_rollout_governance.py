from __future__ import annotations

from pathlib import Path

import yaml

from scripts.omo_rollout import evaluate_rollout_envelope


ROOT = Path(__file__).resolve().parents[2]


def _read_yaml(rel_path: str) -> dict:
    return yaml.safe_load((ROOT / rel_path).read_text(encoding="utf-8"))


def test_system_space_wave4_rollout_contracts_are_linked() -> None:
    system_space = _read_yaml("spaces/system-space.yaml")
    registry = _read_yaml("spaces/registry.yaml")
    system_entry = next(space for space in registry["spaces"] if space["id"] == "system-space")

    assert (ROOT / "spaces/system-space-rollout-policy.yaml").exists()
    assert (ROOT / "runtime/system-runtime-boundary.yaml").exists()
    assert "spaces/system-space-rollout-policy.yaml" in system_space["policy_refs"]
    assert "spaces/system-space-rollout-policy.yaml" in system_entry["policy_refs"]


def test_wave4_live_rollout_path_is_allow_and_acceptance_is_recorded() -> None:
    result = evaluate_rollout_envelope(
        ROOT,
        Path(".omo/workers/runs/phase9-wave4-rollout-ops-envelope.yaml"),
    )

    assert result == {
        "space_ref": "spaces/system-space.yaml",
        "membership_ref": "system-governor-membership",
        "action": "project.dispatch",
        "approval_ref": ".omo/workers/runs/phase9-wave3-identity-admission-approval.yaml",
        "approval_status": "granted",
        "required_evidence_refs": [
            ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/apply.yaml",
            ".omo/_delivery/task-center/proposals/phase9-wave3-identity-admission-approval-proposal/verify.yaml",
        ],
        "missing_evidence_refs": [],
        "runtime_residue_paths": [
            "runtime/run-continuation/phase9-wave4-rollout-ops",
            "runtime/logs/phase9-wave4-rollout-ops.log",
        ],
        "disallowed_runtime_paths": [],
        "decision": "allow",
        "acceptance_ready": True,
    }

    envelope = _read_yaml(".omo/workers/runs/phase9-wave4-rollout-ops-envelope.yaml")
    acceptance = _read_yaml(".omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml")

    assert envelope["gates"]["acceptance_ref"] == ".omo/workers/runs/phase9-wave4-rollout-ops-acceptance.yaml"
    assert acceptance["decision"] == "allow"
    assert acceptance["refs"]["approval_ref"] == ".omo/workers/runs/phase9-wave3-identity-admission-approval.yaml"
