from __future__ import annotations

from omlxc.dataplane.circuit_breaker import CircuitBreaker, CircuitBreakerRegistry
from omlxc.domain.resilience import CircuitBreakerConfig, CircuitState


def test_circuit_breaker_initial_state() -> None:
    cb = CircuitBreaker("p1", clock=100.0)
    assert cb.state == CircuitState.CLOSED
    assert cb.is_available(now=100.0) is True


def test_circuit_breaker_trips_to_open_after_threshold() -> None:
    config = CircuitBreakerConfig(failure_threshold=3, initial_cooldown_seconds=30.0)
    cb = CircuitBreaker("p1", config=config, clock=100.0)

    cb.record_failure(now=101.0)
    assert cb.state == CircuitState.CLOSED
    assert cb.is_available(now=101.0) is True

    cb.record_failure(now=102.0)
    assert cb.state == CircuitState.CLOSED
    assert cb.is_available(now=102.0) is True

    # 3rd failure trips the breaker
    cb.record_failure(now=103.0)
    assert cb.state == CircuitState.OPEN
    assert cb.is_available(now=103.0) is False
    assert cb.is_available(now=120.0) is False  # within 30s cooldown


def test_circuit_breaker_half_open_and_recovery() -> None:
    config = CircuitBreakerConfig(failure_threshold=3, initial_cooldown_seconds=30.0)
    cb = CircuitBreaker("p1", config=config, clock=100.0)

    cb.record_failure(now=101.0)
    cb.record_failure(now=102.0)
    cb.record_failure(now=103.0)
    assert cb.state == CircuitState.OPEN

    # After cooldown (103 + 30 = 133), is_available should transition to HALF_OPEN
    assert cb.is_available(now=134.0) is True
    assert cb.state == CircuitState.HALF_OPEN

    # Success in HALF_OPEN resets to CLOSED
    cb.record_success(now=135.0)
    assert cb.state == CircuitState.CLOSED
    assert cb.is_available(now=136.0) is True


def test_circuit_breaker_half_open_failure_doubles_cooldown() -> None:
    config = CircuitBreakerConfig(
        failure_threshold=3,
        initial_cooldown_seconds=30.0,
        backoff_multiplier=2.0,
    )
    cb = CircuitBreaker("p1", config=config, clock=100.0)

    cb.record_failure(now=101.0)
    cb.record_failure(now=102.0)
    cb.record_failure(now=103.0)
    assert cb.state == CircuitState.OPEN

    # After 30s -> HALF_OPEN
    assert cb.is_available(now=134.0) is True
    assert cb.state == CircuitState.HALF_OPEN

    # Trial probe fails -> trips back to OPEN with doubled cooldown (60s)
    cb.record_failure(now=135.0)
    assert cb.state == CircuitState.OPEN

    # Still OPEN after 30s from 135
    assert cb.is_available(now=165.0) is False

    # Available after 60s (135 + 60 = 195)
    assert cb.is_available(now=196.0) is True
    assert cb.state == CircuitState.HALF_OPEN


def test_circuit_breaker_registry() -> None:
    registry = CircuitBreakerRegistry()
    assert registry.is_available("node-a", now=10.0) is True

    registry.record_failure("node-a", now=11.0)
    registry.record_failure("node-a", now=12.0)
    registry.record_failure("node-a", now=13.0)

    assert registry.is_available("node-a", now=14.0) is False
    assert registry.is_available("node-b", now=14.0) is True

    snapshots = registry.get_all_snapshots(now=14.0)
    assert "node-a" in snapshots
    assert snapshots["node-a"].state == CircuitState.OPEN
