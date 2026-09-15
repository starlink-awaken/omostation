"""RAG (Retrieval-Augmented Generation) pipeline for Minerva.

Builds context from the knowledge base to enrich LLM prompts with relevant
previously-researched information. Uses LanceDB semantic search + SQLite FTS5
for hybrid retrieval, with LRU embedding cache to avoid redundant computation.
"""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# LRU embedding cache to avoid re-encoding identical texts
try:
    from cachetools import TTLCache

    _embedding_cache: TTLCache = TTLCache(maxsize=1000, ttl=3600)  # type: ignore[reportAssignmentType]
except ImportError:
    _embedding_cache: dict = {}  # type: ignore[no-redef]  # Fallback if cachetools unavailable


class RAGContextBuilder:
    """Retrieve relevant knowledge entries and build context for LLM prompts."""

    def __init__(self, knowledge_store: Any = None, vector_store: Any = None, top_k: int = 5) -> None:
        self.kb = knowledge_store
        self.vs = vector_store
        self.top_k = top_k

    async def build_context(self, query: str) -> str:
        """Search knowledge base and return formatted context string.

        Uses hybrid retrieval: LanceDB semantic + SQLite FTS5 fulltext,
        deduplicated and ranked. Returns empty string if no results or no KB.
        """
        # Parallel hybrid retrieval: LanceDB semantic + SQLite FTS5
        import asyncio

        entries: list[dict] = []

        async def _semantic() -> Any:
            if self.vs:
                try:
                    return await self.vs.search(query, top_k=self.top_k)
                except Exception:
                    return []
            return []

        async def _fulltext() -> Any:
            if self.kb:
                try:
                    return await self.kb.search(query, mode="fulltext", top_k=self.top_k)
                except Exception:
                    return []
            return []

        semantic, fts = await asyncio.gather(_semantic(), _fulltext())
        entries = list(semantic) + list(fts)

        if not entries:
            return ""

        # Deduplicate by id
        seen: set[str] = set()
        unique = []
        for e in entries:
            eid = e.get("id", e.get("name", ""))
            if eid and eid not in seen:
                seen.add(eid)
                unique.append(e)

        # Format context
        lines = ["Relevant knowledge from previous research:"]
        for _i, e in enumerate(unique[: self.top_k]):
            name = e.get("name", e.get("content", "Unknown"))
            etype = e.get("type", "Concept")
            lines.append(f"  [{etype}] {name}")
        return "\n".join(lines)

    def enrich_prompt(self, system: str, context: str) -> str:
        """Inject RAG context into the system prompt."""
        if not context:
            return system
        return f"{system}\n\n{context}"


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def get_cached_embedding(text: str) -> list[float] | None:
    """Return cached embedding if available."""
    return _embedding_cache.get(_cache_key(text))


def set_cached_embedding(text: str, vector: list[float]) -> None:
    """Store embedding in LRU cache."""
    _embedding_cache[_cache_key(text)] = vector
