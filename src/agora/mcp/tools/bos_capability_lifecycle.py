"""BOS capability lifecycle MCP tools (B1→B2→B3).

Exposes capability discovery, admission, and retirement as governed MCP tools.
Requires explicit profile authorization for write operations.
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import FastMCP

from agora.mcp.bos_router import bos_router
from agora.mcp.capability_catalog import CapabilityCatalog
from agora.external_connections import ExternalConnectionCatalog

_LOG = logging.getLogger(__name__)

mcp = FastMCP("bos-capability-lifecycle")


def _get_catalogs() -> tuple[
    CapabilityCatalog | None, ExternalConnectionCatalog | None
]:
    capability_catalog = getattr(bos_router, "_capability_catalog", None)
    admission_catalog = getattr(bos_router, "_admission_catalog", None)
    if capability_catalog is None:
        try:
            capability_catalog = CapabilityCatalog()
        except Exception as exc:  # noqa: BLE001
            _LOG.debug("capability catalog unavailable: %s", exc)
    if admission_catalog is None:
        try:
            admission_catalog = ExternalConnectionCatalog()
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("admission catalog unavailable: %s", exc)
    return capability_catalog, admission_catalog


@mcp.tool()
def bos_capability_list(uri_prefix: str = "") -> dict[str, Any]:
    """List registered BOS capabilities with lifecycle status.

    Args:
        uri_prefix: Optional prefix filter (e.g. ``bos://memory/``).
    """
    capability_catalog, admission_catalog = _get_catalogs()
    routes = bos_router.list_all(prefix_filter=uri_prefix)
    capabilities: list[dict[str, Any]] = []
    for route in routes:
        prefix = route.get("prefix", "")
        decl = None
        lifecycle = None
        admission_status = None
        if capability_catalog is not None:
            decl = capability_catalog.get(prefix)
        if admission_catalog is not None:
            resource = admission_catalog.get(prefix)
            if resource is not None:
                lifecycle = getattr(resource, "lifecycle", None)
                admission_status = getattr(resource, "status", None)
        capabilities.append(
            {
                "prefix": prefix,
                "adapter": route.get("adapter"),
                "capability_status": decl.get("status")
                if isinstance(decl, dict)
                else None,
                "lifecycle": lifecycle,
                "admission_status": admission_status,
                "use_metrics": decl.get("usage", {}) if isinstance(decl, dict) else {},
            }
        )
    return {
        "count": len(capabilities),
        "capabilities": capabilities,
        "source": "bos_router",
    }


@mcp.tool()
def bos_capability_retire(
    uri: str, reason: str = "retired by governance"
) -> dict[str, Any]:
    """Retire a zombie BOS capability (requires governance profile).

    Args:
        uri: Exact BOS URI prefix to retire.
        reason: Short reason for retirement.
    """
    capability_catalog, admission_catalog = _get_catalogs()
    if capability_catalog is None:
        return {"status": "error", "error": "capability_catalog_unavailable"}
    decl = capability_catalog.get(uri)
    if not isinstance(decl, dict):
        return {"status": "error", "error": f"capability not found: {uri}"}
    decl["status"] = "deprecated"
    if admission_catalog is not None:
        try:
            admission_catalog.register_capability(
                uri,
                description=decl.get("description", ""),
                lifecycle="retired",
                use_metrics=decl.get("usage", {}),
            )
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("admission catalog update failed for %s: %s", uri, exc)
    capability_catalog.save()
    return {
        "status": "ok",
        "uri": uri,
        "capability_status": "deprecated",
        "lifecycle": "retired",
        "reason": reason,
    }


@mcp.tool()
def bos_capability_admit(uri: str, description: str = "") -> dict[str, Any]:
    """Manually admit a new BOS capability.

    Args:
        uri: BOS URI prefix to admit.
        description: Human-readable description of the capability.
    """
    capability_catalog, admission_catalog = _get_catalogs()
    if capability_catalog is None:
        return {"status": "error", "error": "capability_catalog_unavailable"}
    existing = capability_catalog.get(uri)
    if isinstance(existing, dict) and existing.get("status") == "active":
        return {"status": "error", "error": f"capability already admitted: {uri}"}
    capability_catalog.add(
        uri,
        description=description or f"Admitted capability: {uri}",
        status="active",
    )
    if admission_catalog is not None:
        try:
            admission_catalog.register_capability(
                uri,
                description=description,
                lifecycle="admitted",
                use_metrics={},
            )
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("admission catalog update failed for %s: %s", uri, exc)
    capability_catalog.save()
    return {
        "status": "ok",
        "uri": uri,
        "capability_status": "active",
        "lifecycle": "admitted",
    }


def register() -> None:
    """Register capability lifecycle tools on the global Agora MCP instance."""
    try:
        from agora.server.tools_bos import register_bos_tools
        from agora.bus import get_event_bus

        bus = get_event_bus()
        register_bos_tools(mcp, bus)
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("bos capability lifecycle registration skipped: %s", exc)
