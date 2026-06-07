"""Circuit breaker — fault isolation for LLM provider calls."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

CircuitState = Literal["CLOSED", "OPEN", "HALF_OPEN"]


@dataclass(init=False)
class CircuitBreakerConfig:
    """Configuration for a single circuit breaker."""

    failure_threshold: int = 3
    reset_timeout_ms: int = 30_000
    half_open_max_requests: int = 1

    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout_ms: int = 30_000,
        half_open_max_requests: int = 1,
        recovery_timeout: float | None = None,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_ms = int(recovery_timeout * 1000) if recovery_timeout is not None else reset_timeout_ms
        self.half_open_max_requests = half_open_max_requests

    @property
    def recovery_timeout(self) -> float:
        return self.reset_timeout_ms / 1000


DEFAULT_CB_CONFIG = CircuitBreakerConfig()


@dataclass
class _CircuitEntry:
    """Internal state for a circuit breaker."""

    failures: int = 0
    last_failure_time: float = 0.0
    state: CircuitState = "CLOSED"
    half_open_count: int = 0


class CircuitBreakerRegistry:
    """Manages circuit breakers keyed by provider name.

    Tracks failure counts and transitions between CLOSED, OPEN, and
    HALF_OPEN states to isolate failing providers.
    """

    def __init__(self) -> None:
        self._circuits: dict[str, _CircuitEntry] = {}
        self._configs: dict[str, CircuitBreakerConfig] = {}

    def configure(self, provider: str, config: CircuitBreakerConfig | None = None) -> None:
        """Set per-provider circuit breaker configuration."""
        self._configs[provider] = config or CircuitBreakerConfig()

    def _get_config(self, provider: str) -> CircuitBreakerConfig:
        return self._configs.get(provider) or DEFAULT_CB_CONFIG

    def get_state(self, provider: str) -> CircuitState:
        """Get the current circuit state for *provider*.

        Automatically transitions OPEN -> HALF_OPEN after the reset
        timeout elapses.
        """
        entry = self._circuits.get(provider)
        if not entry:
            return "CLOSED"

        if entry.state == "OPEN":
            cfg = self._get_config(provider)
            if time.time() * 1000 - entry.last_failure_time >= cfg.reset_timeout_ms:
                entry.state = "HALF_OPEN"
                entry.half_open_count = 0

        return entry.state

    def can_request(self, provider: str) -> bool:
        """Check whether a request to *provider* is allowed."""
        state = self.get_state(provider)
        if state == "CLOSED":
            return True
        if state == "OPEN":
            return False
        # HALF_OPEN — allow limited probe requests
        cfg = self._get_config(provider)
        entry = self._circuits.get(provider)
        return (entry.half_open_count if entry else 0) < cfg.half_open_max_requests

    def record_success(self, provider: str) -> None:
        """Record a successful call for *provider*."""
        entry = self._circuits.get(provider)
        if not entry:
            return
        if entry.state == "HALF_OPEN":
            # Probe succeeded — reset to healthy
            self._circuits.pop(provider, None)
        else:
            entry.failures = 0

    def record_failure(self, provider: str) -> None:
        """Record a failed call for *provider*."""
        entry = self._circuits.get(provider)
        if not entry:
            entry = _CircuitEntry()
            self._circuits[provider] = entry

        cfg = self._get_config(provider)

        if entry.state == "HALF_OPEN":
            # Probe failed — back to OPEN
            entry.state = "OPEN"
            entry.last_failure_time = time.time() * 1000
            entry.half_open_count = 0
            return

        entry.failures += 1
        entry.last_failure_time = time.time() * 1000

        if entry.failures >= cfg.failure_threshold:
            entry.state = "OPEN"

    def get_status(self) -> dict[str, dict[str, int | str]]:
        """Return a snapshot of all circuit breaker states."""
        status: dict[str, dict[str, int | str]] = {}
        for name in self._configs:
            entry = self._circuits.get(name)
            status[name] = {
                "state": self.get_state(name),
                "failures": entry.failures if entry else 0,
            }
        return status


class CircuitBreaker:
    """Legacy single-circuit compatibility wrapper."""

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._registry = CircuitBreakerRegistry()
        self._registry.configure(name, self.config)

    @property
    def state(self) -> str:
        return self._registry.get_state(self.name).lower()

    def record_success(self) -> None:
        self._registry.record_success(self.name)

    def record_failure(self) -> None:
        self._registry.record_failure(self.name)
