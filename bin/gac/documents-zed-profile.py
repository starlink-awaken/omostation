#!/usr/bin/env python3
"""Install and verify the governed Documents profile in Zed settings."""

from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = (
    ROOT / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
)
DEFAULT_SETTINGS = Path.home() / ".config" / "zed" / "settings.json"


class ProfileError(RuntimeError):
    """A stable, user-facing Zed profile failure."""


@dataclass(frozen=True)
class ProfileContract:
    profile_id: str
    server: str
    allowed_tools: tuple[str, ...]


def _workspace_root(project_registry: Path) -> Path:
    parent = project_registry.parent
    if (
        project_registry.name != "documents-domain-projects.yaml"
        or parent.name != "registry"
        or parent.parent.name != "_truth"
        or parent.parent.parent.name != ".omo"
    ):
        raise ProfileError(
            "project registry must be Workspace .omo/_truth/registry/"
            "documents-domain-projects.yaml"
        )
    return parent.parents[2].resolve(strict=True)


def _load_contract(project_registry: Path) -> ProfileContract:
    try:
        raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ProfileError(f"project registry invalid: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProfileError("project registry must be a mapping")

    workspace_mcp = raw.get("workspace_mcp")
    clients = raw.get("clients")
    profiles = raw.get("profiles")
    if not isinstance(workspace_mcp, dict):
        raise ProfileError("workspace_mcp must be a mapping")
    if not isinstance(clients, dict) or not isinstance(clients.get("zed"), dict):
        raise ProfileError("clients.zed must be a mapping")
    if not isinstance(profiles, dict) or not isinstance(
        profiles.get("content-domain"), dict
    ):
        raise ProfileError("profiles.content-domain must be a mapping")

    contract = clients["zed"].get("profile_contract")
    if not isinstance(contract, dict):
        raise ProfileError("clients.zed.profile_contract must be a mapping")
    expected = {
        "name": "documents",
        "owner": "workspace",
        "approval_mode": "allow_read_tools",
        "builtin_tool_policy": "disable_all",
    }
    for field, value in expected.items():
        if contract.get(field) != value:
            raise ProfileError(f"clients.zed.profile_contract.{field} must be {value}")

    server = workspace_mcp.get("server")
    if not isinstance(server, str) or not server:
        raise ProfileError("workspace_mcp.server must be non-empty")
    if contract.get("exclusive_mcp_server") != server:
        raise ProfileError(
            "clients.zed.profile_contract.exclusive_mcp_server must match "
            "workspace_mcp.server"
        )

    generator_ref = contract.get("generator_ref")
    if not isinstance(generator_ref, str) or not generator_ref:
        raise ProfileError(
            "clients.zed.profile_contract.generator_ref must be a "
            "Workspace-relative file"
        )
    candidate = Path(generator_ref)
    if candidate.is_absolute() or ".." in candidate.parts or "://" in generator_ref:
        raise ProfileError(
            "clients.zed.profile_contract.generator_ref must be a "
            "Workspace-relative file"
        )
    workspace = _workspace_root(project_registry)
    try:
        generator = (workspace / candidate).resolve(strict=True)
    except OSError as exc:
        raise ProfileError(
            f"clients.zed.profile_contract.generator_ref is unavailable: {generator_ref}"
        ) from exc
    if not generator.is_relative_to(workspace) or not generator.is_file():
        raise ProfileError(
            "clients.zed.profile_contract.generator_ref must be a "
            "Workspace-relative file"
        )

    profile = profiles["content-domain"]
    tools = profile.get("allowed_workspace_tools")
    if (
        not isinstance(tools, list)
        or not tools
        or not all(isinstance(item, str) and item for item in tools)
    ):
        raise ProfileError(
            "profiles.content-domain.allowed_workspace_tools must be a non-empty string list"
        )
    exposed_tools = workspace_mcp.get("read_tools")
    if not isinstance(exposed_tools, list) or not set(tools).issubset(exposed_tools):
        raise ProfileError(
            "profiles.content-domain.allowed_workspace_tools must be exposed by workspace_mcp"
        )
    return ProfileContract(
        profile_id=contract["name"],
        server=server,
        allowed_tools=tuple(sorted(set(tools))),
    )


def _load_settings(path: Path) -> dict[str, Any]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ProfileError(f"settings unavailable: {path}: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ProfileError(f"settings must be a regular file: {path}")
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileError(f"settings invalid: {path}: {exc}") from exc
    if not isinstance(settings, dict):
        raise ProfileError("settings must be a mapping")
    return settings


def _validate_cockpit(settings: dict[str, Any], server: str) -> None:
    context_servers = settings.get("context_servers")
    if not isinstance(context_servers, dict):
        raise ProfileError("context_servers must be a mapping")
    cockpit = context_servers.get(server)
    if not isinstance(cockpit, dict):
        raise ProfileError(f"context_servers.{server} must be a mapping")
    if cockpit.get("enabled") is not True:
        raise ProfileError(f"context_servers.{server}.enabled must be true")
    if not isinstance(cockpit.get("command"), str) or not cockpit["command"]:
        raise ProfileError(f"context_servers.{server}.command must be non-empty")


def _projection(contract: ProfileContract) -> dict[str, Any]:
    permissions = {
        f"mcp:{contract.server}:{tool}": {"default": "allow"}
        for tool in contract.allowed_tools
    }
    return {
        "profile_id": contract.profile_id,
        "profile": {
            "name": contract.profile_id.title(),
            "tools": {},
            "enable_all_context_servers": False,
            "context_servers": {
                contract.server: {
                    "tools": {tool: True for tool in contract.allowed_tools}
                }
            },
        },
        "tool_permissions": permissions,
    }


def _agent_settings(settings: dict[str, Any]) -> dict[str, Any]:
    agent = settings.setdefault("agent", {})
    if not isinstance(agent, dict):
        raise ProfileError("agent must be a mapping")
    return agent


def _check_projection(
    settings: dict[str, Any], projection: dict[str, Any]
) -> list[str]:
    agent = settings.get("agent")
    if not isinstance(agent, dict):
        return ["agent must be a mapping"]
    profile_id = projection["profile_id"]
    profiles = agent.get("profiles")
    errors: list[str] = []
    if (
        not isinstance(profiles, dict)
        or profiles.get(profile_id) != projection["profile"]
    ):
        errors.append(
            f"agent.profiles.{profile_id} does not match the Workspace contract"
        )
    tool_permissions = agent.get("tool_permissions")
    tools = (
        tool_permissions.get("tools") if isinstance(tool_permissions, dict) else None
    )
    for key, expected in projection["tool_permissions"].items():
        if not isinstance(tools, dict) or tools.get(key) != expected:
            errors.append(
                f"agent.tool_permissions.tools.{key} does not match the Workspace contract"
            )
    return errors


def _is_prior_managed_projection(
    current_profile: object,
    projection: dict[str, Any],
    current_permissions: dict[str, Any],
) -> bool:
    """Accept only an older generated profile with a strict tool subset."""
    expected_profile = projection["profile"]
    if not isinstance(current_profile, dict) or not isinstance(expected_profile, dict):
        return False
    if set(current_profile) != set(expected_profile):
        return False
    for key, expected in expected_profile.items():
        if key != "context_servers" and current_profile.get(key) != expected:
            return False

    expected_servers = expected_profile.get("context_servers")
    current_servers = current_profile.get("context_servers")
    if not isinstance(expected_servers, dict) or not isinstance(current_servers, dict):
        return False
    if set(expected_servers) != set(current_servers) or len(expected_servers) != 1:
        return False
    server = next(iter(expected_servers))
    expected_server = expected_servers.get(server)
    current_server = current_servers.get(server)
    if not isinstance(expected_server, dict) or not isinstance(current_server, dict):
        return False
    expected_tools = expected_server.get("tools")
    current_tools = current_server.get("tools")
    if (
        set(expected_server) != {"tools"}
        or set(current_server) != {"tools"}
        or not isinstance(expected_tools, dict)
        or not isinstance(current_tools, dict)
    ):
        return False
    current_tool_names = set(current_tools)
    if (
        not current_tool_names
        or not current_tool_names < set(expected_tools)
        or any(current_tools.get(tool) is not True for tool in current_tool_names)
    ):
        return False

    expected_permissions = projection["tool_permissions"]
    expected_current_permissions = {
        f"mcp:{server}:{tool}": expected_permissions[f"mcp:{server}:{tool}"]
        for tool in current_tool_names
    }
    managed_permissions = {
        key: value
        for key, value in current_permissions.items()
        if key.startswith(f"mcp:{server}:")
    }
    return managed_permissions == expected_current_permissions


def _install_projection(settings: dict[str, Any], projection: dict[str, Any]) -> bool:
    agent = _agent_settings(settings)
    profiles = agent.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        raise ProfileError("agent.profiles must be a mapping")
    profile_id = projection["profile_id"]
    current_profile = profiles.get(profile_id)

    tool_permissions = agent.setdefault("tool_permissions", {})
    if not isinstance(tool_permissions, dict):
        raise ProfileError("agent.tool_permissions must be a mapping")
    tools = tool_permissions.setdefault("tools", {})
    if not isinstance(tools, dict):
        raise ProfileError("agent.tool_permissions.tools must be a mapping")
    if (
        current_profile is not None
        and current_profile != projection["profile"]
        and not _is_prior_managed_projection(current_profile, projection, tools)
    ):
        raise ProfileError(
            f"agent.profiles.{profile_id} already exists with different content"
        )
    for key, expected in projection["tool_permissions"].items():
        current = tools.get(key)
        if current is not None and current != expected:
            raise ProfileError(
                f"agent.tool_permissions.tools.{key} conflicts with the Workspace contract"
            )

    changed = current_profile != projection["profile"]
    if changed:
        profiles[profile_id] = projection["profile"]
    for key, expected in projection["tool_permissions"].items():
        if key not in tools:
            tools[key] = expected
            changed = True
    return changed


def _atomic_write(path: Path, settings: dict[str, Any]) -> None:
    content = json.dumps(settings, ensure_ascii=False, indent=2) + "\n"
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as stream:
            temporary = stream.name
            os.chmod(temporary, 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        path.chmod(0o600)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def _envelope(
    ok: bool, *, status: str, settings_path: Path, errors: list[str] | None = None
) -> dict[str, Any]:
    return {
        "ok": ok,
        "status": status,
        "settings_path": str(settings_path),
        "errors": errors or [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("render", "install", "check"))
    parser.add_argument("--project-registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--settings-path", type=Path, default=DEFAULT_SETTINGS)
    args = parser.parse_args(argv)

    try:
        contract = _load_contract(args.project_registry)
        settings = _load_settings(args.settings_path)
        _validate_cockpit(settings, contract.server)
        projection = _projection(contract)
        if args.command == "render":
            print(json.dumps(projection, ensure_ascii=False, indent=2))
            return 0
        if args.command == "check":
            errors = _check_projection(settings, projection)
            print(
                json.dumps(
                    _envelope(
                        not errors,
                        status="ok" if not errors else "drift",
                        settings_path=args.settings_path,
                        errors=errors,
                    ),
                    ensure_ascii=False,
                )
            )
            return 0 if not errors else 1

        changed = _install_projection(settings, projection)
        mode_changed = args.settings_path.stat().st_mode & 0o777 != 0o600
        if changed:
            _atomic_write(args.settings_path, settings)
        elif mode_changed:
            args.settings_path.chmod(0o600)
        print(
            json.dumps(
                _envelope(
                    True,
                    status="installed" if changed or mode_changed else "unchanged",
                    settings_path=args.settings_path,
                ),
                ensure_ascii=False,
            )
        )
        return 0
    except (OSError, ProfileError) as exc:
        print(
            json.dumps(
                _envelope(
                    False,
                    status="error",
                    settings_path=args.settings_path,
                    errors=[str(exc)],
                ),
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
