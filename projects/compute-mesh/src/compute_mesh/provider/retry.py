"""Retry logic with exponential backoff for LLM provider calls."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")


@dataclass(init=False)
class RetryConfig:
    """Configuration for retry behaviour."""

    max_retries: int = 3
    base_delay_ms: float = 500.0
    max_delay_ms: float = 10_000.0
    retryable_statuses: list[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    call_timeout_ms: float = 30_000.0
    total_timeout_ms: float = 120_000.0

    def __init__(
        self,
        max_retries: int = 3,
        base_delay_ms: float = 500.0,
        max_delay_ms: float = 10_000.0,
        retryable_statuses: list[int] | None = None,
        call_timeout_ms: float = 30_000.0,
        total_timeout_ms: float = 120_000.0,
        base_delay: float | None = None,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay_ms = base_delay * 1000 if base_delay is not None else base_delay_ms
        self.max_delay_ms = max_delay_ms
        self.retryable_statuses = retryable_statuses or [429, 500, 502, 503, 504]
        self.call_timeout_ms = call_timeout_ms
        self.total_timeout_ms = total_timeout_ms

    @property
    def base_delay(self) -> float:
        return self.base_delay_ms / 1000


DEFAULT_RETRY = RetryConfig()


def _is_retryable(status: int, retryable_statuses: list[int]) -> bool:
    return status in retryable_statuses


def _backoff(attempt: int, config: RetryConfig) -> float:
    ms = config.base_delay_ms * (2 ** (attempt - 1))
    return min(ms, config.max_delay_ms)


async def with_retry(  # noqa: UP047
    fn: Callable[[], Awaitable[T]],
    on_retry: Callable[[int, int | None, float], None] | None = None,
    config: RetryConfig | None = None,
) -> T:
    """Execute *fn* with exponential-backoff retry for transient errors.

    Only retries on HTTP status codes listed in *retryable_statuses*.
    Network errors and timeouts are also retried.
    """
    cfg = config or DEFAULT_RETRY
    last_error: Exception | None = None
    start_time = time.monotonic()

    for attempt in range(1, cfg.max_retries + 1):
        elapsed_ms = (time.monotonic() - start_time) * 1000
        if elapsed_ms >= cfg.total_timeout_ms:
            raise TimeoutError(f"Total timeout exceeded: {cfg.total_timeout_ms}ms")

        try:
            if cfg.call_timeout_ms:
                result = await asyncio.wait_for(
                    fn(),
                    timeout=cfg.call_timeout_ms / 1000,
                )
            else:
                result = await fn()
            return result
        except Exception as exc:
            last_error = exc

            # Try to extract HTTP status code from various exception types
            status: int | None = None
            if hasattr(exc, "response"):
                resp = getattr(exc, "response")
                if hasattr(resp, "status_code"):
                    status = resp.status_code
            elif hasattr(exc, "status_code"):
                status = getattr(exc, "status_code")
            elif hasattr(exc, "status"):
                status = getattr(exc, "status")

            if status is not None and not _is_retryable(status, cfg.retryable_statuses):
                raise

            if attempt < cfg.max_retries:
                wait_ms = _backoff(attempt, cfg)
                if on_retry is not None:
                    on_retry(attempt, status, wait_ms)
                await asyncio.sleep(wait_ms / 1000)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Retry failed")
