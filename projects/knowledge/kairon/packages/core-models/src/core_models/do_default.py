"""P58-W0 core_models do_default — 真业务 (调 core_models models 真函数)."""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 core_models do_default: 真调 ENTITY_TYPES / RELATION_TYPES / Entity."""
    try:
        from core_models import ENTITY_TYPES, RELATION_TYPES, Entity, KnowledgeGraph, Relation
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "schema")
    try:
        if action == "schema":
            return {
                "_method": "do_default",
                "_action": "schema",
                "entity_types": list(ENTITY_TYPES),
                "relation_types": list(RELATION_TYPES),
                "entity_count": len(ENTITY_TYPES),
                "relation_count": len(RELATION_TYPES),
            }
        if action == "types":
            return {
                "_method": "do_default",
                "_action": "types",
                "Entity": Entity.__name__,
                "Relation": Relation.__name__,
                "KnowledgeGraph": KnowledgeGraph.__name__,
            }
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
