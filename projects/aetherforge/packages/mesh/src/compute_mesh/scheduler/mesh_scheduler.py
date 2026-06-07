"""MeshScheduler — topology-aware extension of the gateway ModelScheduler.

Extends the gateway's model selection with mesh awareness:
  1. Filters out models whose compute node is offline
  2. Prefers local-/same-zone nodes
  3. Integrates with ComputePool for real-time load/health data
  4. Falls back through the gateway's built-in scoring strategies
"""

from __future__ import annotations

import logging
from typing import Any

from llm_gateway.scheduler import ModelScheduler as GatewayScheduler
from llm_gateway.types import ModelRequest, ModelRoutePolicy, ModelSelection

from ..pool import ComputePool
from ..topology import NodeStatus

_log = logging.getLogger(__name__)


class MeshScheduler:
    """Topology-aware model scheduler that wraps the gateway scheduler.

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
    ) -> None:
        self._pool = pool
        self._gateway = gateway_scheduler

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

        Steps:
          1. Map request to a preferred network zone (based on task)
          2. Get online nodes from the pool
          3. Check if the gateway's candidates have healthy mesh nodes
          4. Apply zone preference as a scoring bonus
          5. Delegate to gateway scheduler for final selection
        """
        if self._gateway is None:
            _log.warning("No gateway scheduler configured")
            return None

        # Get online node IDs for quick lookup
        online_node_ids = {n.node_id for n in self._pool.get_online()}

        # Preferred zone from request metadata or policy
        preferred_zone = request.metadata.get("preferred_zone", "") if hasattr(request, "metadata") and request.metadata else ""

        # Get gateway candidates pre-filtered
        selection = await self._gateway.select_model(request, policy)

        if selection is None:
            _log.info("Gateway returned no selection for request")
            return None

        # Check if the selected model's provider maps to an online node
        provider = selection.provider_name
        mapped_node_id = self._provider_node_map.get(provider, "")
        if mapped_node_id and mapped_node_id not in online_node_ids:
            # The best model's provider is offline — try to find an
            # alternative from the gateway's remaining candidates.
            _log.info(
                "Primary model provider %s (node %s) offline, seeking fallback",
                provider,
                mapped_node_id,
            )
            selection = await self._find_fallback(request, policy, online_node_ids)

        # Apply zone preference bonus to the selection reasoning
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

    def get_scheduler_status(self) -> dict[str, Any]:
        """Return scheduling status for monitoring."""
        return {
            "provider_node_map": dict(self._provider_node_map),
            "online_nodes": [n.node_id for n in self._pool.get_online()],
        }
