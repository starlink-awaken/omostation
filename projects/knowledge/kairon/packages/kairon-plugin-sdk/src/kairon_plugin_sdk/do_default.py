"""P58-W0 kairon_plugin_sdk do_default — 真业务 (调 BosPlugin / PluginContext 真类)."""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 kairon_plugin_sdk do_default: 真调 BosPlugin / PluginContext 反射."""
    try:
        from kairon_plugin_sdk import BosPlugin, PluginContext
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "schema")
    try:
        if action == "schema":
            return {
                "_method": "do_default",
                "_action": "schema",
                "BosPlugin": BosPlugin.__name__,
                "BosPlugin_bases": [b.__name__ for b in BosPlugin.__bases__],
                "PluginContext": PluginContext.__name__,
            }
        if action == "plugin_methods":
            methods = [m for m in dir(BosPlugin) if not m.startswith("_")]
            return {
                "_method": "do_default",
                "_action": "plugin_methods",
                "methods": methods,
                "count": len(methods),
            }
        if action == "context_fields":
            fields = (
                list(PluginContext.__dataclass_fields__.keys())
                if hasattr(PluginContext, "__dataclass_fields__")
                else dir(PluginContext)
            )
            return {
                "_method": "do_default",
                "_action": "context_fields",
                "fields": fields[:20],
                "count": len(fields),
            }
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
