"""Retry logic with exponential backoff for provider calls.

Adapted from agentmesh gateway model-gateway/retry.ts.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY_MS = 500
DEFAULT_MAX_DELAY_MS = 10_000
DEFAULT_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay_ms: int = DEFAULT_BASE_DELAY_MS,
        max_delay_ms: int = DEFAULT_MAX_DELAY_MS,
        retryable_statuses: set[int] | None = None,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay_ms = base_delay_ms
        self.max_delay_ms = max_delay_ms
        self.retryable_statuses = retryable_statuses or DEFAULT_RETRYABLE_STATUSES

    def get_delay(self, attempt: int) -> float:
        """Get delay in seconds for a given attempt (0-indexed)."""
        base = self.base_delay_ms * (2**attempt)
        jitter = 0.75 + random.random() * 0.5  # noqa: S311
        return min(base * jitter, self.max_delay_ms) / 1000.0


_global_config = RetryConfig()


def configure_retry(config: RetryConfig | None = None, **kwargs: Any) -> None:
    """Configure global retry settings."""
    global _global_config
    if config:
        _global_config = config
    else:
        for key, value in kwargs.items():
            if hasattr(_global_config, key):
                setattr(_global_config, key, value)


def get_retry_config() -> RetryConfig:
    return _global_config


def is_retryable(status: int) -> bool:
    return status in _global_config.retryable_statuses


async def with_retry(
    provider: str,
    fn: Callable[..., Any],
    *,
    on_retry: Callable[..., Any] | None = None,
    config: RetryConfig | None = None,
) -> Any:
    """Execute a callable with retry logic.

    Args:
        provider: Provider name for logging.
        fn: Async callable returning a response-like object with .status.
        on_retry: Optional callback (attempt, status, delay_ms).
        config: Override global config.

    Returns:
        The response from fn.

    Raises:
        RuntimeError: When max retries exhausted.
    """
    cfg = config or _global_config
    last_error: Exception | None = None

    for attempt in range(cfg.max_retries + 1):
        try:
            result = await fn()
            status = getattr(result, "status", 200) if hasattr(result, "status") else 200

            if status in cfg.retryable_statuses and attempt < cfg.max_retries:
                delay = cfg.get_delay(attempt)
                if on_retry:
                    on_retry(attempt, status, int(delay * 1000))
                await asyncio.sleep(delay)
                continue

            return result
        except Exception as e:
            last_error = e
            if attempt < cfg.max_retries:
                delay = cfg.get_delay(attempt)
                if on_retry:
                    on_retry(attempt, 0, int(delay * 1000))
                await asyncio.sleep(delay)
                continue
            raise

    msg = f"{provider}: max retries ({cfg.max_retries}) exhausted"
    raise RuntimeError(msg) from last_error
