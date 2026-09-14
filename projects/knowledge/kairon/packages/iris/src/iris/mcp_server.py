"""FastMCP server for Iris — exposes all connector operations as MCP tools.

Tools:
  iris_list_connectors
  iris_connector_status
  iris_list_items
  iris_get_item
  iris_search
  iris_sync
  iris_validate
"""

from __future__ import annotations

from typing import Any, cast

from iris.config import IrisConfig

FORMAT_VERSION = "iris-v1"

# Lazy imports to keep MCP server fast on startup
_registry = None
_config = None


def _ensure_registry() -> Any:
    global _registry
    if _registry is None:
        from iris.connectors import register_all
        from iris.registry import ConnectorRegistry

        _registry = ConnectorRegistry()
        register_all(_registry)
    return _registry


def _ensure_config() -> Any:
    global _config
    if _config is None:
        _config = IrisConfig()
    return _config


_eidos = None


def _ensure_eidos() -> Any:
    global _eidos
    if _eidos is None:
        from iris.adapters.eidos import EidosAdapter

        _eidos = EidosAdapter()
    return _eidos


# ── Tool implementations ──


def list_connectors() -> list[dict[str, Any]]:
    """List all registered connectors with their availability status."""
    registry = _ensure_registry()
    return cast("list[dict[str, Any]]", registry.status_all())


def connector_status(name: str) -> dict[str, Any]:
    """Get health status for a specific connector."""
    registry = _ensure_registry()
    conn = registry.get(name)
    if not conn:
        return {"name": name, "available": False, "error": f"Unknown connector: {name}"}
    try:
        available = conn.is_available()
        s = conn.status()
        return {"name": name, "display_name": conn.display_name, "available": available, **s}
    except Exception as e:
        return {"name": name, "available": False, "error": str(e)}


def list_items(platform: str, limit: int = 20, cursor: str | None = None) -> list[dict[str, Any]]:
    """List items from a specific platform with pagination."""
    registry = _ensure_registry()
    conn = registry.get(platform)
    if not conn:
        return [{"error": f"Unknown platform: {platform}"}]
    if not conn.is_available():
        return [{"error": f"{platform} is not available"}]
    items = conn.list_items(limit=limit, cursor=cursor)
    return [item.to_dict() for item in items]


def get_item(platform: str, id: str) -> dict[str, Any]:
    """Get a single item by platform and ID.

    Returns the item as an eidos-validated KnowledgeCard dict.
    """
    registry = _ensure_registry()
    conn = registry.get(platform)
    if not conn:
        return {"error": f"Unknown platform: {platform}"}
    if not conn.is_available():
        return {"error": f"{platform} is not available"}
    item = conn.get_item(id)
    if item is None:
        return {"error": f"Item {id} not found on {platform}"}

    card = item.to_knowledge_card()

    eidos = _ensure_eidos()
    if eidos.is_eidos_available():
        validation = eidos.validate_knowledge_card(card)
        if not validation.get("is_valid", True):
            return {
                "error": "Item failed eidos validation",
                "item": card,
                "validation_errors": validation.get("errors", []),
            }
        card["_validation"] = validation
    return cast("dict[str, Any]", card)


def search(platform: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search a platform's content by query string."""
    registry = _ensure_registry()
    conn = registry.get(platform)
    if not conn:
        return [{"error": f"Unknown platform: {platform}"}]
    if not conn.is_available():
        return [{"error": f"{platform} is not available"}]
    items = conn.search(query, limit=limit)
    return [item.to_dict() for item in items]


def sync(platforms: list[str] | None = None) -> list[dict[str, Any]]:
    """Pull latest data from one or more platforms."""
    registry = _ensure_registry()
    names = platforms or registry.list_names()
    results = []
    for name in names:
        conn = registry.get(name)
        if not conn:
            results.append({"connector": name, "success": False, "error": "Unknown connector"})
            continue
        result = conn.sync()
        results.append(result.to_dict())
    return results


def sync_bidirectional(dry_run: bool = False) -> dict[str, Any]:
    """Execute Obsidian ↔ WPS Note bidirectional sync.

    Returns a dict with sync statistics.
    """
    from iris.connectors.obsidian import ObsidianConnector
    from iris.connectors.wpsnote import WPSNoteConnector
    from iris.sync.engine import SyncEngine

    config = _ensure_config()
    obsidian = ObsidianConnector(config)
    wpsnote = WPSNoteConnector(config)

    if not obsidian.is_available():
        return {"success": False, "error": "Obsidian connector is not available"}
    if not wpsnote.is_available():
        return {"success": False, "error": "WPS Note connector is not available"}

    engine = SyncEngine(obsidian, wpsnote, config=config)
    result = engine.sync_bidirectional(dry_run=dry_run)
    return result.to_dict()


def validate(data: dict[str, Any], schema_type: str = "KnowledgeCard") -> dict[str, Any]:
    """Validate a data dict against an eidos schema."""
    eidos = _ensure_eidos()
    st = schema_type.lower()
    if "card" in st or "knowledge" in st:
        return cast("dict[str, Any]", eidos.validate_knowledge_card(data))
    elif "fact" in st:
        return cast("dict[str, Any]", eidos.validate_fact(data))
    elif "node" in st or "ontology" in st:
        return cast("dict[str, Any]", eidos.validate_ontology_node(data))
    else:
        return {"is_valid": False, "errors": [f"Unknown schema type: {schema_type}"]}


def main() -> None:
    """Start iris MCP server using FastMCP."""
    try:
        from fastmcp import FastMCP
    except ImportError:
        print("FastMCP is required. Install: pip install fastmcp", file=__import__("sys").stderr)
        __import__("sys").exit(1)

    mcp = FastMCP("iris-mcp")  # type: ignore[reportPossiblyUnboundVariable]

    @mcp.tool()
    def iris_list_connectors() -> dict[str, Any]:
        """List all registered connectors with availability status."""
        items = list_connectors()
        return {"items": items, "format_version": FORMAT_VERSION}

    @mcp.tool()
    def iris_connector_status(name: str) -> dict[str, Any]:
        """Get health/status for a specific connector."""
        result = connector_status(name)
        result["format_version"] = FORMAT_VERSION
        return result

    @mcp.tool()
    def iris_list_items(
        platform: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """List items from a platform (notes, highlights, articles)."""
        items = list_items(platform, limit, cursor)
        return {"items": items, "format_version": FORMAT_VERSION}

    @mcp.tool()
    def iris_get_item(platform: str, id: str) -> dict[str, Any]:
        """Get a single item by platform and ID, validated as KnowledgeCard."""
        result = get_item(platform, id)
        result["format_version"] = FORMAT_VERSION
        return result

    @mcp.tool()
    def iris_search(
        platform: str,
        query: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search platform content by query."""
        items = search(platform, query, limit)
        return {"items": items, "format_version": FORMAT_VERSION}

    @mcp.tool()
    def iris_sync(
        platforms: list[str] | None = None,
    ) -> dict[str, Any]:
        """Pull latest data from platforms. Omit to sync all."""
        results = sync(platforms)
        return {"results": results, "format_version": FORMAT_VERSION}

    @mcp.tool()
    def iris_sync_bidirectional(
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """执行 Obsidian ↔ WPS Note 双向同步。启用时同步最新数据到两端。"""
        result = sync_bidirectional(dry_run=dry_run)
        result["format_version"] = FORMAT_VERSION
        return result

    @mcp.tool()
    def iris_validate(
        data: dict[str, Any],
        schema_type: str = "KnowledgeCard",
    ) -> dict[str, Any]:
        """Validate a dict against eidos KnowledgeCard/Fact/OntologyNode schema."""
        result = validate(data, schema_type)
        result["format_version"] = FORMAT_VERSION
        return result

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
