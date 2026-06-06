"""Request Router — routes incoming calls to the correct service.

Phase 3: Load balancing — supports multiple instances per service
with round-robin routing strategy.
"""

from __future__ import annotations

import atexit
import json as _json
import os
import time as _time
from collections import deque
from pathlib import Path as _Path

import structlog

from agora._protocols import close_client  # type: ignore[import-not-found]
from agora._protocols import dispatch as _dispatch
from agora.auth.identity import Identity, normalize_identity  # type: ignore[import-not-found]
from agora.compressor import Compressor as _Compressor  # type: ignore[import-not-found]
from agora.core.event_bus import EventBus  # type: ignore[import-not-found]
from agora.core.registry import ServiceRegistry  # type: ignore[import-not-found]
from agora.core.service_cache import (  # type: ignore[import-not-found]
    load_service_cache as _load_service_cache,
)
from agora.core.service_cache import (
    save_service_cache as _save_service_cache,
)

logger = structlog.get_logger(__name__)

# atexit 去重：跟踪所有 Router 实例，确保只注册一次
_routers: list[Router] = []
_atexit_registered = False


# Module-level compressor for response compression middleware
_router_compressor: _Compressor = _Compressor()


def _flush_all_routers():
    """Flush trace buffers for all Router instances at exit."""
    import contextlib

    for r in _routers:
        with contextlib.suppress(Exception):
            r._flush_traces()


class Router:
    """Routes tool calls to the appropriate registered service via protocol dispatch.

    Supports:
    - Exact and prefix-based route resolution
    - Circuit breaker awareness (skips OPEN services)
    - Load balancing with round-robin across service instances
    - Multi-protocol dispatch: mcp (implemented), rest/grpc/stdio (reserved)
    - Event bus integration: auto-publishes route:call.succeeded/failed events
    """

    def __init__(
        self,
        registry: ServiceRegistry,
        strategy: str = "round-robin",
        event_bus: EventBus | None = None,
        routes_path: str | None = None,
    ):
        self.registry = registry
        self._event_bus = event_bus
        self._routes: dict[str, str] = {}  # tool_name → service_name
        self._strategy = strategy
        self._rr_index: dict[str, int] = {}  # service_name → next instance index
        self._latencies: deque[float] = deque(maxlen=1000)  # auto-FIFO truncation
        self._degraded_services: set[str] = set()  # track services in degrade mode for exit events
        self._trace_buffer: list[str] = []  # batched disk writes
        self._trace_path = _Path(__file__).parent.parent.parent / "trace_log.jsonl"
        if routes_path:
            self._routes_path = _Path(routes_path)
        else:
            package_root = _Path(__file__).resolve().parents[3]
            package_root_routes = package_root / "agora-routes.json"
            storage_sibling_routes = _Path(registry._storage_path).parent / "agora-routes.json"
            self._routes_path = package_root_routes if package_root_routes.exists() else storage_sibling_routes
        self._load_routes()
        global _routers, _atexit_registered
        _routers.append(self)
        if not _atexit_registered:
            atexit.register(_flush_all_routers)
            _atexit_registered = True

    def _load_routes(self):
        """Load persisted route mappings from JSON file."""
        from agora.persistence import json_load  # type: ignore[import-not-found]

        data = json_load(self._routes_path, default={})
        self._routes = data.get("routes", {})

    def _save_routes(self):
        """Persist route mappings to JSON file."""
        from agora.persistence import json_save

        json_save(self._routes_path, {"routes": self._routes})

    def add_route(self, tool_name: str, service_name: str):
        """Register a tool → service mapping and persist it."""
        self._routes[tool_name] = service_name
        self._save_routes()

    def resolve(self, tool_name: str) -> str | None:
        """Find which service handles a tool. Supports prefix matching."""
        if tool_name in self._routes:
            return self._routes[tool_name]
        # Prefix match: "minerva.research_now" → try "minerva" prefix
        parts = tool_name.split(".", 1)
        if parts[0] in self._routes:
            return self._routes[parts[0]]
        return None

    def _next_instance(self, service_name: str) -> dict | None:
        """Get the next available instance using current strategy (round-robin).

        Skips services in OPEN circuit state.
        """
        svc = self.registry.get(service_name)
        if not svc:
            return None
        if not svc.is_available:
            return None

        result = {  # single instance mode
            "mcp_endpoint": svc.mcp_endpoint,
            "health_endpoint": svc.health_endpoint,
            "port": svc.port,
            "protocol": svc.protocol,
            "protocol_config": svc.protocol_config,
        }

        # Check if this service has multiple instances
        instances = svc.instances
        if instances:
            idx = self._rr_index.get(service_name, 0)
            instance = instances[idx % len(instances)]
            self._rr_index[service_name] = idx + 1
            result = instance

        return result

    def _cached_instance(self, service_name: str, tool_name: str) -> dict | None:
        """Fall back to the local service cache when registry is unavailable.

        Searches the cached service list for the given service_name and
        returns an instance dict compatible with ``_next_instance()`` output.
        """
        cached = _load_service_cache()
        services = cached.get("services", [])
        if not services:
            logger.warning(
                "cache_fallback_empty",
                service=service_name,
                tool=tool_name,
            )
            return None

        for svc in services:
            if not isinstance(svc, dict):
                continue
            if svc.get("name") == service_name:
                logger.info(
                    "cache_fallback_hit",
                    service=service_name,
                    mcp_endpoint=svc.get("mcp_endpoint"),
                )
                return {
                    "mcp_endpoint": svc.get("mcp_endpoint", ""),
                    "health_endpoint": svc.get("health_endpoint", ""),
                    "port": svc.get("port", 0),
                    "protocol": svc.get("protocol", "mcp"),
                    "protocol_config": svc.get("protocol_config", {}),
                }

        logger.warning(
            "cache_fallback_miss",
            service=service_name,
            tool=tool_name,
        )
        return None

    def persist_cache(self) -> bool:
        """Save the current registry service list to the local cache.

        Call this after every successful discovery to keep the cache fresh.
        Converts ``Service.to_dict()`` format (uses ``endpoint`` key) to the
        canonical cache format (uses ``mcp_endpoint`` and ``health_endpoint``).
        """
        from agora.core.service_base import Service as _Service  # type: ignore[import-not-found]

        def _convert(svc: _Service | dict) -> dict:
            if isinstance(svc, dict):
                d = dict(svc)
                # Normalize key names: endpoint -> mcp_endpoint
                if "mcp_endpoint" not in d and "endpoint" in d:
                    d["mcp_endpoint"] = d.pop("endpoint")
                if "health_endpoint" not in d and "health" in d:
                    d["health_endpoint"] = d.pop("health")
                return d
            # Service dataclass instance
            return {
                "name": svc.name,
                "description": svc.description,
                "protocol": svc.protocol,
                "protocol_config": svc.protocol_config,
                "mcp_endpoint": svc.mcp_endpoint,
                "health_endpoint": svc.health_endpoint or "",
                "port": svc.port,
                "tags": svc.tags,
                "instances": svc.instances,
            }

        services = [_convert(s) for s in self.registry.list_all()]
        return _save_service_cache(services)

    def _add_instance(self, service_name: str, mcp_endpoint: str, health_endpoint: str = "", port: int = 0):
        """Add a load-balanced instance to an existing service."""
        svc = self.registry.get(service_name)
        if not svc:
            return
        if not svc.instances:
            # First instance: promote existing to list
            svc.instances.append(
                {
                    "mcp_endpoint": svc.mcp_endpoint,
                    "health_endpoint": svc.health_endpoint,
                    "port": svc.port,
                    "protocol": svc.protocol,
                    "protocol_config": svc.protocol_config,
                }
            )
        svc.instances.append(
            {
                "mcp_endpoint": mcp_endpoint,
                "health_endpoint": health_endpoint or "",
                "port": port or 0,
                "protocol": svc.protocol,
                "protocol_config": svc.protocol_config,
            }
        )

    async def route(
        self,
        tool_name: str,
        arguments: dict,
        caller_id: Identity | dict | str = "unknown",
        use_cache: bool = True,
    ) -> dict:
        """Route a tool call to the target service via protocol dispatch.

        Args:
            tool_name: Name of the tool to invoke.
            arguments: Tool arguments dict.
            caller_id: Identity of the caller for auditing.
            use_cache: If True (default), fall back to the local service cache
                       when the registry is unavailable or returns empty.
        """
        _start = _time.monotonic()
        caller = normalize_identity(caller_id)

        service_name = self.resolve(tool_name)
        if not service_name:
            self._trace(tool_name, service_name or "unknown", _start, "error", "not_found")
            logger.warning("route_not_found", tool=tool_name)
            return {"status": "error", "error": "Tool not available"}

        instance = self._next_instance(service_name)
        # ── Degrade exit: previously degraded service is now available ──
        if instance and service_name in self._degraded_services:
            self._degraded_services.discard(service_name)
            import subprocess  # type: ignore[import-untyped]

            try:
                ops_home = os.path.expanduser("~")
                reason = f"service {service_name} recovered, tool {tool_name}"
                subprocess.run(
                    [
                        "python3",
                        "-c",
                        f"""
import sys
sys.path.insert(0, '{ops_home}/Workspace/hermes-ops/src')
from hermes_ops.events import emit
emit('AGORA_DEGRADE_EXITED', {{"service": "agora", "reason": "{reason}"}})
""",
                    ],
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass
        if not instance and use_cache:
            # ── Degrade: fall back to local service cache ──────────────
            logger.info(
                "route_cache_fallback",
                tool=tool_name,
                service=service_name,
            )
            # 发射 Agora 降级事件 (hermes-ops)
            import subprocess  # type: ignore[import-untyped]

            try:
                ops_home = os.path.expanduser("~")
                reason = f"primary_instance_unavailable for service {service_name}, tool {tool_name}"
                subprocess.run(
                    [
                        "python3",
                        "-c",
                        f"""
import sys
sys.path.insert(0, '{ops_home}/Workspace/hermes-ops/src')
from hermes_ops.events import emit
emit('AGORA_DEGRADE_ENTERED', {{"service": "agora", "reason": "{reason}"}})
""",
                    ],
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass
            self._degraded_services.add(service_name)
            instance = self._cached_instance(service_name, tool_name)

        if not instance:
            self._trace(tool_name, service_name, _start, "error", "no_instance")
            return {"status": "error", "error": "Service temporarily unavailable"}

        # Check for explicit compress flag in request arguments
        compress_requested = arguments.pop("_compress", False) if isinstance(arguments, dict) else False

        try:
            result = await _dispatch(instance, tool_name, arguments)

            # ── Accounting middleware ────────────────────────────────────
            if result.get("status") != "error":
                try:
                    from agora.accounting import (  # type: ignore[import-not-found]
                        CallRecord,
                        ResourceAccountDB,
                        estimate_cost,
                    )

                    # Extract token usage from response if available
                    # Common MCP response patterns for usage info
                    input_tokens = 0
                    output_tokens = 0
                    # Pattern 1: result.meta.usage or result.usage
                    meta = result.get("meta") or {}
                    usage = (
                        meta.get("usage") or result.get("usage") or {}
                        if isinstance(meta, dict)
                        else result.get("usage") or {}
                    )
                    if isinstance(usage, dict):
                        input_tokens = usage.get("inputTokens") or usage.get("input_tokens") or 0
                        output_tokens = usage.get("outputTokens") or usage.get("output_tokens") or 0
                    # Pattern 2: result.result.usage (nested MCP response)
                    inner = result.get("result") or {}
                    if isinstance(inner, dict):
                        inner_usage = inner.get("usage") or {}
                        if isinstance(inner_usage, dict):
                            input_tokens = (
                                input_tokens or inner_usage.get("inputTokens") or inner_usage.get("input_tokens") or 0
                            )
                            output_tokens = (
                                output_tokens
                                or inner_usage.get("outputTokens")
                                or inner_usage.get("output_tokens")
                                or 0
                            )

                    cost = estimate_cost(input_tokens, output_tokens)

                    record = CallRecord(
                        caller_id=caller.actor,
                        service_name=service_name,
                        tool_name=tool_name,
                        input_tokens=int(input_tokens),
                        output_tokens=int(output_tokens),
                        cost_usd=round(cost, 6),
                        billed_to=caller.billing_subject,
                    )
                    ResourceAccountDB().record_call(record)
                except Exception as acct_err:
                    logger.warning("accounting_record_failed", error=str(acct_err))

            # ── EU cost tracking middleware ────────────────────────────────
            if result.get("status") != "error":
                try:
                    from kaironcloud_billing.pricing.eu_ledger import EULedger  # type: ignore[import-not-found]

                    # Map tool name to EU operation — fall back to tool prefix
                    eu_operation = tool_name.split(".")[0] if "." in tool_name else tool_name
                    tx = EULedger().consume(caller.actor, eu_operation)
                    if not tx.success:
                        logger.info(
                            "eu_cost_tracking_failed", caller=caller.actor, operation=eu_operation, error=tx.error
                        )
                except Exception as eu_err:
                    logger.warning("eu_cost_tracking_failed", error=str(eu_err))
            # ── End EU cost tracking middleware ────────────────────────────

            if result.get("status") == "error":
                self._trace(tool_name, service_name, _start, "error", result.get("error", "")[:100])
                logger.warning(
                    "route_dispatch_failed", tool=tool_name, service=service_name, error=result.get("error", "")
                )
                self.registry.mark_failure(service_name)
                self._maybe_publish(
                    "route:call.failed",
                    {
                        "tool": tool_name,
                        "service": service_name,
                        "error": result.get("error", "")[:100],
                        "identity": caller.to_payload(),
                    },
                )
                # Audit
                try:
                    from agora.audit import AuditLogger  # type: ignore[import-not-found]

                    AuditLogger().log("route.call", caller.actor, service_name, "error", result.get("error", "")[:100])
                except Exception:
                    pass
            else:
                self.registry.mark_success(service_name)
                self._trace(tool_name, service_name, _start, "ok")
                self._maybe_publish(
                    "route:call.succeeded",
                    {
                        "tool": tool_name,
                        "service": service_name,
                        "duration_s": round(_time.monotonic() - _start, 4),
                        "identity": caller.to_payload(),
                    },
                )
                # Audit
                try:
                    from agora.audit import AuditLogger

                    AuditLogger().log("route.call", caller.actor, service_name)
                except Exception:
                    pass

            # Compression middleware: compress large responses
            result_json = _json.dumps(result)
            if compress_requested or len(result_json) > 1024:
                compressed = _router_compressor.compress(result_json, "json")
                result = {
                    "compressed": True,
                    "original_len": compressed.original_len,
                    "compressed_len": compressed.compressed_len,
                    "ratio": compressed.ratio,
                    "content": _json.loads(compressed.content),
                    "stats": compressed.stats,
                }
            return result
        except Exception as e:
            self._trace(tool_name, service_name, _start, "error", str(e)[:100])
            logger.warning("route_failed", tool=tool_name, service=service_name, error=str(e))
            self.registry.mark_failure(service_name)
            self._maybe_publish(
                "route:call.failed",
                {
                    "tool": tool_name,
                    "service": service_name,
                    "error": str(e)[:100],
                    "identity": caller.to_payload(),
                },
            )
            return {"status": "error", "error": "Routing failed"}

    def _maybe_publish(self, event_type: str, payload: dict):
        """Publish route event if event_bus is configured."""
        if self._event_bus:
            self._event_bus.publish(event_type, payload, "agora-router")

    def _trace(self, tool: str, service: str, start: float, status: str, detail: str = ""):
        """Buffer trace entry; flush to disk every 50 calls."""
        elapsed = round(_time.monotonic() - start, 4)

        if status == "ok":
            self._latencies.append(elapsed)

        entry = _json.dumps(
            {
                "time": _time.time(),
                "tool": tool,
                "service": service,
                "status": status,
                "elapsed_s": elapsed,
                "detail": detail,
            }
        )
        self._trace_buffer.append(entry)
        if len(self._trace_buffer) >= 50:
            self._flush_traces()

    def _flush_traces(self):
        """Write buffered traces to disk, auto-rotate at 1MB."""
        if not self._trace_buffer:
            return
        try:
            # Rotate if exceeds 1MB
            if self._trace_path.exists() and self._trace_path.stat().st_size > 1_048_576:
                rotated = self._trace_path.with_suffix(".jsonl.1")
                if rotated.exists():
                    rotated.unlink()
                os.rename(self._trace_path, rotated)
            with open(self._trace_path, "a") as f:
                f.write("\n".join(self._trace_buffer) + "\n")
            self._trace_buffer.clear()
        except Exception:
            pass

    def get_percentiles(self) -> dict:
        """Calculate P50/P90/P99 from rolling latency window."""
        if not self._latencies:
            return {"p50": 0, "p90": 0, "p99": 0, "samples": 0, "avg": 0}
        sorted_l = sorted(self._latencies)
        n = len(sorted_l)
        return {
            "p50": round(sorted_l[int(n * 0.50)], 4),
            "p90": round(sorted_l[int(n * 0.90)], 4),
            "p99": round(sorted_l[min(int(n * 0.99), n - 1)], 4),
            "samples": n,
            "avg": round(sum(sorted_l) / n, 4),
        }

    def list_routes(self) -> dict[str, str]:
        return dict(self._routes)

    async def close(self):
        """Clean up the shared HTTP client connection pool."""
        await close_client()
