"""Circuit breaker for LLM providers — prevents cascading failures.

When a provider fails consecutively, the circuit opens and fast-fails subsequent
calls for a cooldown period. After cooldown, a single probe call is allowed
(half-open); if it succeeds, the circuit closes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class CircuitState:
    provider: str
    failures: int = 0
    last_failure: float = 0.0
    open_until: float = 0.0

    @property
    def is_open(self) -> bool:
        return time.monotonic() < self.open_until

    @property
    def is_half_open(self) -> bool:
        return not self.is_open and self.failures > 0


class CircuitBreaker:
    """Simple circuit breaker for LLM provider calls.

    Usage:
        breaker = CircuitBreaker("deepseek", threshold=3, cooldown=60)
        if not breaker.acquire():
            return None  # Circuit open, skip call
        try:
            result = await llm.generate(...)
            breaker.success()
        except Exception:  # noqa: BLE001
            breaker.failure()
    """

    def __init__(self, provider: str, failure_threshold: int = 3, cooldown_seconds: float = 60.0) -> None:
        self.provider = provider
        self.threshold = failure_threshold
        self.cooldown = cooldown_seconds
        self._state = CircuitState(provider=provider)

    def acquire(self) -> bool:
        """Check if a call should be allowed. Returns False if circuit is open."""
        return not self._state.is_open

    def success(self) -> None:
        """Reset failure count on successful call."""
        self._state.failures = 0
        self._state.open_until = 0.0

    def failure(self) -> None:
        """Record a failure. Opens circuit if threshold reached."""
        self._state.failures += 1
        self._state.last_failure = time.monotonic()
        if self._state.failures >= self.threshold:
            self._state.open_until = time.monotonic() + self.cooldown

    @property
    def status(self) -> dict:
        """Return current breaker status for health checks."""
        return {
            "provider": self.provider,
            "failures": self._state.failures,
            "is_open": self._state.is_open,
            "remaining_cooldown": max(0.0, self._state.open_until - time.monotonic()),
        }
