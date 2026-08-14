#!/usr/bin/env python3
"""Install and verify the governed Documents MCP entry in Claude Desktop."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT_REGISTRY = (
    ROOT / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"
)
DEFAULT_DOMAIN_REGISTRY = Path(
    os.environ.get(
        "L4_DOMAIN_REGISTRY",
        Path.home() / "Documents" / "@公共" / "_control" / "L4-DOMAIN-REGISTRY.yaml",
    )
)
DEFAULT_SETTINGS = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Claude"
    / "claude_desktop_config.json"
)


class ConfigError(RuntimeError):
    """A stable, user-facing Claude Desktop configuration failure."""


@dataclass(frozen=True)
class ConfigContract:
    workspace_root: Path
    documents_root: Path
    domain_registry: Path
    server: str
    command: Path


def _workspace_root(project_registry: Path) -> Path:
    parent = project_registry.parent
    if (
        project_registry.name != "documents-domain-projects.yaml"
        or parent.name != "registry"
        or parent.parent.name != "_truth"
        or parent.parent.parent.name != ".omo"
    ):
        raise ConfigError(
            "project registry must be Workspace .omo/_truth/registry/"
            "documents-domain-projects.yaml"
        )
    try:
        return parent.parents[2].resolve(strict=True)
    except OSError as exc:
        raise ConfigError(f"Workspace root unavailable: {exc}") from exc


def _regular_file(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ConfigError(f"{label} unavailable: {path}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ConfigError(f"{label} must be a regular file: {path}")


def _documents_root(domain_registry: Path, instruction_file: str) -> Path:
    if (
        domain_registry.name != "L4-DOMAIN-REGISTRY.yaml"
        or domain_registry.parent.name != "_control"
        or domain_registry.parent.parent.name != "@公共"
    ):
        raise ConfigError(
            "domain registry must be Documents/@公共/_control/L4-DOMAIN-REGISTRY.yaml"
        )
    _regular_file(domain_registry, "domain registry")
    try:
        root = domain_registry.parents[2].resolve(strict=True)
    except OSError as exc:
        raise ConfigError(f"Documents root unavailable: {exc}") from exc
    gateway = root / instruction_file
    _regular_file(gateway, "Documents gateway")
    return root


def _generator_path(
    workspace: Path, contract: dict[str, Any], field_prefix: str
) -> None:
    generator_ref = contract.get("generator_ref")
    if not isinstance(generator_ref, str) or not generator_ref:
        raise ConfigError(
            f"{field_prefix}.generator_ref must be a Workspace-relative file"
        )
    candidate = Path(generator_ref)
    if candidate.is_absolute() or ".." in candidate.parts or "://" in generator_ref:
        raise ConfigError(
            f"{field_prefix}.generator_ref must be a Workspace-relative file"
        )
    try:
        generator = (workspace / candidate).resolve(strict=True)
    except OSError as exc:
        raise ConfigError(
            f"{field_prefix}.generator_ref is unavailable: {generator_ref}"
        ) from exc
    if not generator.is_relative_to(workspace) or not generator.is_file():
        raise ConfigError(
            f"{field_prefix}.generator_ref must be a Workspace-relative file"
        )


def _load_contract(project_registry: Path, domain_registry: Path) -> ConfigContract:
    try:
        raw = yaml.safe_load(project_registry.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"project registry invalid: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("project registry must be a mapping")

    workspace_mcp = raw.get("workspace_mcp")
    clients = raw.get("clients")
    if not isinstance(workspace_mcp, dict):
        raise ConfigError("workspace_mcp must be a mapping")
    if not isinstance(clients, dict) or not isinstance(clients.get("claude"), dict):
        raise ConfigError("clients.claude must be a mapping")
    client = clients["claude"]
    if client.get("instruction_file") != "CLAUDE.md":
        raise ConfigError("clients.claude.instruction_file must be CLAUDE.md")
    if client.get("mcp_scope") != "user":
        raise ConfigError("clients.claude.mcp_scope must be user")

    contract = client.get("config_contract")
    if not isinstance(contract, dict):
        raise ConfigError("clients.claude.config_contract must be a mapping")
    expected: dict[str, object] = {
        "owner": "workspace",
        "configuration_surface": "native_json",
        "config_path": "~/Library/Application Support/Claude/claude_desktop_config.json",
        "preserve_unrelated_servers": True,
    }
    for field, value in expected.items():
        if type(contract.get(field)) is not type(value) or contract.get(field) != value:
            rendered = str(value).lower() if isinstance(value, bool) else value
            raise ConfigError(
                f"clients.claude.config_contract.{field} must be {rendered}"
            )

    server = workspace_mcp.get("server")
    entrypoint = workspace_mcp.get("entrypoint")
    if not isinstance(server, str) or not server:
        raise ConfigError("workspace_mcp.server must be non-empty")
    if workspace_mcp.get("transport") != "stdio":
        raise ConfigError("workspace_mcp.transport must be stdio")
    if not isinstance(entrypoint, str) or not entrypoint:
        raise ConfigError("workspace_mcp.entrypoint must be non-empty")
    if contract.get("managed_mcp_server") != server:
        raise ConfigError(
            "clients.claude.config_contract.managed_mcp_server must match "
            "workspace_mcp.server"
        )

    workspace = _workspace_root(project_registry)
    _generator_path(workspace, contract, "clients.claude.config_contract")
    documents = _documents_root(domain_registry, "CLAUDE.md")
    command = workspace / "projects" / "cockpit" / ".venv" / "bin" / entrypoint
    _regular_file(command, "Cockpit MCP entrypoint")
    if not os.access(command, os.X_OK):
        raise ConfigError(f"Cockpit MCP entrypoint is not executable: {command}")
    return ConfigContract(
        workspace_root=workspace,
        documents_root=documents,
        domain_registry=domain_registry.resolve(strict=True),
        server=server,
        command=command.resolve(strict=True),
    )


def _projection(contract: ConfigContract) -> dict[str, Any]:
    return {
        "mcpServers": {
            contract.server: {
                "command": str(contract.command),
                "args": [],
                "env": {
                    "WORKSPACE_ROOT": str(contract.workspace_root),
                    "L4_DOCUMENTS_ROOT": str(contract.documents_root),
                    "L4_DOMAIN_REGISTRY": str(contract.domain_registry),
                },
            }
        }
    }


def _claude_desktop_running() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        result = subprocess.run(
            ["pgrep", "-x", "Claude"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise ConfigError(f"Claude Desktop process check unavailable: {exc}") from exc
    return result.returncode == 0


def _load_settings(path: Path, *, allow_missing: bool) -> dict[str, Any]:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        if allow_missing:
            return {}
        raise ConfigError(f"settings unavailable: {path}") from None
    except OSError as exc:
        raise ConfigError(f"settings unavailable: {path}: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ConfigError(f"settings must be a regular file: {path}")
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"settings invalid: {path}: {exc}") from exc
    if not isinstance(settings, dict):
        raise ConfigError("settings must be a mapping")
    return settings


def _server_map(settings: dict[str, Any], *, create: bool) -> dict[str, Any]:
    servers = settings.get("mcpServers")
    if servers is None and create:
        servers = {}
        settings["mcpServers"] = servers
    if not isinstance(servers, dict):
        raise ConfigError("mcpServers must be a mapping")
    return servers


def _check_settings(
    settings: dict[str, Any], expected: dict[str, Any], settings_path: Path
) -> list[str]:
    errors: list[str] = []
    try:
        servers = _server_map(settings, create=False)
        server, projection = next(iter(expected["mcpServers"].items()))
        if servers.get(server) != projection:
            errors.append(f"mcpServers.{server} does not match the Workspace contract")
    except ConfigError as exc:
        errors.append(str(exc))
    if settings_path.stat().st_mode & 0o777 != 0o600:
        errors.append("settings mode must be 0600")
    return errors


def _install_projection(settings: dict[str, Any], expected: dict[str, Any]) -> bool:
    servers = _server_map(settings, create=True)
    server, projection = next(iter(expected["mcpServers"].items()))
    if servers.get(server) == projection:
        return False
    servers[server] = projection
    return True


def _atomic_write(path: Path, settings: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    ok: bool,
    *,
    status: str,
    settings_path: Path,
    restart_required: bool = False,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "status": status,
        "settings_path": str(settings_path),
        "restart_required": restart_required,
        "errors": errors or [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("render", "install", "check"))
    parser.add_argument(
        "--project-registry", type=Path, default=DEFAULT_PROJECT_REGISTRY
    )
    parser.add_argument("--domain-registry", type=Path, default=DEFAULT_DOMAIN_REGISTRY)
    parser.add_argument("--settings-path", type=Path, default=DEFAULT_SETTINGS)
    args = parser.parse_args(argv)

    try:
        contract = _load_contract(args.project_registry, args.domain_registry)
        projection = _projection(contract)
        if args.command == "render":
            print(json.dumps(projection, ensure_ascii=False, indent=2))
            return 0

        if (
            args.command == "install"
            and args.settings_path == DEFAULT_SETTINGS
            and _claude_desktop_running()
        ):
            print(
                json.dumps(
                    _envelope(
                        False,
                        status="client_running",
                        settings_path=args.settings_path,
                        restart_required=True,
                        errors=[
                            "Claude Desktop must be fully exited before installation"
                        ],
                    ),
                    ensure_ascii=False,
                )
            )
            return 1

        settings = _load_settings(
            args.settings_path, allow_missing=args.command == "install"
        )
        if args.command == "check":
            errors = _check_settings(settings, projection, args.settings_path)
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
        mode_changed = (
            not args.settings_path.exists()
            or args.settings_path.stat().st_mode & 0o777 != 0o600
        )
        if changed or mode_changed:
            _atomic_write(args.settings_path, settings)
        print(
            json.dumps(
                _envelope(
                    True,
                    status="installed" if changed or mode_changed else "unchanged",
                    settings_path=args.settings_path,
                    restart_required=changed or mode_changed,
                ),
                ensure_ascii=False,
            )
        )
        return 0
    except (OSError, ConfigError) as exc:
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
