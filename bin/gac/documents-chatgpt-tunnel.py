#!/usr/bin/env python3
"""Render and check the ChatGPT Secure MCP Tunnel prerequisites."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT_REGISTRY = (
    WORKSPACE / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
)
DEFAULT_DOMAIN_REGISTRY = Path(
    os.environ.get(
        "L4_DOMAIN_REGISTRY",
        str(
            Path.home() / "Documents" / "@公共" / "_control" / "L4-DOMAIN-REGISTRY.yaml"
        ),
    )
)
EXPECTED_TOOLS = [
    "workspace_context",
    "domain_context",
    "cards_status",
    "cards_check",
    "domain_facts_validation_status",
    "domain_controller_shadow_status",
    "domain_model_freshness_status",
    "domain_sanyi_status_consistency_status",
]


class ContractError(ValueError):
    """The declared tunnel contract is unavailable or invalid."""


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be a mapping")
    return value


def _regular_file(path: Path, label: str) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ContractError(f"{label} unavailable: {path}") from exc
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise ContractError(f"{label} must be a regular file: {path}")
    return metadata


def _read_yaml(path: Path, label: str) -> dict[str, Any]:
    _regular_file(path, label)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ContractError(f"{label} unavailable: {path}: {exc}") from exc
    return _mapping(raw, label)


def _workspace_root(registry: Path) -> Path:
    if registry.name != "documents-domain-projects.yaml":
        raise ContractError("project registry must be documents-domain-projects.yaml")
    return registry.parent.parent.parent.parent


def _regular_executable(path: Path, label: str) -> None:
    metadata = _regular_file(path, label)
    if metadata.st_mode & 0o111 == 0:
        raise ContractError(f"{label} must be executable: {path}")


def _plan(project_registry: Path, domain_registry: Path) -> dict[str, Any]:
    raw = _read_yaml(project_registry, "project registry")
    client = _mapping(
        _mapping(raw.get("clients"), "clients").get("chatgpt_web"),
        "clients.chatgpt_web",
    )
    contract = _mapping(
        client.get("tunnel_contract"), "clients.chatgpt_web.tunnel_contract"
    )
    profiles = _mapping(raw.get("profiles"), "profiles")
    profile_id = contract.get("tool_profile")
    if not isinstance(profile_id, str) or not profile_id:
        raise ContractError(
            "clients.chatgpt_web.tunnel_contract.tool_profile must be a string"
        )
    profile = _mapping(profiles.get(profile_id), f"profiles.{profile_id}")
    allowed_tools = profile.get("allowed_workspace_tools")
    if allowed_tools != EXPECTED_TOOLS:
        raise ContractError(
            f"profiles.{profile_id}.allowed_workspace_tools must match the bounded Documents read tools"
        )
    if profile.get("execution_policy") != "workspace_only":
        raise ContractError(
            f"profiles.{profile_id}.execution_policy must be workspace_only"
        )
    expected_contract = {
        "owner": "workspace",
        "checker_ref": "bin/gac/documents-chatgpt-tunnel.py",
        "transport": "secure_mcp_tunnel",
        "local_entrypoint": "cockpit-documents-mcp",
        "tool_profile": "content-domain",
        "tunnel_profile": "documents-readonly",
        "tunnel_id_env": "DOCUMENTS_CHATGPT_TUNNEL_ID",
        "api_key_env": "CONTROL_PLANE_API_KEY",
    }
    if contract != expected_contract:
        raise ContractError(
            "clients.chatgpt_web.tunnel_contract does not match the Workspace contract"
        )
    workspace = _workspace_root(project_registry)
    checker = workspace / str(contract["checker_ref"])
    _regular_file(checker, "tunnel checker")
    _regular_file(domain_registry, "domain registry")
    entrypoint = (
        workspace
        / "projects"
        / "cockpit"
        / ".venv"
        / "bin"
        / str(contract["local_entrypoint"])
    )
    _regular_executable(entrypoint, "Documents MCP entrypoint")
    return {
        "ok": True,
        "status": "plan",
        "transport": contract["transport"],
        "tunnel_profile": contract["tunnel_profile"],
        "mcp_command": str(entrypoint),
        "tool_profile": profile_id,
        "allowed_tools": list(allowed_tools),
        "required_environment": [
            str(contract["api_key_env"]),
            str(contract["tunnel_id_env"]),
        ],
        "tunnel_ref": client.get("tunnel_ref"),
    }


def _check(plan: dict[str, Any], tunnel_client: Path | None) -> dict[str, Any]:
    errors: list[str] = []
    client = tunnel_client
    if client is None:
        resolved = shutil.which("tunnel-client")
        client = Path(resolved) if resolved else None
    if client is None:
        errors.append("tunnel-client unavailable")
    else:
        try:
            _regular_executable(client, "tunnel-client")
        except ContractError:
            errors.append(f"tunnel-client unavailable: {client}")
    for name in plan["required_environment"]:
        if not os.environ.get(name, "").strip():
            errors.append(f"{name} is required")
    if not errors and client is not None:
        try:
            doctor = subprocess.run(
                [
                    str(client.resolve()),
                    "doctor",
                    "--profile",
                    str(plan["tunnel_profile"]),
                    "--explain",
                ],
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            errors.append("tunnel-client doctor unavailable")
        else:
            if doctor.returncode != 0:
                errors.append(f"tunnel-client doctor failed (exit {doctor.returncode})")
    return {
        "ok": not errors,
        "status": "ready" if not errors else "unavailable",
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("render", "check"))
    parser.add_argument(
        "--project-registry", type=Path, default=DEFAULT_PROJECT_REGISTRY
    )
    parser.add_argument("--domain-registry", type=Path, default=DEFAULT_DOMAIN_REGISTRY)
    parser.add_argument("--tunnel-client", type=Path)
    args = parser.parse_args(argv)

    try:
        plan = _plan(args.project_registry, args.domain_registry)
        payload = plan if args.command == "render" else _check(plan, args.tunnel_client)
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload["ok"] else 1
    except (ContractError, OSError) as exc:
        print(
            json.dumps(
                {"ok": False, "status": "error", "errors": [str(exc)]},
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
