#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import yaml

from .omo_io import write_yaml_atomic


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _resolve_rollout_rule(policy: dict, action: str) -> dict:
    for rule in policy.get("rules", []):
        if rule.get("action") == action:
            return rule
    return {}


def _is_allowed_runtime_path(path: str, allowed_roots: list[str]) -> bool:
    return any(path == root or path.startswith(f"{root}/") for root in allowed_roots)


def evaluate_rollout_envelope(root: Path, envelope_ref: Path) -> dict[str, object]:
    envelope = _load_yaml(root / envelope_ref)
    execution_context = envelope.get("execution_context", {})
    rollout_context = envelope.get("rollout_context", {})
    approval = _load_yaml(root / envelope["gates"]["approval_ref"])
    policy = _load_yaml(root / rollout_context["rollout_policy_ref"])
    runtime_boundary = _load_yaml(root / rollout_context["runtime_boundary_ref"])
    rule = _resolve_rollout_rule(policy, str(execution_context["action"]))

    required_evidence_refs = list(rule.get("required_evidence_refs", []))
    missing_evidence_refs = [
        ref for ref in required_evidence_refs if not (root / ref).exists()
    ]
    runtime_residue_paths = list(rollout_context.get("runtime_residue_paths", []))
    allowed_runtime_roots = list(runtime_boundary.get("allowed_runtime_roots", []))
    disallowed_runtime_paths = [
        path
        for path in runtime_residue_paths
        if not _is_allowed_runtime_path(path, allowed_runtime_roots)
    ]
    approval_status = approval.get("approval_status")
    required_approval_status = rule.get("required_approval_status")

    decision = "allow"
    if (
        approval_status != required_approval_status
        or missing_evidence_refs
        or disallowed_runtime_paths
    ):
        decision = "deny"

    return {
        "space_ref": execution_context["space_ref"],
        "membership_ref": execution_context["membership_ref"],
        "action": execution_context["action"],
        "approval_ref": envelope["gates"]["approval_ref"],
        "approval_status": approval_status,
        "required_evidence_refs": required_evidence_refs,
        "missing_evidence_refs": missing_evidence_refs,
        "runtime_residue_paths": runtime_residue_paths,
        "disallowed_runtime_paths": disallowed_runtime_paths,
        "decision": decision,
        "acceptance_ready": decision == "allow",
    }


def _acceptance_ref_for_envelope(envelope_ref: Path) -> str:
    stem = envelope_ref.stem
    if stem.endswith("-envelope"):
        stem = stem[: -len("-envelope")]
    return f".omo/workers/runs/{stem}-acceptance.yaml"


def accept_rollout_envelope(
    root: Path, envelope_ref: Path, accepted_by: str, now: str
) -> dict[str, str]:
    result = evaluate_rollout_envelope(root, envelope_ref)
    if result["decision"] != "allow":
        raise ValueError("rollout envelope must evaluate to allow before acceptance")

    envelope_path = root / envelope_ref
    envelope = _load_yaml(envelope_path)
    rollout_context = envelope.get("rollout_context", {})
    acceptance_ref = _acceptance_ref_for_envelope(envelope_ref)
    acceptance_record = {
        "version": 1,
        "acceptance_id": Path(acceptance_ref).stem,
        "task_id": envelope["task_id"],
        "worker_id": envelope["worker_id"],
        "accepted_by": accepted_by,
        "accepted_at": now,
        "decision": result["decision"],
        "refs": {
            "envelope_ref": str(envelope_ref),
            "approval_ref": envelope["gates"]["approval_ref"],
            "run_ref": envelope.get("run_ref"),
            "task_ref": envelope.get("task_yaml"),
            "rollout_policy_ref": rollout_context["rollout_policy_ref"],
            "runtime_boundary_ref": rollout_context["runtime_boundary_ref"],
        },
        "evidence": {
            "acceptance_evidence_refs": list(
                rollout_context.get("acceptance_evidence_refs", [])
            ),
            "runtime_residue_paths": list(
                rollout_context.get("runtime_residue_paths", [])
            ),
        },
    }
    write_yaml_atomic(root / acceptance_ref, acceptance_record)

    envelope.setdefault("gates", {})
    envelope["gates"]["acceptance_ref"] = acceptance_ref
    write_yaml_atomic(envelope_path, envelope)

    return {
        "acceptance_ref": acceptance_ref,
        "decision": str(result["decision"]),
    }
