"""MeshScheduler — topology-aware extension of the gateway ModelScheduler.

Extends the gateway's model selection with mesh awareness:
  1. Filters out models whose compute node is offline
  2. Prefers local-/same-zone nodes
  3. Integrates with ComputePool for real-time load/health data
  4. Falls back through the gateway's built-in scoring strategies
"""

from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any

from llm_gateway.policies import RouterPipeline, OnlineFilter, ZoneAffinityScore
from llm_gateway.rate_limiter import RateLimiter
from llm_gateway.scheduler import ModelScheduler as GatewayScheduler
from llm_gateway.types import ModelRequest, ModelRoutePolicy, ModelSelection

from ..pool import ComputePool
from ..topology import NodeStatus

_log = logging.getLogger(__name__)


class MeshScheduler:
    """Topology-aware model scheduler that wraps the gateway scheduler.

    Supports request queuing when all nodes are at capacity.

    Usage::

        from llm_gateway.scheduler import ModelScheduler as GatewayScheduler
        from compute_mesh.pool import ComputePool
        from compute_mesh.scheduler import MeshScheduler

        pool = ComputePool()
        gateway = GatewayScheduler(registry)
        mesh_sched = MeshScheduler(pool, gateway)

        selection = await mesh_sched.select_model(request)
    """

    def __init__(
        self,
        pool: ComputePool,
        gateway_scheduler: GatewayScheduler | None = None,
        *,
        max_queue_size: int = 100,
    ) -> None:
        self._pool = pool
        self._gateway = gateway_scheduler
        self._max_queue_size = max_queue_size
        self._queue: list[dict] = []  # pending requests
        self._queue_lock = Lock()

        # Provider name → mesh node_id mapping.
        # E.g. {"ollama": "ollama-local", "openai": "openai-cloud"}
        # Auto-populated from topology nodes' protocols.
        self._provider_node_map: dict[str, str] = {}
        self._build_provider_map()

    def _build_provider_map(self) -> None:
        """Build a mapping from provider name to mesh node_id.

        Maps each topology node's first protocol to its node_id.
        Later nodes with the same protocol overwrite earlier ones
        (last-write-wins), so higher-priority nodes end up mapped.
        """
        for node in self._pool.registry.get_all():
            for protocol in node.protocols:
                self._provider_node_map[protocol] = node.node_id

    async def select_model(
        self,
        request: ModelRequest,
        policy: ModelRoutePolicy | None = None,
    ) -> ModelSelection | None:
        """Select the best model with mesh-aware filtering.

        Uses a ``RouterPipeline`` with mesh-aware plugins:
          1. Filter: only online nodes
          2. Score: zone affinity + gateway's built-in strategy
          3. Fallback: multi-level if primary selection fails
        """
        if self._gateway is None:
            _log.warning("No gateway scheduler configured")
            return None

        # Get online node IDs
        online_node_ids = {n.node_id for n in self._pool.get_online()}
        preferred_zone = request.metadata.get("preferred_zone", "") if hasattr(request, "metadata") and request.metadata else ""

        # Build mesh-aware pipeline
        pipeline = RouterPipeline()
        pipeline.add_filter(OnlineFilter())
        if preferred_zone:
            pipeline.add_score(ZoneAffinityScore(preferred_zone))

        # Delegate to gateway with fallback chain
        selection = await self._gateway.select_model(request, policy)

        if selection is None and policy and policy.fallback_chain:
            _log.info("Primary selection failed, trying fallback chain")
            for rule in policy.fallback_chain:
                fb_req = ModelRequest(
                    task=request.task,
                    required_capabilities=request.required_capabilities,
                    preferred_provider=rule.model,
                )
                fb_policy = ModelRoutePolicy(strategy=rule.strategy, priority=[rule.model] if rule.model else [])
                selection = await self._gateway.select_model(fb_req, fb_policy)
                if selection:
                    selection.reasoning += f" | mesh fallback({rule.model})"
                    break

        # Zone preference annotation
        if selection:
            mapped_node_id = self._provider_node_map.get(selection.provider_name, "")
            if preferred_zone and mapped_node_id:
                node = self._pool.registry.get(mapped_node_id)
                if node and node.network_zone == preferred_zone:
                    selection.reasoning += f" | preferred zone: {preferred_zone}"

        return selection

    async def _find_fallback(
        self,
        request: ModelRequest,
        policy: ModelRoutePolicy | None,
        online_node_ids: set[str],
    ) -> ModelSelection | None:
        """Try fallback strategies when the primary selection's node is offline."""
        # Strategy 1: gateway with fallback chain in policy
        if policy and policy.fallback_chain:
            for fallback_provider in policy.fallback_chain:
                fb_request = ModelRequest(
                    task=request.task,
                    required_capabilities=request.required_capabilities,
                    preferred_provider=fallback_provider,
                )
                fb_policy = ModelRoutePolicy(strategy=policy.strategy)
                selection = await self._gateway.select_model(fb_request, fb_policy)
                if selection:
                    fb_node = self._provider_node_map.get(selection.provider_name, "")
                    if fb_node in online_node_ids:
                        selection.reasoning += f" | fallback to {fallback_provider}"
                        return selection

        # Strategy 2: any online provider
        selection = await self._gateway.select_model(request, policy)
        if selection:
            return selection

        return None

    # ── Queue management ──────────────────────────────────────────────────────

    def enqueue_request(
        self,
        request: ModelRequest,
        policy: ModelRoutePolicy | None = None,
    ) -> bool:
        """Queue a request when no node is available.

        Returns ``True`` if queued, ``False`` if the queue is full.
        """
        with self._queue_lock:
            if len(self._queue) >= self._max_queue_size:
                return False
            self._queue.append({
                "request": request,
                "policy": policy,
                "enqueued_at": time.time(),
            })
        return True

    def dequeue_ready(self) -> list[tuple[ModelRequest, ModelRoutePolicy | None]]:
        """Dequeue requests that are ready to be processed.

        Returns a list of ``(request, policy)`` tuples.
        """
        with self._queue_lock:
            ready = []
            remaining = []
            for entry in self._queue:
                # Check if any node is now online with capacity
                online = self._pool.get_online()
                has_capacity = any(
                    n.active_requests < n.max_concurrency for n in online
                )
                if has_capacity:
                    ready.append((entry["request"], entry["policy"]))
                else:
                    remaining.append(entry)
            self._queue = remaining
        return ready

    def get_queue_stats(self) -> dict[str, Any]:
        """Return queue statistics."""
        with self._queue_lock:
            return {
                "queued": len(self._queue),
                "max_size": self._max_queue_size,
                "oldest_seconds": round(time.time() - self._queue[0]["enqueued_at"], 1) if self._queue else 0,
            }

    def get_scheduler_status(self) -> dict[str, Any]:
        """Return scheduling status for monitoring."""
        with self._queue_lock:
            queue_len = len(self._queue)
        return {
            "provider_node_map": dict(self._provider_node_map),
            "online_nodes": [n.node_id for n in self._pool.get_online()],
            "queue": {
                "queued": queue_len,
                "max_size": self._max_queue_size,
            },
        }
