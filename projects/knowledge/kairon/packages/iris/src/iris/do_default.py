"""P58-W0 iris do_default — 真业务 (调 iris 真模块: list connectors / build_parser)."""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 iris do_default: 真调 iris registry / build_parser / config."""
    try:
        from iris import __version__
        from iris.cli import build_parser
        from iris.config import IrisConfig
        from iris.registry import ConnectorRegistry
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "list_connectors")
    try:
        if action == "list_connectors":
            reg = ConnectorRegistry()
            try:
                connectors = [c.name for c in reg.list_all()]
            except Exception:
                connectors = []
            return {
                "_method": "do_default",
                "_action": "list_connectors",
                "version": __version__,
                "count": len(connectors),
                "connectors": connectors,
            }
        if action == "commands":
            parser = build_parser()
            _last = parser._actions[-1] if parser._actions else None
            sub_actions = sorted(_last.choices) if _last and _last.choices else []
            return {
                "_method": "do_default",
                "_action": "commands",
                "commands": sub_actions,
                "count": len(sub_actions),
            }
        if action == "config":
            cfg = IrisConfig()
            return {"_method": "do_default", "_action": "config", "config_repr": repr(cfg)[:500]}
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
