#!/usr/bin/env python3
"""Executable agent workflow runner for project-level governance."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml


WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY_PATH = WORKSPACE / ".omo/_truth/registry/agent-workflows.yaml"
AGENT_CLIS_PATH = WORKSPACE / ".omo/_truth/registry/agent-clis.yaml"
AGORA_BOS_REGISTRY_PATH = WORKSPACE / "projects/agora/etc/bos-services.yaml"
AGCP_MOF_WORKFLOW_PATH = (
    WORKSPACE / "projects/ecos/src/ecos/ssot/mof/m1/workflow/"
    "WORKFLOW-AGENT-GOVERNANCE-CONTROL-PLANE.yaml"
)
AGCP_MOF_BOSROUTE_PATH = (
    WORKSPACE / "projects/ecos/src/ecos/ssot/mof/m1/bosroute/"
    "BOSROUTE-GOVERNANCE-AGENT-WORKFLOW.yaml"
)
AGCP_BOS_ROUTES = {
    "bos://governance/agent-workflow/bootstrap",
    "bos://governance/agent-workflow/verify-plan",
    "bos://governance/agent-workflow/observe",
    "bos://governance/agent-workflow/compliance",
    "bos://governance/agent-workflow/doctor",
}
MOF_MODEL_PATH_PATTERN = "projects/ecos/src/ecos/ssot/mof/**"
MOF_DIFF_CHECK_IDS = {"mof-schema-validate", "mof-state-bridge", "mof-drift"}
ADAPTER_AUTHORITIES = {"discipline_layer", "input_adapter", "memory_adapter"}
INTEGRATION_AUTHORITIES = {
    "entrypoint",
    "governance_gate",
    "model_registry",
    "state_broker",
    "strategy_ingress",
}
CLAIM_POLICY_MODES = {"off", "advisory", "required"}
RUN_UPDATE_LOCK_TIMEOUT_SECONDS = 30.0


class WorkflowError(RuntimeError):
    """Raised when the workflow registry or run state is invalid."""


class SafeFormatDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        raise WorkflowError(f"workflow registry not found: {path}")
    documents = [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]
    for document in documents:
        if isinstance(document, dict) and "workflows" in document:
            return document
    raise WorkflowError(f"workflow registry has no workflows document: {path}")


def is_default_registry_path(path: Path) -> bool:
    candidate = path if path.is_absolute() else WORKSPACE / path
    try:
        return candidate.resolve() == REGISTRY_PATH.resolve()
    except OSError:
        return False


def load_yaml_document_with(path: Path, key: str) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"missing file: {display_path(path)}"
    try:
        documents = [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]
    except yaml.YAMLError as exc:
        return None, f"invalid YAML: {display_path(path)} ({exc})"
    for document in documents:
        if isinstance(document, dict) and key in document:
            return document, None
    return None, f"{display_path(path)} has no YAML document with key '{key}'"


def workflow_by_id(registry: dict[str, Any], workflow_id: str) -> dict[str, Any]:
    for workflow in registry.get("workflows", []):
        if workflow.get("id") == workflow_id:
            return workflow
    raise WorkflowError(f"unknown workflow: {workflow_id}")


def workflow_roles(workflow: dict[str, Any]) -> list[str]:
    agents = workflow.get("agents") or {}
    roles = agents.get("roles") if isinstance(agents, dict) else []
    if not isinstance(roles, list):
        return []
    return [role for role in roles if isinstance(role, str)]


def validate_agent_profile(
    registry: dict[str, Any],
    workflow: dict[str, Any],
    profile_id: str,
    require: bool,
) -> None:
    roles = workflow_roles(workflow)
    workflow_id = str(workflow.get("id") or "")
    if not profile_id:
        if require and roles:
            raise WorkflowError(f"{workflow_id} requires --profile ({', '.join(roles)})")
        return
    profiles = registry.get("agent_profiles") or {}
    profile = profiles.get(profile_id) if isinstance(profiles, dict) else None
    if not isinstance(profile, dict):
        raise WorkflowError(f"unknown agent profile: {profile_id}")
    allowed = profile.get("allowed_workflows", [])
    if allowed != ["*"] and workflow_id not in allowed:
        raise WorkflowError(f"agent profile {profile_id} cannot run workflow {workflow_id}")
    if roles and profile_id not in roles:
        raise WorkflowError(f"agent profile {profile_id} is not listed in {workflow_id}.agents.roles")


def context_from_args(args: argparse.Namespace) -> dict[str, str]:
    return {
        "project": str(getattr(args, "project", "") or ""),
        "format": str(getattr(args, "format", "") or "openspec"),
        "source_file": str(getattr(args, "source_file", "") or ""),
        "run_id": str(getattr(args, "run_id", "") or ""),
        "actor": str(getattr(args, "actor", "") or "agent"),
        "profile": str(getattr(args, "profile", "") or ""),
    }


def substitute(value: Any, context: dict[str, str]) -> Any:
    if isinstance(value, str):
        return value.format_map(SafeFormatDict(context))
    if isinstance(value, list):
        return [substitute(item, context) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item, context) for key, item in value.items()}
    return value


def command_display(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def normalize_repo_path(raw_path: str) -> str:
    if not raw_path:
        raise WorkflowError("path cannot be empty")
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(WORKSPACE)
        except ValueError as exc:
            raise WorkflowError(f"path is outside workspace: {raw_path}") from exc
    normalized = path.as_posix().strip("/")
    if normalized in {"", "."}:
        return "."
    if normalized == ".." or normalized.startswith("../") or "/../" in normalized:
        raise WorkflowError(f"path escapes workspace: {raw_path}")
    return normalized


def changed_files_from_git(include_untracked: bool) -> list[str]:
    commands = [
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
    ]
    if include_untracked:
        commands.append(["git", "ls-files", "--others", "--exclude-standard"])
    changed: set[str] = set()
    for command in commands:
        completed = subprocess.run(command, cwd=WORKSPACE, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise WorkflowError(f"failed to inspect changed files: {command_display(command)}")
        for line in completed.stdout.splitlines():
            if line.strip():
                changed.add(normalize_repo_path(line.strip()))
    return sorted(changed)


def path_matches(patterns: list[str], path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def suggest_workflows(
    registry: dict[str, Any],
    files: list[str],
    profile: str = "",
) -> list[dict[str, Any]]:
    """Suggest workflows for a set of files (P74 stage 3 — advisory routing).

    Walks every workflow's `surfaces.write` glob list and scores it by the
    fraction of `files` that match. Returns suggestions sorted by score
    descending. Empty list when nothing matches. Does not raise; suggestions
    are advisory only and must be confirmed by `start --workflow-id`.
    """
    normalized = sorted({normalize_repo_path(item) for item in files})
    if not normalized:
        return []
    suggestions: list[dict[str, Any]] = []
    for workflow in registry.get("workflows") or []:
        if not isinstance(workflow, dict):
            continue
        surfaces = workflow.get("surfaces") or {}
        write_patterns = surfaces.get("write") if isinstance(surfaces, dict) else None
        if not isinstance(write_patterns, list) or not write_patterns:
            continue
        matched = [file for file in normalized if path_matches([str(p) for p in write_patterns], file)]
        if not matched:
            continue
        score = round(len(matched) / len(normalized), 3)
        agents = workflow.get("agents") or {}
        roles = agents.get("roles") if isinstance(agents, dict) else []
        suggestions.append(
            {
                "workflow_id": str(workflow.get("id") or ""),
                "title": str(workflow.get("title") or ""),
                "score": score,
                "matched_files": matched,
                "total_files": len(normalized),
                "agents": [str(r) for r in roles if isinstance(r, str)],
                "allowed_lanes": [
                    str(item) for item in (workflow.get("allowed_lanes") or []) if isinstance(item, str)
                ],
                "profile_hint": _profile_hint(profile, roles),
            }
        )
    suggestions.sort(key=lambda item: (item["score"], item["workflow_id"]), reverse=True)
    return suggestions


def _profile_hint(profile: str, roles: list[object]) -> str:
    if not profile:
        return ""
    if any(str(role) == profile for role in roles):
        return "exact"
    return "allowed_via_governance_agent"


def suggest_command(registry: dict[str, Any], files: list[str], profile: str, as_json: bool) -> int:
    suggestions = suggest_workflows(registry, files, profile)
    matched_files = {
        matched for suggestion in suggestions for matched in suggestion["matched_files"]
    }
    uncovered = [file for file in files if file not in matched_files]
    if as_json:
        json.dump(
            {
                "file_count": len(files),
                "profile": profile,
                "suggestion_count": len(suggestions),
                "suggestions": suggestions,
                "uncovered_files": uncovered,
            },
            sys.stdout,
            indent=2,
            ensure_ascii=False,
            sort_keys=False,
        )
        sys.stdout.write("\n")
        return 0
    if not suggestions:
        print(f"[INFO] no workflow matches {len(files)} file(s); use --workflow-id to override")
        if uncovered:
            print(f"[WARN] {len(uncovered)} file(s) uncovered by any workflow.surfaces.write:")
            for file in uncovered:
                print(f"  - {file}")
            print("[HINT] consider extending an existing workflow's surfaces or registering a new one.")
        return 0
    print(f"[advisory] {len(suggestions)} workflow candidate(s) for {len(files)} file(s):")
    for item in suggestions:
        marker = " <-- profile matches" if item["profile_hint"] == "exact" else ""
        print(
            f"  - {item['workflow_id']} (score={item['score']}, agents={','.join(item['agents']) or '-'}){marker}"
        )
        for matched in item["matched_files"]:
            print(f"      matched: {matched}")
    if uncovered:
        print(f"[WARN] {len(uncovered)} file(s) uncovered by any workflow.surfaces.write:")
        for file in uncovered:
            print(f"  - {file}")
    return 0


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
                "allowed_lanes": [str(item) for item in check.get("allowed_lanes") or [] if isinstance(item, str)],
            }
        )
    return rows


def select_diff_checks(
    registry: dict[str, Any],
    files: list[str],
    all_checks: bool,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for check in diff_check_rows(registry):
        patterns = check["paths"]
        matched_files = sorted(file for file in files if path_matches(patterns, file))
        if all_checks or check["always"] or matched_files:
            selected.append({**check, "matched_files": matched_files})
    return selected


def agcp_drift_findings(registry: dict[str, Any]) -> list[str]:
    findings: list[str] = []

    cockpit = (registry.get("internal_integrations") or {}).get("cockpit")
    if not isinstance(cockpit, dict):
        findings.append("internal_integrations.cockpit is missing")
    else:
        agent_command = str(cockpit.get("agent") or "")
        if "cockpit agent" not in agent_command:
            findings.append("internal_integrations.cockpit.agent must point to `cockpit agent`")

    agent_clis, error = load_yaml_document_with(AGENT_CLIS_PATH, "clis")
    if error:
        findings.append(error)
    else:
        cli_entries = agent_clis.get("clis") if isinstance(agent_clis, dict) else []
        clis = {
            str(item.get("name") or ""): item
            for item in cli_entries
            if isinstance(item, dict) and item.get("name")
        }
        cockpit_agent = clis.get("cockpit-agent")
        if not isinstance(cockpit_agent, dict):
            findings.append("agent-clis registry is missing cockpit-agent")
        elif "cockpit agent" not in str(cockpit_agent.get("entrypoint") or ""):
            findings.append("agent-clis.cockpit-agent entrypoint must delegate to `cockpit agent`")

    cli_path = WORKSPACE / "projects/cockpit/src/cockpit/cli.py"
    command_path = WORKSPACE / "projects/cockpit/src/cockpit/commands/agent_workflow.py"
    if not cli_path.exists():
        findings.append(f"missing Cockpit CLI file: {display_path(cli_path)}")
    else:
        cli_text = cli_path.read_text(encoding="utf-8")
        if not re.search(r"sub\.add_parser\(\s*[\"']agent[\"']", cli_text):
            findings.append("Cockpit CLI must expose `cockpit agent`")
    if not command_path.exists():
        findings.append(f"missing Cockpit agent workflow command: {display_path(command_path)}")
    else:
        command_text = command_path.read_text(encoding="utf-8")
        if "agent-workflow.py" not in command_text or "bootstrap" not in command_text:
            findings.append("Cockpit agent workflow command must delegate to root runner and bootstrap default")

    bos_registry, error = load_yaml_document_with(AGORA_BOS_REGISTRY_PATH, "services")
    if error:
        findings.append(error)
    else:
        services = bos_registry.get("services") if isinstance(bos_registry, dict) else []
        uris = {
            str(item.get("uri") or "")
            for item in services
            if isinstance(item, dict) and item.get("uri")
        }
        missing_routes = sorted(AGCP_BOS_ROUTES - uris)
        if missing_routes:
            findings.append(f"Agora BOS registry missing AGCP routes: {', '.join(missing_routes)}")

    for path, expected_id in (
        (AGCP_MOF_WORKFLOW_PATH, "WORKFLOW-AGENT-GOVERNANCE-CONTROL-PLANE"),
        (AGCP_MOF_BOSROUTE_PATH, "BOSROUTE-GOVERNANCE-AGENT-WORKFLOW"),
    ):
        document, error = load_yaml_document_with(path, "id")
        if error:
            findings.append(error)
            continue
        if str(document.get("id") or "") != expected_id:
            findings.append(f"{display_path(path)} id must be {expected_id}")

    diff_checks = {row["id"]: row for row in diff_check_rows(registry)}
    missing_mof_checks = sorted(MOF_DIFF_CHECK_IDS - set(diff_checks))
    if missing_mof_checks:
        findings.append(f"diff_checks missing MOF checks: {', '.join(missing_mof_checks)}")
    for check_id in sorted(MOF_DIFF_CHECK_IDS & set(diff_checks)):
        if MOF_MODEL_PATH_PATTERN not in diff_checks[check_id].get("paths", []):
            findings.append(f"diff_checks.{check_id} must include {MOF_MODEL_PATH_PATTERN}")

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


def run_check_command(check: dict[str, Any], context: dict[str, str]) -> dict[str, Any]:
    command = substitute(check["command"], context)
    cwd = WORKSPACE / substitute([check.get("cwd") or "."], context)[0]
    env = os.environ.copy()
    matched_files = check.get("matched_files", [])
    if matched_files:
        env["AGENT_WORKFLOW_MATCHED_FILES"] = json.dumps(matched_files, ensure_ascii=False)
    allowed_lanes = check.get("allowed_lanes") or []
    if matched_files and allowed_lanes:
        env["AGENT_WORKFLOW_ALLOWED_LANES"] = ",".join(str(item) for item in allowed_lanes)
    started = time.monotonic()
    completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    duration_s = round(time.monotonic() - started, 3)
    stdout = completed.stdout[-4000:] if completed.stdout else ""
    stderr = completed.stderr[-4000:] if completed.stderr else ""
    return {
        "id": check["id"],
        "description": check.get("description", ""),
        "required": bool(check.get("required", True)),
        "command": command_display(command),
        "cwd": str(cwd.relative_to(WORKSPACE)) if cwd.is_relative_to(WORKSPACE) else str(cwd),
        "returncode": completed.returncode,
        "duration_s": duration_s,
        "ok": completed.returncode == 0 or not check.get("required", True),
        "stdout_tail": stdout,
        "stderr_tail": stderr,
        "matched_files": matched_files,
        "allowed_lanes": allowed_lanes,
    }


def validate_command(workflow_id: str, phase: str, index: int, item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    prefix = f"{workflow_id}.{phase}[{index}]"
    if not isinstance(item, dict):
        return [f"{prefix}: command entry must be a mapping"]
    if not item.get("id"):
        errors.append(f"{prefix}: missing id")
    if item.get("mode") not in {"required", "advisory", "manual"}:
        errors.append(f"{prefix}: mode must be required/advisory/manual")
    command = item.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
        errors.append(f"{prefix}: command must be a non-empty list of strings")
    return errors


def lint_registry(registry: dict[str, Any], include_agcp_drift: bool = True) -> tuple[list[str], list[str]]:
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
        for field in ("title", "purpose", "allowed_lanes", "lock_scopes", "surfaces", "phases"):
            if field not in workflow:
                errors.append(f"{workflow_id}: missing {field}")
        for field in ("allowed_lanes", "lock_scopes"):
            values = workflow.get(field, [])
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                errors.append(f"{workflow_id}: {field} must be a list of strings")
        agents = workflow.get("agents")
        if agents is not None:
            if not isinstance(agents, dict):
                errors.append(f"{workflow_id}: agents must be a mapping")
            else:
                roles = agents.get("roles", [])
                if not isinstance(roles, list) or not all(isinstance(item, str) for item in roles):
                    errors.append(f"{workflow_id}: agents.roles must be a list of strings")
                for role in roles if isinstance(roles, list) else []:
                    profile = agent_profiles.get(role) if isinstance(agent_profiles, dict) else None
                    if not isinstance(profile, dict):
                        errors.append(f"{workflow_id}: unknown agent role: {role}")
                        continue
                    allowed = profile.get("allowed_workflows", [])
                    if allowed != ["*"] and workflow_id not in allowed:
                        errors.append(f"{workflow_id}: role {role} does not allow this workflow")
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

    claim_policy_payload = registry.get("claim_policy")
    if claim_policy_payload is not None:
        if not isinstance(claim_policy_payload, dict):
            errors.append("claim_policy must be a mapping")
        else:
            mode = str(claim_policy_payload.get("mode") or "advisory")
            if mode not in CLAIM_POLICY_MODES:
                errors.append("claim_policy.mode must be off/advisory/required")
            required_paths = claim_policy_payload.get("required_paths", [])
            if not isinstance(required_paths, list) or not all(isinstance(item, str) for item in required_paths):
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
                if not isinstance(paths, list) or not paths or not all(isinstance(item, str) for item in paths):
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
            if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
                errors.append(f"agent_profiles.{profile_id}: allowed_workflows must be a list of strings")
            else:
                for workflow_ref in allowed:
                    if workflow_ref != "*" and workflow_ref not in seen:
                        errors.append(
                            f"agent_profiles.{profile_id}: unknown workflow in allowed_workflows: {workflow_ref}"
                        )
            lanes = profile.get("can_write_lanes", [])
            if not isinstance(lanes, list) or not all(isinstance(item, str) for item in lanes):
                errors.append(f"agent_profiles.{profile_id}: can_write_lanes must be a list of strings")

    for name, integration in (registry.get("internal_integrations") or {}).items():
        if not isinstance(integration, dict):
            errors.append(f"internal_integrations.{name}: integration must be a mapping")
            continue
        for field in ("status", "authority", "owner", "ssot_rule", "health_command", "health_required"):
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
            errors.append(f"internal_integrations.{name}: health_command must be a non-empty list of strings")
        if "health_required" in integration and not isinstance(integration.get("health_required"), bool):
            errors.append(f"internal_integrations.{name}: health_required must be a boolean")

    for name, adapter in (registry.get("external_patterns") or {}).items():
        if not isinstance(adapter, dict):
            errors.append(f"external_patterns.{name}: adapter must be a mapping")
            continue
        for field in ("status", "pattern", "authority", "ssot_rule", "ingress_workflow"):
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
            errors.append(f"external_patterns.{name}: health_command must be a non-empty list of strings")
        if "health_required" in adapter and not isinstance(adapter.get("health_required"), bool):
            errors.append(f"external_patterns.{name}: health_required must be a boolean")
    for index, check_item in enumerate(registry.get("doctor_checks") or []):
        prefix = f"doctor_checks[{index}]"
        if not isinstance(check_item, dict):
            errors.append(f"{prefix}: entry must be a mapping")
            continue
        command = check_item.get("command")
        if not check_item.get("id"):
            errors.append(f"{prefix}: missing id")
        if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
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
        if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
            errors.append(f"{prefix}: command must be a non-empty list of strings")
        if not isinstance(paths, list) or not all(isinstance(part, str) for part in paths):
            errors.append(f"{prefix}: paths must be a list of strings")
        if not paths and not check_item.get("always"):
            errors.append(f"{prefix}: paths must be non-empty unless always=true")
        if "required" in check_item and not isinstance(check_item.get("required"), bool):
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
        errors.extend(f"agcp_drift: {finding}" for finding in agcp_drift_findings(registry))
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


def list_workflows(registry: dict[str, Any], as_json: bool) -> None:
    rows = workflow_rows(registry)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        print(f"{row['id']:<28} {row['title']} [{', '.join(row['lanes'])}]")


def list_agents(registry: dict[str, Any], as_json: bool) -> None:
    rows = agent_rows(registry)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        workflows = ", ".join(row["allowed_workflows"])
        lanes = ", ".join(row["can_write_lanes"])
        print(f"{row['id']:<20} workflows=[{workflows}] lanes=[{lanes}]")


def workflow_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": workflow["id"],
            "title": workflow.get("title", ""),
            "lanes": workflow.get("allowed_lanes", []),
        }
        for workflow in registry.get("workflows", [])
    ]


def agent_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": profile_id,
            "purpose": profile.get("purpose", ""),
            "allowed_workflows": profile.get("allowed_workflows", []),
            "can_write_lanes": profile.get("can_write_lanes", []),
        }
        for profile_id, profile in sorted((registry.get("agent_profiles") or {}).items())
        if isinstance(profile, dict)
    ]


def integration_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, integration in (registry.get("internal_integrations") or {}).items():
        if not isinstance(integration, dict):
            continue
        rows.append(
            {
                "name": name,
                "status": integration.get("status"),
                "authority": integration.get("authority"),
                "owner": integration.get("owner"),
                "ssot_rule": integration.get("ssot_rule"),
                "gate_binding": integration.get("gate_binding"),
                "health_command": integration.get("health_command"),
                "health_required": bool(integration.get("health_required", False)),
                "commands": {
                    key: value
                    for key, value in integration.items()
                    if key
                    not in {
                        "status",
                        "authority",
                        "owner",
                        "ssot_rule",
                        "gate_binding",
                        "health_command",
                        "health_required",
                    }
                },
            }
        )
    return rows


def list_integrations(registry: dict[str, Any], as_json: bool) -> None:
    rows = integration_rows(registry)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        print(
            f"{row['name']:<14} {row['status']:<12} {row['authority']:<16} "
            f"owner={row['owner']} gate={row.get('gate_binding') or '-'}"
        )
        if row.get("ssot_rule"):
            print(f"  ssot: {row['ssot_rule']}")


def adapter_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, adapter in (registry.get("external_patterns") or {}).items():
        if not isinstance(adapter, dict):
            continue
        command = adapter.get("command")
        found = shutil.which(str(command)) if command else None
        rows.append(
            {
                "name": name,
                "status": adapter.get("status"),
                "authority": adapter.get("authority"),
                "ssot_rule": adapter.get("ssot_rule"),
                "ingress_workflow": adapter.get("ingress_workflow"),
                "skill": adapter.get("skill"),
                "command": command,
                "available": bool(found) if command else True,
                "path": found,
                "bridge": adapter.get("bridge"),
                "pattern": adapter.get("pattern"),
                "degrade_to": adapter.get("degrade_to"),
                "health_command": adapter.get("health_command"),
                "health_required": bool(adapter.get("health_required", False)),
            }
        )
    return rows


def list_adapters(registry: dict[str, Any], as_json: bool) -> None:
    rows = adapter_rows(registry)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        availability = "available" if row["available"] else "missing"
        command = row["command"] or row["skill"] or "-"
        print(
            f"{row['name']:<14} {row['status']:<16} {row['authority']:<16} "
            f"workflow={row['ingress_workflow']} command={command} {availability}"
        )
        if row.get("bridge"):
            print(f"  bridge: {row['bridge']}")
        if row.get("degrade_to"):
            print(f"  degrade_to: {row['degrade_to']}")
        if row.get("ssot_rule"):
            print(f"  ssot: {row['ssot_rule']}")


def workflow_plan(workflow: dict[str, Any], context: dict[str, str]) -> dict[str, Any]:
    resolved = substitute(workflow, context)
    return {
        "id": resolved["id"],
        "title": resolved.get("title", ""),
        "purpose": resolved.get("purpose", ""),
        "agents": resolved.get("agents", {}),
        "allowed_lanes": resolved.get("allowed_lanes", []),
        "lock_scopes": resolved.get("lock_scopes", []),
        "phases": resolved.get("phases", {}),
    }


def print_plan(plan: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    print(f"{plan['id']} — {plan['title']}")
    print(plan["purpose"])
    roles = plan.get("agents", {}).get("roles") or []
    if roles:
        print(f"agents: {', '.join(roles)}")
    print(f"lanes: {', '.join(plan['allowed_lanes'])}")
    print(f"locks: {', '.join(plan['lock_scopes'])}")
    for phase, entries in plan["phases"].items():
        print(f"\n[{phase}]")
        for item in entries:
            mode = item.get("mode", "?")
            cwd = item.get("cwd")
            prefix = f"({mode})"
            if cwd:
                prefix += f" cwd={cwd}"
            print(f"  {item.get('id')}: {prefix} {command_display(item['command'])}")


def run_stage(
    workflow: dict[str, Any],
    stage: str,
    context: dict[str, str],
    execute: bool,
    as_json: bool,
) -> int:
    plan = workflow_plan(workflow, context)
    entries = plan["phases"].get(stage)
    if not entries:
        raise WorkflowError(f"{plan['id']} has no stage: {stage}")

    results: list[dict[str, Any]] = []
    for item in entries:
        mode = item.get("mode")
        command = item["command"]
        cwd = WORKSPACE / item.get("cwd", ".")
        skipped = mode == "manual" or not execute
        result: dict[str, Any] = {
            "id": item.get("id"),
            "mode": mode,
            "command": command_display(command),
            "cwd": str(cwd.relative_to(WORKSPACE)) if cwd.is_relative_to(WORKSPACE) else str(cwd),
            "skipped": skipped,
            "ok": True,
        }
        if not skipped:
            completed = subprocess.run(command, cwd=cwd, check=False)
            result["returncode"] = completed.returncode
            result["ok"] = completed.returncode == 0 or mode == "advisory"
        results.append(result)

    report = {"workflow": plan["id"], "stage": stage, "execute": execute, "results": results}
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for result in results:
            status = "SKIP" if result["skipped"] else ("PASS" if result["ok"] else "FAIL")
            print(f"[{status}] {result['id']} :: {result['command']}")
    return 0 if all(item["ok"] for item in results) else 1


def run_state_dir(registry: dict[str, Any]) -> Path:
    return WORKSPACE / registry.get("runner", {}).get(
        "run_state_dir", ".omo/_delivery/agent-workflows/runs"
    )


def lock_state_dir(registry: dict[str, Any]) -> Path:
    return WORKSPACE / registry.get("runner", {}).get(
        "lock_state_dir", ".omo/_delivery/agent-workflows/locks"
    )


def ledger_path(registry: dict[str, Any]) -> Path:
    return WORKSPACE / registry.get("runner", {}).get(
        "ledger_path", ".omo/_delivery/agent-workflows/events.jsonl"
    )


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE))
    except ValueError:
        return str(path)


def sanitize_lock_name(scope: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", scope).strip("_") or "workspace"


@contextmanager
def run_update_lock(registry: dict[str, Any], run_id: str):
    lock_dir = lock_state_dir(registry)
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"run_{sanitize_lock_name(run_id)}.update.lock"
    deadline = time.monotonic() + RUN_UPDATE_LOCK_TIMEOUT_SECONDS
    acquired = False
    while not acquired:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"run_id: {run_id}\ncreated_at: {utc_now()}\n")
            acquired = True
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime > RUN_UPDATE_LOCK_TIMEOUT_SECONDS:
                    lock_path.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise WorkflowError(f"timed out waiting for run update lock: {display_path(lock_path)}")
            time.sleep(0.05)
    try:
        yield
    finally:
        if acquired:
            lock_path.unlink(missing_ok=True)


def append_ledger_event(registry: dict[str, Any], event: dict[str, Any]) -> None:
    path = ledger_path(registry)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": utc_now(), **event}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def acquire_locks(
    registry: dict[str, Any],
    scopes: list[str],
    run_id: str,
    actor: str,
    force: bool,
) -> list[str]:
    lock_dir = lock_state_dir(registry)
    lock_dir.mkdir(parents=True, exist_ok=True)
    acquired: list[str] = []
    acquired_paths: list[Path] = []
    ttl_hours = float(registry.get("runner", {}).get("lock_ttl_hours", 24))
    expires_at = (datetime.now(UTC) + timedelta(hours=ttl_hours)).replace(microsecond=0)
    try:
        for scope in scopes:
            lock_path = lock_dir / f"{sanitize_lock_name(scope)}.lock.yaml"
            payload = {
                "run_id": run_id,
                "actor": actor,
                "scope": scope,
                "created_at": utc_now(),
                "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            }
            if lock_path.exists() and not force:
                existing = lock_path.read_text(encoding="utf-8").strip()
                raise WorkflowError(f"lock already held for {scope}: {lock_path}\n{existing}")
            with lock_path.open("w" if force else "x", encoding="utf-8") as handle:
                yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)
            acquired_paths.append(lock_path)
            acquired.append(display_path(lock_path))
    except Exception:
        for path in acquired_paths:
            path.unlink(missing_ok=True)
        raise
    return acquired


def release_locks(registry: dict[str, Any], run_id: str) -> list[str]:
    lock_dir = lock_state_dir(registry)
    released: list[str] = []
    if not lock_dir.exists():
        return released
    for lock_path in lock_dir.glob("*.lock.yaml"):
        try:
            payload = yaml.safe_load(lock_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if payload.get("run_id") == run_id:
            lock_path.unlink()
            released.append(display_path(lock_path))
    return released


def run_file_for(registry: dict[str, Any], run_id: str) -> Path:
    run_dir = run_state_dir(registry)
    direct = run_dir / f"{run_id}.yaml"
    if direct.exists():
        return direct
    matches = list(run_dir.glob(f"*{run_id}*.yaml")) if run_dir.exists() else []
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise WorkflowError(f"ambiguous run id {run_id}: {', '.join(str(p) for p in matches)}")
    raise WorkflowError(f"run not found: {run_id}")


def start_run(
    registry: dict[str, Any],
    workflow: dict[str, Any],
    context: dict[str, str],
    objective: str,
    dry_run: bool,
    force_lock: bool,
) -> dict[str, Any]:
    validate_agent_profile(registry, workflow, context.get("profile", ""), require=True)
    plan = workflow_plan(workflow, context)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}-{plan['id']}-{uuid.uuid4().hex[:8]}"
    context = {**context, "run_id": run_id}
    plan = workflow_plan(workflow, context)
    record = {
        "run_id": run_id,
        "workflow_id": plan["id"],
        "status": "active",
        "actor": context["actor"],
        "agent_profile": context.get("profile", ""),
        "objective": objective,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "context": context,
        "locks": [],
        "plan": plan,
        "evidence": [],
    }
    if dry_run:
        return record
    record["locks"] = acquire_locks(registry, plan["lock_scopes"], run_id, context["actor"], force_lock)
    run_dir = run_state_dir(registry)
    run_dir.mkdir(parents=True, exist_ok=True)
    run_path = run_dir / f"{run_id}.yaml"
    run_path.write_text(yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8")  # audit-exempt: non-atomic-write — run state single-writer under run_update_lock
    record["path"] = display_path(run_path)
    append_ledger_event(
        registry,
        {
            "event": "agent_workflow_start",
            "run_id": run_id,
            "workflow_id": plan["id"],
            "actor": context["actor"],
            "agent_profile": context.get("profile", ""),
            "objective": objective,
            "path": record["path"],
            "locks": record["locks"],
        },
    )
    return record


def read_run(registry: dict[str, Any], run_id: str) -> tuple[Path, dict[str, Any]]:
    path = run_file_for(registry, run_id)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict) or not payload.get("run_id"):
        raise WorkflowError(f"invalid run file: {path}")
    return path, payload


def write_run(path: Path, payload: dict[str, Any]) -> None:
    payload["updated_at"] = utc_now()
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")  # audit-exempt: non-atomic-write — under run_update_lock


def claim_run(
    registry: dict[str, Any],
    run_id: str,
    actor: str,
    paths: list[str],
    surfaces: list[str],
    force_lock: bool,
) -> dict[str, Any]:
    if not paths and not surfaces:
        raise WorkflowError("claim requires at least one --path or --surface")
    with run_update_lock(registry, run_id):
        path, payload = read_run(registry, run_id)
        if payload.get("status") != "active":
            raise WorkflowError(f"cannot claim against non-active run: {run_id}")
        normalized_paths = sorted({normalize_repo_path(item) for item in paths})
        normalized_surfaces = sorted({item.strip() for item in surfaces if item.strip()})
        scopes = [f"path:{item}" for item in normalized_paths] + [f"surface:{item}" for item in normalized_surfaces]
        lock_paths = acquire_locks(registry, scopes, run_id, actor, force_lock)
        try:
            payload.setdefault("locks", [])
            for lock_path in lock_paths:
                if lock_path not in payload["locks"]:
                    payload["locks"].append(lock_path)
            claim = {
                "claimed_at": utc_now(),
                "actor": actor,
                "paths": normalized_paths,
                "surfaces": normalized_surfaces,
                "scopes": scopes,
                "locks": lock_paths,
            }
            payload.setdefault("claims", []).append(claim)
            write_run(path, payload)
        except Exception:
            for lock_path in lock_paths:
                lock_file = Path(lock_path)
                if not lock_file.is_absolute():
                    lock_file = WORKSPACE / lock_file
                lock_file.unlink(missing_ok=True)
            raise
        append_ledger_event(
            registry,
            {
                "event": "agent_workflow_claim",
                "run_id": run_id,
                "actor": actor,
                "paths": normalized_paths,
                "surfaces": normalized_surfaces,
                "locks": lock_paths,
            },
        )
        return {**claim, "run_id": run_id}


def normalize_claim_mode(raw_mode: Any, default: str = "advisory") -> str:
    mode = str(raw_mode or default)
    return mode if mode in CLAIM_POLICY_MODES else default


def claim_policy(registry: dict[str, Any]) -> dict[str, Any]:
    policy = registry.get("claim_policy")
    if not isinstance(policy, dict):
        return {"mode": "advisory", "required_paths": [], "tiers": []}
    mode = normalize_claim_mode(policy.get("mode"))
    required_paths = policy.get("required_paths") or []
    normalized_required_paths = [str(item) for item in required_paths if isinstance(item, str)]
    tiers: list[dict[str, Any]] = []
    if normalized_required_paths:
        tiers.append(
            {
                "id": "legacy-required-paths",
                "mode": mode,
                "paths": normalized_required_paths,
            }
        )
    for index, tier in enumerate(policy.get("tiers") or []):
        if not isinstance(tier, dict):
            continue
        paths = [str(item) for item in tier.get("paths") or [] if isinstance(item, str)]
        if not paths:
            continue
        tier_mode = normalize_claim_mode(tier.get("mode"), default="advisory")
        if tier_mode == "off":
            continue
        tiers.append(
            {
                "id": str(tier.get("id") or f"tier-{index + 1}"),
                "mode": tier_mode,
                "paths": paths,
            }
        )
    return {
        "mode": mode,
        "required_paths": normalized_required_paths,
        "tiers": tiers,
    }


def claimed_paths(payload: dict[str, Any]) -> list[str]:
    paths: set[str] = set()
    for claim in payload.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        for item in claim.get("paths") or []:
            if isinstance(item, str) and item.strip():
                paths.add(normalize_repo_path(item))
    return sorted(paths)


def claim_covers_path(claimed_path: str, changed_path: str) -> bool:
    normalized_claim = normalize_repo_path(claimed_path)
    normalized_changed = normalize_repo_path(changed_path)
    if normalized_claim == ".":
        return True
    if path_matches([normalized_claim], normalized_changed):
        return True
    return normalized_changed.startswith(normalized_claim.rstrip("/") + "/")


def claim_coverage_report(
    registry: dict[str, Any],
    run_id: str | None,
    changed_files: list[str],
) -> dict[str, Any]:
    policy = claim_policy(registry)
    mode = str(policy["mode"])
    if mode == "off" or not run_id:
        return {
            "ok": True,
            "mode": mode,
            "checked": False,
            "run_id": run_id,
            "required_paths": policy["required_paths"],
            "tiers": policy["tiers"],
            "claimed_paths": [],
            "missing_files": [],
            "missing_required_files": [],
            "missing_advisory_files": [],
            "warnings": [],
        }
    _, payload = read_run(registry, run_id)
    claimed = claimed_paths(payload)
    tiers = policy["tiers"] or [{"id": "default", "mode": mode, "paths": policy["required_paths"]}]
    missing_required: list[str] = []
    missing_advisory: list[str] = []
    for item in changed_files:
        matching_tiers = [
            tier
            for tier in tiers
            if not tier.get("paths") or path_matches(tier.get("paths", []), item)
        ]
        if not matching_tiers:
            continue
        if any(claim_covers_path(claimed_path, item) for claimed_path in claimed):
            continue
        if any(tier.get("mode") == "required" for tier in matching_tiers):
            missing_required.append(item)
        else:
            missing_advisory.append(item)
    missing = sorted({*missing_required, *missing_advisory})
    ok = not missing_required
    warnings = [
        f"unclaimed required file under claim_policy: {item}"
        for item in missing_required
    ] + [
        f"unclaimed advisory file under claim_policy: {item}"
        for item in missing_advisory
    ]
    return {
        "ok": ok,
        "mode": mode,
        "checked": True,
        "run_id": run_id,
        "required_paths": policy["required_paths"],
        "tiers": tiers,
        "claimed_paths": claimed,
        "missing_files": missing,
        "missing_required_files": sorted(missing_required),
        "missing_advisory_files": sorted(missing_advisory),
        "warnings": warnings,
    }


def build_verify_report(
    registry: dict[str, Any],
    run_id: str | None,
    files: list[str],
    from_diff: bool,
    include_untracked: bool,
    all_checks: bool,
    execute: bool,
) -> dict[str, Any]:
    if from_diff:
        files = [*files, *changed_files_from_git(include_untracked)]
    normalized_files = sorted({normalize_repo_path(item) for item in files})
    if not from_diff and not normalized_files and not all_checks:
        raise WorkflowError("verify requires --from-diff, --file, or --all")
    context: dict[str, str] = {"run_id": run_id or ""}
    if run_id:
        _, run_payload = read_run(registry, run_id)
        context.update({str(key): str(value) for key, value in (run_payload.get("context") or {}).items()})
    checks = select_diff_checks(registry, normalized_files, all_checks)
    results: list[dict[str, Any]] = []
    for check in checks:
        if execute:
            result = run_check_command(check, context)
        else:
            result = {
                "id": check["id"],
                "description": check.get("description", ""),
                "required": bool(check.get("required", True)),
                "command": command_display(substitute(check["command"], context)),
                "cwd": check.get("cwd", "."),
                "matched_files": check.get("matched_files", []),
                "skipped": True,
                "ok": True,
            }
        results.append(result)
    claim_coverage = claim_coverage_report(registry, run_id, normalized_files)
    ok = all(result.get("ok", False) for result in results) and bool(claim_coverage["ok"])
    report = {
        "ok": ok,
        "run_id": run_id,
        "from_diff": from_diff,
        "include_untracked": include_untracked,
        "execute": execute,
        "changed_files": normalized_files,
        "claim_coverage": claim_coverage,
        "check_count": len(results),
        "checks": results,
    }
    if run_id:
        append_ledger_event(
            registry,
            {
                "event": "agent_workflow_verify",
                "run_id": run_id,
                "ok": ok,
                "execute": execute,
                "from_diff": from_diff,
                "changed_files": normalized_files,
                "claim_coverage": {
                    "mode": claim_coverage.get("mode"),
                    "ok": claim_coverage.get("ok"),
                    "missing_files": claim_coverage.get("missing_files"),
                },
                "checks": [
                    {
                        "id": item.get("id"),
                        "ok": item.get("ok"),
                        "required": item.get("required"),
                        "returncode": item.get("returncode"),
                        "duration_s": item.get("duration_s"),
                    }
                    for item in results
                ],
            },
        )
    return report


def print_verify_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    mode = "executed" if report["execute"] else "planned"
    print(f"agent-workflow verify: {'ok' if report['ok'] else 'failed'} ({mode})")
    print(f"files={len(report['changed_files'])} checks={report['check_count']}")
    claim_coverage = report.get("claim_coverage")
    if isinstance(claim_coverage, dict):
        for warning in claim_coverage.get("warnings") or []:
            print(f"[WARN] claim_policy: {warning}")
    for result in report["checks"]:
        status = "PASS" if result.get("ok") and not result.get("skipped") else "SKIP" if result.get("skipped") else "FAIL"
        print(f"[{status}] {result['id']} :: {result['command']}")


def parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_run_records(registry: dict[str, Any]) -> dict[str, tuple[Path, dict[str, Any]]]:
    run_dir = run_state_dir(registry)
    records: dict[str, tuple[Path, dict[str, Any]]] = {}
    if not run_dir.exists():
        return records
    for path in sorted(run_dir.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            payload = {}
        run_id = payload.get("run_id") if isinstance(payload, dict) else None
        if run_id:
            records[str(run_id)] = (path, payload)
    return records


def load_lock_records(registry: dict[str, Any]) -> list[tuple[Path, dict[str, Any]]]:
    lock_dir = lock_state_dir(registry)
    records: list[tuple[Path, dict[str, Any]]] = []
    if not lock_dir.exists():
        return records
    for path in sorted(lock_dir.glob("*.lock.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            payload = {"run_id": None, "parse_error": True}
        records.append((path, payload if isinstance(payload, dict) else {"run_id": None, "parse_error": True}))
    return records


def ledger_mentions_run(registry: dict[str, Any], run_id: str) -> bool:
    path = ledger_path(registry)
    if not path.exists():
        return False
    needle = f'"run_id": "{run_id}"'
    return needle in path.read_text(encoding="utf-8", errors="replace")


def build_observe_report(registry: dict[str, Any], run_id: str | None) -> dict[str, Any]:
    runs = load_run_records(registry)
    locks = load_lock_records(registry)
    now = datetime.now(UTC)
    findings: list[dict[str, Any]] = []

    selected_runs = {run_id: runs[run_id]} if run_id and run_id in runs else runs
    if run_id and run_id not in runs:
        findings.append(
            {
                "severity": "halt",
                "kind": "run_missing",
                "message": f"run not found: {run_id}",
                "run_id": run_id,
            }
        )

    for lock_path, lock in locks:
        lock_run_id = str(lock.get("run_id") or "")
        if run_id and lock_run_id != run_id:
            continue
        lock_rel = display_path(lock_path)
        if lock.get("parse_error"):
            findings.append(
                {
                    "severity": "halt",
                    "kind": "lock_parse_error",
                    "message": f"lock file is not valid YAML: {lock_rel}",
                    "path": lock_rel,
                }
            )
            continue
        if not lock_run_id or lock_run_id not in runs:
            findings.append(
                {
                    "severity": "halt",
                    "kind": "orphan_lock",
                    "message": f"lock has no matching run record: {lock_rel}",
                    "path": lock_rel,
                    "run_id": lock_run_id or None,
                }
            )
            continue
        expires_at = parse_utc_timestamp(str(lock.get("expires_at") or ""))
        if expires_at and expires_at < now:
            findings.append(
                {
                    "severity": "escalate",
                    "kind": "expired_lock",
                    "message": f"lock expired: {lock_rel}",
                    "path": lock_rel,
                    "run_id": lock_run_id,
                    "expires_at": lock.get("expires_at"),
                }
            )
        run_status = runs[lock_run_id][1].get("status")
        if run_status in {"ok", "failed", "blocked"}:
            findings.append(
                {
                    "severity": "halt",
                    "kind": "closed_run_lock",
                    "message": f"closed run still holds a lock: {lock_rel}",
                    "path": lock_rel,
                    "run_id": lock_run_id,
                    "status": run_status,
                }
            )

    lock_paths_by_run: dict[str, set[str]] = {}
    for lock_path, lock in locks:
        lock_run_id = str(lock.get("run_id") or "")
        if lock_run_id:
            lock_paths_by_run.setdefault(lock_run_id, set()).add(display_path(lock_path))

    for current_run_id, (path, payload) in selected_runs.items():
        expected_locks = set(payload.get("locks") or [])
        if payload.get("status") == "active":
            missing_locks = sorted(expected_locks - lock_paths_by_run.get(current_run_id, set()))
            if missing_locks:
                findings.append(
                    {
                        "severity": "halt",
                        "kind": "active_run_missing_locks",
                        "message": f"active run is missing lock files: {current_run_id}",
                        "run_id": current_run_id,
                        "missing_locks": missing_locks,
                    }
                )
        if not ledger_mentions_run(registry, current_run_id):
            findings.append(
                {
                    "severity": "warn",
                    "kind": "ledger_missing_run",
                    "message": f"ledger has no event for run: {current_run_id}",
                    "run_id": current_run_id,
                    "path": display_path(path),
                }
            )

    severities = {finding["severity"] for finding in findings}
    decision = "escalate" if "escalate" in severities else "halt" if "halt" in severities else "continue"
    report = {
        "ok": decision == "continue",
        "decision": decision,
        "run_count": len(selected_runs),
        "lock_count": len([lock for _, lock in locks if not run_id or str(lock.get("run_id") or "") == run_id]),
        "ledger": display_path(ledger_path(registry)),
        "findings": findings,
    }
    return report


def observe(registry: dict[str, Any], run_id: str | None, as_json: bool) -> int:
    report = build_observe_report(registry, run_id)
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"agent-workflow observe: {report['decision']}")
        print(f"runs={report['run_count']} locks={report['lock_count']} ledger={report['ledger']}")
        for finding in report["findings"]:
            print(f"[{finding['severity'].upper()}] {finding['kind']}: {finding['message']}")
    return 0 if report["decision"] == "continue" else 1


def close_run(
    registry: dict[str, Any],
    run_id: str,
    status: str,
    evidence: list[str],
    release: bool,
) -> dict[str, Any]:
    path, payload = read_run(registry, run_id)
    payload["status"] = status
    payload["updated_at"] = utc_now()
    payload["closed_at"] = utc_now()
    payload.setdefault("evidence", [])
    payload["evidence"].extend(evidence)
    if release:
        payload["released_locks"] = release_locks(registry, payload["run_id"])
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")  # audit-exempt: non-atomic-write — under run_update_lock
    payload["path"] = display_path(path)
    append_ledger_event(
        registry,
        {
            "event": "agent_workflow_close",
            "run_id": payload["run_id"],
            "workflow_id": payload.get("workflow_id"),
            "status": status,
            "evidence": evidence,
            "released_locks": payload.get("released_locks", []),
        },
    )
    return payload


def closeout_run(
    registry: dict[str, Any],
    run_id: str,
    status: str,
    evidence: list[str],
    files: list[str],
    from_diff: bool,
    include_untracked: bool,
    all_checks: bool,
    keep_locks: bool,
) -> dict[str, Any]:
    verify_report = build_verify_report(
        registry,
        run_id,
        files,
        from_diff,
        include_untracked,
        all_checks,
        execute=True,
    )
    observe_report = build_observe_report(registry, run_id)
    if status == "ok" and not verify_report["ok"]:
        raise WorkflowError("closeout blocked: verify failed")
    if status == "ok" and not observe_report["ok"]:
        raise WorkflowError(f"closeout blocked: observe decision={observe_report['decision']}")
    closeout_evidence = [
        *evidence,
        f"agent-workflow verify: {verify_report['check_count']} checks ok={verify_report['ok']}",
        f"agent-workflow observe: {observe_report['decision']}",
    ]
    payload = close_run(registry, run_id, status, closeout_evidence, not keep_locks)
    report = {
        "ok": status == "ok",
        "run": payload,
        "verify": verify_report,
        "observe": observe_report,
    }
    append_ledger_event(
        registry,
        {
            "event": "agent_workflow_closeout",
            "run_id": run_id,
            "status": status,
            "ok": report["ok"],
            "verify_ok": verify_report["ok"],
            "observe_decision": observe_report["decision"],
        },
    )
    if status == "ok":
        try:
            import subprocess
            # 1. Loop Convergence: auto-run evidence-smoke.py (silently)
            smoke_script = WORKSPACE / "bin/evidence-smoke.py"
            subprocess.run(
                [sys.executable, str(smoke_script), "--quiet"],
                cwd=WORKSPACE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            # 2. Sync state officially using omo CLI
            omo_cmd = [
                sys.executable,
                "-m",
                "omo.cli",
                "state",
                "sync",
            ]
            env = os.environ.copy()
            env["PYTHONPATH"] = str(WORKSPACE / "projects/omo/src")
            subprocess.run(
                omo_cmd,
                cwd=str(WORKSPACE / "projects/omo"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                check=False,
            )
            # 3. KOS Knowledge Ingress Sync (Incremental + Ontology Rebuild)
            # Refreshes L2 Knowledge Engine dynamically during closeout
            kos_cli_path = WORKSPACE / "projects/kairon/packages/kos/kos-cli.py"
            if kos_cli_path.is_file():
                env_kos = os.environ.copy()
                env_kos["KOS_HOME"] = str(WORKSPACE / "kos")
                env_kos["PYTHONPATH"] = str(WORKSPACE / "projects/kairon/packages/kos/src")
                # 3.1 Incremental Ingest
                subprocess.run(
                    [sys.executable, str(kos_cli_path), "ingest", "--incremental"],
                    cwd=WORKSPACE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env_kos,
                    check=False,
                )
                # 3.2 Ontology Rebuild
                subprocess.run(
                    [sys.executable, str(kos_cli_path), "onto", "rebuild"],
                    cwd=WORKSPACE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env_kos,
                    check=False,
                )
        except Exception:
            pass
    return report


def ledger_events(registry: dict[str, Any]) -> list[dict[str, Any]]:
    path = ledger_path(registry)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            events.append({"parse_error": True, "raw": line})
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def p74_solidification_report(
    registry: dict[str, Any],
    events: list[dict[str, Any]],
    runs: dict[str, Any],
) -> dict[str, Any]:
    """P74 stage 5 self-evolution report (P74 §4.5).

    Walks every workflow and computes its activation profile:

    - has_recent_run: at least one agent_workflow_start within the window.
    - has_check_coverage: workflow surfaces appear in any diff_checks.paths
      or doctor_checks.paths.

    A workflow is considered silently healthy (no warn) when:
      (has_recent_run) OR (has_check_coverage)
      OR (workflow id is in silent_workflow_policy.excluded_workflows).

    Otherwise it produces a [warn] entry in the report.
    """
    silent_policy = registry.get("silent_workflow_policy") or {}
    excluded = set(str(item) for item in (silent_policy.get("excluded_workflows") or []))

    started_runs: dict[str, str] = {}
    for event in events:
        if str(event.get("event") or "") == "agent_workflow_start":
            workflow_id = str(event.get("workflow_id") or "")
            if workflow_id:
                started_runs[workflow_id] = str(event.get("ts") or "")

    covered_paths: set[str] = set()
    for check in registry.get("diff_checks") or []:
        if isinstance(check, dict):
            for path in check.get("paths") or []:
                if isinstance(path, str):
                    covered_paths.add(path)
    for check in registry.get("doctor_checks") or []:
        if isinstance(check, dict):
            for path in check.get("paths") or []:
                if isinstance(path, str):
                    covered_paths.add(path)

    # Workflows whose id appears in any doctor_checks.command string are
    # covered transitively (e.g. root-agent-workflow-observe runs observer-audit
    # as a side effect of `make gac-local-gate`).
    doctor_commands: list[str] = []
    for check in registry.get("doctor_checks") or []:
        if isinstance(check, dict):
            command = check.get("command") or []
            if isinstance(command, list):
                doctor_commands.extend(str(item) for item in command if isinstance(item, str))

    workflows_summary: list[dict[str, Any]] = []
    for workflow in registry.get("workflows") or []:
        if not isinstance(workflow, dict):
            continue
        workflow_id = str(workflow.get("id") or "")
        surfaces = workflow.get("surfaces") or {}
        write_patterns = surfaces.get("write") if isinstance(surfaces, dict) else None
        read_patterns = surfaces.get("read") if isinstance(surfaces, dict) else None
        workflow_paths = [str(p) for p in (write_patterns or []) if isinstance(p, str)]
        if not workflow_paths:
            workflow_paths = [str(p) for p in (read_patterns or []) if isinstance(p, str)]
        has_check_coverage = any(
            any(fnmatch.fnmatch(p, pattern) for p in covered_paths) for pattern in workflow_paths
        ) if workflow_paths else False
        if not has_check_coverage and workflow_id:
            # Workflow id referenced in a doctor_checks.command string counts
            # as transitive coverage (e.g. observer-audit via root-agent-workflow-observe).
            has_check_coverage = any(workflow_id in command for command in doctor_commands)
        last_start = started_runs.get(workflow_id, "")
        has_recent_run = bool(last_start)
        excluded_workflow = workflow_id in excluded
        silent_health = "active" if has_recent_run or has_check_coverage else (
            "excluded" if excluded_workflow else "warn"
        )
        workflows_summary.append(
            {
                "workflow_id": workflow_id,
                "has_recent_run": has_recent_run,
                "last_start_ts": last_start,
                "has_check_coverage": has_check_coverage,
                "silent_health": silent_health,
                "agents": workflow.get("agents"),
            }
        )

    warn_count = sum(1 for item in workflows_summary if item["silent_health"] == "warn")
    return {
        "ok": warn_count == 0,
        "policy": silent_policy,
        "summary_count": len(workflows_summary),
        "warn_count": warn_count,
        "workflows": workflows_summary,
    }


def compliance_report(registry: dict[str, Any], run_id: str | None) -> dict[str, Any]:
    runs = load_run_records(registry)
    events = ledger_events(registry)
    observe_report = build_observe_report(registry, run_id)
    findings: list[dict[str, Any]] = []
    event_names_by_run: dict[str, set[str]] = {}
    for event in events:
        current_run_id = str(event.get("run_id") or "")
        if current_run_id:
            event_names_by_run.setdefault(current_run_id, set()).add(str(event.get("event") or ""))
        if event.get("parse_error"):
            findings.append(
                {
                    "severity": "halt",
                    "kind": "ledger_parse_error",
                    "message": "ledger contains a non-JSON line",
                }
            )
    selected_runs = {run_id: runs[run_id]} if run_id and run_id in runs else runs
    if run_id and run_id not in runs:
        findings.append(
            {
                "severity": "halt",
                "kind": "run_missing",
                "message": f"run not found: {run_id}",
                "run_id": run_id,
            }
        )
    for current_run_id, (_, payload) in selected_runs.items():
        status = payload.get("status")
        evidence = payload.get("evidence") or []
        if status == "active":
            findings.append(
                {
                    "severity": "warn",
                    "kind": "active_run",
                    "message": f"run is still active: {current_run_id}",
                    "run_id": current_run_id,
                }
            )
        if status == "ok" and not evidence:
            findings.append(
                {
                    "severity": "halt",
                    "kind": "closed_run_missing_evidence",
                    "message": f"closed run has no evidence: {current_run_id}",
                    "run_id": current_run_id,
                }
            )
        event_names = event_names_by_run.get(current_run_id, set())
        if status == "ok" and "agent_workflow_verify" not in event_names:
            findings.append(
                {
                    "severity": "warn",
                    "kind": "closed_run_missing_verify_event",
                    "message": f"closed run has no verify event: {current_run_id}",
                    "run_id": current_run_id,
                }
            )
        close_event_names = {"agent_workflow_closeout", "agent_workflow_close"}
        if status == "ok" and not event_names.intersection(close_event_names):
            findings.append(
                {
                    "severity": "warn",
                    "kind": "closed_run_missing_closeout_event",
                    "message": f"closed run did not use closeout: {current_run_id}",
                    "run_id": current_run_id,
                }
            )
    severities = {finding["severity"] for finding in [*findings, *observe_report["findings"]]}
    decision = "halt" if "halt" in severities else "escalate" if "escalate" in severities else "continue"
    p74_report = p74_solidification_report(registry, events, runs)
    return {
        "ok": decision == "continue",
        "decision": decision,
        "run_count": len(selected_runs),
        "event_count": len(events),
        "observe": observe_report,
        "findings": findings,
        "slo": registry.get("compliance_slo") or {},
        "p74_solidification": p74_report,
    }


def print_compliance_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"agent-workflow compliance: {report['decision']}")
    print(f"runs={report['run_count']} events={report['event_count']}")
    for finding in report["findings"]:
        print(f"[{finding['severity'].upper()}] {finding['kind']}: {finding['message']}")
    for finding in report["observe"]["findings"]:
        print(f"[{finding['severity'].upper()}] {finding['kind']}: {finding['message']}")
    p74 = report.get("p74_solidification") or {}
    if p74:
        ok = "OK" if p74.get("ok") else "WARN"
        print(f"P74 solidification: [{ok}] {p74.get('warn_count', 0)} silent workflow(s)")
        for wf in p74.get("workflows", []):
            if wf.get("silent_health") != "active":
                print(
                    f"  - {wf['workflow_id']}: {wf['silent_health']} "
                    f"(run={wf['has_recent_run']}, check={wf['has_check_coverage']})"
                )


def last_ledger_event(
    events: list[dict[str, Any]],
    names: set[str],
) -> dict[str, Any] | None:
    for event in reversed(events):
        if str(event.get("event") or "") in names:
            return event
    return None


def staged_lane_report() -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "bin/change-lane-check.py", "--staged", "--json"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "lanes": payload.get("lanes", []),
        "files": payload.get("files", []),
        "message": payload.get("message") or completed.stderr.strip(),
    }


def recommended_next(status: dict[str, Any]) -> str:
    if status["stale_locks"] > 0:
        return "Run `agent-workflow observe` and inspect stale locks before editing."
    claim_coverage = status.get("claim_coverage")
    if isinstance(claim_coverage, dict) and claim_coverage.get("missing_files"):
        run_id = status.get("current_run_id") or "<run-id>"
        return f"Claim missing files with `agent-workflow claim {run_id} --path <path>`."
    if status["active_runs"]:
        run_id = status["active_runs"][0]
        return f"Continue with `agent-workflow verify {run_id} --from-diff --execute` or closeout."
    if not status["staged_lane"]["ok"]:
        return "Resolve the staged lane split or use a run-scoped/file-scoped gate for AGCP work."
    return "Start a governed run with `agent-workflow start <workflow-id> --profile <agent-profile>`."


def build_status_report(
    registry: dict[str, Any],
    include_health: bool,
    include_agcp_drift: bool = True,
) -> dict[str, Any]:
    runs = load_run_records(registry)
    active_runs = sorted(
        run_id for run_id, (_, payload) in runs.items() if payload.get("status") == "active"
    )
    closed_runs = sorted(
        run_id for run_id, (_, payload) in runs.items() if payload.get("status") in {"ok", "failed", "blocked"}
    )
    observe_report = build_observe_report(registry, None)
    compliance = compliance_report(registry, None)
    events = ledger_events(registry)
    staged_lane = staged_lane_report()
    stale_locks = len(
        [finding for finding in observe_report["findings"] if finding.get("kind") == "expired_lock"]
    )
    current_run_id = active_runs[0] if len(active_runs) == 1 else None
    changed_files = changed_files_from_git(include_untracked=False)
    policy = claim_policy(registry)
    claim_coverage = claim_coverage_report(registry, current_run_id, changed_files) if current_run_id else {
        "ok": True,
        "mode": policy["mode"],
        "checked": False,
        "run_id": current_run_id,
        "required_paths": policy["required_paths"],
        "tiers": policy["tiers"],
        "claimed_paths": [],
        "missing_files": [],
        "missing_required_files": [],
        "missing_advisory_files": [],
        "warnings": ["multiple active runs; pass a run id to verify/closeout"] if len(active_runs) > 1 else [],
    }
    health = build_doctor_report(registry, include_agcp_drift) if include_health else None
    report = {
        "ok": observe_report["decision"] == "continue"
        and compliance["decision"] == "continue"
        and (health is None or bool(health["ok"])),
        "active_runs": active_runs,
        "closed_runs": closed_runs,
        "run_count": len(runs),
        "lock_count": observe_report["lock_count"],
        "stale_locks": stale_locks,
        "current_run_id": current_run_id,
        "last_verify": last_ledger_event(events, {"agent_workflow_verify"}),
        "last_closeout": last_ledger_event(events, {"agent_workflow_closeout", "agent_workflow_close"}),
        "compliance": {
            "ok": compliance["ok"],
            "decision": compliance["decision"],
            "slo": compliance["slo"],
            "findings": compliance["findings"],
            "observe_findings": compliance["observe"]["findings"],
        },
        "staged_lane": staged_lane,
        "changed_files": changed_files,
        "claim_coverage": claim_coverage,
        "health": None if health is None else {"ok": health["ok"], "checks": check_summary(health["checks"])},
    }
    report["recommended_next"] = recommended_next(report)
    return report


def print_status_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"agent-workflow status: {'ok' if report['ok'] else 'attention'}")
    print(
        f"runs active={len(report['active_runs'])} closed={len(report['closed_runs'])} "
        f"locks={report['lock_count']} stale={report['stale_locks']}"
    )
    staged_lane = report["staged_lane"]
    print(f"staged_lane={'PASS' if staged_lane['ok'] else 'WARN'} lanes={','.join(staged_lane['lanes']) or '-'}")
    claim_coverage = report.get("claim_coverage")
    if isinstance(claim_coverage, dict):
        for warning in claim_coverage.get("warnings") or []:
            print(f"[WARN] claim_policy: {warning}")
    print(f"compliance={report['compliance']['decision']}")
    print(f"next: {report['recommended_next']}")


def handoff_markdown(payload: dict[str, Any]) -> str:
    plan = payload.get("plan", {})
    context = payload.get("context", {})
    lines = [
        f"# Agent Workflow Handoff: {payload.get('run_id')}",
        "",
        f"- workflow: `{payload.get('workflow_id')}`",
        f"- status: `{payload.get('status')}`",
        f"- actor: `{payload.get('actor')}`",
        f"- agent_profile: `{payload.get('agent_profile') or context.get('profile') or '-'}`",
        f"- objective: {payload.get('objective') or '(none)'}",
        f"- created_at: `{payload.get('created_at')}`",
        f"- updated_at: `{payload.get('updated_at')}`",
        f"- project: `{context.get('project') or '-'}`",
        f"- source_file: `{context.get('source_file') or '-'}`",
        "",
        "## Locks",
    ]
    locks = payload.get("locks") or []
    if locks:
        lines.extend(f"- `{lock}`" for lock in locks)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Resume",
            "",
            "```bash",
            f"uv run --with pyyaml python bin/agent-workflow.py resume {payload.get('run_id')}",
            "uv run --with pyyaml python bin/agent-workflow.py doctor",
            "```",
            "",
            "## Verification Plan",
        ]
    )
    for item in plan.get("phases", {}).get("verification", []):
        lines.append(f"- `{item.get('mode')}` {item.get('id')}: `{command_display(item.get('command', []))}`")
    lines.extend(["", "## Evidence"])
    evidence = payload.get("evidence") or []
    if evidence:
        lines.extend(f"- {entry}" for entry in evidence)
    else:
        lines.append("- none yet")
    return "\n".join(lines)


def run_doctor_check(check_item: dict[str, Any]) -> dict[str, Any]:
    command = check_item["command"]
    env = os.environ.copy()
    # Nested `uv run` invocations inherit the runner's temporary VIRTUAL_ENV and
    # otherwise emit noisy mismatch warnings for project-local checks.
    env.pop("VIRTUAL_ENV", None)
    try:
        completed = subprocess.run(
            command,
            cwd=WORKSPACE,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        ok = completed.returncode == 0
        return {
            "id": check_item["id"],
            "description": check_item.get("description", ""),
            "required": bool(check_item.get("required", True)),
            "command": command_display(command),
            "ok": ok,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip()[-1000:],
            "stderr": completed.stderr.strip()[-1000:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "id": check_item["id"],
            "description": check_item.get("description", ""),
            "required": bool(check_item.get("required", True)),
            "command": command_display(command),
            "ok": False,
            "error": str(exc),
        }


def build_doctor_report(registry: dict[str, Any], include_agcp_drift: bool = True) -> dict[str, Any]:
    integrations = integration_rows(registry)
    for integration in integrations:
        name = str(integration["name"])
        health = None
        health_command = integration.get("health_command")
        health_required = bool(integration.get("health_required", False))
        if isinstance(health_command, list) and health_command:
            health = run_doctor_check(
                {
                    "id": f"integration-{name}-health",
                    "description": f"Internal integration health check for {name}.",
                    "required": health_required,
                    "command": health_command,
                }
            )
        integration["health"] = health

    adapters = adapter_rows(registry)
    for adapter in adapters:
        name = str(adapter["name"])
        health = None
        health_command = adapter.get("health_command")
        health_required = bool(adapter.get("health_required", False))
        if isinstance(health_command, list) and health_command:
            health = run_doctor_check(
                {
                    "id": f"adapter-{name}-health",
                    "description": f"External adapter health check for {name}.",
                    "required": health_required,
                    "command": health_command,
                }
            )
        adapter["health"] = health
    checks = [run_doctor_check(item) for item in registry.get("doctor_checks", [])]
    if include_agcp_drift:
        checks.insert(0, agcp_drift_check(registry))
    required_integration_health = [
        integration["health"]
        for integration in integrations
        if integration.get("health_required") and isinstance(integration.get("health"), dict)
    ]
    required_adapter_health = [
        adapter["health"]
        for adapter in adapters
        if adapter.get("health_required") and isinstance(adapter.get("health"), dict)
    ]
    ok = all(
        (not item["required"]) or item["ok"]
        for item in [*checks, *required_integration_health, *required_adapter_health]
    )
    return {
        "ok": ok,
        "registry": str(REGISTRY_PATH.relative_to(WORKSPACE)),
        "integrations": integrations,
        "adapters": adapters,
        "checks": checks,
    }


def print_doctor_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"registry: {report['registry']}")
    for integration in report["integrations"]:
        health = integration.get("health")
        health_status = ""
        if isinstance(health, dict):
            label = "PASS" if health["ok"] else ("FAIL" if integration.get("health_required") else "WARN")
            health_status = f" health={label}"
        print(
            f"{integration['name']:<14} {integration['status']:<12} "
            f"{integration['authority']:<16}{health_status}"
        )
    for adapter in report["adapters"]:
        status = "available" if adapter["available"] else "missing"
        suffix = f" ({adapter['path']})" if adapter["path"] else ""
        health = adapter.get("health")
        if isinstance(health, dict):
            health_status = "PASS" if health["ok"] else ("FAIL" if adapter.get("health_required") else "WARN")
            suffix += f" health={health_status}"
        print(f"{adapter['name']:<14} {status}{suffix}")
    for item in report["checks"]:
        status = "PASS" if item["ok"] else ("WARN" if not item["required"] else "FAIL")
        print(f"[{status}] {item['id']} :: {item['command']}")
        if not item["ok"] and item.get("stderr"):
            print(item["stderr"], file=sys.stderr)


def doctor(registry: dict[str, Any], as_json: bool, include_agcp_drift: bool = True) -> int:
    report = build_doctor_report(registry, include_agcp_drift)
    print_doctor_report(report, as_json)
    return 0 if report["ok"] else 1


def health_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for row in rows:
        health = row.get("health")
        summary.append(
            {
                "name": row.get("name"),
                "status": row.get("status"),
                "authority": row.get("authority"),
                "required": bool(row.get("health_required", False)),
                "health_ok": health.get("ok") if isinstance(health, dict) else None,
                "command": health.get("command") if isinstance(health, dict) else command_display(row.get("health_command", [])),
                "advisory": not bool(row.get("health_required", False)),
            }
        )
    return summary


def check_summary(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": check.get("id"),
            "required": bool(check.get("required", True)),
            "ok": bool(check.get("ok", False)),
            "command": check.get("command"),
        }
        for check in checks
    ]


def bootstrap_report(
    registry: dict[str, Any],
    include_health: bool,
    include_agcp_drift: bool = True,
) -> dict[str, Any]:
    errors, warnings = lint_registry(registry, include_agcp_drift)
    doctor_report = build_doctor_report(registry, include_agcp_drift) if include_health else None
    integrations = (
        doctor_report["integrations"] if isinstance(doctor_report, dict) else integration_rows(registry)
    )
    adapters = doctor_report["adapters"] if isinstance(doctor_report, dict) else adapter_rows(registry)
    ok = not errors and (doctor_report is None or bool(doctor_report["ok"]))
    return {
        "ok": ok,
        "registry": str(REGISTRY_PATH.relative_to(WORKSPACE)),
        "version": registry.get("version"),
        "ssot": registry.get("ssot", {}),
        "runner": registry.get("runner", {}),
        "lint": {"ok": not errors, "errors": errors, "warnings": warnings},
        "workflows": workflow_rows(registry),
        "agent_profiles": agent_rows(registry),
        "integrations": [
            {key: value for key, value in row.items() if key != "health"}
            for row in integrations
        ],
        "adapters": [
            {key: value for key, value in row.items() if key != "health"}
            for row in adapters
        ],
        "health": None
        if doctor_report is None
        else {
            "ok": doctor_report["ok"],
            "integrations": health_summary(doctor_report["integrations"]),
            "adapters": health_summary(doctor_report["adapters"]),
            "checks": check_summary(doctor_report["checks"]),
        },
        "next_commands": {
            "status": "uv run --with pyyaml python bin/agent-workflow.py status --json",
            "start": "uv run --with pyyaml python bin/agent-workflow.py start <workflow-id> --profile <agent-profile> --objective \"<summary>\"",
            "claim": "uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path <path>",
            "verify": "uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute",
            "closeout": "uv run --with pyyaml python bin/agent-workflow.py closeout <run-id>",
            "compliance": "uv run --with pyyaml python bin/agent-workflow.py compliance",
            "doctor": "uv run --with pyyaml python bin/agent-workflow.py doctor",
            "gate": "make gac-local-gate",
            "scoped_gate": "uv run --with pyyaml python bin/gac-local-gate.py --scope files --file <path> --json",
        },
    }


def print_bootstrap_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"registry: {report['registry']}")
    print(f"lint: {'PASS' if report['lint']['ok'] else 'FAIL'}")
    for warning in report["lint"]["warnings"]:
        print(f"[WARN] {warning}")
    health = report.get("health")
    if isinstance(health, dict):
        print(f"health: {'PASS' if health['ok'] else 'FAIL'}")
    print("\nworkflows:")
    for row in report["workflows"]:
        print(f"  {row['id']:<28} {row['title']}")
    print("\nagent profiles:")
    for row in report["agent_profiles"]:
        print(f"  {row['id']:<20} workflows={len(row['allowed_workflows'])} lanes={','.join(row['can_write_lanes'])}")
    print("\ninternal integrations:")
    for row in report["integrations"]:
        print(f"  {row['name']:<14} {row['authority']:<16} owner={row['owner']}")
    print("\nexternal adapters:")
    for row in report["adapters"]:
        availability = "available" if row["available"] else "missing"
        command = row["command"] or row["skill"] or "-"
        print(f"  {row['name']:<14} {row['authority']:<16} {availability} command={command}")
    print("\nnext:")
    for command in report["next_commands"].values():
        print(f"  {command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run executable project governance workflows")
    parser.add_argument("--registry", default=str(REGISTRY_PATH), help="Workflow registry path")
    sub = parser.add_subparsers(dest="command", required=True)

    p_lint = sub.add_parser("lint", help="Validate the workflow registry")
    p_lint.add_argument("--json", action="store_true")

    p_doctor = sub.add_parser("doctor", help="Report optional adapter availability")
    p_doctor.add_argument("--json", action="store_true")

    p_observe = sub.add_parser("observe", help="Read-only observer audit for workflow runs and locks")
    p_observe.add_argument("run_id", nargs="?")
    p_observe.add_argument("--json", action="store_true")

    p_status = sub.add_parser("status", help="Show AGCP run, lock, claim, compliance, and lane status")
    p_status.add_argument("--json", action="store_true")
    p_status.add_argument("--health", action="store_true", help="Include doctor health checks")

    p_claim = sub.add_parser("claim", help="Claim paths or governance surfaces for an active run")
    p_claim.add_argument("run_id")
    p_claim.add_argument("--path", action="append", default=[])
    p_claim.add_argument("--surface", action="append", default=[])
    p_claim.add_argument("--actor", default=os.environ.get("USER", "agent"))
    p_claim.add_argument("--force-lock", action="store_true")
    p_claim.add_argument("--json", action="store_true")

    p_verify = sub.add_parser("verify", help="Select and optionally run checks for changed files")
    p_verify.add_argument("run_id", nargs="?")
    p_verify.add_argument("--from-diff", action="store_true")
    p_verify.add_argument("--file", action="append", default=[])
    p_verify.add_argument("--include-untracked", action="store_true")
    p_verify.add_argument("--all", action="store_true", dest="all_checks")
    p_verify.add_argument("--execute", action="store_true")
    p_verify.add_argument("--json", action="store_true")

    p_compliance = sub.add_parser("compliance", help="Audit run, lock, ledger, and evidence compliance")
    p_compliance.add_argument("run_id", nargs="?")
    p_compliance.add_argument("--json", action="store_true")

    p_list = sub.add_parser("list", help="List workflows")
    p_list.add_argument("--json", action="store_true")

    p_agents = sub.add_parser("agents", help="List registered agent profiles")
    p_agents.add_argument("--json", action="store_true")

    p_adapters = sub.add_parser("adapters", help="List external adapter contracts")
    p_adapters.add_argument("--json", action="store_true")

    p_integrations = sub.add_parser("integrations", help="List internal integration contracts")
    p_integrations.add_argument("--json", action="store_true")

    p_bootstrap = sub.add_parser("bootstrap", help="Show one-shot startup context for agents")
    p_bootstrap.add_argument("--json", action="store_true")
    p_bootstrap.add_argument("--skip-health", action="store_true")

    p_context = sub.add_parser("context", help="Alias for bootstrap")
    p_context.add_argument("--json", action="store_true")
    p_context.add_argument("--skip-health", action="store_true")

    p_show = sub.add_parser("show", help="Show a workflow plan")
    p_show.add_argument("workflow_id")
    p_show.add_argument("--project", default="")
    p_show.add_argument("--format", default="openspec")
    p_show.add_argument("--source-file", default="")
    p_show.add_argument("--run-id", default="")
    p_show.add_argument("--profile", default="")
    p_show.add_argument("--json", action="store_true")

    p_run = sub.add_parser("run", help="Run or print a workflow stage")
    p_run.add_argument("workflow_id")
    p_run.add_argument("--stage", default="preflight")
    p_run.add_argument("--execute", action="store_true", help="Actually run non-manual commands")
    p_run.add_argument("--project", default="")
    p_run.add_argument("--format", default="openspec")
    p_run.add_argument("--source-file", default="")
    p_run.add_argument("--run-id", default="")
    p_run.add_argument("--profile", default="")
    p_run.add_argument("--json", action="store_true")

    p_start = sub.add_parser("start", help="Create a resumable workflow run record")
    p_start.add_argument("workflow_id")
    p_start.add_argument("--project", default="")
    p_start.add_argument("--format", default="openspec")
    p_start.add_argument("--source-file", default="")
    p_start.add_argument("--actor", default=os.environ.get("USER", "agent"))
    p_start.add_argument("--profile", default="")
    p_start.add_argument("--objective", default="")
    p_start.add_argument("--dry-run", action="store_true")
    p_start.add_argument("--force-lock", action="store_true")
    p_start.add_argument("--json", action="store_true")

    p_resume = sub.add_parser("resume", help="Show a resumable run plan")
    p_resume.add_argument("run_id")
    p_resume.add_argument("--json", action="store_true")

    p_show_run = sub.add_parser("show-run", help="Show a run record")
    p_show_run.add_argument("run_id")
    p_show_run.add_argument("--json", action="store_true")

    p_handoff = sub.add_parser("handoff", help="Print a compression-safe handoff note")
    p_handoff.add_argument("run_id")
    p_handoff.add_argument("--json", action="store_true")

    p_close = sub.add_parser("close", help="Close a workflow run")
    p_close.add_argument("run_id")
    p_close.add_argument("--status", choices=["ok", "failed", "blocked"], required=True)
    p_close.add_argument("--evidence", action="append", default=[])
    p_close.add_argument("--keep-locks", action="store_true")
    p_close.add_argument("--json", action="store_true")

    p_closeout = sub.add_parser("closeout", help="Verify, observe, record evidence, and close a run")
    p_closeout.add_argument("run_id")
    p_closeout.add_argument("--status", choices=["ok", "failed", "blocked"], default="ok")
    p_closeout.add_argument("--evidence", action="append", default=[])
    p_closeout.add_argument("--from-diff", action="store_true")
    p_closeout.add_argument("--file", action="append", default=[])
    p_closeout.add_argument("--include-untracked", action="store_true")
    p_closeout.add_argument("--all", action="store_true", dest="all_checks")
    p_closeout.add_argument("--keep-locks", action="store_true")
    p_closeout.add_argument("--json", action="store_true")

    p_suggest = sub.add_parser(
        "suggest",
        help="Advisory workflow suggestion for a set of changed files (P74 stage 3).",
    )
    p_suggest.add_argument("--file", action="append", default=[])
    p_suggest.add_argument("--from-diff", action="store_true")
    p_suggest.add_argument("--include-untracked", action="store_true")
    p_suggest.add_argument("--profile", default="")
    p_suggest.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        registry_path = Path(args.registry)
        registry = load_registry(registry_path)
        include_agcp_drift = is_default_registry_path(registry_path)
        if args.command == "lint":
            errors, warnings = lint_registry(registry, include_agcp_drift)
            print_lint(errors, warnings, args.json)
            return 0 if not errors else 1
        if args.command == "doctor":
            return doctor(registry, args.json, include_agcp_drift)
        if args.command == "observe":
            return observe(registry, args.run_id, args.json)
        if args.command == "status":
            report = build_status_report(registry, args.health, include_agcp_drift)
            print_status_report(report, args.json)
            return 0 if report["ok"] else 1
        if args.command == "claim":
            claim = claim_run(
                registry,
                args.run_id,
                args.actor,
                args.path,
                args.surface,
                args.force_lock,
            )
            if args.json:
                print(json.dumps(claim, ensure_ascii=False, indent=2))
            else:
                print(f"claimed {claim['run_id']}")
                for scope in claim["scopes"]:
                    print(f"- {scope}")
            return 0
        if args.command == "verify":
            report = build_verify_report(
                registry,
                args.run_id,
                args.file,
                args.from_diff,
                args.include_untracked,
                args.all_checks,
                args.execute,
            )
            print_verify_report(report, args.json)
            return 0 if report["ok"] else 1
        if args.command == "compliance":
            report = compliance_report(registry, args.run_id)
            print_compliance_report(report, args.json)
            return 0 if report["ok"] else 1
        if args.command == "list":
            list_workflows(registry, args.json)
            return 0
        if args.command == "agents":
            list_agents(registry, args.json)
            return 0
        if args.command == "adapters":
            list_adapters(registry, args.json)
            return 0
        if args.command == "integrations":
            list_integrations(registry, args.json)
            return 0
        if args.command in {"bootstrap", "context"}:
            report = bootstrap_report(registry, not args.skip_health, include_agcp_drift)
            print_bootstrap_report(report, args.json)
            return 0 if report["ok"] else 1
        if args.command == "suggest":
            files = list(args.file or [])
            if args.from_diff:
                files.extend(changed_files_from_git(args.include_untracked))
            return suggest_command(registry, files, args.profile, args.json)
        if args.command == "show":
            workflow = workflow_by_id(registry, args.workflow_id)
            context = context_from_args(args)
            validate_agent_profile(registry, workflow, context["profile"], require=False)
            print_plan(workflow_plan(workflow, context), args.json)
            return 0
        if args.command == "run":
            workflow = workflow_by_id(registry, args.workflow_id)
            context = context_from_args(args)
            validate_agent_profile(registry, workflow, context["profile"], require=args.execute)
            return run_stage(workflow, args.stage, context, args.execute, args.json)
        if args.command == "start":
            workflow = workflow_by_id(registry, args.workflow_id)
            record = start_run(
                registry,
                workflow,
                context_from_args(args),
                args.objective,
                args.dry_run,
                args.force_lock,
            )
            if args.json:
                print(json.dumps(record, ensure_ascii=False, indent=2))
            else:
                print(f"started {record['run_id']}")
                if record.get("path"):
                    print(record["path"])
            return 0
        if args.command in {"resume", "show-run"}:
            _, payload = read_run(registry, args.run_id)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print_plan(payload["plan"], False)
            return 0
        if args.command == "handoff":
            _, payload = read_run(registry, args.run_id)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(handoff_markdown(payload))
            return 0
        if args.command == "close":
            payload = close_run(registry, args.run_id, args.status, args.evidence, not args.keep_locks)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"closed {payload['run_id']} as {payload['status']}")
            return 0
        if args.command == "closeout":
            report = closeout_run(
                registry,
                args.run_id,
                args.status,
                args.evidence,
                args.file,
                args.from_diff or not args.file,
                args.include_untracked,
                args.all_checks,
                args.keep_locks,
            )
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print(f"closeout {report['run']['run_id']} as {report['run']['status']}")
                print(f"verify checks={report['verify']['check_count']} ok={report['verify']['ok']}")
                print(f"observe={report['observe']['decision']}")
            return 0 if report["ok"] else 1
    except WorkflowError as exc:
        print(f"agent-workflow: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
