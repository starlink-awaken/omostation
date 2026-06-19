"""CLI tool connection management — one-click connect/disconnect for AI tools.

Adapted from agentmesh gateway cli/connect.ts.
Discovers installed AI tools (Codex, Claude Code, Cursor, etc.) and configures
them to route through the agora gateway.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

HOME = Path.home()
BACKUP_DIR = HOME / ".config" / "agentmesh" / "backups"
GATEWAY_URL = os.environ.get("AGORA_URL", "http://127.0.0.1:3100/v1")
GATEWAY_HOST = re.sub(r"https?://", "", GATEWAY_URL).split("/")[0]


# ── Types ─────────────────────────────────────────────────────────────────────


class ToolAdapter:
    """Describes how to detect, configure, and revert a tool."""

    def __init__(
        self,
        name: str,
        description: str,
        detect_fn=lambda: False,
        config_path_fn=lambda: None,
        read_config_fn=lambda: None,
        generate_config_fn=lambda gw: None,
        has_gateway_fn=lambda c: False,
    ) -> None:
        self.name = name
        self.description = description
        self._detect = detect_fn
        self._config_path = config_path_fn
        self._read = read_config_fn
        self._generate = generate_config_fn
        self._has_gateway = has_gateway_fn

    def detect(self) -> bool:
        return self._detect()

    def get_config_path(self) -> str | None:
        return self._config_path()

    def read_config(self) -> Any:
        return self._read()

    def generate_config(self, gw_url: str) -> dict | None:
        return self._generate(gw_url)

    def has_gateway_config(self, config: Any) -> bool:
        return self._has_gateway(config)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _backup_file(original_path: str) -> str | None:
    if not os.path.exists(original_path):
        return None
    _ensure_dir(BACKUP_DIR)
    ts = time.strftime("%Y-%m-%dT%H-%M-%S")
    safe_name = original_path.replace("/", "_").lstrip("_")
    backup = BACKUP_DIR / f"{safe_name}.{ts}.bak"
    shutil.copy2(original_path, backup)
    return str(backup)


def _to_toml(obj: dict, parent_key: str = "") -> str:
    lines: list[str] = []
    for key, value in obj.items():
        if value is None:
            continue
        full = f"{parent_key}.{key}" if parent_key else key
        if isinstance(value, dict):
            lines.append(f"[{full}]")
            lines.append(_to_toml(value, full))
        elif isinstance(value, list):
            for item in value:
                q = f'"{item}"' if isinstance(item, str) else json.dumps(item)
                lines.append(f"{key} = {q}")
        elif isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        else:
            lines.append(f"{key} = {value}")
    return "\n".join(lines)


# ── Tool Adapters ──────────────────────────────────────────────────────────────

ADAPTERS: list[ToolAdapter] = []


def _codex_detect() -> bool:
    return (HOME / ".codex").exists()


def _codex_config_path() -> str:
    return str(HOME / ".codex" / "config.toml")


def _codex_generate(gw_url: str) -> dict | None:
    return {
        "path": _codex_config_path(),
        "format": "toml",
        "content": {
            "model": "deepseek-v4-pro",
            "model_provider": "agentmesh",
            "model_catalog_json": str(
                HOME / ".codex" / "model-catalogs" / "agentmesh-models.json"
            ),
            "model_providers": {
                "agentmesh": {
                    "name": "Agora Gateway",
                    "base_url": gw_url,
                    "wire_api": "responses",
                    "env_key": "OPENAI_API_KEY",
                }
            },
        },
    }


def _codex_has_gateway(config: Any) -> bool:
    raw = config if isinstance(config, str) else ""
    return "agentmesh" in raw or "model_providers" in raw


def _cursor_detect() -> bool:
    return (HOME / "Library" / "Application Support" / "Cursor").exists()


def _cursor_config_path() -> str:
    return str(
        HOME / "Library" / "Application Support" / "Cursor" / "User" / "settings.json"
    )


def _cursor_generate(gw_url: str) -> dict | None:
    return {
        "path": _cursor_config_path(),
        "format": "json-merge",
        "content": {
            "openai.apiBase": gw_url,
            "openai.customHeaders": {"x-custom-provider": "agentmesh"},
        },
    }


def _cursor_has_gateway(config: Any) -> bool:
    return bool(config and config.get("openai", {}).get("apiBase", "").endswith("3100"))


def _shell_detect() -> bool:
    return (HOME / ".zshrc").exists() or (HOME / ".bashrc").exists()


def _shell_config_path() -> str | None:
    if (HOME / ".zshrc").exists():
        return str(HOME / ".zshrc")
    if (HOME / ".bashrc").exists():
        return str(HOME / ".bashrc")
    return None


def _shell_generate(gw_url: str) -> dict | None:
    path = _shell_config_path()
    if not path:
        return None
    block = (
        "\n# >>> Agora Gateway (agora connect) >>>\n"
        f'export OPENAI_API_BASE="{gw_url}"\n'
        f'export AGORA_URL="{gw_url}"\n'
        f'export AGENT_GATEWAY_URL="http://{GATEWAY_HOST}"\n'
        "# <<< Agora Gateway <<<\n"
    )
    return {"path": path, "format": "env", "content": block}


def _shell_has_gateway(config: Any) -> bool:
    return bool(config and "Agora Gateway" in str(config))


ADAPTERS.extend(
    [
        ToolAdapter(
            "codex-desktop",
            "OpenAI Codex Desktop (macOS)",
            detect_fn=_codex_detect,
            config_path_fn=_codex_config_path,
            generate_config_fn=_codex_generate,
            has_gateway_fn=_codex_has_gateway,
        ),
        ToolAdapter(
            "cursor",
            "Cursor IDE",
            detect_fn=_cursor_detect,
            config_path_fn=_cursor_config_path,
            generate_config_fn=_cursor_generate,
            has_gateway_fn=_cursor_has_gateway,
        ),
        ToolAdapter(
            "shell-env",
            "Shell environment variables",
            detect_fn=_shell_detect,
            config_path_fn=_shell_config_path,
            generate_config_fn=_shell_generate,
            has_gateway_fn=_shell_has_gateway,
        ),
        ToolAdapter(
            "openai-compat",
            "Generic OpenAI-compatible tools",
            detect_fn=lambda: True,
            config_path_fn=lambda: None,
            generate_config_fn=lambda gw: None,
            has_gateway_fn=lambda c: False,
            read_config_fn=lambda: None,
        ),
    ]
)


# ── Connect / Disconnect ─────────────────────────────────────────────────────


def connect_tools(
    target_tools: list[str] | None = None,
    dry_run: bool = False,
    host: str | None = None,
    port: int | None = None,
) -> list[dict[str, Any]]:
    """Configure tools to route through the gateway.

    Args:
        target_tools: List of tool names, or None/["all"] for all.
        dry_run: Preview changes without modifying files.
        host: Override gateway host.
        port: Override gateway port.

    Returns:
        List of result dicts with tool, status, and detail keys.
    """
    gw_url = f"http://{host}:{port}/v1" if host and port else GATEWAY_URL
    results: list[dict[str, Any]] = []

    targets = (
        [
            a
            for a in ADAPTERS
            if target_tools is None or "all" in target_tools or a.name in target_tools
        ]
        if target_tools
        else ADAPTERS
    )

    for adapter in targets:
        if target_tools and "all" in target_tools and adapter.name == "openai-compat":
            continue

        installed = adapter.detect()
        if not installed:
            results.append(
                {
                    "tool": adapter.name,
                    "status": "not_installed",
                    "detail": f"{adapter.description} not installed",
                }
            )
            continue

        config = adapter.read_config()
        generated = adapter.generate_config(gw_url)

        if not generated:
            results.append(
                {
                    "tool": adapter.name,
                    "status": "ok",
                    "detail": f"Set env OPENAI_API_BASE={gw_url}",
                }
            )
            continue

        if adapter.has_gateway_config(config):
            results.append(
                {
                    "tool": adapter.name,
                    "status": "skipped",
                    "detail": "Already configured",
                }
            )
            continue

        if dry_run:
            results.append(
                {
                    "tool": adapter.name,
                    "status": "ok",
                    "detail": f"[DRY-RUN] Would modify {generated['path']}",
                }
            )
            continue

        backup_path = _backup_file(generated["path"])

        try:
            _ensure_dir(Path(generated["path"]).parent)
            fmt = generated["format"]
            content = generated["content"]

            if fmt == "toml":
                toml = _to_toml(content)
                existing = (
                    Path(generated["path"]).read_text()
                    if Path(generated["path"]).exists()
                    else ""
                )
                Path(generated["path"]).write_text(
                    existing.rstrip() + "\n\n# Added by agora connect\n" + toml + "\n"
                )

            elif fmt == "json-merge":
                existing = (
                    json.loads(Path(generated["path"]).read_text())
                    if Path(generated["path"]).exists()
                    else {}
                )
                merged = {**existing, **content}
                Path(generated["path"]).write_text(json.dumps(merged, indent=2) + "\n")

            elif fmt == "env":
                existing = (
                    Path(generated["path"]).read_text()
                    if Path(generated["path"]).exists()
                    else ""
                )
                Path(generated["path"]).write_text(existing.rstrip() + "\n" + content)

            elif fmt == "json":
                Path(generated["path"]).write_text(json.dumps(content, indent=2) + "\n")

            detail = f"Configured -> {gw_url}"
            if backup_path:
                detail += f" (backup: {backup_path})"
            results.append({"tool": adapter.name, "status": "ok", "detail": detail})

        except Exception as e:
            results.append({"tool": adapter.name, "status": "failed", "detail": str(e)})

    return results


def disconnect_tools(target_tools: list[str] | None = None) -> list[dict[str, Any]]:
    """Revert tool configuration by restoring from backup."""
    targets = target_tools or ["codex-desktop", "cursor", "shell-env"]
    results: list[dict[str, Any]] = []

    for tool_name in targets:
        adapter = next((a for a in ADAPTERS if a.name == tool_name), None)
        if not adapter:
            results.append(
                {
                    "tool": tool_name,
                    "status": "not_configured",
                    "detail": "Unknown tool",
                }
            )
            continue

        config_path = adapter.get_config_path()
        if not config_path or not os.path.exists(config_path):
            results.append(
                {
                    "tool": tool_name,
                    "status": "no_backup",
                    "detail": "Config file not found",
                }
            )
            continue

        # Shell env: remove marker block
        if adapter.name == "shell-env":
            content = Path(config_path).read_text()
            if "Agora Gateway" not in content:
                results.append(
                    {
                        "tool": tool_name,
                        "status": "not_configured",
                        "detail": "No gateway config block found",
                    }
                )
                continue
            cleaned = re.sub(
                r"# >>> Agora Gateway[\s\S]*?# <<< Agora Gateway <<<\n?", "", content
            )
            Path(config_path).write_text(cleaned.strip() + "\n")
            results.append(
                {"tool": tool_name, "status": "ok", "detail": "Removed env config"}
            )
            continue

        # Other tools: restore from backup
        safe_name = config_path.replace("/", "_").lstrip("_")
        backups = (
            sorted(BACKUP_DIR.glob(f"{safe_name}.*.bak"), reverse=True)
            if BACKUP_DIR.exists()
            else []
        )

        if backups:
            shutil.copy2(backups[0], config_path)
            results.append(
                {
                    "tool": tool_name,
                    "status": "ok",
                    "detail": f"Restored from {backups[0]}",
                }
            )
        else:
            results.append(
                {"tool": tool_name, "status": "no_backup", "detail": "No backup found"}
            )

    return results


def list_detected_tools() -> list[dict[str, Any]]:
    """List all known tools with installation status."""
    return [
        {
            "name": a.name,
            "description": a.description,
            "installed": a.detect(),
            "config_path": a.get_config_path(),
        }
        for a in ADAPTERS
    ]
