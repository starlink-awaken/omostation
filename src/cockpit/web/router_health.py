"""Shared router loading registry for dashboard diagnostics and SystemMap."""

from __future__ import annotations

ROUTER_MODULES = (
    "cockpit.web.governance.api",
    "cockpit.web.api_compute",
    "cockpit.web.api_domain_apps",
    "cockpit.web.api_system_map",
    "cockpit.web.api_omos",
    "cockpit.web.api_ecos",
    "cockpit.web.api_knowledge",
    "cockpit.web.api_bos",
    "cockpit.web.api_proposals",
    "cockpit.web.api_metaos",
    "cockpit.web.api_agora",
    "cockpit.web.api_sandbox",
    "cockpit.web.api_l4",
    "cockpit.web.api_health",
    "cockpit.web.api_alerts",
    "cockpit.web.api_tasks",
    "cockpit.web.api_kems",
    "cockpit.web.api_logs",
    "cockpit.web.api_metrics",
    "cockpit.web.api_hubs",
)

ROUTER_LOAD_REPORT: list[dict[str, object]] = []


def router_health_snapshot() -> dict[str, object]:
    """Return a stable, read-only snapshot for SystemMap and operator views."""
    loaded = sum(1 for item in ROUTER_LOAD_REPORT if item.get("status") == "loaded")
    unavailable = [item for item in ROUTER_LOAD_REPORT if item.get("status") != "loaded"]
    return {
        "status": "ready" if not unavailable and ROUTER_LOAD_REPORT else "attention",
        "summary": {
            "total": len(ROUTER_LOAD_REPORT),
            "loaded": loaded,
            "unavailable": len(unavailable),
        },
        "items": [dict(item) for item in ROUTER_LOAD_REPORT],
    }
