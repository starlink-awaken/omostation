from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Retry ≡ Module
# 内涵 ≝ {Retry}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Retry)}
# 功能 ⊢ {Init_Retry, Execute_Retry, Validate_Retry}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
Retry Strategy for Transient Failures

Implements exponential backoff retry mechanism for harvest operations.
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    """Retry configuration for harvest operations"""

    max_attempts: int = 3
    backoff_multiplier: float = 2.0
    initial_delay: float = 1.0
    retryable_errors: tuple[type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
        asyncio.TimeoutError,
    )


class RetryExecutor:
    """Execute operations with retry logic"""

    def __init__(self, policy: RetryPolicy | None = None) -> None:
        self.policy = policy or RetryPolicy()

    async def execute_with_retry(
        self,
        operation: Callable[[str], Awaitable[object]],
        source_id: str,
        on_retry: Callable[[int, float, Exception], Awaitable[None]] | None = None,
    ) -> Any:
        """
        Execute operation with exponential backoff retry

        Args:
            operation: Async function to execute
            source_id: Source identifier for logging
            on_retry: Optional callback after each retry

        Returns:
            Result of successful operation

        Raises:
            ConnectionError: If all retry attempts exhausted
        """
        last_error = None

        for attempt in range(self.policy.max_attempts):
            try:
                return await operation(source_id)
            except self.policy.retryable_errors as e:
                last_error = e
                if attempt < self.policy.max_attempts - 1:
                    delay = self.policy.initial_delay * (self.policy.backoff_multiplier**attempt)

                    _log.warning(
                        f"Retry {attempt + 1}/{self.policy.max_attempts} for {source_id} after {delay:.2f}s delay: {e}"
                    )

                    if on_retry:
                        await on_retry(attempt + 1, delay, e)

                    await asyncio.sleep(delay)
                continue
            except Exception as e:
                # Non-retryable error, fail immediately
                last_error = e
                break

        raise ConnectionError(f"Failed {source_id} after {self.policy.max_attempts} attempts") from last_error


class CircuitBreaker:
    """Prevent retry storms during cascading failures"""

    def __init__(self, failure_threshold: int = 5, timeout_seconds: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failures = 0
        self.last_failure_time: float | None = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    async def acquire(self, source_id: str) -> bool:
        """Check if circuit breaker allows request"""
        if self.state == "OPEN":
            if self.last_failure_time is None:
                # No failure recorded yet, allow request
                return True

            current_time = asyncio.get_event_loop().time()
            time_diff = current_time - self.last_failure_time

            if time_diff > self.timeout_seconds:
                self.state = "HALF_OPEN"
                _log.info(f"Circuit breaker HALF_OPEN for {source_id}")
            else:
                return False

        return True

    def record_success(self, source_id: str) -> None:
        """Record successful operation"""
        self.failures = 0
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            _log.info(f"Circuit breaker CLOSED for {source_id}")

    async def record_failure(self, source_id: str) -> None:
        """Record failed operation (async for consistent time handling)"""
        self.failures += 1
        # Use monotonic time from event loop for consistency with acquire()
        self.last_failure_time = asyncio.get_event_loop().time()

        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            _log.warning(f"Circuit breaker OPEN for {source_id} after {self.failures} failures")
