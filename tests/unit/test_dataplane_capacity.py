from __future__ import annotations

import asyncio
import time

import pytest

from omlxc.dataplane import CapacityCoordinator
from omlxc.scheduler import PlacementSnapshot


def _placement(pid: str, node: str, backend: str) -> PlacementSnapshot:
    return PlacementSnapshot(
        placement_id=pid,
        model_id="m",
        backend_id=backend,
        backend_model_id=f"physical/{pid}",
        node_id=node,
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat"}),
        context_limit=10,
        memory_admitted=True,
        loaded=True,
        ttft_ms=1,
        throughput_tps=1,
        queue_depth=0,
        error_rate=0,
        network_cost_ms=0,
        affinity=0,
        available_concurrency=1,
        local=True,
        security_allowed=True,
    )


@pytest.mark.asyncio
async def test_same_placement_is_serialized_and_cancelled_waiter_releases_every_gate() -> None:
    coordinator = CapacityCoordinator(global_limit=2, per_node=2, per_backend=2)
    placement = _placement("p", "n", "b")
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    second_entered = asyncio.Event()

    async def first() -> None:
        async with coordinator.acquire(
            placement, deadline=time.monotonic() + 10, monotonic=time.monotonic
        ):
            first_entered.set()
            await release_first.wait()

    async def second() -> None:
        async with coordinator.acquire(
            placement, deadline=time.monotonic() + 10, monotonic=time.monotonic
        ):
            second_entered.set()

    first_task = asyncio.create_task(first())
    await first_entered.wait()
    cancelled_waiter = asyncio.create_task(second())
    await asyncio.sleep(0)
    assert not second_entered.is_set()
    cancelled_waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled_waiter
    release_first.set()
    await first_task

    await second()
    assert second_entered.is_set()


@pytest.mark.asyncio
async def test_different_nodes_and_backends_can_execute_in_parallel() -> None:
    coordinator = CapacityCoordinator(global_limit=2, per_node=1, per_backend=1)
    placements = (_placement("p1", "n1", "b1"), _placement("p2", "n2", "b2"))
    both_entered = asyncio.Event()
    release = asyncio.Event()
    active = 0
    maximum = 0

    async def run(placement: PlacementSnapshot) -> None:
        nonlocal active, maximum
        async with coordinator.acquire(
            placement, deadline=time.monotonic() + 10, monotonic=time.monotonic
        ):
            active += 1
            maximum = max(maximum, active)
            if active == 2:
                both_entered.set()
            await release.wait()
            active -= 1

    tasks = [asyncio.create_task(run(placement)) for placement in placements]
    await both_entered.wait()
    release.set()
    await asyncio.gather(*tasks)
    assert maximum == 2
