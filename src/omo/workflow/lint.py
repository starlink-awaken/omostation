from __future__ import annotations

import json
import re
import shutil
import sys
from typing import Any

from .core import (
    ADAPTER_AUTHORITIES,
    AGCP_BOS_ROUTES,
    AGCP_MOF_BOSROUTE_PATH,
    AGCP_MOF_WORKFLOW_PATH,
    AGENT_CLIS_PATH,
    AGORA_BOS_REGISTRY_PATH,
    CLAIM_POLICY_MODES,
    INTEGRATION_AUTHORITIES,
    MOF_DIFF_CHECK_IDS,
    MOF_MODEL_PATH_PATTERN,
    WORKSPACE,
    display_path,
    load_yaml_document_with,
)


def diff_check_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for check in registry.get("diff_checks") or []:
        if not isinstance(check, dict):
            continue
        rows.append(
            {
                "id": str(check.get("id") or ""),
                "description": str(check.get("description") or ""),
                "required": bool(check.get("required", True)),
                "always": bool(check.get("always", False)),
                "paths": list(check.get("paths") or []),
                "command": list(check.get("command") or []),
                "cwd": str(check.get("cwd") or "."),
                "allowed_lanes": [
                    str(item)
                    for item in check.get("allowed_lanes") or []
                    if isinstance(item, str)
                ],
            }
        )
    return rows


def validate_command(
    workflow_id: str, phase: str, index: int, item: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    prefix = f"{workflow_id}.{phase}[{index}]"
    if not isinstance(item, dict):
        return [f"{prefix}: command entry must be a mapping"]
    if not item.get("id"):
        errors.append(f"{prefix}: missing id")
    if item.get("mode") not in {"required", "advisory", "manual"}:
        errors.append(f"{prefix}: mode must be required/advisory/manual")
    command = item.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(part, str) for part in command)
    ):
        errors.append(f"{prefix}: command must be a non-empty list of strings")
    return errors


def agcp_drift_findings(registry: dict[str, Any]) -> list[str]:
    findings: list[str] = []

    cockpit = (registry.get("internal_integrations") or {}).get("cockpit")
    if not isinstance(cockpit, dict):
        findings.append("internal_integrations.cockpit is missing")
    else:
        agent_command = str(cockpit.get("agent") or "")
        if "cockpit agent" not in agent_command:
            findings.append(
                "internal_integrations.cockpit.agent must point to `cockpit agent`"
            )

    agent_clis, error = load_yaml_document_with(AGENT_CLIS_PATH, "clis")
    if error:
        findings.append(error)
    else:
        cli_entries = agent_clis.get("clis") if isinstance(agent_clis, dict) else []
        clis = {
            str(item.get("name") or ""): item
            for item in (cli_entries or [])
            if isinstance(item, dict) and item.get("name")
        }
        cockpit_agent = clis.get("cockpit-agent")
        if not isinstance(cockpit_agent, dict):
            findings.append("agent-clis registry is missing cockpit-agent")
        elif "cockpit agent" not in str(cockpit_agent.get("entrypoint") or ""):
            findings.append(
                "agent-clis.cockpit-agent entrypoint must delegate to `cockpit agent`"
            )

    cli_path = WORKSPACE / "projects/cockpit/src/cockpit/cli.py"
    command_path = WORKSPACE / "projects/cockpit/src/cockpit/commands/agent_workflow.py"
    if not cli_path.exists():
        findings.append(f"missing Cockpit CLI file: {display_path(cli_path)}")
    else:
        cli_text = cli_path.read_text(encoding="utf-8")
        if not re.search(r"sub\.add_parser\(\s*[\"']agent[\"']", cli_text):
            findings.append("Cockpit CLI must expose `cockpit agent`")
    if not command_path.exists():
        findings.append(
            f"missing Cockpit agent workflow command: {display_path(command_path)}"
        )
    else:
        command_text = command_path.read_text(encoding="utf-8")
        if "agent-workflow.py" not in command_text or "bootstrap" not in command_text:
            findings.append(
                "Cockpit agent workflow command must delegate to root runner and bootstrap default"
            )

    bos_registry, error = load_yaml_document_with(AGORA_BOS_REGISTRY_PATH, "services")
    if error:
        findings.append(error)
    else:
        services = (
            bos_registry.get("services") if isinstance(bos_registry, dict) else []
        )
        uris = {
            str(item.get("uri") or "")
            for item in (services or [])
            if isinstance(item, dict) and item.get("uri")
        }
        missing_routes = sorted(AGCP_BOS_ROUTES - uris)
        if missing_routes:
            findings.append(
                f"Agora BOS registry missing AGCP routes: {', '.join(missing_routes)}"
            )

    for path, expected_id in (
        (AGCP_MOF_WORKFLOW_PATH, "WORKFLOW-AGENT-GOVERNANCE-CONTROL-PLANE"),
        (AGCP_MOF_BOSROUTE_PATH, "BOSROUTE-GOVERNANCE-AGENT-WORKFLOW"),
    ):
        document, error = load_yaml_document_with(path, "id")
        if error:
            findings.append(error)
            continue
        if str((document or {}).get("id") or "") != expected_id:
            findings.append(f"{display_path(path)} id must be {expected_id}")

    diff_checks = {row["id"]: row for row in diff_check_rows(registry)}
    missing_mof_checks = sorted(MOF_DIFF_CHECK_IDS - set(diff_checks))
    if missing_mof_checks:
        findings.append(
            f"diff_checks missing MOF checks: {', '.join(missing_mof_checks)}"
        )
    for check_id in sorted(MOF_DIFF_CHECK_IDS & set(diff_checks)):
        if MOF_MODEL_PATH_PATTERN not in diff_checks[check_id].get("paths", []):
            findings.append(
                f"diff_checks.{check_id} must include {MOF_MODEL_PATH_PATTERN}"
            )

    return findings


def agcp_drift_check(registry: dict[str, Any]) -> dict[str, Any]:
    findings = agcp_drift_findings(registry)
    return {
        "id": "agcp-drift",
        "description": "AGCP registry, Cockpit, Agora BOS, and MOF route invariants.",
        "required": True,
        "command": "agent-workflow lint agcp-drift",
        "ok": not findings,
        "findings": findings,
        "stdout": "\n".join(findings),
        "stderr": "",
    }


def lint_registry(
    registry: dict[str, Any], include_agcp_drift: bool = True
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    agent_profiles = registry.get("agent_profiles") or {}
    if agent_profiles and not isinstance(agent_profiles, dict):
        errors.append("registry.agent_profiles must be a mapping")
        agent_profiles = {}
    workflows = registry.get("workflows")
    if not isinstance(workflows, list) or not workflows:
        errors.append("registry.workflows must be a non-empty list")
        return errors, warnings

    seen: set[str] = set()
    for workflow in workflows:
        if not isinstance(workflow, dict):
            errors.append("workflow entry must be a mapping")
            continue
        workflow_id = workflow.get("id")
        if not workflow_id:
            errors.append("workflow missing id")
            continue
        if workflow_id in seen:
            errors.append(f"duplicate workflow id: {workflow_id}")
        seen.add(workflow_id)
        for field in (
            "title",
            "purpose",
            "allowed_lanes",
            "lock_scopes",
            "surfaces",
            "phases",
        ):
            if field not in workflow:
                errors.append(f"{workflow_id}: missing {field}")
        for field in ("allowed_lanes", "lock_scopes"):
            values = workflow.get(field, [])
            if not isinstance(values, list) or not all(
                isinstance(item, str) for item in values
            ):
                errors.append(f"{workflow_id}: {field} must be a list of strings")
        agents = workflow.get("agents")
        if agents is not None:
            if not isinstance(agents, dict):
                errors.append(f"{workflow_id}: agents must be a mapping")
            else:
                roles = agents.get("roles", [])
                if not isinstance(roles, list) or not all(
                    isinstance(item, str) for item in roles
                ):
                    errors.append(
                        f"{workflow_id}: agents.roles must be a list of strings"
                    )
                for role in roles if isinstance(roles, list) else []:
                    profile = (
                        agent_profiles.get(role)
                        if isinstance(agent_profiles, dict)
                        else None
                    )
                    if not isinstance(profile, dict):
                        errors.append(f"{workflow_id}: unknown agent role: {role}")
                        continue
                    allowed = profile.get("allowed_workflows", [])
                    if allowed != ["*"] and workflow_id not in allowed:
                        errors.append(
                            f"{workflow_id}: role {role} does not allow this workflow"
                        )
        phases = workflow.get("phases", {})
        if not isinstance(phases, dict):
            errors.append(f"{workflow_id}: phases must be a mapping")
            continue
        for phase in ("preflight", "execute", "verification", "closeout"):
            entries = phases.get(phase)
            if not isinstance(entries, list) or not entries:
                errors.append(f"{workflow_id}: missing non-empty phase {phase}")
                continue
            for index, item in enumerate(entries):
                errors.extend(validate_command(workflow_id, phase, index, item))

    req_iter = registry.get("requirement_iteration_policy")
    if req_iter is not None:
        if not isinstance(req_iter, dict):
            errors.append("requirement_iteration_policy must be a mapping")
        else:
            req_mode = str(req_iter.get("mode") or "off")
            if req_mode not in {"off", "advisory", "required"}:
                errors.append(
                    "requirement_iteration_policy.mode must be off/advisory/required"
                )
            for list_field in (
                "required_lifecycle",
                "in_scope",
                "exempt_classes",
                "exempt_workflows",
                "in_scope_paths",
                "exclude_paths",
            ):
                value = req_iter.get(list_field)
                if value is not None and (
                    not isinstance(value, list)
                    or not all(isinstance(item, str) for item in value)
                ):
                    errors.append(
                        f"requirement_iteration_policy.{list_field} must be a list of strings"
                    )

    claim_policy_payload = registry.get("claim_policy")
    if claim_policy_payload is not None:
        if not isinstance(claim_policy_payload, dict):
            errors.append("claim_policy must be a mapping")
        else:
            mode = str(claim_policy_payload.get("mode") or "advisory")
            if mode not in CLAIM_POLICY_MODES:
                errors.append("claim_policy.mode must be off/advisory/required")
            required_paths = claim_policy_payload.get("required_paths", [])
            if not isinstance(required_paths, list) or not all(
                isinstance(item, str) for item in required_paths
            ):
                errors.append("claim_policy.required_paths must be a list of strings")
            tiers = claim_policy_payload.get("tiers", [])
            if tiers and not isinstance(tiers, list):
                errors.append("claim_policy.tiers must be a list")
            for index, tier in enumerate(tiers if isinstance(tiers, list) else []):
                prefix = f"claim_policy.tiers[{index}]"
                if not isinstance(tier, dict):
                    errors.append(f"{prefix}: tier must be a mapping")
                    continue
                tier_mode = str(tier.get("mode") or "advisory")
                if tier_mode not in {"advisory", "required"}:
                    errors.append(f"{prefix}.mode must be advisory/required")
                paths = tier.get("paths", [])
                if (
                    not isinstance(paths, list)
                    or not paths
                    or not all(isinstance(item, str) for item in paths)
                ):
                    errors.append(f"{prefix}.paths must be a non-empty list of strings")

    if isinstance(agent_profiles, dict):
        for profile_id, profile in agent_profiles.items():
            if not isinstance(profile, dict):
                errors.append(f"agent_profiles.{profile_id}: profile must be a mapping")
                continue
            for field in ("purpose", "allowed_workflows", "can_write_lanes"):
                if field not in profile:
                    errors.append(f"agent_profiles.{profile_id}: missing {field}")
            allowed = profile.get("allowed_workflows", [])
            if not isinstance(allowed, list) or not all(
                isinstance(item, str) for item in allowed
            ):
                errors.append(
                    f"agent_profiles.{profile_id}: allowed_workflows must be a list of strings"
                )
            else:
                for workflow_ref in allowed:
                    if workflow_ref != "*" and workflow_ref not in seen:
                        errors.append(
                            f"agent_profiles.{profile_id}: unknown workflow in allowed_workflows: {workflow_ref}"
                        )
            lanes = profile.get("can_write_lanes", [])
            if not isinstance(lanes, list) or not all(
                isinstance(item, str) for item in lanes
            ):
                errors.append(
                    f"agent_profiles.{profile_id}: can_write_lanes must be a list of strings"
                )

    for name, integration in (registry.get("internal_integrations") or {}).items():
        if not isinstance(integration, dict):
            errors.append(
                f"internal_integrations.{name}: integration must be a mapping"
            )
            continue
        for field in (
            "status",
            "authority",
            "owner",
            "ssot_rule",
            "health_command",
            "health_required",
        ):
            if field not in integration:
                errors.append(f"internal_integrations.{name}: missing {field}")
        authority = integration.get("authority")
        if authority and authority not in INTEGRATION_AUTHORITIES:
            errors.append(
                "internal_integrations."
                f"{name}: authority must be one of {', '.join(sorted(INTEGRATION_AUTHORITIES))}"
            )
        health_command = integration.get("health_command")
        if health_command is not None and (
            not isinstance(health_command, list)
            or not health_command
            or not all(isinstance(part, str) for part in health_command)
        ):
            errors.append(
                f"internal_integrations.{name}: health_command must be a non-empty list of strings"
            )
        if "health_required" in integration and not isinstance(
            integration.get("health_required"), bool
        ):
            errors.append(
                f"internal_integrations.{name}: health_required must be a boolean"
            )

    for name, adapter in (registry.get("external_patterns") or {}).items():
        if not isinstance(adapter, dict):
            errors.append(f"external_patterns.{name}: adapter must be a mapping")
            continue
        for field in (
            "status",
            "pattern",
            "authority",
            "ssot_rule",
            "ingress_workflow",
        ):
            if not adapter.get(field):
                errors.append(f"external_patterns.{name}: missing {field}")
        authority = adapter.get("authority")
        if authority and authority not in ADAPTER_AUTHORITIES:
            errors.append(
                f"external_patterns.{name}: authority must be one of {', '.join(sorted(ADAPTER_AUTHORITIES))}"
            )
        command = adapter.get("command")
        if command and shutil.which(str(command)) is None:
            warnings.append(f"optional adapter not installed: {name} ({command})")
        health_command = adapter.get("health_command")
        if health_command is not None and (
            not isinstance(health_command, list)
            or not health_command
            or not all(isinstance(part, str) for part in health_command)
        ):
            errors.append(
                f"external_patterns.{name}: health_command must be a non-empty list of strings"
            )
        if "health_required" in adapter and not isinstance(
            adapter.get("health_required"), bool
        ):
            errors.append(
                f"external_patterns.{name}: health_required must be a boolean"
            )
    for index, check_item in enumerate(registry.get("doctor_checks") or []):
        prefix = f"doctor_checks[{index}]"
        if not isinstance(check_item, dict):
            errors.append(f"{prefix}: entry must be a mapping")
            continue
        command = check_item.get("command")
        if not check_item.get("id"):
            errors.append(f"{prefix}: missing id")
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(part, str) for part in command)
        ):
            errors.append(f"{prefix}: command must be a non-empty list of strings")
    for index, check_item in enumerate(registry.get("diff_checks") or []):
        prefix = f"diff_checks[{index}]"
        if not isinstance(check_item, dict):
            errors.append(f"{prefix}: entry must be a mapping")
            continue
        command = check_item.get("command")
        paths = check_item.get("paths", [])
        if not check_item.get("id"):
            errors.append(f"{prefix}: missing id")
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(part, str) for part in command)
        ):
            errors.append(f"{prefix}: command must be a non-empty list of strings")
        if not isinstance(paths, list) or not all(
            isinstance(part, str) for part in paths
        ):
            errors.append(f"{prefix}: paths must be a list of strings")
        if not paths and not check_item.get("always"):
            errors.append(f"{prefix}: paths must be non-empty unless always=true")
        if "required" in check_item and not isinstance(
            check_item.get("required"), bool
        ):
            errors.append(f"{prefix}: required must be a boolean")
        if "always" in check_item and not isinstance(check_item.get("always"), bool):
            errors.append(f"{prefix}: always must be a boolean")
        allowed_lanes = check_item.get("allowed_lanes", [])
        if allowed_lanes and (
            not isinstance(allowed_lanes, list)
            or not all(isinstance(part, str) for part in allowed_lanes)
        ):
            errors.append(f"{prefix}: allowed_lanes must be a list of strings")
    if include_agcp_drift:
        errors.extend(
            f"agcp_drift: {finding}" for finding in agcp_drift_findings(registry)
        )
    return errors, warnings


def print_lint(errors: list[str], warnings: list[str], as_json: bool) -> None:
    report = {"ok": not errors, "errors": errors, "warnings": warnings}
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    for warning in warnings:
        print(f"[WARN] {warning}")
    if errors:
        for error in errors:
            print(f"[FAIL] {error}", file=sys.stderr)
        print("agent-workflow lint: FAIL", file=sys.stderr)
    else:
        print("agent-workflow lint: PASS")
