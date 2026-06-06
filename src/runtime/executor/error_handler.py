"""Error Handler — classification, recovery strategies, retry with backoff.

Ported from agentmesh error-handler.ts.

"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from runtime.executor.engine_types import (
    EngineError,
    ErrorCategory,
    ErrorSeverity,
    RecoveryStrategy,
)

T = TypeVar("T")

# ====================================================================
# Default Recovery Strategies
# ====================================================================

_DEFAULT_STRATEGIES: dict[ErrorCategory, RecoveryStrategy] = {
    ErrorCategory.NETWORK: RecoveryStrategy(
        category=ErrorCategory.NETWORK,
        severity=ErrorSeverity.RECOVERABLE,
        max_retries=3,
        base_delay_ms=1000.0,
        max_delay_ms=10000.0,
        use_exponential_backoff=True,
        jitter_factor=0.1,
        log_as_warning=True,
    ),
    ErrorCategory.TIMEOUT: RecoveryStrategy(
        category=ErrorCategory.TIMEOUT,
        severity=ErrorSeverity.RECOVERABLE,
        max_retries=2,
        base_delay_ms=500.0,
        max_delay_ms=5000.0,
        use_exponential_backoff=True,
        jitter_factor=0.2,
        log_as_warning=True,
    ),
    ErrorCategory.DATABASE: RecoveryStrategy(
        category=ErrorCategory.DATABASE,
        severity=ErrorSeverity.NON_RECOVERABLE,
        max_retries=2,
        base_delay_ms=500.0,
        max_delay_ms=2000.0,
        use_exponential_backoff=True,
        jitter_factor=0.1,
        log_as_warning=False,
    ),
    ErrorCategory.AGENT_EXECUTION: RecoveryStrategy(
        category=ErrorCategory.AGENT_EXECUTION,
        severity=ErrorSeverity.RECOVERABLE,
        max_retries=1,
        base_delay_ms=1000.0,
        max_delay_ms=3000.0,
        use_exponential_backoff=False,
        jitter_factor=0.1,
        log_as_warning=True,
    ),
    ErrorCategory.CONFIGURATION: RecoveryStrategy(
        category=ErrorCategory.CONFIGURATION,
        severity=ErrorSeverity.NON_RECOVERABLE,
        max_retries=0,
        base_delay_ms=0.0,
        max_delay_ms=0.0,
        use_exponential_backoff=False,
        jitter_factor=0.0,
        log_as_warning=False,
    ),
    ErrorCategory.VALIDATION: RecoveryStrategy(
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.NON_RECOVERABLE,
        max_retries=0,
        base_delay_ms=0.0,
        max_delay_ms=0.0,
        use_exponential_backoff=False,
        jitter_factor=0.0,
        log_as_warning=False,
    ),
    ErrorCategory.RESOURCE_EXHAUSTED: RecoveryStrategy(
        category=ErrorCategory.RESOURCE_EXHAUSTED,
        severity=ErrorSeverity.NON_RECOVERABLE,
        max_retries=0,
        base_delay_ms=0.0,
        max_delay_ms=0.0,
        use_exponential_backoff=False,
        jitter_factor=0.0,
        log_as_warning=False,
    ),
    ErrorCategory.PLUGIN: RecoveryStrategy(
        category=ErrorCategory.PLUGIN,
        severity=ErrorSeverity.RECOVERABLE,
        max_retries=2,
        base_delay_ms=500.0,
        max_delay_ms=5000.0,
        use_exponential_backoff=True,
        jitter_factor=0.1,
        log_as_warning=True,
    ),
}


class ErrorHandler:
    """Error handler with classification, retry, and fallback strategies."""

    def __init__(self) -> None:
        self._custom_strategies: dict[ErrorCategory, RecoveryStrategy] = {}

    def set_recovery_strategy(self, category: ErrorCategory, **overrides: Any) -> None:
        base = _DEFAULT_STRATEGIES.get(category) or RecoveryStrategy(category=category)
        merged = RecoveryStrategy(
            category=category,
            severity=overrides.get("severity", base.severity),
            max_retries=overrides.get("max_retries", base.max_retries),
            base_delay_ms=overrides.get("base_delay_ms", base.base_delay_ms),
            max_delay_ms=overrides.get("max_delay_ms", base.max_delay_ms),
            use_exponential_backoff=overrides.get("use_exponential_backoff", base.use_exponential_backoff),
            jitter_factor=overrides.get("jitter_factor", base.jitter_factor),
            log_as_warning=overrides.get("log_as_warning", base.log_as_warning),
        )
        self._custom_strategies[category] = merged

    def _get_strategy(self, category: ErrorCategory) -> RecoveryStrategy:
        return self._custom_strategies.get(category) or _DEFAULT_STRATEGIES.get(
            category,
            RecoveryStrategy(category=category, max_retries=0),
        )

    def _calculate_delay(self, attempt: int, strategy: RecoveryStrategy) -> float:
        if not strategy.use_exponential_backoff:
            return strategy.base_delay_ms
        delay = strategy.base_delay_ms * (2**attempt)
        jitter = delay * strategy.jitter_factor * 0.5
        return max(0.0, min(delay + jitter, strategy.max_delay_ms))

    async def execute_with_retry(
        self,
        fn: Callable[[], Awaitable[T]],
        category: ErrorCategory,
        context: dict[str, Any] | None = None,
    ) -> T:
        """Execute an async function with retry and backoff."""
        strategy = self._get_strategy(category)
        last_error: Exception | None = None

        for attempt in range(strategy.max_retries + 1):
            try:
                return await fn()
            except EngineError as e:
                last_error = e
                if attempt >= strategy.max_retries:
                    break
                if not e.retryable:
                    raise
                delay = self._calculate_delay(attempt, strategy)
                await asyncio.sleep(delay / 1000.0)
            except Exception as e:
                last_error = e
                if attempt >= strategy.max_retries:
                    break
                engine_err = EngineError.from_exception(e, **(context or {}))
                if not engine_err.retryable:
                    raise engine_err
                delay = self._calculate_delay(attempt, strategy)
                await asyncio.sleep(delay / 1000.0)

        raise last_error  # type: ignore[misc]

    def handle_error(self, error: Exception, context: dict[str, Any] | None = None) -> EngineError:
        """Classify and log an error."""
        engine_err = EngineError.from_exception(error, **(context or {}))
        return engine_err

    def is_recoverable(self, error: Exception) -> bool:
        engine_err = EngineError.from_exception(error)
        return engine_err.severity == ErrorSeverity.RECOVERABLE or engine_err.retryable


# ====================================================================
# Helper Functions
# ====================================================================


async def with_error_handling(
    fn: Callable[[], Awaitable[T]],
    handler: ErrorHandler,
    category: ErrorCategory,
    context: dict[str, Any] | None = None,
) -> T:
    """Execute with automatic retry and error handling."""
    try:
        return await handler.execute_with_retry(fn, category, context)
    except Exception as e:
        raise handler.handle_error(e, context)
