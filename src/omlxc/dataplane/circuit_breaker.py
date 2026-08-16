"""
Runtime Circuit Breaker implementation with exponential backoff and half-open probing.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from omlxc.domain.resilience import (
    CircuitBreakerConfig,
    CircuitBreakerSnapshot,
    CircuitState,
)


class CircuitBreaker:
    """Stateful 3-state Circuit Breaker protecting against cascading node/model failures."""

    def __init__(
        self,
        target_id: str,
        config: CircuitBreakerConfig | None = None,
        clock: float | None = None,
    ) -> None:
        self.target_id = target_id
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._consecutive_trips = 0
        self._last_state_change = clock if clock is not None else time.monotonic()
        self._last_failure_time = 0.0
        self._current_cooldown = self.config.initial_cooldown_seconds
        self._next_allowed_time = 0.0
        self._failure_timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    def is_available(self, now: float | None = None) -> bool:
        """Evaluate if traffic or probing should be permitted to this target."""
        ts = now if now is not None else time.monotonic()
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                if ts >= self._next_allowed_time:
                    # Cooldown elapsed -> transition to HALF_OPEN for trial probe
                    self._state = CircuitState.HALF_OPEN
                    self._last_state_change = ts
                    return True
                return False
            return self._state == CircuitState.HALF_OPEN

    def record_success(self, now: float | None = None) -> None:
        """Record successful execution. Recovers HALF_OPEN to CLOSED."""
        ts = now if now is not None else time.monotonic()
        with self._lock:
            if self._state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                self._state = CircuitState.CLOSED
                self._last_state_change = ts
                self._consecutive_trips = 0
                self._current_cooldown = self.config.initial_cooldown_seconds
                self._failure_timestamps.clear()
            elif self._state == CircuitState.CLOSED:
                self._failure_timestamps.clear()

    def record_failure(self, now: float | None = None) -> None:
        """Record execution failure or timeout. May trip circuit to OPEN."""
        ts = now if now is not None else time.monotonic()
        with self._lock:
            self._last_failure_time = ts
            # Clean up old failures outside window
            window_cutoff = ts - self.config.window_seconds
            while self._failure_timestamps and self._failure_timestamps[0] < window_cutoff:
                self._failure_timestamps.popleft()
            self._failure_timestamps.append(ts)

            if self._state == CircuitState.HALF_OPEN:
                # Trial probe failed: immediately trip back to OPEN with doubled cooldown
                self._state = CircuitState.OPEN
                self._consecutive_trips += 1
                self._last_state_change = ts
                self._current_cooldown = min(
                    self._current_cooldown * self.config.backoff_multiplier,
                    self.config.max_cooldown_seconds,
                )
                self._next_allowed_time = ts + self._current_cooldown
            elif self._state == CircuitState.CLOSED:
                if len(self._failure_timestamps) >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._consecutive_trips += 1
                    self._last_state_change = ts
                    self._current_cooldown = min(
                        self.config.initial_cooldown_seconds
                        * (self.config.backoff_multiplier ** max(0, self._consecutive_trips - 1)),
                        self.config.max_cooldown_seconds,
                    )
                    self._next_allowed_time = ts + self._current_cooldown

    def get_snapshot(self, now: float | None = None) -> CircuitBreakerSnapshot:
        """Retrieve point-in-time snapshot."""
        ts = now if now is not None else time.monotonic()
        with self._lock:
            # Self-heal state check if OPEN has timed out
            curr_state = self._state
            if curr_state == CircuitState.OPEN and ts >= self._next_allowed_time:
                curr_state = CircuitState.HALF_OPEN

            return CircuitBreakerSnapshot(
                target_id=self.target_id,
                state=curr_state,
                failure_count=len(self._failure_timestamps),
                consecutive_trips=self._consecutive_trips,
                last_failure_time=self._last_failure_time,
                last_state_change_time=self._last_state_change,
                current_cooldown_seconds=self._current_cooldown,
                next_allowed_time=self._next_allowed_time,
            )


class CircuitBreakerRegistry:
    """Registry coordinating circuit breakers across all placement targets."""

    def __init__(self, default_config: CircuitBreakerConfig | None = None) -> None:
        self.default_config = default_config or CircuitBreakerConfig()
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_or_create(self, target_id: str) -> CircuitBreaker:
        with self._lock:
            if target_id not in self._breakers:
                self._breakers[target_id] = CircuitBreaker(
                    target_id=target_id, config=self.default_config
                )
            return self._breakers[target_id]

    def is_available(self, target_id: str, now: float | None = None) -> bool:
        breaker = self.get_or_create(target_id)
        return breaker.is_available(now=now)

    def record_success(self, target_id: str, now: float | None = None) -> None:
        breaker = self.get_or_create(target_id)
        breaker.record_success(now=now)

    def record_failure(self, target_id: str, now: float | None = None) -> None:
        breaker = self.get_or_create(target_id)
        breaker.record_failure(now=now)

    def get_all_snapshots(self, now: float | None = None) -> dict[str, CircuitBreakerSnapshot]:
        with self._lock:
            items = list(self._breakers.items())
        return {tid: b.get_snapshot(now=now) for tid, b in items}
