from __future__ import annotations

import math
from datetime import UTC, datetime
from importlib.util import find_spec

import pytest

from omlxc.domain import HealthSnapshot, NodeState


class FakeMonotonic:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def test_runtime_health_module_is_available() -> None:
    assert find_spec("omlxc.health") is not None


@pytest.mark.parametrize(
    ("current", "observed", "authorization", "available"),
    [
        (110.0, 100.0, "fresh", True),
        (131.0, 100.0, "fresh", False),
        (99.0, 100.0, "fresh", False),
        (110.0, 100.0, "stale", False),
        (math.inf, 100.0, "fresh", False),
    ],
)
def test_health_ttl_and_authorization_fail_closed(
    current: float, observed: float, authorization: str, available: bool
) -> None:
    from omlxc.health import AuthorizationFreshness, HealthCacheEntry, HealthPolicy

    clock = FakeMonotonic(current)
    policy = HealthPolicy(ttl_seconds=30.0, monotonic_clock=clock)
    snapshot = HealthSnapshot(
        state=NodeState.HEALTHY,
        observed_at=datetime(2026, 8, 11, tzinfo=UTC),
        stale=False,
    )
    result = policy.evaluate(
        HealthCacheEntry(
            snapshot=snapshot,
            observed_monotonic=observed,
            authorization=AuthorizationFreshness(authorization),
        )
    )
    assert result.available is available
    assert result.stale is (not available)


@pytest.mark.asyncio
async def test_circuit_state_table_and_half_open_probe_cap_are_deterministic() -> None:
    from omlxc.health import (
        CircuitBreaker,
        CircuitConfig,
        CircuitOpenError,
        CircuitState,
        FailureClass,
    )

    clock = FakeMonotonic()
    breaker = CircuitBreaker(
        CircuitConfig(failure_threshold=2, cooldown_seconds=10.0, half_open_probes=1),
        monotonic_clock=clock,
    )
    first = await breaker.acquire()
    await breaker.record_failure(first, FailureClass.RETRYABLE)
    ignored = await breaker.acquire()
    await breaker.record_failure(ignored, FailureClass.CAPACITY)
    assert breaker.state is CircuitState.CLOSED
    second = await breaker.acquire()
    await breaker.record_failure(second, FailureClass.RETRYABLE)
    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        await breaker.acquire()
    clock.value += 10.0
    probe = await breaker.acquire()
    assert breaker.state is CircuitState.HALF_OPEN
    with pytest.raises(CircuitOpenError):
        await breaker.acquire()
    await breaker.record_success(probe)
    assert breaker.state is CircuitState.CLOSED


def test_adaptive_probe_interval_is_bounded_and_jitter_is_deterministic() -> None:
    from omlxc.health import AdaptiveProbePolicy, CircuitState

    policy = AdaptiveProbePolicy(
        minimum_seconds=2.0,
        maximum_seconds=60.0,
        offline_seconds=45.0,
        jitter_fraction=0.1,
    )
    stable = policy.interval(
        node_state=NodeState.HEALTHY,
        circuit_state=CircuitState.CLOSED,
        stable_successes=20,
        jitter=1.0,
    )
    degraded = policy.interval(
        node_state=NodeState.DEGRADED,
        circuit_state=CircuitState.HALF_OPEN,
        stable_successes=0,
        jitter=-1.0,
    )
    offline = policy.interval(
        node_state=NodeState.UNREACHABLE,
        circuit_state=CircuitState.OPEN,
        stable_successes=0,
        jitter=0.0,
    )
    assert 2.0 <= degraded < stable <= 60.0
    assert offline == 45.0
