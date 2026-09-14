"""P58-W0 kronos do_default — 真业务 (调 kronos fetch_router / dispatcher 真函数)."""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 kronos do_default: 真调 list_all_methods / plan_for_url / execute_fallback_chain."""
    try:
        from kronos import __version__
        from kronos.fetch_router import (  # type: ignore[import-not-found]
            content_type_label,
            list_all_methods,
            plan_for_url,
        )
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "list_methods")
    try:
        if action == "list_methods":
            methods = list_all_methods()
            return {
                "_method": "do_default",
                "_action": "list_methods",
                "version": __version__,
                "count": len(methods),
                "methods": methods[:20],
            }
        if action == "plan":
            url = args.get("url", "https://example.com")
            plan = plan_for_url(url)
            return {
                "_method": "do_default",
                "_action": "plan",
                "url": url,
                "content_type": content_type_label(plan.content_type),
            }
        if action == "version":
            return {"_method": "do_default", "_action": "version", "version": __version__}
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
