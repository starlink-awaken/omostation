"""Pipeline stage: immune audit for minerva research pipeline.

Runs after search/entity extraction. Audits research results against
SharedBrain D-Immunity before proceeding to analysis stages.

High-risk results are flagged with immune_review_required in metadata.
No auto-high-risk scheduling — just flagging for human review.

Gracefully skips if immune bridge is unavailable (audit only).
"""

from __future__ import annotations

import logging
import os
from typing import Any, cast

import httpx
import structlog

from minerva.pipeline.engine import IPipelineStage, ResearchContext

logger = structlog.get_logger(__name__)
_log = logging.getLogger(__name__)


class ImmuneAuditStage(IPipelineStage):
    """Audit research results against SharedBrain D-Immunity.

    Scans search results and extracted entities for HIGH risk content.
    Flagged items are marked with ``immune_review_required``.

    Single-research audits run at L1 (auto-allowed, audit trail only).
    No auto-high-risk scheduling — human review required for HIGH risk.
    """

    name = "immune_audit"

    def __init__(
        self,
        agora_endpoint: str = f"http://localhost:{os.environ.get('AGORA_MCP_HTTP_PORT', '7422')}",
        timeout: int = 10,
    ) -> None:
        self._endpoint = agora_endpoint.rstrip("/")
        self._timeout = timeout

    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        """Audit search results and entities in research context.

        Adds immune_review_required flags to the context if any HIGH risk
        content is found. Returns ctx unchanged on skip or failure.
        """
        items_to_audit: list[dict[str, str]] = []

        # Collect search results for audit
        for r in ctx.search_results or []:
            if isinstance(r, dict):
                items_to_audit.append(
                    {
                        "content": r.get("snippet", "") or r.get("content", "") or "",
                        "title": r.get("title", "") or "",
                        "source": r.get("source", "") or "unknown",
                    }
                )

        # Collect entities for audit
        for e in ctx.entities or []:
            if isinstance(e, dict):
                items_to_audit.append(
                    {
                        "content": e.get("description", "") or e.get("label", "") or "",
                        "title": e.get("label", "") or e.get("name", "") or "",
                        "source": e.get("source", "") or "entity_extraction",
                    }
                )

        if not items_to_audit:
            logger.info("immune_audit_skip_no_content", query=ctx.query)
            return ctx

        high_risk_count = 0
        for item in items_to_audit:
            try:
                result = await self._audit(item)
                if result.get("risk") == "HIGH":
                    high_risk_count += 1
                    _log.warning(
                        "Immune audit flagged HIGH risk: %s",
                        item.get("title", "")[:80],
                    )
            except Exception:
                _log.error("Immune audit request failed for item", exc_info=True)

        if high_risk_count > 0:
            # Flag the context for human review — stored in metadata
            ctx.metadata["immune_review_required"] = True
            ctx.metadata["immune_high_risk_count"] = high_risk_count
            logger.warning(
                "immune_audit_flagged",
                query=ctx.query[:100],
                high_risk_count=high_risk_count,
            )

        logger.info(
            "immune_audit_complete",
            query=ctx.query[:100],
            items_audited=len(items_to_audit),
            high_risk_count=high_risk_count,
        )
        return ctx

    async def _audit(self, item: dict[str, str]) -> dict[str, Any]:
        """Send a single item to SharedBrain D-Immunity for audit."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._endpoint}/call", json=item)
                return cast("dict[str, Any]", resp.json())
        except Exception as e:
            return {"risk": "UNKNOWN", "error": str(e)}
