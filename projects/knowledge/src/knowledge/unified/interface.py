"""Unified Memory Interface — Three-Primitive Contract.

Defines the canonical query/ingest/search contract for bos://memory/unified,
replacing separate gbrain and kairon access paths with a single entry point.

Design principles:
- Consumer-agnostic: callers don't know which backend (gbrain/kairon) serves the result.
- Progressive degradation: if one backend is offline, degrade gracefully.
- Audit-first: every write produces a SyncEvent for downstream consistency checks.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from knowledge.models import KnowledgeDocument, RetrievalResult, SyncEvent

logger = logging.getLogger("knowledge.unified")


class UnifiedMemoryInterface(ABC):
    """Abstract unified memory contract — the single source of truth for memory operations.

    Three primitives:
    - query: retrieve knowledge by natural language or structured filter
    - ingest: write knowledge documents with dedup and conflict detection
    - search: full-text / semantic / graph-hybrid search with domain routing
    """

    @abstractmethod
    def query(
        self,
        q: str,
        *,
        domain: str = "common",
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve knowledge entries matching a query.

        Args:
            q: Natural language query string.
            domain: Business domain scope (work, health, knowledge, governance).
            limit: Maximum results to return.
            filters: Optional structured filters (zone, kind, trust_level, date_range).

        Returns:
            Ranked list of RetrievalResult entries, most relevant first.
        """
        ...

    @abstractmethod
    def ingest(
        self,
        documents: list[KnowledgeDocument],
        *,
        dedup: bool = True,
        source: str = "unified",
    ) -> list[SyncEvent]:
        """Write knowledge documents with dedup and conflict detection.

        Args:
            documents: Knowledge documents to ingest.
            dedup: If True, check for existing duplicates before writing.
            source: Origin identifier for audit trail.

        Returns:
            SyncEvent per document recording write outcome.
        """
        ...

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        domain: str = "common",
        limit: int = 10,
        include_entities: bool = True,
    ) -> list[RetrievalResult]:
        """Full search with mode routing (keyword / semantic / graph / hybrid).

        Args:
            query: Search query.
            mode: Search mode — keyword, semantic, graph, hybrid.
            domain: Business domain scope.
            limit: Maximum results.
            include_entities: If True, include matched entity IDs in results.

        Returns:
            Ranked search results with source attribution.
        """
        ...

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return health status of all underlying memory backends."""
        ...
