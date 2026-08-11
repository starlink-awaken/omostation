"""Deterministic health freshness and transport circuit state."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

import anyio

from omlxc.domain import HealthSnapshot, NodeState


class AuthorizationFreshness(StrEnum):
    UNKNOWN = "unknown"
    STALE = "stale"
    FRESH = "fresh"


@dataclass(frozen=True, slots=True)
class HealthCacheEntry:
    snapshot: HealthSnapshot
    observed_monotonic: float
    authorization: AuthorizationFreshness = AuthorizationFreshness.FRESH


@dataclass(frozen=True, slots=True)
class EffectiveHealth:
    state: NodeState
    stale: bool
    available: bool
    reason: str | None = None


class HealthPolicy:
    def __init__(self, *, ttl_seconds: float, monotonic_clock: Callable[[], float]) -> None:
        if not math.isfinite(ttl_seconds) or ttl_seconds <= 0:
            raise ValueError("health TTL must be finite and positive")
        self._ttl = ttl_seconds
        self._clock = monotonic_clock

    def evaluate(self, entry: HealthCacheEntry | None) -> EffectiveHealth:
        if entry is None:
            return EffectiveHealth(NodeState.UNKNOWN, True, False, "unobserved")
        if entry.authorization is not AuthorizationFreshness.FRESH:
            return EffectiveHealth(entry.snapshot.state, True, False, "authorization_stale")
        try:
            current = self._clock()
            age = current - entry.observed_monotonic
        except (ArithmeticError, TypeError, ValueError):
            return EffectiveHealth(entry.snapshot.state, True, False, "clock_invalid")
        if (
            not math.isfinite(current)
            or not math.isfinite(entry.observed_monotonic)
            or not math.isfinite(age)
            or age < 0
            or age > self._ttl
            or entry.snapshot.stale
        ):
            return EffectiveHealth(entry.snapshot.state, True, False, "snapshot_stale")
        available = entry.snapshot.state in {NodeState.HEALTHY, NodeState.DEGRADED}
        return EffectiveHealth(entry.snapshot.state, False, available)


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class FailureClass(StrEnum):
    RETRYABLE = "retryable"
    CONFIGURATION = "configuration"
    SECURITY = "security"
    UNSUPPORTED = "unsupported"
    CAPACITY = "capacity"


class CircuitOpenError(RuntimeError):
    """The circuit cannot admit a normal request or another probe."""


@dataclass(frozen=True, slots=True)
class CircuitConfig:
    failure_threshold: int
    cooldown_seconds: float
    half_open_probes: int

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError("failure threshold must be positive")
        if not math.isfinite(self.cooldown_seconds) or self.cooldown_seconds <= 0:
            raise ValueError("circuit cooldown must be finite and positive")
        if self.half_open_probes < 1:
            raise ValueError("half-open probe cap must be positive")


@dataclass(frozen=True, slots=True)
class CircuitPermit:
    token: int
    probe: bool


class CircuitBreaker:
    def __init__(self, config: CircuitConfig, *, monotonic_clock: Callable[[], float]) -> None:
        self._config = config
        self._clock = monotonic_clock
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: float | None = None
        self._active_probes = 0
        self._next_token = 1
        self._permits: dict[int, CircuitPermit] = {}
        self._lock = anyio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def acquire(self) -> CircuitPermit:
        async with self._lock:
            now = self._clock()
            if not math.isfinite(now):
                raise CircuitOpenError("circuit clock is invalid")
            if self._state is CircuitState.OPEN:
                opened_at = self._opened_at
                if opened_at is None or now < opened_at:
                    raise CircuitOpenError("circuit clock rolled back")
                if now - opened_at < self._config.cooldown_seconds:
                    raise CircuitOpenError("circuit is open")
                self._state = CircuitState.HALF_OPEN
                self._active_probes = 0
            probe = self._state is CircuitState.HALF_OPEN
            if probe and self._active_probes >= self._config.half_open_probes:
                raise CircuitOpenError("half-open probe capacity is exhausted")
            token = self._next_token
            self._next_token += 1
            permit = CircuitPermit(token=token, probe=probe)
            self._permits[token] = permit
            if probe:
                self._active_probes += 1
            return permit

    async def record_success(self, permit: CircuitPermit) -> None:
        async with self._lock:
            accepted = self._consume(permit)
            if accepted.probe:
                self._state = CircuitState.CLOSED
                self._failures = 0
                self._opened_at = None
                self._active_probes = 0
            elif self._state is CircuitState.CLOSED:
                self._failures = 0

    async def record_failure(self, permit: CircuitPermit, category: FailureClass) -> None:
        async with self._lock:
            accepted = self._consume(permit)
            if accepted.probe and category is FailureClass.RETRYABLE:
                self._open()
                return
            if self._state is not CircuitState.CLOSED or category is not FailureClass.RETRYABLE:
                return
            self._failures += 1
            if self._failures >= self._config.failure_threshold:
                self._open()

    async def release(self, permit: CircuitPermit) -> None:
        """Settle an unused permit without changing circuit outcome state."""
        async with self._lock:
            self._consume(permit)

    def _consume(self, permit: CircuitPermit) -> CircuitPermit:
        accepted = self._permits.pop(permit.token, None)
        if accepted is None or accepted != permit:
            raise ValueError("circuit permit is unknown or already settled")
        if accepted.probe:
            self._active_probes = max(0, self._active_probes - 1)
        return accepted

    def _open(self) -> None:
        now = self._clock()
        if not math.isfinite(now):
            raise CircuitOpenError("circuit clock is invalid")
        self._state = CircuitState.OPEN
        self._opened_at = now
        self._failures = 0
        self._active_probes = 0


@dataclass(frozen=True, slots=True)
class AdaptiveProbePolicy:
    minimum_seconds: float
    maximum_seconds: float
    offline_seconds: float
    jitter_fraction: float = 0.0

    def __post_init__(self) -> None:
        values = (self.minimum_seconds, self.maximum_seconds, self.offline_seconds)
        if any(not math.isfinite(value) or value <= 0 for value in values):
            raise ValueError("probe intervals must be finite and positive")
        if self.minimum_seconds > self.maximum_seconds:
            raise ValueError("minimum probe interval cannot exceed maximum")
        if not self.minimum_seconds <= self.offline_seconds <= self.maximum_seconds:
            raise ValueError("offline interval must be within probe bounds")
        if not math.isfinite(self.jitter_fraction) or not 0 <= self.jitter_fraction <= 0.5:
            raise ValueError("probe jitter fraction is invalid")

    def interval(
        self,
        *,
        node_state: NodeState,
        circuit_state: CircuitState,
        stable_successes: int,
        jitter: float,
    ) -> float:
        if stable_successes < 0 or not math.isfinite(jitter) or not -1 <= jitter <= 1:
            raise ValueError("probe state or jitter is invalid")
        if node_state is NodeState.UNREACHABLE:
            base = self.offline_seconds
        elif node_state is NodeState.DEGRADED or circuit_state is CircuitState.HALF_OPEN:
            base = self.minimum_seconds
        else:
            exponent = min(stable_successes // 4, 8)
            base = min(self.maximum_seconds, self.minimum_seconds * (2**exponent))
        adjusted = base * (1 + jitter * self.jitter_fraction)
        return min(self.maximum_seconds, max(self.minimum_seconds, adjusted))
