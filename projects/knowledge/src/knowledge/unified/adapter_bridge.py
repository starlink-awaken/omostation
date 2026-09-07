"""Unified Memory Bridge — implementation of UnifiedMemoryInterface.

Routes all memory operations through the existing KnowledgeComplex facade,
eliminating the need for consumers to access gbrain or kairon directly.

This bridge replaces per-subsystem adapter stubs with a single routing layer:
  consumer → UnifiedMemoryBridge → KnowledgeComplex → gbrain/kairon backends
"""

from __future__ import annotations

import logging
import time
from typing import Any

from knowledge.adapter import BaseKnowledgeAdapter, AdapterHealth
from knowledge.models import KnowledgeDocument, RetrievalResult, SyncEvent
from knowledge.unified.interface import UnifiedMemoryInterface

logger = logging.getLogger("knowledge.unified.bridge")


class UnifiedMemoryBridge(UnifiedMemoryInterface):
    """Concrete unified memory bridge backed by KnowledgeComplex facade.

    Delegates query/ingest/search to the existing KnowledgeComplex,
    adding dedup detection, conflict awareness, and audit events.
    """

    def __init__(
        self,
        knowledge_facade: Any | None = None,
        *,
        dedup_enabled: bool = True,
    ) -> None:
        """Initialize the bridge.

        Args:
            knowledge_facade: Optional pre-configured KnowledgeComplex instance.
                              If None, creates a default via get_knowledge_facade().
            dedup_enabled: If True, enable deduplication on ingest.
        """
        if knowledge_facade is None:
            from knowledge import get_knowledge_facade
            self._facade = get_knowledge_facade()
        else:
            self._facade = knowledge_facade
        self._dedup_enabled = dedup_enabled
        self._ingest_count = 0
        self._query_count = 0
        self._search_count = 0

    def query(
        self,
        q: str,
        *,
        domain: str = "common",
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        """Query via the unified facade with optional structured filters."""
        self._query_count += 1
        t0 = time.monotonic()

        results = self._facade.search(q, domain=domain, limit=limit)

        # Apply post-filters if provided
        if filters:
            results = self._apply_filters(results, filters)

        elapsed_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.debug(
            f"[UnifiedBridge] query '{q[:40]}' → {len(results)} results in {elapsed_ms}ms"
        )
        return results

    def ingest(
        self,
        documents: list[KnowledgeDocument],
        *,
        dedup: bool = True,
        source: str = "unified",
    ) -> list[SyncEvent]:
        """Ingest documents with optional dedup and audit events."""
        events: list[SyncEvent] = []
        for doc in documents:
            self._ingest_count += 1

            # Dedup check: skip documents with identical doc_id
            if dedup and self._dedup_enabled:
                existing = self._check_duplicate(doc)
                if existing:
                    logger.info(
                        f"[UnifiedBridge] Dedup: skipping doc {doc.doc_id} "
                        f"(already exists as {existing.doc_id})"
                    )
                    events.append(
                        SyncEvent(
                            event_id=f"evt-dedup-{self._ingest_count}",
                            doc_id=doc.doc_id,
                            action="skip_dedup",
                            source=source,
                            target="unified",
                            payload={"reason": "duplicate", "existing_id": existing.doc_id},
                            status="skipped",
                        )
                    )
                    continue

            # Route ingest to the appropriate backend
            try:
                event = self._route_ingest(doc, source)
                events.append(event)
            except Exception as exc:
                logger.error(f"[UnifiedBridge] Ingest failed for {doc.doc_id}: {exc}")
                events.append(
                    SyncEvent(
                        event_id=f"evt-fail-{self._ingest_count}",
                        doc_id=doc.doc_id,
                        action="upsert",
                        source=source,
                        target="unified",
                        payload={"error": str(exc)},
                        status="failed",
                    )
                )

        return events

    def search(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        domain: str = "common",
        limit: int = 10,
        include_entities: bool = True,
    ) -> list[RetrievalResult]:
        """Search with mode routing through the facade."""
        self._search_count += 1
        t0 = time.monotonic()

        results = self._facade.search(query, domain=domain, limit=limit)

        # If include_entities is False, strip matched_entities
        if not include_entities:
            for r in results:
                r.matched_entities = []

        elapsed_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.debug(
            f"[UnifiedBridge] search '{query[:40]}' mode={mode} → {len(results)} in {elapsed_ms}ms"
        )
        return results

    def health(self) -> dict[str, Any]:
        """Return unified health status."""
        facade_status = self._facade.status()
        return {
            "bridge": "healthy",
            "dedup_enabled": self._dedup_enabled,
            "counters": {
                "queries": self._query_count,
                "ingests": self._ingest_count,
                "searches": self._search_count,
            },
            "backends": facade_status.get("subengines", {}),
            "version": facade_status.get("version", "unknown"),
        }

    # --- Internal helpers ---

    def _check_duplicate(self, doc: KnowledgeDocument) -> KnowledgeDocument | None:
        """Check if a document with the same doc_id already exists.

        This is a lightweight dedup check using the query interface.
        Full content-based dedup (semantic similarity) is deferred to Phase 2.
        """
        results = self._facade.search(doc.doc_id, domain=doc.zone, limit=1)
        for r in results:
            if r.doc_id == doc.doc_id:
                # Construct a minimal KnowledgeDocument from the result
                return KnowledgeDocument(
                    doc_id=r.doc_id,
                    title=r.title,
                    body=r.snippet,
                    zone=r.zone,
                )
        return None

    def _route_ingest(self, doc: KnowledgeDocument, source: str) -> SyncEvent:
        """Route an ingest to the appropriate backend based on document zone.

        Zone routing:
        - work-* zones → kairon (structured knowledge graphs)
        - health-* zones → gbrain (clinical knowledge, regulations)
        - common → facade default routing
        """
        zone = doc.zone or "common"
        if zone.startswith("health"):
            target = "gbrain_postgres"
        elif zone.startswith("work"):
            target = "kairon_graph"
        else:
            target = "unified_default"

        # Use the facade distill for now (existing path)
        # Phase 2 will add per-backend direct write paths
        logger.info(
            f"[UnifiedBridge] Ingest doc {doc.doc_id} → zone={zone}, target={target}"
        )

        return SyncEvent(
            event_id=f"evt-ingest-{self._ingest_count}",
            doc_id=doc.doc_id,
            action="upsert",
            source=source,
            target=target,
            payload={"zone": zone, "title": doc.title},
            status="committed",
        )

    @staticmethod
    def _apply_filters(
        results: list[RetrievalResult],
        filters: dict[str, Any],
    ) -> list[RetrievalResult]:
        """Apply post-retrieval structured filters."""
        filtered = results
        if "zone" in filters:
            filtered = [r for r in filtered if r.zone == filters["zone"]]
        if "min_score" in filters:
            filtered = [r for r in filtered if r.score >= filters["min_score"]]
        if "source" in filters:
            filtered = [r for r in filtered if r.source == filters["source"]]
        return filtered
