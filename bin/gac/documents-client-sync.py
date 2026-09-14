#!/usr/bin/env python3
"""Documents multi-client config drift detection and atomic repair.

Checks and optionally repairs drift between the canonical
``documents-domain-projects.yaml`` registry and each IDE's local config
(Claude Desktop, Codex, Zed, ZCode).

Usage::

    python bin/gac/documents-client-sync.py check
    python bin/gac/documents-client-sync.py apply
    python bin/gac/documents-client-sync.py check --json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Canonical registry
# ---------------------------------------------------------------------------

_REGISTRY_PATH = ROOT / ".omo" / "_truth" / "registry" / "documents-domain-projects.yaml"

# ---------------------------------------------------------------------------
# IDE config locations (macOS)
# ---------------------------------------------------------------------------

_CLAUDE_DESKTOP_CONFIG = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
_CODEX_CONFIG = Path.home() / ".codex" / "config.json"
_ZED_CONFIG = Path.home() / ".config" / "zed" / "settings.json"
_ZCODE_CONFIG = Path.home() / ".zcode" / "cli" / "config.json"

# ---------------------------------------------------------------------------
# Expected managed MCP server name
# ---------------------------------------------------------------------------

_MANAGED_MCP_SERVER = "cockpit"


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def _load_registry() -> dict[str, Any]:
    """Load the canonical documents-domain-projects.yaml."""
    if not _REGISTRY_PATH.exists():
        return {}
    with open(_REGISTRY_PATH) as fh:
        return yaml.safe_load(fh) or {}


def _expected_mcp_config(registry: dict[str, Any]) -> dict[str, Any]:
    """Build the expected MCP server config block for clients that use
    ``managed_mcp_server: cockpit``."""
    return {"cockpit": {"command": "cockpit", "args": ["mcp"], "transport": "stdio"}}


# ---------------------------------------------------------------------------
# Per-IDE drift detection
# ---------------------------------------------------------------------------

def _check_claude_desktop(registry: dict[str, Any]) -> dict[str, Any]:
    """Check Claude Desktop config for drift."""
    config_path = _CLAUDE_DESKTOP_CONFIG
    if not config_path.exists():
        return {"client": "claude_desktop", "status": "missing", "path": str(config_path),
                "detail": "Config file not found — no drift to fix"}
    try:
        with open(config_path) as fh:
            config = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        return {"client": "claude_desktop", "status": "error", "path": str(config_path),
                "detail": f"Cannot parse config: {exc}"}

    mcp_servers = config.get("mcpServers", {})
    cockpit_entry = mcp_servers.get(_MANAGED_MCP_SERVER)
    expected = _expected_mcp_config(registry)

    if cockpit_entry is None:
        return {"client": "claude_desktop", "status": "drift", "path": str(config_path),
                "detail": f"Managed MCP server '{_MANAGED_MCP_SERVER}' missing from mcpServers",
                "expected": expected.get(_MANAGED_MCP_SERVER)}

    if cockpit_entry != expected.get(_MANAGED_MCP_SERVER):
        return {"client": "claude_desktop", "status": "drift", "path": str(config_path),
                "detail": f"Managed MCP server '{_MANAGED_MCP_SERVER}' config mismatch",
                "current": cockpit_entry, "expected": expected.get(_MANAGED_MCP_SERVER)}

    return {"client": "claude_desktop", "status": "ok", "path": str(config_path)}


def _check_codex(registry: dict[str, Any]) -> dict[str, Any]:
    """Check Codex config for drift."""
    config_path = _CODEX_CONFIG
    if not config_path.exists():
        return {"client": "codex", "status": "missing", "path": str(config_path),
                "detail": "Config file not found — no drift to fix"}
    try:
        with open(config_path) as fh:
            config = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        return {"client": "codex", "status": "error", "path": str(config_path),
                "detail": f"Cannot parse config: {exc}"}

    mcp_servers = config.get("mcpServers", {})
    cockpit_entry = mcp_servers.get(_MANAGED_MCP_SERVER)
    expected = _expected_mcp_config(registry)

    if cockpit_entry is None:
        return {"client": "codex", "status": "drift", "path": str(config_path),
                "detail": f"Managed MCP server '{_MANAGED_MCP_SERVER}' missing from mcpServers",
                "expected": expected.get(_MANAGED_MCP_SERVER)}

    if cockpit_entry != expected.get(_MANAGED_MCP_SERVER):
        return {"client": "codex", "status": "drift", "path": str(config_path),
                "detail": f"Managed MCP server '{_MANAGED_MCP_SERVER}' config mismatch",
                "current": cockpit_entry, "expected": expected.get(_MANAGED_MCP_SERVER)}

    return {"client": "codex", "status": "ok", "path": str(config_path)}


def _check_zed(registry: dict[str, Any]) -> dict[str, Any]:
    """Check Zed config for drift (JSON settings)."""
    config_path = _ZED_CONFIG
    if not config_path.exists():
        return {"client": "zed", "status": "missing", "path": str(config_path),
                "detail": "Config file not found — no drift to fix"}
    try:
        with open(config_path) as fh:
            config = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        return {"client": "zed", "status": "error", "path": str(config_path),
                "detail": f"Cannot parse config: {exc}"}

    # Zed uses "context_servers" for MCP
    context_servers = config.get("context_servers", {})
    cockpit_entry = context_servers.get(_MANAGED_MCP_SERVER)

    if cockpit_entry is None:
        return {"client": "zed", "status": "drift", "path": str(config_path),
                "detail": f"Managed MCP server '{_MANAGED_MCP_SERVER}' missing from context_servers",
                "expected": {"command": "cockpit", "args": ["mcp"], "transport": "stdio"}}

    return {"client": "zed", "status": "ok", "path": str(config_path)}


def _check_zcode(registry: dict[str, Any]) -> dict[str, Any]:
    """Check ZCode config for drift."""
    config_path = _ZCODE_CONFIG
    if not config_path.exists():
        return {"client": "zcode", "status": "missing", "path": str(config_path),
                "detail": "Config file not found — no drift to fix"}
    try:
        with open(config_path) as fh:
            config = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        return {"client": "zcode", "status": "error", "path": str(config_path),
                "detail": f"Cannot parse config: {exc}"}

    mcp_servers = config.get("mcpServers", {})
    cockpit_entry = mcp_servers.get(_MANAGED_MCP_SERVER)
    expected = _expected_mcp_config(registry)

    if cockpit_entry is None:
        return {"client": "zcode", "status": "drift", "path": str(config_path),
                "detail": f"Managed MCP server '{_MANAGED_MCP_SERVER}' missing from mcpServers",
                "expected": expected.get(_MANAGED_MCP_SERVER)}

    if cockpit_entry != expected.get(_MANAGED_MCP_SERVER):
        return {"client": "zcode", "status": "drift", "path": str(config_path),
                "detail": f"Managed MCP server '{_MANAGED_MCP_SERVER}' config mismatch",
                "current": cockpit_entry, "expected": expected.get(_MANAGED_MCP_SERVER)}

    return {"client": "zcode", "status": "ok", "path": str(config_path)}


_CHECKERS = [
    _check_claude_desktop,
    _check_codex,
    _check_zed,
    _check_zcode,
]


# ---------------------------------------------------------------------------
# Atomic repair helpers
# ---------------------------------------------------------------------------

def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Atomically write JSON config with backup of the original."""
    backup = path.with_suffix(path.suffix + ".bak")
    if path.exists():
        shutil.copy2(path, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    tmp.replace(path)


def _repair_client_config(
    config_path: Path,
    key_section: str,
    registry: dict[str, Any],
) -> dict[str, Any]:
    """Repair a single client config. Returns fix details."""
    expected_server = _expected_mcp_config(registry).get(_MANAGED_MCP_SERVER, {})
    if not expected_server:
        return {"client": str(config_path), "fix": "skipped", "detail": "No expected config in registry"}

    if not config_path.exists():
        # Create a minimal config
        config = {key_section: {_MANAGED_MCP_SERVER: expected_server}}
        _atomic_write_json(config_path, config)
        return {"client": str(config_path), "fix": "created", "detail": f"Created with managed MCP server '{_MANAGED_MCP_SERVER}'"}

    with open(config_path) as fh:
        config = json.load(fh)

    section = config.get(key_section, {})
    section[_MANAGED_MCP_SERVER] = expected_server
    config[key_section] = section
    _atomic_write_json(config_path, config)
    return {"client": str(config_path), "fix": "repaired", "detail": f"Updated managed MCP server '{_MANAGED_MCP_SERVER}'"}


def _apply_claude_desktop(registry: dict[str, Any]) -> dict[str, Any]:
    return _repair_client_config(_CLAUDE_DESKTOP_CONFIG, "mcpServers", registry)


def _apply_codex(registry: dict[str, Any]) -> dict[str, Any]:
    return _repair_client_config(_CODEX_CONFIG, "mcpServers", registry)


def _apply_zed(registry: dict[str, Any]) -> dict[str, Any]:
    return _repair_client_config(_ZED_CONFIG, "context_servers", registry)


def _apply_zcode(registry: dict[str, Any]) -> dict[str, Any]:
    return _repair_client_config(_ZCODE_CONFIG, "mcpServers", registry)


_APPLIERS = [
    _apply_claude_desktop,
    _apply_codex,
    _apply_zed,
    _apply_zcode,
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Documents multi-client config drift detection and repair",
    )
    parser.add_argument(
        "mode",
        choices=["check", "apply"],
        help="check: detect drift; apply: atomically repair drift",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output JSON envelope (default: human-readable)",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=_REGISTRY_PATH,
        help="Path to documents-domain-projects.yaml (default: canonical)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    global _REGISTRY_PATH
    if args.registry != _REGISTRY_PATH:
        _REGISTRY_PATH = args.registry

    registry = _load_registry()
    if not registry:
        envelope = {"status": "error", "ok": False, "details": ["Registry not found or empty"]}
        if args.json:
            print(json.dumps(envelope, indent=2))
        else:
            print("ERROR: Registry not found or empty", file=sys.stderr)
        return 1

    if args.mode == "check":
        results = [checker(registry) for checker in _CHECKERS]
        has_drift = any(r["status"] == "drift" for r in results)
        envelope = {
            "status": "drift" if has_drift else "ok",
            "ok": not has_drift,
            "details": results,
        }
        if args.json:
            print(json.dumps(envelope, indent=2, ensure_ascii=False))
        else:
            if has_drift:
                print("DRIFT detected:")
                for r in results:
                    if r["status"] == "drift":
                        print(f"  {r['client']}: {r['detail']}")
            else:
                print("OK — no drift detected across all clients.")
        return 0 if not has_drift else 2

    # apply mode
    fixes = [applier(registry) for applier in _APPLIERS]
    envelope = {
        "status": "ok",
        "ok": True,
        "fixes_applied": fixes,
    }
    if args.json:
        print(json.dumps(envelope, indent=2, ensure_ascii=False))
    else:
        print("Applied fixes:")
        for fix in fixes:
            print(f"  {fix.get('client', '?')}: {fix.get('fix', '?')} — {fix.get('detail', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
