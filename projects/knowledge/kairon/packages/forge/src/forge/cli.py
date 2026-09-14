#!/usr/bin/env python3
"""forge.cli — Forge BOS CLI entry point

BOS stdio transport wrapper for forge capability services.

Subcommands:
  discover       - 生态嗅探，发现新工具/服务
  exec-tool      - 执行已注册工具
  list-tools     - 列出已注册工具
  register-tool  - 注册新工具

Usage (via BOS):
  uv run --directory projects/kairon python -m forge.cli discover [--eco npm,brew,...]
  uv run --directory projects/kairon python -m forge.cli exec-tool <tool-id> [-- args...]
  uv run --directory projects/kairon python -m forge.cli list-tools [--limit N]
  uv run --directory projects/kairon python -m forge.cli register-tool '<json>'
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any


def _load_registry() -> dict[str, Any]:
    """Load the tools-registry.json."""
    from forge.forge_config import REGISTRY  # type: ignore[import-not-found]

    try:
        return json.loads(Path(REGISTRY).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"tools": [], "schema_version": "?", "event_log": []}


def _find_tool(tool_id: str, reg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Find a tool by ID in the registry."""
    if reg is None:
        reg = _load_registry()
    for t in reg.get("tools", []):
        if t.get("id") == tool_id:
            return t
    return None


def do_discover(args: list[str]) -> dict[str, Any]:
    """Discover new tools/services from package manager ecosystems.

    Delegates to forge.discover_ecosystem.run(). Captures human-readable
    output and returns it as a JSON envelope for BOS compatibility.
    """
    from forge.discover_ecosystem import run as discover_run  # type: ignore[import-not-found]

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = discover_run(args)
    output = buf.getvalue()
    return {
        "status": "ok" if exit_code == 0 else "error",
        "exit_code": exit_code,
        "output": output,
    }


def do_exec_tool(args: list[str]) -> dict[str, Any]:
    """Execute a registered tool by ID.

    Usage (via BOS):
      exec-tool <tool-id> [-- <tool-args>...]

    Looks up the tool in tools-registry.json, then dispatches via the
    forge COMMANDS dict or forge main() routing. Returns stdout/stderr
    and exit code.
    """
    if not args or args[0] in ("-h", "--help", "help"):
        return {
            "status": "error",
            "error": "Usage: exec-tool <tool-id> [-- <tool-args>...]",
        }

    tool_id = args[0]
    tool_args = args[1:]
    # Strip leading '--' separator if present
    if tool_args and tool_args[0] == "--":
        tool_args = tool_args[1:]

    # 1. Check forge COMMANDS dict for a matching entry
    from forge.forge import COMMANDS  # type: ignore[import-not-found]

    if tool_id in COMMANDS:
        cmd_type, path, _ = COMMANDS[tool_id]
        try:
            if cmd_type == "script":
                r = subprocess.run(
                    ["bash", str(path)] + tool_args,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            elif cmd_type == "python":
                r = subprocess.run(
                    [sys.executable, str(path)] + tool_args,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            else:
                return {"status": "error", "error": f"Unknown command type: {cmd_type}"}
            return {
                "status": "ok" if r.returncode == 0 else "error",
                "exit_code": r.returncode,
                "stdout": r.stdout,
                "stderr": r.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": f"Tool '{tool_id}' timed out after 300s"}
        except FileNotFoundError:
            return {"status": "error", "error": f"Script for '{tool_id}' not found: {path}"}

    # 2. Check forge ALIASES for indirect matches
    from forge.forge import ALIASES  # type: ignore[import-not-found]

    resolved = ALIASES.get(tool_id)
    if resolved and resolved in COMMANDS:
        return do_exec_tool([resolved] + tool_args)

    # 3. Tool not found in COMMANDS — return tool info from registry
    tool = _find_tool(tool_id)
    if tool:
        return {
            "status": "ok",
            "note": f"Tool '{tool_id}' found in registry but has no executable command in forge COMMANDS dict",
            "tool": tool,
            "executed": False,
        }

    return {"status": "error", "error": f"Tool '{tool_id}' not found in registry or forge COMMANDS"}


def do_list_tools(args: list[str]) -> dict[str, Any]:
    """List registered tools from the forge registry.

    Delegates to mcp_server.list_tools() for consistent output with
    the existing forge MCP tool.
    """
    import mcp_server  # type: ignore[import-not-found]

    limit = 50
    if args:
        for i, a in enumerate(args):
            if a == "--limit" and i + 1 < len(args):
                try:
                    limit = int(args[i + 1])
                except ValueError:
                    pass
                break
            elif a == "--help" or a == "-h":
                return {
                    "status": "error",
                    "error": "Usage: list-tools [--limit N]",
                }
            else:
                try:
                    limit = int(a)
                    break
                except ValueError:
                    pass

    tools = mcp_server.list_tools(limit=limit)
    reg = _load_registry()
    return {
        "status": "ok",
        "schema_version": reg.get("schema_version", "?"),
        "total": len(tools),
        "tools": tools,
    }


def do_register_tool(args: list[str]) -> dict[str, Any]:
    """Register a new tool in the forge tools-registry.json.

    Usage (via BOS):
      register-tool '<json>'

    The JSON must include at minimum "id", "name".
    Adds the tool to the tools-registry.json for compatibility
    with forge's tool discovery and listing infrastructure.
    """
    if not args or args[0] in ("-h", "--help", "help"):
        return {
            "status": "error",
            "error": "Usage: register-tool '<json>'  (requires id, name)",
        }

    json_str = args[0]
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"JSON parse error: {e}"}

    missing = [f for f in ("id", "name") if f not in data]
    if missing:
        return {
            "status": "error",
            "error": f"Missing required fields: {', '.join(missing)}",
        }

    from datetime import datetime

    from forge.forge_config import REGISTRY  # type: ignore[import-not-found]

    reg = _load_registry()
    tools_list = reg.setdefault("tools", [])

    # Check if tool already exists
    idx = None
    for i, t in enumerate(tools_list):
        if t.get("id") == data["id"]:
            idx = i
            break

    today = datetime.now().strftime("%Y-%m-%d")

    if idx is not None:
        old = tools_list[idx]
        old.update(data)
        old["updated"] = today
        tools_list[idx] = old
        action = "updated"
    else:
        data.setdefault("added", today)
        data.setdefault("updated", today)
        data.setdefault("status", "active")
        data.setdefault("type", "tool")
        tools_list.append(data)
        action = "registered"

    # Write back
    reg["updated"] = today
    Path(REGISTRY).write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")

    return {
        "status": "ok",
        "action": action,
        "id": data["id"],
    }


_COMMANDS: dict[str, Any] = {
    "discover": do_discover,
    "exec-tool": do_exec_tool,
    "list-tools": do_list_tools,
    "register-tool": do_register_tool,
}


def main() -> int:
    """CLI entry point: parse argv[1] as subcommand and dispatch."""
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": "Usage: python -m forge.cli <subcommand> [args...]",
                    "subcommands": list(_COMMANDS.keys()),
                },
                ensure_ascii=False,
            )
        )
        return 1

    command = sys.argv[1]
    cmd_args = sys.argv[2:]

    fn = _COMMANDS.get(command)
    if fn is None:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": f"Unknown subcommand: '{command}'",
                    "subcommands": list(_COMMANDS.keys()),
                },
                ensure_ascii=False,
            )
        )
        return 1

    try:
        result = fn(cmd_args)
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0 if result.get("status") == "ok" else 1
    except Exception as e:
        print(
            json.dumps(
                {"status": "error", "error": f"{type(e).__name__}: {e}"},
                ensure_ascii=False,
                default=str,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
