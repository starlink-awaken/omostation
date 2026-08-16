"""P58-W0 kairon_observability do_default — 真业务 (调 metrics / alerts / SLO 真类)."""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 kairon_observability do_default: 真调 MetricsCollector / AlertManager / SLOTracker."""
    try:
        from kairon_observability import (
            AlertManager,
            MetricsCollector,
            SLOTracker,
        )
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "list_components")
    try:
        if action == "list_components":
            return {
                "_method": "do_default",
                "_action": "list_components",
                "MetricsCollector": MetricsCollector.__name__,
                "AlertManager": AlertManager.__name__,
                "SLOTracker": SLOTracker.__name__,
            }
        if action == "metric":
            mc = MetricsCollector()
            metric_name = args.get("metric", "test.metric")
            return {
                "_method": "do_default",
                "_action": "metric",
                "metric": metric_name,
                "collector": type(mc).__name__,
                "methods": [m for m in dir(mc) if not m.startswith("_")][:10],
            }
        if action == "alert":
            am = AlertManager()
            return {
                "_method": "do_default",
                "_action": "alert",
                "manager_type": type(am).__name__,
                "methods": [m for m in dir(am) if not m.startswith("_")][:10],
            }
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
