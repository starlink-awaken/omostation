from __future__ import annotations

from ._compat import BOSUri

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Layer: L3
Summary: Routing and Tracing Engine for ExecutionCoordinator
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Routing ≡ Module
# 内涵 ≝ {Routing}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Routing)}
# 功能 ⊢ {Init_Routing, Execute_Routing, Validate_Routing}
# =============================================================================

import asyncio
import logging
import time
from typing import Any

_log = logging.getLogger(__name__)


class RoutingEngine:
    """Handles BOS-URI parsing, holographic tracing, and domain routing."""

    def __init__(self, router: Any) -> None:
        self._router = router

    async def execute_route(
        self, uri: str, params: dict[str, Any] | None = None, trace_analyzer: Any | None = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Parse URI, perform safety checks, and route to domain handler.

        Returns:
            tuple: (result_dict, log_entry)
        """
        try:
            parsed = BOSUri.parse(uri)
            domain = parsed.domain
            resource = parsed.resource
            action = parsed.action
        except (TypeError, ValueError, AttributeError) as e:
            _log.error("%s: %s", type(e).__name__, e)
            return {"status": "error", "message": f"Invalid URI: {e!s}"}, {}

        start_time = time.time()

        # Inject holographic trace context
        if params is None:
            params = {}
        if "_trace_context" not in params:
            params["_trace_context"] = {
                "trace_id": parsed.trace_id,
                "span_id": parsed.span_id,
                "parent_span_id": params.get("_parent_span_id"),
                "origin_uri": uri,
            }

        # RFC-004 Depth Guard
        depth = self._calculate_depth(params, parsed, domain, resource, action)
        if isinstance(params, dict):
            params["_depth"] = depth

        # Quarantine check
        if trace_analyzer and not trace_analyzer.record_call(parsed.trace_id, metadata={"depth": depth}):
            return {
                "status": "error",
                "message": f"Immunity Shield: Trace {parsed.trace_id} is quarantined.",
            }, {"timestamp": start_time, "uri": uri, "status": "quarantined"}

        log_entry = {
            "timestamp": start_time,
            "uri": uri,
            "domain": domain,
            "resource": resource,
            "action": action,
            "params": params,
        }

        try:
            result = await self._router.route(domain, resource, action, params)
            log_entry["result"] = result
            log_entry["status"] = result.get("status", "unknown")
        except (TimeoutError, asyncio.CancelledError, Exception) as e:
            _log.error("Routing error: %s", e)
            result = {"status": "error", "message": str(e)}
            log_entry["result"] = result
            log_entry["status"] = "error"

        return result, log_entry

    def _calculate_depth(self, params: dict, parsed: Any, domain: str, resource: str, action: str) -> int:
        depth_val = params.get("_depth") or parsed.query.get("depth", 0)
        try:
            depth = int(depth_val)
        except (ValueError, TypeError):
            depth = 0
        if domain == "execution" and resource == "task" and action == "spawn":
            depth += 1
        return depth
