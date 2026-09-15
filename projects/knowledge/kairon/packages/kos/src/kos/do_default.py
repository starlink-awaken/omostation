"""P57-W0 kos do_default — 真业务 (调 kos.search 真函数)."""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P57-W0 kos do_default: 真调 kos.search 真业务."""
    try:
        from kos import list_documents, search, stats
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "search")
    try:
        if action == "search":
            query = args.get("query", "")
            meta_type = args.get("meta_type")
            limit = int(args.get("limit", 10))
            results = search(query, meta_type=meta_type, limit=limit)
            return {
                "_method": "do_default",
                "_action": "search",
                "query": query,
                "count": len(results),
                "results": results[:5],
            }
        if action == "list_documents":
            limit = int(args.get("limit", 10))
            docs = list_documents(limit=limit)
            return {
                "_method": "do_default",
                "_action": "list_documents",
                "count": len(docs),
                "docs": docs[:5],
            }
        if action == "stats":
            s = stats()
            return {"_method": "do_default", "_action": "stats", "stats": s}
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
