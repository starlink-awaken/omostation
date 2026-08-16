"""Optional Graphiti bridge — try real graphiti-core, else TemporalShadow.

Never requires Neo4j for default path. Set MOS_GRAPHITI=1 to attempt import.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from mos.adapters.temporal_shadow import TemporalShadowAdapter, temporal_enabled

logger = logging.getLogger("mos.graphiti_bridge")


def graphiti_enabled() -> bool:
    val = (os.environ.get("MOS_GRAPHITI") or "").strip().lower()
    return val in {"1", "true", "on", "yes"}


def build_temporal_backend() -> TemporalShadowAdapter:
    """Return temporal-capable backend; Graphiti only if explicitly enabled + installed."""
    if graphiti_enabled():
        try:
            import graphiti_core  # noqa: F401

            logger.info("graphiti_core import ok — using TemporalShadow as compatibility facade")
            # Full Graphiti wiring needs Neo4j driver config; keep shadow as current-state store
            # with a marker so status can report bridge available.
            adapter = TemporalShadowAdapter(name="graphiti_shadow")
            adapter._graphiti_available = True  # type: ignore[attr-defined]
            return adapter
        except Exception as exc:
            logger.warning("MOS_GRAPHITI=1 but graphiti_core unavailable: %s", exc)
    return TemporalShadowAdapter(name="temporal")


def backend_status() -> dict[str, Any]:
    from mos.neo4j_writer import neo4j_configured

    return {
        "temporal_enabled": temporal_enabled(),
        "graphiti_flag": graphiti_enabled(),
        "graphiti_importable": _can_import_graphiti(),
        "neo4j_uri_set": neo4j_configured(),
        "production_path": "Neo4jFactWriter when NEO4J_URI set; else TemporalShadow",
    }


def _can_import_graphiti() -> bool:
    try:
        import graphiti_core  # noqa: F401

        return True
    except Exception:
        return False
