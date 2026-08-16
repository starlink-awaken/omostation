"""P58-W0 codeanalyze do_default — 真业务 (调 codeanalyze commands 真模块)."""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 codeanalyze do_default: 真调 codeanalyze commands 子模块."""
    try:
        from codeanalyze import __version__
        from codeanalyze.cli import cli  # type: ignore[import-not-found]
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "list_commands")
    try:
        if action == "list_commands":
            commands = sorted(cli.commands.keys())
            return {
                "_method": "do_default",
                "_action": "list_commands",
                "version": __version__,
                "count": len(commands),
                "commands": commands,
            }
        if action == "version":
            return {"_method": "do_default", "_action": "version", "version": __version__}
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
