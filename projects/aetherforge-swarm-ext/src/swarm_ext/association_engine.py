from __future__ import annotations

import json
import logging
from typing import Any

_log = logging.getLogger(__name__)


class _LayeredLRUCacheStub:
    """Simple dict-based cache stub replacing LayeredLRUCache."""

    def __init__(self, max_items: int = 1000, mem_limit_mb: float = 128.0) -> None:
        self._data: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def put(self, key: str, value: Any, ttl: int = 3600) -> None:
        self._data[key] = value


LayeredLRUCache = _LayeredLRUCacheStub


def _get_graph_class() -> type[object] | None:
    """Lazy-import Graph from D-Memory to avoid cross-organ direct import."""
    try:
        Graph = __import__("organs.D_Memory.organs.fact_graph", fromlist=["Graph"]).Graph  # noqa: N806
        return Graph
    except (ImportError, AttributeError):
        return None


class ProceduralMapper:
    """Maps retrieved heterogeneous experiences to contextual hints."""

    @staticmethod
    def map_to_hints(current_task: str, associated_facts: list[dict[str, Any]]) -> list[str]:
        hints = []
        for fact in associated_facts:
            meta_str: Any = fact.get("metadata", "{}")
            if isinstance(meta_str, str):
                try:
                    meta: dict[str, Any] = json.loads(meta_str)
                except json.JSONDecodeError:
                    meta = {}
            else:
                meta = meta_str if isinstance(meta_str, dict) else {}

            if meta.get("type") == "procedural":
                pattern = meta.get("full_pattern", fact.get("sub"))
                solution = meta.get("patch_diff") or fact.get("obj")
                solution_str = str(solution) if solution is not None else ""
                hints.append(
                    f"[Associative Insight] Similar structural challenge "
                    f"'{pattern}' was resolved by: \n{solution_str[:200]}..."
                )
            else:
                hints.append(f"[Latent Link] Related concept: {fact['sub']} {fact['pred']} {fact['obj']}")

        return hints


class AssociationEngine:
    """[RFC-030] Cross-context association engine.

    Provides serendipitous latent retrieval with LRU cache for memory control.
    """

    _instance: AssociationEngine | None = None

    @classmethod
    def get_instance(cls) -> AssociationEngine:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def trigger_association(self, intent: str, complexity: float = 1.0) -> list[str]:
        return []
