from __future__ import annotations

import asyncio
from typing import Any

import anyio
import pytest

from omlxc.autonomy import (
    AutonomyStatus,
    MemoryAdmissionPolicy,
    MemorySnapshot,
    PlacementTarget,
    ReconciliationEngine,
)
from omlxc.domain.protocols import LifecycleResult, OperationStatus


def _target(identifier: str, node_id: str = "node-a") -> PlacementTarget:
    return PlacementTarget(
        id=identifier,
        node_id=node_id,
        model_id=f"model-{identifier}",
        resident=True,
        memory_gb=1.0,
        idle_unload_seconds=60.0,
        last_used_monotonic=90.0,
        rollback_reference=f"rollback:{identifier}",
    )


class CoordinatorOperator:
    def __init__(self, *, block_first_load: bool = False) -> None:
        self.loaded: set[str] = set()
        self.load_calls: list[str] = []
        self.unload_calls: list[str] = []
        self.block_first_load = block_first_load
        self.entered = anyio.Event()
        self.release = anyio.Event()

    async def fresh_for_write(self, target: PlacementTarget) -> bool:
        return True

    async def is_loaded(self, target: PlacementTarget) -> bool:
        return target.id in self.loaded

    async def load(self, target: PlacementTarget, *, idempotency_key: str) -> LifecycleResult:
        del idempotency_key
        self.load_calls.append(target.id)
        if self.block_first_load and len(self.load_calls) == 1:
            self.entered.set()
            await self.release.wait()
        self.loaded.add(target.id)
        return LifecycleResult(
            model_id=target.model_id,
            status=OperationStatus.SUCCEEDED,
            changed=True,
        )

    async def unload(self, target: PlacementTarget, *, idempotency_key: str) -> LifecycleResult:
        del idempotency_key
        self.unload_calls.append(target.id)
        self.loaded.discard(target.id)
        return LifecycleResult(
            model_id=target.model_id,
            status=OperationStatus.SUCCEEDED,
            changed=True,
        )


@pytest.mark.asyncio
async def test_explicit_operation_and_reconcile_share_placement_single_flight() -> None:
    from omlxc.autonomy import OperationTimeouts, PlacementOperationCoordinator

    operator = CoordinatorOperator(block_first_load=True)
    coordinator = PlacementOperationCoordinator(
        operator,
        timeouts=OperationTimeouts.uniform(10.0),
        global_limit=2,
        per_node_limit=1,
    )
    engine = ReconciliationEngine(
        operator,
        coordinator=coordinator,
        memory_policy=MemoryAdmissionPolicy(stale_seconds=10.0, safety_margin_gb=1.0),
        global_limit=2,
        per_node_limit=1,
    )
    target = _target("placement-a")
    reconcile_task = asyncio.create_task(
        engine.reconcile(target, MemorySnapshot(16.0, 8.0, 100.0), now_monotonic=100.0)
    )
    await operator.entered.wait()
    explicit_task = asyncio.create_task(coordinator.ensure_loaded(target))
    operator.release.set()
    reconciled = await reconcile_task
    explicit = await explicit_task
    assert reconciled.status is AutonomyStatus.SUCCEEDED
    assert explicit.actual_loaded
    assert operator.load_calls == [target.id]
    assert coordinator.active_key_count == 0


@pytest.mark.asyncio
async def test_phase_timeout_is_injected_bounded_and_releases_all_resources() -> None:
    from omlxc.autonomy import (
        OperationPhase,
        OperationPhaseTimeout,
        OperationTimeouts,
        PlacementOperationCoordinator,
    )

    class SelectiveTimeoutRunner:
        def __init__(self) -> None:
            self.fail_bad = True
            self.calls: list[tuple[str, OperationPhase, float]] = []

        async def run(
            self,
            resource_id: str,
            phase: OperationPhase,
            timeout_seconds: float,
            operation: Any,
        ) -> Any:
            self.calls.append((resource_id, phase, timeout_seconds))
            if resource_id == "bad" and phase is OperationPhase.LOAD and self.fail_bad:
                raise OperationPhaseTimeout(resource_id, phase)
            return await operation()

    operator = CoordinatorOperator()
    runner = SelectiveTimeoutRunner()
    coordinator = PlacementOperationCoordinator(
        operator,
        timeouts=OperationTimeouts(1.0, 2.0, 3.0, 4.0, 5.0),
        timeout_runner=runner,
        global_limit=2,
        per_node_limit=1,
    )
    engine = ReconciliationEngine(
        operator,
        coordinator=coordinator,
        memory_policy=MemoryAdmissionPolicy(stale_seconds=10.0, safety_margin_gb=1.0),
        global_limit=2,
        per_node_limit=1,
    )
    results = await engine.reconcile_many(
        (_target("bad", "node-bad"), _target("good", "node-good")),
        MemorySnapshot(16.0, 8.0, 100.0),
        now_monotonic=100.0,
    )
    assert results["bad"].status is AutonomyStatus.FAILED
    assert results["good"].status is AutonomyStatus.SUCCEEDED
    assert coordinator.active_key_count == 0
    good_phases = [phase for resource, phase, _ in runner.calls if resource == "good"]
    assert good_phases == [
        OperationPhase.DISCOVER,
        OperationPhase.AUTHORIZATION,
        OperationPhase.LOAD,
        OperationPhase.POSTVERIFY,
    ]

    runner.fail_bad = False
    retried = await engine.reconcile(
        _target("bad", "node-bad"),
        MemorySnapshot(16.0, 8.0, 100.0),
        now_monotonic=100.0,
    )
    assert retried.status is AutonomyStatus.SUCCEEDED
    assert coordinator.active_key_count == 0


@pytest.mark.asyncio
async def test_unload_runs_discover_authorization_unload_and_postverify() -> None:
    from omlxc.autonomy import (
        OperationPhase,
        OperationTimeouts,
        PlacementOperationCoordinator,
    )

    class RecordingRunner:
        def __init__(self) -> None:
            self.phases: list[tuple[OperationPhase, float]] = []

        async def run(
            self,
            resource_id: str,
            phase: OperationPhase,
            timeout_seconds: float,
            operation: Any,
        ) -> Any:
            assert resource_id == "idle"
            self.phases.append((phase, timeout_seconds))
            return await operation()

    operator = CoordinatorOperator()
    operator.loaded.add("idle")
    runner = RecordingRunner()
    coordinator = PlacementOperationCoordinator(
        operator,
        timeouts=OperationTimeouts(1.0, 2.0, 3.0, 4.0, 5.0),
        timeout_runner=runner,
        global_limit=1,
        per_node_limit=1,
    )
    outcome = await coordinator.ensure_unloaded(_target("idle"))
    assert not outcome.actual_loaded
    assert operator.unload_calls == ["idle"]
    assert runner.phases == [
        (OperationPhase.DISCOVER, 1.0),
        (OperationPhase.AUTHORIZATION, 2.0),
        (OperationPhase.UNLOAD, 4.0),
        (OperationPhase.POSTVERIFY, 5.0),
    ]
    assert coordinator.active_key_count == 0


@pytest.mark.parametrize("seconds", [0.0, -1.0, float("inf"), float("nan")])
def test_operation_timeouts_reject_unbounded_values(seconds: float) -> None:
    from omlxc.autonomy import OperationTimeouts

    with pytest.raises(ValueError, match="finite and positive"):
        OperationTimeouts.uniform(seconds)
