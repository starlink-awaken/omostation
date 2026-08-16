"""Pipeline stage: save research results to KOS ontology store.

Runs after OutputStageImpl. Creates a CONCEPT entity in KOS
with zone=minerva_research for auditability and cross-project discovery.

Single research saves run at L1 (auto-allowed, audit trail only).
Batch rebuilds are gated at L2 by the orchestrator.

Gracefully skips if KOS package is not installed (no hard dependency).
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

import structlog

from minerva.audit_store import AuditLogger
from minerva.pipeline.engine import IPipelineStage, ResearchContext

logger = structlog.get_logger(__name__)

# Lazy KOS import — not all deployments have it
_kos_store: dict[str, Any] | None = None


def _get_kos_store() -> dict[str, Any]:
    """Import KOS modules lazily, return a dict of references or empty."""
    global _kos_store
    if _kos_store is not None:
        return _kos_store
    try:
        from kos.ontology._types import Entity, EntityType
        from kos.ontology.store import put_entity, search_entities

        _kos_store = {
            "put_entity": put_entity,
            "search_entities": search_entities,
            "Entity": Entity,
            "EntityType": EntityType,
        }
    except ImportError:
        logger.warning("kos_import_failed", exc_info=True)
        _kos_store = {}
    return _kos_store


def _make_entity_id(query: str) -> str:
    """Generate deterministic KOS entity ID from query content."""
    prefix = hashlib.sha256(query.encode()).hexdigest()[:12]
    return f"RCH-{prefix}"


class KOSSaveStage(IPipelineStage):
    """Save research context to KOS as a CONCEPT entity.

    Skips silently if:
    - ctx.report is None (no research output)
    - KOS package is not installed (graceful degradation)
    """

    name = "kos_save"

    def __init__(self, confirmed: bool = False) -> None:
        self._confirmed = confirmed

    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        """Execute the stage: create KOS entity from research context.

        Returns ctx unchanged on success or skip.
        """
        if not ctx.report:
            logger.info("kos_save_skip_no_report", query=ctx.query)
            return ctx

        store = _get_kos_store()
        if not store:
            logger.info("kos_save_skip_no_kos", query=ctx.query)
            return ctx

        entity_id = _make_entity_id(ctx.query)
        audit = AuditLogger()
        t0 = time.time()

        entity = store["Entity"](
            entity_id=entity_id,
            entity_type=store["EntityType"].CONCEPT,
            label=ctx.query[:200],
            description=ctx.report[:2000],
            zone="minerva_research",
            source="minerva",
            confidence=0.85,
            metadata={
                "query": ctx.query,
                "level": ctx.level.value if hasattr(ctx.level, "value") else str(ctx.level),
                "cost": ctx.cost,
                "search_count": len(ctx.search_results),
                "entity_count": len(ctx.entities),
                "stage_timings": {k: round(v, 3) for k, v in ctx.stage_timings.items()},
            },
            references=[
                r.get("url", "") if isinstance(r, dict) else str(r).strip() for r in (ctx.search_results or [])
            ],
        )

        result = store["put_entity"](entity)
        duration_ms = (time.time() - t0) * 1000

        if "error" in result:
            audit.log(
                actor="pipeline",
                action="kos_save",
                resource=ctx.query[:100],
                result="error",
                detail=f"entity_id={entity_id}: {result['error']}",
                duration_ms=duration_ms,
            )
            logger.error("kos_save_failed", entity_id=entity_id, error=result["error"])
        else:
            audit.log(
                actor="pipeline",
                action="kos_save",
                resource=ctx.query[:100],
                result="success",
                detail=f"entity_id={entity_id}",
                duration_ms=duration_ms,
            )
            logger.info("kos_save_complete", entity_id=entity_id, query=ctx.query[:50])

        return ctx
