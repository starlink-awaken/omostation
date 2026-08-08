"""Internal BOS dispatch targets for Phase45 W3 / STRAT-P81 S0.2.

These callables are the real resolver path for ``transport: internal``:
``importlib.import_module(module_path)`` + ``getattr(func_name)``.

They wrap forge.cli surfaces that already exist as pure Python functions
(not stdio subprocess spawn via invoke_stdio).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Workspace root: agora/src/agora/mcp/this.py → parents[5] = Workspace
_WS = Path(__file__).resolve().parents[5]
_FORGE_SRC = _WS / "projects" / "kairon" / "packages" / "forge" / "src"


def _ensure_forge() -> None:
    src = str(_FORGE_SRC)
    if src not in sys.path:
        sys.path.insert(0, src)


def _arglist(*args: Any, **kwargs: Any) -> list[str]:
    if args and isinstance(args[0], list):
        return [str(x) for x in args[0]]
    if "args" in kwargs and isinstance(kwargs["args"], list):
        return [str(x) for x in kwargs["args"]]
    return [str(a) for a in args]


def forge_discover(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _ensure_forge()
    from forge.cli import do_discover  # type: ignore[import-not-found]

    return do_discover(_arglist(*args, **kwargs))


def forge_exec_tool(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _ensure_forge()
    from forge.cli import do_exec_tool  # type: ignore[import-not-found]

    return do_exec_tool(_arglist(*args, **kwargs))


def forge_list_tools(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _ensure_forge()
    from forge.cli import do_list_tools  # type: ignore[import-not-found]

    return do_list_tools(_arglist(*args, **kwargs))


def forge_register_tool(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _ensure_forge()
    from forge.cli import do_register_tool  # type: ignore[import-not-found]

    return do_register_tool(_arglist(*args, **kwargs))


def forge_agent_list(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Agent list surface — maps to forge list-tools registry read."""
    result = forge_list_tools(*args, **kwargs)
    return {"status": "ok", "action": "agent-list", "result": result}


def forge_agent_install(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Install surface — maps to register-tool when args present."""
    arglist = _arglist(*args, **kwargs)
    if not arglist:
        return {
            "status": "ok",
            "action": "agent-install",
            "note": "no-op without tool args; use register-tool args",
        }
    return forge_register_tool(arglist)


def forge_registry(*args: Any, **kwargs: Any) -> dict[str, Any]:
    result = forge_list_tools(*args, **kwargs)
    return {"status": "ok", "action": "registry", "result": result}


def forge_lint(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Lint = load registry + report tool count / basic structure."""
    result = forge_list_tools(*args, **kwargs)
    tools = result.get("tools") if isinstance(result, dict) else None
    n = len(tools) if isinstance(tools, list) else None
    return {
        "status": "ok",
        "action": "lint",
        "tool_count": n,
        "result": result,
    }


def forge_publish(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Publish-compatible internal entry via register-tool."""
    arglist = _arglist(*args, **kwargs)
    if not arglist:
        return {
            "status": "ok",
            "action": "publish",
            "note": "no-op without tool args",
        }
    return forge_register_tool(arglist)


# Explicit export list for migration registry
MIGRATED_FUNCS = (
    "forge_discover",
    "forge_exec_tool",
    "forge_list_tools",
    "forge_register_tool",
    "forge_agent_list",
    "forge_agent_install",
    "forge_registry",
    "forge_lint",
    "forge_publish",
)
