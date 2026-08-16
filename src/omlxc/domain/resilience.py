"""
Pure domain models for circuit breaker resilience and failure isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CircuitState(StrEnum):
    """Canonical 3-state circuit breaker enumeration."""

    CLOSED = "closed"  # Normal operation: all traffic passed
    OPEN = "open"  # Tripped: traffic rejected/redirected
    HALF_OPEN = "half_open"  # Trial probe: single probe allowed to test recovery


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Configuration governing circuit tripping and exponential backoff recovery."""

    failure_threshold: int = 3
    initial_cooldown_seconds: float = 30.0
    backoff_multiplier: float = 2.0
    max_cooldown_seconds: float = 300.0
    window_seconds: float = 60.0


@dataclass(frozen=True)
class CircuitBreakerSnapshot:
    """Point-in-time state of a circuit breaker for a specific target/placement."""

    target_id: str
    state: CircuitState
    failure_count: int
    consecutive_trips: int
    last_failure_time: float
    last_state_change_time: float
    current_cooldown_seconds: float
    next_allowed_time: float
