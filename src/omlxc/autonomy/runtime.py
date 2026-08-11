"""Bounded, injected, and fail-closed autonomous placement maintenance."""

from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import anyio

from omlxc.domain.protocols import AdapterErrorCode, LifecycleResult, OperationStatus


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    total_gb: float
    available_gb: float
    observed_monotonic: float


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class MemoryAdmissionPolicy:
    stale_seconds: float
    safety_margin_gb: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.stale_seconds) or self.stale_seconds <= 0:
            raise ValueError("memory staleness threshold must be finite and positive")
        if not math.isfinite(self.safety_margin_gb) or self.safety_margin_gb < 0:
            raise ValueError("memory safety margin must be finite and non-negative")

    def admit(
        self,
        snapshot: MemorySnapshot | None,
        *,
        required_gb: float,
        now_monotonic: float,
    ) -> AdmissionDecision:
        if not math.isfinite(required_gb) or required_gb <= 0:
            return AdmissionDecision(False, "invalid_budget")
        if snapshot is None:
            return AdmissionDecision(False, "memory_unknown")
        values = (
            snapshot.total_gb,
            snapshot.available_gb,
            snapshot.observed_monotonic,
            now_monotonic,
        )
        if any(not math.isfinite(value) for value in values):
            return AdmissionDecision(False, "memory_invalid")
        if (
            snapshot.total_gb <= 0
            or snapshot.available_gb < 0
            or snapshot.available_gb > snapshot.total_gb
        ):
            return AdmissionDecision(False, "memory_invalid")
        age = now_monotonic - snapshot.observed_monotonic
        if age < 0 or age > self.stale_seconds:
            return AdmissionDecision(False, "memory_stale")
        if snapshot.available_gb - self.safety_margin_gb < required_gb:
            return AdmissionDecision(False, "memory_pressure")
        return AdmissionDecision(True, "admitted")


@dataclass(frozen=True, slots=True)
class PlacementTarget:
    id: str
    node_id: str
    model_id: str
    resident: bool
    memory_gb: float
    idle_unload_seconds: float
    last_used_monotonic: float
    rollback_reference: str

    def __post_init__(self) -> None:
        if not self.id or not self.node_id or not self.model_id:
            raise ValueError("placement identity is required")
        if not math.isfinite(self.memory_gb) or self.memory_gb <= 0:
            raise ValueError("placement memory budget must be finite and positive")
        if not math.isfinite(self.idle_unload_seconds) or self.idle_unload_seconds < 0:
            raise ValueError("idle unload threshold must be finite and non-negative")
        if not math.isfinite(self.last_used_monotonic):
            raise ValueError("placement last-used time must be finite")
        if not self.rollback_reference:
            raise ValueError("placement rollback reference is required")


class PlacementOperator(Protocol):
    async def fresh_for_write(self, target: PlacementTarget) -> bool: ...

    async def is_loaded(self, target: PlacementTarget) -> bool: ...

    async def load(self, target: PlacementTarget, *, idempotency_key: str) -> LifecycleResult: ...

    async def unload(self, target: PlacementTarget, *, idempotency_key: str) -> LifecycleResult: ...


class AutonomyStatus(StrEnum):
    NOOP = "noop"
    SUCCEEDED = "succeeded"
    DENIED = "denied"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AutonomyResult:
    placement_id: str
    status: AutonomyStatus
    action: str
    reason: str
    rollback_reference: str | None = None


class OperationPhase(StrEnum):
    DISCOVER = "discover"
    AUTHORIZATION = "authorization"
    LOAD = "load"
    UNLOAD = "unload"
    POSTVERIFY = "postverify"


class OperationPhaseTimeout(TimeoutError):
    def __init__(self, resource_id: str, phase: OperationPhase) -> None:
        self.resource_id = resource_id
        self.phase = phase
        super().__init__(f"placement operation phase timed out: {phase.value}")


@dataclass(frozen=True, slots=True)
class OperationTimeouts:
    discover_seconds: float
    authorization_seconds: float
    load_seconds: float
    unload_seconds: float
    postverify_seconds: float

    def __post_init__(self) -> None:
        if any(
            not math.isfinite(value) or value <= 0
            for value in (
                self.discover_seconds,
                self.authorization_seconds,
                self.load_seconds,
                self.unload_seconds,
                self.postverify_seconds,
            )
        ):
            raise ValueError("placement operation timeouts must be finite and positive")

    @classmethod
    def uniform(cls, seconds: float) -> OperationTimeouts:
        return cls(seconds, seconds, seconds, seconds, seconds)

    def for_phase(self, phase: OperationPhase) -> float:
        return {
            OperationPhase.DISCOVER: self.discover_seconds,
            OperationPhase.AUTHORIZATION: self.authorization_seconds,
            OperationPhase.LOAD: self.load_seconds,
            OperationPhase.UNLOAD: self.unload_seconds,
            OperationPhase.POSTVERIFY: self.postverify_seconds,
        }[phase]


class TimeoutRunner(Protocol):
    async def run[T](
        self,
        resource_id: str,
        phase: OperationPhase,
        timeout_seconds: float,
        operation: Callable[[], Awaitable[T]],
    ) -> T: ...


class AnyioTimeoutRunner:
    async def run[T](
        self,
        resource_id: str,
        phase: OperationPhase,
        timeout_seconds: float,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        try:
            with anyio.fail_after(timeout_seconds):
                return await operation()
        except TimeoutError:
            raise OperationPhaseTimeout(resource_id, phase) from None


@dataclass(frozen=True, slots=True)
class PlacementOperationOutcome:
    actual_loaded: bool
    authorized: bool
    result: LifecycleResult | None


@dataclass(slots=True)
class _KeyEntry:
    lock: anyio.Lock
    users: int = 0


@dataclass(slots=True)
class _NodeEntry:
    limiter: anyio.CapacityLimiter
    users: int = 0


class PlacementOperationCoordinator:
    """Shared placement lock, capacity, timeout, and adapter-operation boundary."""

    def __init__(
        self,
        operator: PlacementOperator,
        *,
        timeouts: OperationTimeouts,
        global_limit: int,
        per_node_limit: int,
        timeout_runner: TimeoutRunner | None = None,
    ) -> None:
        if global_limit <= 0 or per_node_limit <= 0:
            raise ValueError("placement operation concurrency limits must be positive")
        self._operator = operator
        self._timeouts = timeouts
        self._timeout_runner = timeout_runner or AnyioTimeoutRunner()
        self._global = anyio.CapacityLimiter(global_limit)
        self._per_node_limit = per_node_limit
        self._registry_lock = anyio.Lock()
        self._keys: dict[str, _KeyEntry] = {}
        self._nodes: dict[str, _NodeEntry] = {}

    @property
    def active_key_count(self) -> int:
        return len(self._keys)

    async def ensure_loaded(self, target: PlacementTarget) -> PlacementOperationOutcome:
        async with self._resources(target):
            loaded = await self._phase(
                target, OperationPhase.DISCOVER, lambda: self._operator.is_loaded(target)
            )
            if loaded:
                return PlacementOperationOutcome(True, True, None)
            authorized = await self._phase(
                target,
                OperationPhase.AUTHORIZATION,
                lambda: self._operator.fresh_for_write(target),
            )
            if not authorized:
                return PlacementOperationOutcome(False, False, None)
            result = await self._phase(
                target,
                OperationPhase.LOAD,
                lambda: self._operator.load(target, idempotency_key=f"placement:load:{target.id}"),
            )
            actual = await self._phase(
                target, OperationPhase.POSTVERIFY, lambda: self._operator.is_loaded(target)
            )
            return PlacementOperationOutcome(actual, True, result)

    async def ensure_unloaded(self, target: PlacementTarget) -> PlacementOperationOutcome:
        async with self._resources(target):
            loaded = await self._phase(
                target, OperationPhase.DISCOVER, lambda: self._operator.is_loaded(target)
            )
            if not loaded:
                return PlacementOperationOutcome(False, True, None)
            authorized = await self._phase(
                target,
                OperationPhase.AUTHORIZATION,
                lambda: self._operator.fresh_for_write(target),
            )
            if not authorized:
                return PlacementOperationOutcome(True, False, None)
            result = await self._phase(
                target,
                OperationPhase.UNLOAD,
                lambda: self._operator.unload(
                    target, idempotency_key=f"placement:unload:{target.id}"
                ),
            )
            actual = await self._phase(
                target, OperationPhase.POSTVERIFY, lambda: self._operator.is_loaded(target)
            )
            return PlacementOperationOutcome(actual, True, result)

    async def _phase[T](
        self,
        target: PlacementTarget,
        phase: OperationPhase,
        operation: Callable[[], Awaitable[T]],
    ) -> T:
        return await self._timeout_runner.run(
            target.id, phase, self._timeouts.for_phase(phase), operation
        )

    @asynccontextmanager
    async def _resources(self, target: PlacementTarget) -> AsyncGenerator[None]:
        async with (
            self._placement_lock(target.id),
            self._global,
            self._node_limiter(target.node_id),
        ):
            yield

    @asynccontextmanager
    async def _placement_lock(self, key: str) -> AsyncGenerator[None]:
        async with self._registry_lock:
            entry = self._keys.setdefault(key, _KeyEntry(anyio.Lock()))
            entry.users += 1
        try:
            async with entry.lock:
                yield
        finally:
            async with self._registry_lock:
                entry.users -= 1
                if entry.users == 0:
                    self._keys.pop(key, None)

    @asynccontextmanager
    async def _node_limiter(self, node_id: str) -> AsyncGenerator[None]:
        async with self._registry_lock:
            entry = self._nodes.setdefault(
                node_id, _NodeEntry(anyio.CapacityLimiter(self._per_node_limit))
            )
            entry.users += 1
        try:
            async with entry.limiter:
                yield
        finally:
            async with self._registry_lock:
                entry.users -= 1
                if entry.users == 0:
                    self._nodes.pop(node_id, None)


class ReconciliationEngine:
    def __init__(
        self,
        operator: PlacementOperator,
        *,
        memory_policy: MemoryAdmissionPolicy,
        global_limit: int,
        per_node_limit: int,
        coordinator: PlacementOperationCoordinator | None = None,
        operation_timeouts: OperationTimeouts | None = None,
    ) -> None:
        if global_limit <= 0 or per_node_limit <= 0:
            raise ValueError("reconciliation concurrency limits must be positive")
        self._memory_policy = memory_policy
        self._coordinator = coordinator or PlacementOperationCoordinator(
            operator,
            timeouts=operation_timeouts or OperationTimeouts.uniform(30.0),
            global_limit=global_limit,
            per_node_limit=per_node_limit,
        )

    @property
    def active_key_count(self) -> int:
        return self._coordinator.active_key_count

    async def reconcile(
        self,
        target: PlacementTarget,
        memory: MemorySnapshot | None,
        *,
        now_monotonic: float,
    ) -> AutonomyResult:
        if not math.isfinite(now_monotonic):
            return AutonomyResult(target.id, AutonomyStatus.DENIED, "none", "clock_invalid")
        return await self._reconcile(target, memory, now_monotonic)

    async def reconcile_many(
        self,
        targets: tuple[PlacementTarget, ...],
        memory: MemorySnapshot | None,
        *,
        now_monotonic: float,
    ) -> dict[str, AutonomyResult]:
        results: dict[str, AutonomyResult] = {}

        async def run(target: PlacementTarget) -> None:
            try:
                results[target.id] = await self.reconcile(
                    target, memory, now_monotonic=now_monotonic
                )
            except Exception as exc:
                results[target.id] = AutonomyResult(
                    target.id,
                    AutonomyStatus.FAILED,
                    "reconcile",
                    type(exc).__name__,
                    target.rollback_reference,
                )

        async with anyio.create_task_group() as group:
            for target in targets:
                group.start_soon(run, target)
        return {target.id: results[target.id] for target in targets}

    async def _reconcile(
        self,
        target: PlacementTarget,
        memory: MemorySnapshot | None,
        now_monotonic: float,
    ) -> AutonomyResult:
        if target.resident:
            admission = self._memory_policy.admit(
                memory, required_gb=target.memory_gb, now_monotonic=now_monotonic
            )
            if not admission.allowed:
                return AutonomyResult(target.id, AutonomyStatus.DENIED, "load", admission.reason)
            outcome = await self._coordinator.ensure_loaded(target)
            if not outcome.authorized:
                return AutonomyResult(
                    target.id, AutonomyStatus.DENIED, "load", "health_or_authorization_stale"
                )
            if outcome.result is None:
                return AutonomyResult(target.id, AutonomyStatus.NOOP, "none", "already_resident")
            return self._verify_result(
                target,
                outcome.result,
                actual_loaded=outcome.actual_loaded,
                expected_loaded=True,
                action="load",
            )
        idle_age = now_monotonic - target.last_used_monotonic
        if idle_age < 0:
            return AutonomyResult(target.id, AutonomyStatus.DENIED, "none", "clock_rollback")
        if idle_age < target.idle_unload_seconds:
            return AutonomyResult(target.id, AutonomyStatus.NOOP, "none", "no_change")
        outcome = await self._coordinator.ensure_unloaded(target)
        if not outcome.authorized:
            return AutonomyResult(
                target.id, AutonomyStatus.DENIED, "unload", "health_or_authorization_stale"
            )
        if outcome.result is None:
            return AutonomyResult(target.id, AutonomyStatus.NOOP, "none", "no_change")
        return self._verify_result(
            target,
            outcome.result,
            actual_loaded=outcome.actual_loaded,
            expected_loaded=False,
            action="unload",
        )

    def _verify_result(
        self,
        target: PlacementTarget,
        result: LifecycleResult,
        *,
        actual_loaded: bool,
        expected_loaded: bool,
        action: str,
    ) -> AutonomyResult:
        if result.status in {OperationStatus.FAILED, OperationStatus.UNSUPPORTED}:
            partial = (
                result.error is not None and result.error.code is AdapterErrorCode.PARTIAL_FAILURE
            )
            return AutonomyResult(
                target.id,
                AutonomyStatus.PARTIAL if partial else AutonomyStatus.FAILED,
                action,
                result.error.code.value if result.error is not None else "adapter_failed",
                target.rollback_reference if partial else None,
            )
        if actual_loaded is not expected_loaded:
            return AutonomyResult(
                target.id,
                AutonomyStatus.PARTIAL,
                action,
                "postcondition_failed",
                target.rollback_reference,
            )
        status = (
            AutonomyStatus.NOOP
            if result.status is OperationStatus.UNCHANGED
            else AutonomyStatus.SUCCEEDED
        )
        return AutonomyResult(target.id, status, action, result.status.value)


def select_eviction_candidate(
    candidates: tuple[PlacementTarget, ...],
) -> PlacementTarget | None:
    eligible = (candidate for candidate in candidates if not candidate.resident)
    return min(eligible, key=lambda item: (item.last_used_monotonic, item.id), default=None)


def _ignore_error(_error: str) -> None:
    return


class ReconcileLoop:
    """Explicitly managed reconciliation loop with injected pacing and probes."""

    def __init__(
        self,
        engine: ReconciliationEngine,
        *,
        targets_provider: Callable[[], Awaitable[tuple[PlacementTarget, ...]]],
        memory_probe: Callable[[], Awaitable[MemorySnapshot | None]],
        monotonic_clock: Callable[[], float],
        interval_seconds: float,
        wait_next: Callable[[float], Awaitable[None]],
        error_sink: Callable[[str], None] | None = None,
    ) -> None:
        if not math.isfinite(interval_seconds) or interval_seconds <= 0:
            raise ValueError("reconcile interval must be finite and positive")
        self._engine = engine
        self._targets_provider = targets_provider
        self._memory_probe = memory_probe
        self._clock = monotonic_clock
        self._interval = interval_seconds
        self._wait_next = wait_next
        self._error_sink = error_sink or _ignore_error
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.running:
            return
        previous = self._task
        if previous is not None:
            with suppress(asyncio.CancelledError):
                await previous
        self._task = asyncio.create_task(self._run(), name="omlxc-reconcile-loop")

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def _run(self) -> None:
        while True:
            try:
                targets = await self._targets_provider()
                memory = await self._memory_probe()
                await self._engine.reconcile_many(targets, memory, now_monotonic=self._clock())
            except Exception as exc:
                self._error_sink(type(exc).__name__)
            try:
                await self._wait_next(self._interval)
            except Exception as exc:
                self._error_sink(type(exc).__name__)
                return
