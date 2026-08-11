from __future__ import annotations

from dataclasses import replace
from typing import Any

import anyio
import pytest

from omlxc.domain.protocols import LifecycleResult, OperationStatus


def test_memory_admission_fails_closed_for_unknown_stale_and_invalid_values() -> None:
    from omlxc.autonomy import MemoryAdmissionPolicy, MemorySnapshot

    policy = MemoryAdmissionPolicy(stale_seconds=10.0, safety_margin_gb=2.0)
    assert not policy.admit(None, required_gb=1.0, now_monotonic=10.0).allowed
    assert not policy.admit(
        MemorySnapshot(total_gb=16.0, available_gb=8.0, observed_monotonic=0.0),
        required_gb=1.0,
        now_monotonic=11.0,
    ).allowed
    assert not policy.admit(
        MemorySnapshot(total_gb=16.0, available_gb=-1.0, observed_monotonic=10.0),
        required_gb=1.0,
        now_monotonic=10.0,
    ).allowed
    assert policy.admit(
        MemorySnapshot(total_gb=16.0, available_gb=8.0, observed_monotonic=10.0),
        required_gb=5.0,
        now_monotonic=10.0,
    ).allowed


class FakePlacementOperator:
    def __init__(self, loaded: set[str], *, block_first_load: bool = False) -> None:
        self.loaded = loaded
        self.load_calls: list[str] = []
        self.unload_calls: list[str] = []
        self.authorized = True
        self.entered = anyio.Event()
        self.release = anyio.Event()
        self.block_first_load = block_first_load

    async def fresh_for_write(self, target: Any) -> bool:
        return self.authorized

    async def is_loaded(self, target: Any) -> bool:
        return target.id in self.loaded

    async def load(self, target: Any, *, idempotency_key: str) -> LifecycleResult:
        del idempotency_key
        self.load_calls.append(target.id)
        if self.block_first_load and len(self.load_calls) == 1:
            self.entered.set()
            await self.release.wait()
        self.loaded.add(target.id)
        return LifecycleResult(
            model_id=target.model_id, status=OperationStatus.SUCCEEDED, changed=True
        )

    async def unload(self, target: Any, *, idempotency_key: str) -> LifecycleResult:
        del idempotency_key
        self.unload_calls.append(target.id)
        self.loaded.discard(target.id)
        return LifecycleResult(
            model_id=target.model_id, status=OperationStatus.SUCCEEDED, changed=True
        )


def _target(**changes: Any) -> Any:
    from omlxc.autonomy import PlacementTarget

    target = PlacementTarget(
        id="placement-a",
        node_id="node-a",
        model_id="model-a",
        resident=True,
        memory_gb=4.0,
        idle_unload_seconds=60.0,
        last_used_monotonic=0.0,
        rollback_reference="rollback:placement-a",
    )
    return replace(target, **changes)


def _memory() -> Any:
    from omlxc.autonomy import MemorySnapshot

    return MemorySnapshot(total_gb=32.0, available_gb=16.0, observed_monotonic=100.0)


@pytest.mark.asyncio
async def test_resident_reconcile_is_single_flight_and_rechecks_after_wait() -> None:
    from omlxc.autonomy import AutonomyStatus, MemoryAdmissionPolicy, ReconciliationEngine

    operator = FakePlacementOperator(set(), block_first_load=True)
    engine = ReconciliationEngine(
        operator,
        memory_policy=MemoryAdmissionPolicy(stale_seconds=10.0, safety_margin_gb=2.0),
        global_limit=2,
        per_node_limit=1,
    )
    results: list[Any] = []

    async def run() -> None:
        results.append(await engine.reconcile(_target(), _memory(), now_monotonic=100.0))

    async with anyio.create_task_group() as group:
        group.start_soon(run)
        await operator.entered.wait()
        group.start_soon(run)
        operator.release.set()

    assert operator.load_calls == ["placement-a"]
    assert {result.status for result in results} == {
        AutonomyStatus.SUCCEEDED,
        AutonomyStatus.NOOP,
    }
    assert engine.active_key_count == 0


@pytest.mark.asyncio
async def test_idle_nonresident_unloads_but_stale_authorization_blocks_write() -> None:
    from omlxc.autonomy import AutonomyStatus, MemoryAdmissionPolicy, ReconciliationEngine

    target = _target(resident=False, last_used_monotonic=0.0)
    operator = FakePlacementOperator({target.id})
    engine = ReconciliationEngine(
        operator,
        memory_policy=MemoryAdmissionPolicy(stale_seconds=10.0, safety_margin_gb=2.0),
        global_limit=2,
        per_node_limit=1,
    )
    unloaded = await engine.reconcile(target, _memory(), now_monotonic=100.0)
    assert unloaded.status is AutonomyStatus.SUCCEEDED
    operator.loaded.add(target.id)
    operator.authorized = False
    denied = await engine.reconcile(target, _memory(), now_monotonic=100.0)
    assert denied.status is AutonomyStatus.DENIED
    assert operator.unload_calls == [target.id]


@pytest.mark.asyncio
async def test_reconcile_loop_start_stop_settles_background_task_without_busy_loop() -> None:
    from omlxc.autonomy import MemoryAdmissionPolicy, ReconcileLoop, ReconciliationEngine

    operator = FakePlacementOperator(set())
    engine = ReconciliationEngine(
        operator,
        memory_policy=MemoryAdmissionPolicy(stale_seconds=10.0, safety_margin_gb=2.0),
        global_limit=1,
        per_node_limit=1,
    )
    waited = anyio.Event()
    release = anyio.Event()

    async def targets() -> tuple[Any, ...]:
        return (_target(),)

    async def memory() -> Any:
        return _memory()

    async def wait_next(interval: float) -> None:
        assert interval == 5.0
        waited.set()
        await release.wait()

    loop = ReconcileLoop(
        engine,
        targets_provider=targets,
        memory_probe=memory,
        monotonic_clock=lambda: 100.0,
        interval_seconds=5.0,
        wait_next=wait_next,
    )
    await loop.start()
    await waited.wait()
    assert loop.running
    await loop.stop()
    assert not loop.running
    assert operator.load_calls == ["placement-a"]


@pytest.mark.asyncio
async def test_different_placements_reconcile_in_parallel_with_deterministic_barrier() -> None:
    from omlxc.autonomy import MemoryAdmissionPolicy, ReconciliationEngine

    class ParallelOperator(FakePlacementOperator):
        def __init__(self) -> None:
            super().__init__(set())
            self.active = 0
            self.both_entered = anyio.Event()

        async def load(self, target: Any, *, idempotency_key: str) -> LifecycleResult:
            del idempotency_key
            self.active += 1
            if self.active == 2:
                self.both_entered.set()
            await self.both_entered.wait()
            self.loaded.add(target.id)
            self.active -= 1
            return LifecycleResult(
                model_id=target.model_id,
                status=OperationStatus.SUCCEEDED,
                changed=True,
            )

    operator = ParallelOperator()
    engine = ReconciliationEngine(
        operator,
        memory_policy=MemoryAdmissionPolicy(stale_seconds=10.0, safety_margin_gb=2.0),
        global_limit=2,
        per_node_limit=1,
    )
    results = await engine.reconcile_many(
        (_target(id="placement-a", node_id="node-a"), _target(id="placement-b", node_id="node-b")),
        _memory(),
        now_monotonic=100.0,
    )
    assert set(results) == {"placement-a", "placement-b"}


def test_memory_pressure_eviction_is_deterministic_and_never_selects_resident() -> None:
    from omlxc.autonomy import select_eviction_candidate

    candidates = (
        _target(id="z", resident=False, last_used_monotonic=2.0),
        _target(id="b", resident=False, last_used_monotonic=1.0),
        _target(id="a", resident=False, last_used_monotonic=1.0),
        _target(id="resident", resident=True, last_used_monotonic=0.0),
    )
    assert select_eviction_candidate(candidates).id == "a"
