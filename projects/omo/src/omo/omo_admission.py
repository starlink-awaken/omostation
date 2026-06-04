#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import yaml

try:
    from .omo_governance import propose_truth_mutation
    from .omo_io import write_yaml_atomic
except ModuleNotFoundError:
    from .omo_governance import propose_truth_mutation
    from .omo_io import write_yaml_atomic


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _resolve_required_capabilities(matrix: dict, action: str, fallback: list[str]) -> tuple[list[str], str]:
    for rule in matrix.get("rules", []):
        if rule.get("action") == action:
            return list(rule.get("required_capabilities", [])), rule.get("decision", "deny")
    return fallback, "deny"


def evaluate_worker_envelope(root: Path, envelope_ref: Path, matrix_ref: Path | None = None) -> dict[str, object]:
    envelope = _load_yaml(root / envelope_ref)
    context = envelope.get("execution_context", {})

    contract = _load_yaml(root / context["admission_contract_ref"])
    matrix = _load_yaml(root / matrix_ref) if matrix_ref is not None else _load_yaml(root / contract["admission_matrix_ref"])

    required_capabilities, decision = _resolve_required_capabilities(
        matrix,
        context["action"],
        list(context.get("required_capabilities", [])),
    )

    granted_capabilities = sorted(
        {
            capability
            for binding in contract.get("capability_bindings", [])
            if binding.get("membership_ref") == context["membership_ref"]
            for capability in binding.get("capabilities", [])
        }
    )
    missing_capabilities = [capability for capability in required_capabilities if capability not in granted_capabilities]

    if missing_capabilities:
        decision = "deny"

    return {
        "space_ref": context["space_ref"],
        "membership_ref": context["membership_ref"],
        "action": context["action"],
        "required_capabilities": required_capabilities,
        "granted_capabilities": granted_capabilities,
        "missing_capabilities": missing_capabilities,
        "decision": decision,
        "approval_required": decision == "conditional_approval",
    }


def _approval_ref_for_envelope(envelope_ref: Path) -> str:
    stem = envelope_ref.stem
    if stem.endswith("-envelope"):
        stem = stem[: -len("-envelope")]
    return f".omo/workers/runs/{stem}-approval.yaml"


def _review_ref(envelope: dict) -> str | None:
    for ref in envelope.get("handoff_refs", []):
        if str(ref).endswith("review.md"):
            return ref
    return None


def request_conditional_approval(
    root: Path,
    envelope_ref: Path,
    requested_by: str,
    now: str,
) -> dict[str, str]:
    result = evaluate_worker_envelope(root, envelope_ref)
    if result["decision"] != "conditional_approval":
        raise ValueError("conditional approval required before requesting governance approval")

    envelope_path = root / envelope_ref
    envelope = _load_yaml(envelope_path)
    approval_ref = _approval_ref_for_envelope(envelope_ref)
    approval_id = Path(approval_ref).stem

    approval_record = {
        "version": 1,
        "approval_id": approval_id,
        "task_id": envelope["task_id"],
        "dispatch_id": Path(envelope["run_ref"]).stem.replace("-dispatch", ""),
        "worker_id": envelope["worker_id"],
        "approval_status": "requested",
        "requested_operation_level": "L2",
        "release_scope": {
            "exact_action": result["action"],
            "allowed_paths": [result["space_ref"]],
            "denied_paths": [],
        },
        "requested_at": now,
        "approved_at": None,
        "expires_at": None,
        "approver": None,
        "refs": {
            "task_ref": envelope["task_yaml"],
            "run_ref": envelope["run_ref"],
            "review_ref": _review_ref(envelope),
        },
        "evidence": {
            "request_evidence": [str(envelope_ref)],
            "approval_evidence": [],
        },
    }
    write_yaml_atomic(root / approval_ref, approval_record)

    envelope.setdefault("gates", {})
    envelope["gates"]["approval_ref"] = approval_ref
    write_yaml_atomic(envelope_path, envelope)

    proposal_id = f"{approval_id}-proposal"
    propose_truth_mutation(
        root,
        {
            "id": proposal_id,
            "title": f"Grant conditional approval for {result['action']}",
            "operation_level": "L2",
            "requested_by": requested_by,
            "target": {"ref": approval_ref},
            "changes": {"set": {"approval_status": "granted"}},
            "change_summary": f"Grant {result['action']} for {result['membership_ref']}",
            "impact": "Releases a conditional approval request into the governance chain.",
            "verification_plan": [
                f"python3 scripts/omo_worker.py worker admission-eval {envelope_ref}",
            ],
            "rollback_plan": [
                f"Set {approval_ref} approval_status back to requested if approval must be withdrawn.",
            ],
            "secret_refs": [],
            "trace_id": f"trace-{approval_id}",
        },
        now=now,
    )

    return {
        "approval_ref": approval_ref,
        "proposal_id": proposal_id,
        "decision": str(result["decision"]),
    }
