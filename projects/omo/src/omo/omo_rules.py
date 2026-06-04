#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import yaml


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _resolve_rule(registry: dict, space_ref: str, action: str) -> dict:
    for rule in registry.get("rules", []):
        if rule.get("space_ref") == space_ref and rule.get("action") == action:
            return rule
    raise ValueError(f"no cross-root rule found for space={space_ref!r} action={action!r}")


def _find_data_rule(data_policy: dict, action: str) -> dict:
    for rule in data_policy.get("rules", []):
        if rule.get("action") == action:
            return rule
    raise ValueError(f"no data policy rule found for action={action!r}")


def _resolve_data_policy_ref(rule: dict) -> str:
    return str(rule.get("data_policy_ref") or rule.get("data", {}).get("policy_ref"))


def _resolve_runtime_boundary_ref(rule: dict) -> str:
    return str(rule.get("runtime_boundary_ref") or rule.get("runtime", {}).get("boundary_ref"))


def _resolve_admission_contract_ref(rule: dict) -> str:
    return str(rule.get("admission_contract_ref") or rule.get("governance", {}).get("admission_contract_ref"))


def _resolve_rollout_policy_ref(rule: dict) -> str:
    return str(rule.get("rollout_policy_ref") or rule.get("governance", {}).get("rollout_policy_ref"))


def _resolve_delivery_contract_ref(rule: dict) -> str | None:
    delivery = rule.get("delivery", {})
    contract_ref = delivery.get("contract_ref")
    return str(contract_ref) if contract_ref else None


def _uses_normalized_bundle(rule: dict, envelope: dict) -> bool:
    bundle_format = envelope.get("rules_context", {}).get("bundle_format")
    if bundle_format == "legacy":
        return False
    return _resolve_delivery_contract_ref(rule) is not None


def evaluate_rule_bundle(root: Path, envelope_ref: Path) -> dict[str, object]:
    envelope = _load_yaml(root / envelope_ref)
    execution_context = envelope.get("execution_context", {})
    rules_context = envelope.get("rules_context", {})

    registry_ref = rules_context.get("registry_ref")
    if not registry_ref:
        raise ValueError("worker envelope must include rules_context.registry_ref")

    registry = _load_yaml(root / registry_ref)
    rule = _resolve_rule(registry, str(execution_context["space_ref"]), str(execution_context["action"]))
    data_policy_ref = _resolve_data_policy_ref(rule)
    runtime_boundary_ref = _resolve_runtime_boundary_ref(rule)
    admission_contract_ref = _resolve_admission_contract_ref(rule)
    rollout_policy_ref = _resolve_rollout_policy_ref(rule)

    if _uses_normalized_bundle(rule, envelope):
        data_policy = _load_yaml(root / data_policy_ref)
        data_rule = _find_data_rule(data_policy, str(execution_context["action"]))
        delivery_contract_ref = str(_resolve_delivery_contract_ref(rule))
        delivery_contract = _load_yaml(root / delivery_contract_ref)

        return {
            "space_ref": execution_context["space_ref"],
            "membership_ref": execution_context["membership_ref"],
            "action": execution_context["action"],
            "registry_ref": registry_ref,
            "data_policy_ref": data_policy_ref,
            "runtime_boundary_ref": runtime_boundary_ref,
            "admission_contract_ref": admission_contract_ref,
            "rollout_policy_ref": rollout_policy_ref,
            "data_contract": {
                "policy_ref": data_policy_ref,
                "allowed_roots": list(data_rule.get("allowed_roots", [])),
            },
            "delivery_contract_ref": delivery_contract_ref,
            "delivery_contract": {
                "proposal_ref": delivery_contract["proposal_ref"],
                "apply_ref": delivery_contract["apply_ref"],
                "verify_ref": delivery_contract["verify_ref"],
                "acceptance_ref": delivery_contract.get("acceptance_ref", envelope["gates"]["acceptance_ref"]),
            },
            "approval_ref": envelope["gates"]["approval_ref"],
            "acceptance_ref": envelope["gates"]["acceptance_ref"],
        }

    return {
        "space_ref": execution_context["space_ref"],
        "membership_ref": execution_context["membership_ref"],
        "action": execution_context["action"],
        "registry_ref": registry_ref,
        "data_policy_ref": data_policy_ref,
        "runtime_boundary_ref": runtime_boundary_ref,
        "admission_contract_ref": admission_contract_ref,
        "rollout_policy_ref": rollout_policy_ref,
        "delivery_evidence_refs": list(rule.get("delivery_evidence_refs", [])),
        "approval_ref": envelope["gates"]["approval_ref"],
        "acceptance_ref": envelope["gates"]["acceptance_ref"],
    }
