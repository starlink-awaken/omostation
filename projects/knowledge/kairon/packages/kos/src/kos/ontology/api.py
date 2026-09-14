"""Ontology API adapter — CLI/MCP integration layer.

Adapted from SPEC-v0.1.md §4.7.
"""

from typing import Any

from kos.ontology import discover, export, resolver, store  # type: ignore[import-not-found]


def handle_action(action: str, **kwargs: Any) -> Any:
    """Dispatch ontology actions from CLI or MCP."""
    if action == "put":
        from kos.ontology._types import Entity  # type: ignore[import-not-found]

        return store.put_entity(Entity(**kwargs))
    elif action == "get":
        return store.get_entity(kwargs.get("entity_id", ""))
    elif action == "search":
        return store.search_entities(
            kwargs.get("query", ""),
            entity_type=kwargs.get("entity_type"),
            zone=kwargs.get("zone"),
            limit=kwargs.get("limit", 20),
        )
    elif action == "delete":
        return store.delete_entity(kwargs.get("entity_id", ""))
    elif action == "resolve":
        entity = store.get_entity(kwargs.get("entity_id", ""))
        if entity:
            threshold = kwargs.get("threshold", 0.7)
            return [
                {"target": c.target_id, "score": c.score, "method": c.method}
                for c in resolver.find_candidates(entity, threshold)
            ]
        return {"error": "not found"}
    elif action == "merge":
        return resolver.merge_entities(kwargs["source_id"], kwargs["target_id"])
    elif action == "discover":
        return discover.discover_implicit_relations(kwargs.get("threshold", 3))
    elif action == "path":
        return discover.shortest_path(kwargs["from_id"], kwargs["to_id"])
    elif action == "export":
        return export.export_jsonld(kwargs.get("zone"))
    elif action == "summary":
        return export.export_entity_summary(kwargs.get("zone"))
    return {"error": f"Unknown action: {action}"}
