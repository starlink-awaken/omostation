"""Hierarchical capacity acquisition with narrow resources acquired first."""

from __future__ import annotations

import math
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager

import anyio

from omlxc.scheduler import PlacementSnapshot


class CapacityCoordinator:
    def __init__(
        self,
        *,
        global_limit: int,
        per_node: int,
        per_backend: int,
        per_placement: int = 1,
    ) -> None:
        if min(global_limit, per_node, per_backend, per_placement) <= 0:
            raise ValueError("capacity limits must be positive")
        self._global = anyio.CapacityLimiter(global_limit)
        self._per_node = per_node
        self._per_backend = per_backend
        self._per_placement = per_placement
        self._nodes: dict[str, anyio.CapacityLimiter] = {}
        self._backends: dict[str, anyio.CapacityLimiter] = {}
        self._placements: dict[str, anyio.CapacityLimiter] = {}

    @asynccontextmanager
    async def acquire(
        self,
        placement: PlacementSnapshot,
        *,
        deadline: float,
        monotonic: Callable[[], float],
    ) -> AsyncGenerator[None]:
        limiters = (
            self._placements.setdefault(
                placement.placement_id, anyio.CapacityLimiter(self._per_placement)
            ),
            self._nodes.setdefault(placement.node_id, anyio.CapacityLimiter(self._per_node)),
            self._backends.setdefault(
                placement.backend_id, anyio.CapacityLimiter(self._per_backend)
            ),
            self._global,
        )
        acquired: list[anyio.CapacityLimiter] = []
        borrower = object()
        try:
            for limiter in limiters:
                remaining = deadline - monotonic()
                if not math.isfinite(remaining) or remaining <= 0:
                    raise TimeoutError
                with anyio.fail_after(remaining):
                    await limiter.acquire_on_behalf_of(borrower)
                acquired.append(limiter)
            yield
        finally:
            for limiter in reversed(acquired):
                limiter.release_on_behalf_of(borrower)
