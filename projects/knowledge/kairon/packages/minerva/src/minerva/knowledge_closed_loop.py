"""Knowledge Closed-Loop Orchestrator.

User query → KOS search cache → minerva research → KOSSaveStage → audit log.

Architecture:
    The orchestrator wraps a ResearchExecutor whose pipeline already includes
    KOSSaveStage (enabled via create_default_pipeline(kos_save_enabled=True)).

Flow:
    1. Audit: log start
    2. KOS cache check (skipped when fresh=True or KOS unavailable)
    3. L2 batch guard (requires confirmed=True)
    4. Run pipeline via executor.execute_now (includes KOSSaveStage)
    5. Audit: log complete
    6. Return standard _ok() response

Operation Levels:
    - Single query research: L1 auto-allowed (KOSSaveStage saves to KOS)
    - Batch rebuild: L2 requires confirmed=True (denied without confirmation)
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

import structlog

from minerva.audit_store import AuditLogger
from minerva.executor.executor import ExecutionMode, ResearchExecutor, ResearchTask

FORMAT_VERSION = "minerva-v1"
logger = structlog.get_logger(__name__)


def _ok_response(**kwargs: Any) -> dict:
    """Build standard success response."""
    return {"status": "ok", "format_version": FORMAT_VERSION, **kwargs}


def _error_response(msg: str) -> dict:
    """Build standard error response."""
    return {"status": "error", "error": msg, "format_version": FORMAT_VERSION}


class KnowledgeClosedLoop:
    """Orchestrate the knowledge closed-loop flow.

    Usage:
        loop = KnowledgeClosedLoop(executor)
        result = await loop.search("What is MoE?", level="auto", fresh=True)
    """

    def __init__(self, executor: ResearchExecutor) -> None:
        self.executor = executor
        self.audit = AuditLogger()
        self._kos_store: dict[str, Any] | None = None

    # ── Lazy KOS import ──────────────────────────────────────

    def _get_kos(self) -> dict[str, Any]:
        if self._kos_store is not None:
            return self._kos_store
        try:
            from kos.ontology._types import Entity, EntityType
            from kos.ontology.store import search_entities

            self._kos_store = {
                "search_entities": search_entities,
                "Entity": Entity,
                "EntityType": EntityType,
            }
        except ImportError:
            self._kos_store = {}
        return self._kos_store

    def _make_entity_id(self, query: str) -> str:
        """Deterministic entity ID for a query."""
        prefix = hashlib.sha256(query.encode()).hexdigest()[:12]
        return f"RCH-{prefix}"

    # ── KOS cache check ─────────────────────────────────────

    def _check_kos_cache(self, query: str) -> dict | None:
        """Search KOS for existing research results for this query.

        Returns cached entity info or None.
        """
        store = self._get_kos()
        if not store:
            return None

        try:
            results = store["search_entities"](query, zone="minerva_research", limit=3)
        except Exception:
            return None

        # Find exact or best match
        for entity in results:
            label = (entity.label or "").strip().lower()
            if label == query.strip().lower() or label.startswith(query.strip().lower()[:50]):
                return {
                    "entity_id": entity.entity_id,
                    "label": entity.label,
                    "description": getattr(entity, "description", "")[:300],
                }
            # Fuzzy: query appears in label
            if query.strip().lower() in label:
                return {
                    "entity_id": entity.entity_id,
                    "label": entity.label,
                    "description": getattr(entity, "description", "")[:300],
                }
        return None

    # ── Public API ───────────────────────────────────────────

    async def search(
        self,
        query: str,
        level: str = "auto",
        confirmed: bool = False,
        fresh: bool = False,
    ) -> dict:
        """Run the knowledge closed-loop.

        Args:
            query: Research question
            level: Pipeline level — auto|L0|L1|L2|L3|L4
            confirmed: L2 confirmation for batch/rebuild operations
            fresh: Skip KOS cache, force fresh research

        Returns:
            _ok() dict with research results.
        """
        t0 = time.time()

        # 1. Audit: start
        self.audit.log(
            actor="mcp",
            action="closed_loop",
            resource=query[:100],
            result="pending",
        )
        logger.info("closed_loop_start", query=query[:80], level=level, fresh=fresh)

        # 2. KOS cache hit (skip when fresh=True)
        if not fresh:
            cached = self._check_kos_cache(query)
            if cached is not None:
                duration_ms = (time.time() - t0) * 1000
                self.audit.log(
                    actor="mcp",
                    action="closed_loop",
                    resource=query[:100],
                    result="cache_hit",
                    detail=f"entity_id={cached['entity_id']}",
                    duration_ms=duration_ms,
                )
                logger.info("closed_loop_cache_hit", entity_id=cached["entity_id"])
                return _ok_response(
                    action="cache_hit",
                    query=query,
                    level=level,
                    entity_id=cached["entity_id"],
                    label=cached["label"],
                    description=cached["description"],
                    elapsed_ms=round(duration_ms, 1),
                )

        # 3. L2 batch/rebuild guard
        if level == "batch" and not confirmed:
            duration_ms = (time.time() - t0) * 1000
            self.audit.log(
                actor="mcp",
                action="closed_loop",
                resource=query[:100],
                result="denied",
                detail="L2 batch requires confirmed=True",
                duration_ms=duration_ms,
            )
            logger.warning("closed_loop_l2_denied", query=query[:80])
            return _error_response(
                "L2 batch operation requires confirmed=True. Set confirmed=True to proceed with batch rebuild."
            )

        # 4. Run research pipeline (includes KOSSaveStage)
        task = ResearchTask(
            id=str(uuid.uuid4())[:8],
            query=query,
            mode=ExecutionMode.IMMEDIATE,
            level=level,
            max_cost=5.0,
        )

        try:
            result = await self.executor.execute_now(task)
        except Exception as exc:
            duration_ms = (time.time() - t0) * 1000
            self.audit.log(
                actor="mcp",
                action="closed_loop",
                resource=query[:100],
                result="error",
                detail=str(exc)[:500],
                duration_ms=duration_ms,
            )
            logger.error("closed_loop_error", query=query[:80], error=str(exc))
            return _error_response(str(exc))

        duration_ms = (time.time() - t0) * 1000
        entity_id = self._make_entity_id(query)

        # 5. Audit: complete
        self.audit.log(
            actor="mcp",
            action="closed_loop",
            resource=query[:100],
            result="success",
            detail=f"entity_id={entity_id}, cost={result.cost}",
            duration_ms=duration_ms,
        )
        logger.info("closed_loop_complete", entity_id=entity_id, cost=result.cost)

        return _ok_response(
            action="completed",
            query=query,
            level=level,
            entity_id=entity_id,
            task_id=result.task_id,
            summary=result.summary[:500] if result.summary else "",
            report_path=result.report_path,
            cost=result.cost,
            completed_at=result.completed_at,
            elapsed_ms=round(duration_ms, 1),
            stage_timings=result.context.stage_timings,
        )
