from __future__ import annotations

import argparse
import fnmatch
import shlex
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

WORKSPACE = Path(__file__).resolve().parents[5]
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
    documents = [
        doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc
    ]
    merged: dict[str, Any] = {}
    workflows_doc: dict[str, Any] | None = None
    for document in documents:
        if not isinstance(document, dict):
            continue
        if "workflows" in document and workflows_doc is None:
            workflows_doc = document
        for key, value in document.items():
            if key == "workflows":
                continue
            merged[key] = value
    if workflows_doc is None:
        raise WorkflowError(f"workflow registry has no workflows document: {path}")
    merged["workflows"] = workflows_doc["workflows"]
    return merged


def is_default_registry_path(path: Path) -> bool:
    candidate = path if path.is_absolute() else WORKSPACE / path
    try:
        return candidate.resolve() == REGISTRY_PATH.resolve()
    except OSError:
        return False


def load_yaml_document_with(
    path: Path, key: str
) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"missing file: {display_path(path)}"
    try:
        documents = [
            doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc
        ]
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
            raise WorkflowError(
                f"{workflow_id} requires --profile ({', '.join(roles)})"
            )
        return
    profiles = registry.get("agent_profiles") or {}
    profile = profiles.get(profile_id) if isinstance(profiles, dict) else None
    if not isinstance(profile, dict):
        raise WorkflowError(f"unknown agent profile: {profile_id}")
    allowed = profile.get("allowed_workflows", [])
    if allowed != ["*"] and workflow_id not in allowed:
        raise WorkflowError(
            f"agent profile {profile_id} cannot run workflow {workflow_id}"
        )
    if roles and profile_id not in roles:
        raise WorkflowError(
            f"agent profile {profile_id} is not listed in {workflow_id}.agents.roles"
        )


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
        completed = subprocess.run(
            command, cwd=WORKSPACE, capture_output=True, text=True, check=False
        )
        if completed.returncode != 0:
            raise WorkflowError(
                f"failed to inspect changed files: {command_display(command)}"
            )
        for line in completed.stdout.splitlines():
            if line.strip():
                changed.add(normalize_repo_path(line.strip()))
    return sorted(changed)


def path_matches(patterns: list[str], path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE))
    except ValueError:
        return str(path)


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
        for profile_id, profile in sorted(
            (registry.get("agent_profiles") or {}).items()
        )
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
