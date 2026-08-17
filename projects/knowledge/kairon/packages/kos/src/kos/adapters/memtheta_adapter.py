"""
MemTheta Dual-Track Pipeline Adapter
====================================
Implements the MemTheta dual-track memory architecture for eCOS Phase 1.3.
- Raw Track: Original raw conversations append to local .omo/_log
- Theta Track: Summarized meta-nodes pushed to gbrain via MCP/DB

Exposes operators:
- update: Overwrite an existing state instead of appending.
- merge: Distill multiple fragments into a higher-density meta-node.
- filter: Evict cold nodes.

.. deprecated:: T3-03 (2026-08-08)
   Theta track is logger-only simulation. Superseded by MOS DualTrackWriter.
   Raw-track OMO event emit preserved for backward compat; new writes MUST use MOS.
"""

import json
import logging
import os
import warnings
from pathlib import Path
from typing import Any

from kairon_observability.tracing import get_tracer

logger = logging.getLogger(__name__)
warnings.warn(
    "kos.adapters.memtheta_adapter is deprecated (T3-03). Use MOS DualTrackWriter instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Fallback workspace directory detection
WORKSPACE_DIR = os.environ.get("ECOS_WORKSPACE", str(Path.home() / "Workspace"))


class MemThetaAdapter:
    """
    Adapter implementing the Dual-Track memory write pipeline.
    """

    def __init__(self, workspace_path: str | None = None):
        self.workspace = Path(workspace_path or WORKSPACE_DIR)

    def _emit_omo_event(self, domain: str, payload: dict[str, Any]) -> None:
        """X1/X4 Governance: Emit raw track via OMO Event Bus."""
        import subprocess

        try:
            subprocess.run(
                [
                    "omo",
                    "event",
                    "emit",
                    "--type",
                    f"memory.{domain}",
                    "--source",
                    "memtheta",
                    "--payload",
                    json.dumps(payload, ensure_ascii=False),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception as e:
            logger.error(f"[MemTheta] X1 Governance failure - could not emit OMO event: {e}")

    def update(self, target_id: str, context: str, confidence: float, trigger_source: str) -> bool:
        """
        Update Operator (MemTheta): Overwrite state with confidence > threshold.
        """
        tracer = get_tracer("memtheta-adapter")
        with tracer.start_as_current_span("MemTheta.Update") as span:
            span.set_attribute("memtheta.target_id", target_id)
            span.set_attribute("memtheta.confidence", confidence)
            span.set_attribute("memtheta.trigger_source", trigger_source)

            if confidence < 0.6:
                span.set_attribute("memtheta.rejected", True)
                logger.warning(f"[MemTheta] Update rejected: low confidence {confidence} < 0.6")
                return False

            payload = {
                "op": "update",
                "target_id": target_id,
                "context": context,
                "confidence": confidence,
                "trigger_source": trigger_source,
            }

            # 1. Write to Raw Track (X1 Governance)
            self._emit_omo_event("update", payload)

            # 2. Write to Theta Track (gbrain schema simulation for now, via stdout/MCP)
            logger.info(f"[MemTheta] Executed UPDATE on {target_id}. Conf: {confidence}")

            # In actual integration, this would call `gbrain` MCP `bos://memory/operator/update`
            return True

    def merge(self, query_topic: str, source_ids: list[str], distilled_context: str) -> str:
        """
        Merge Operator (MemTheta): Condense multiple fragments into a meta-node.
        """
        tracer = get_tracer("memtheta-adapter")
        with tracer.start_as_current_span("MemTheta.Merge") as span:
            span.set_attribute("memtheta.query_topic", query_topic)
            span.set_attribute("memtheta.sources_count", len(source_ids))

            payload = {
                "op": "merge",
                "query_topic": query_topic,
                "source_ids": source_ids,
                "distilled_context": distilled_context,
            }

            # 1. Write to Raw Track (X1 Governance)
            self._emit_omo_event("merge", payload)

            # 2. Issue Meta-Node to Theta Track
            meta_node_id = f"meta_{hash(query_topic) % 1000000}"
            span.set_attribute("memtheta.meta_node_id", meta_node_id)
            logger.info(f"[MemTheta] Executed MERGE. Created meta-node {meta_node_id} from {len(source_ids)} sources.")

            return meta_node_id

    def filter(self, domain: str, decay_days: int, access_threshold: int, dry_run: bool = False) -> dict[str, Any]:
        """
        Filter Operator (MemTheta): Evict cold nodes based on decay and access.
        """
        tracer = get_tracer("memtheta-adapter")
        with tracer.start_as_current_span("MemTheta.Filter") as span:
            span.set_attribute("memtheta.domain", domain)
            span.set_attribute("memtheta.decay_days", decay_days)
            span.set_attribute("memtheta.dry_run", dry_run)

            payload = {
                "op": "filter",
                "domain": domain,
                "decay_days": decay_days,
                "access_threshold": access_threshold,
                "dry_run": dry_run,
            }

            # 1. Write to Raw Track (X1 Governance)
            self._emit_omo_event("filter", payload)

            # Simulated filter response
            report = {"scanned": 100, "evicted": 0 if dry_run else 12, "dry_run": dry_run}
            span.set_attribute("memtheta.evicted_count", report["evicted"])
            logger.info(f"[MemTheta] Executed FILTER. Report: {report}")
            return report


memtheta_adapter = MemThetaAdapter()
