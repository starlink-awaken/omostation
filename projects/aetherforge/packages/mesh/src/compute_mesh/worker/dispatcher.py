"""TaskDispatcher — routes tasks to workers and aggregates results.

Connects the worker layer to the pool and gateway for actual execution.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from llm_gateway.provider import LLMRequest, LLMResponse

from ..pool import ComputePool
from ..topology import NodeStatus
from .registry import WorkerRegistry
from .worker import MeshWorker, WorkerStatus

_log = logging.getLogger(__name__)

DispatchListener = Callable[[str, dict[str, Any]], None]


class TaskDispatcher:
    """Dispatches tasks to workers on compute nodes.

    Usage::

        dispatcher = TaskDispatcher(pool, worker_registry)
        result = dispatcher.dispatch("ollama-local", prompt="你好")
    """

    def __init__(
        self,
        pool: ComputePool,
        worker_registry: WorkerRegistry,
    ) -> None:
        self._pool = pool
        self._registry = worker_registry
        self._listeners: list[DispatchListener] = []

    # ── Core dispatch ─────────────────────────────────────────────────────────

    def dispatch(
        self,
        node_id: str,
        prompt: str,
        *,
        model: str = "",
        system_prompt: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Dispatch a generation task to a node.

        Finds an idle worker on the node, or executes directly if no
        worker is available.

        Returns a result dict with keys:
          - ``success``: bool
          - ``content``: str (response text)
          - ``worker_id``: str or None
          - ``latency_ms``: float
          - ``error``: str (if failed)
        """
        node = self._pool.registry.get(node_id)
        if node is None:
            return {"success": False, "error": f"Node {node_id} not found"}

        if not node.is_online:
            return {"success": False, "error": f"Node {node_id} is offline"}

        # Try to claim an idle worker
        worker = self._claim_worker(node_id)
        worker_id = worker.worker_id if worker else None

        start = time.time() * 1000
        try:
            content, resp = self._execute_via_gateway(node, prompt, model, system_prompt, max_tokens, temperature)
            latency = time.time() * 1000 - start

            if worker:
                worker.tasks_completed += 1
                worker.current_load = 0.0
                worker.avg_latency_ms = (worker.avg_latency_ms * 0.8 + latency * 0.2) if worker.avg_latency_ms else latency
                worker.last_task_end = time.time()
                self._registry.set_idle(worker.worker_id)

            # Track load on the pool
            self._pool.release_request(node_id)

            result = {
                "success": True,
                "content": content,
                "worker_id": worker_id,
                "node_id": node_id,
                "model": resp.model if resp else model,
                "latency_ms": round(latency, 1),
                "input_tokens": resp.input_tokens if resp else 0,
                "output_tokens": resp.output_tokens if resp else 0,
            }
            self._notify("completed", result)
            return result

        except Exception as e:
            latency = time.time() * 1000 - start
            if worker:
                worker.tasks_failed += 1
                self._registry.set_error(worker.worker_id, str(e))

            self._pool.release_request(node_id)

            result = {
                "success": False,
                "error": str(e),
                "worker_id": worker_id,
                "node_id": node_id,
                "latency_ms": round(latency, 1),
            }
            self._notify("failed", result)
            return result

    def _claim_worker(self, node_id: str) -> MeshWorker | None:
        """Find and claim an idle worker on the given node."""
        workers = self._registry.get_by_node(node_id)
        for w in workers:
            if w.status == WorkerStatus.IDLE:
                self._registry.set_busy(w.worker_id)
                return w
        return None

    def _execute_via_gateway(
        self,
        node: Any,
        prompt: str,
        model: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, LLMResponse | None]:
        """Execute generation via the gateway's provider layer."""
        provider_name = node.protocols[0] if node.protocols else ""
        if not provider_name:
            raise RuntimeError(f"Node {node.node_id} has no known protocol")

        from llm_gateway.detection import create_provider, detect_backends

        provider = create_provider(provider_name) if provider_name else None
        if not provider or not provider.is_available():
            backends = detect_backends()
            if not backends:
                raise RuntimeError(f"No available provider for node {node.node_id}")
            provider = backends[0]

        req = LLMRequest(
            prompt=prompt,
            model=model or getattr(provider, "default_model", ""),
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        resp = provider.complete(req)
        return resp.content, resp

    # ── Auto-provision workers ────────────────────────────────────────────────

    def provision_for_node(self, node_id: str, count: int = 4) -> list[MeshWorker]:
        """Auto-create *count* workers for a compute node."""
        node = self._pool.registry.get(node_id)
        if node is None:
            _log.warning("Cannot provision workers for unknown node: %s", node_id)
            return []

        created: list[MeshWorker] = []
        for i in range(count):
            wid = f"{node_id}-w{i + 1}"
            existing = self._registry.get(wid)
            if existing:
                continue
            worker = MeshWorker(
                worker_id=wid,
                node_id=node_id,
                tags={"auto_provisioned": "true"},
            )
            self._registry.register(worker)
            created.append(worker)

        return created

    def provision_all(self, workers_per_node: int = 4) -> list[MeshWorker]:
        """Auto-create workers for all online nodes."""
        all_workers: list[MeshWorker] = []
        for node in self._pool.get_online():
            all_workers.extend(self.provision_for_node(node.node_id, workers_per_node))
        return all_workers

    # ── Listeners ─────────────────────────────────────────────────────────────

    def add_listener(self, listener: DispatchListener) -> None:
        self._listeners.append(listener)

    def _notify(self, event: str, data: dict[str, Any]) -> None:
        for listener in self._listeners:
            try:
                listener(event, data)
            except Exception:
                _log.exception("Dispatch listener failed for event %s", event)

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        return {
            "workers": self._registry.get_stats(),
            "nodes": {
                "total": self._pool.node_count,
                "online": len(self._pool.get_online()),
            },
        }
