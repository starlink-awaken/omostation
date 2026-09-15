"""
Per-Source Rate Limiting.

Implements token bucket algorithm for rate limiting operations.
Extracted from D_Harvest utils/rate_limiter.py.
"""

import asyncio
import logging
import time
from dataclasses import dataclass

_log = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket rate limiter."""

    rate: float  # tokens per second
    capacity: int  # max tokens
    tokens: float
    last_update: float

    def __init__(self, rate: float, capacity: int) -> None:
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens from bucket.

        Args:
            tokens: Number of tokens to acquire.

        Returns:
            True if tokens acquired (may wait), False if unavailable.
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            # Calculate wait time needed
            wait_time = (tokens - self.tokens) / self.rate
            _log.debug(f"Rate limit: waiting {wait_time:.2f}s for {tokens} tokens")

            # Wait and acquire
            await asyncio.sleep(wait_time)
            self.tokens = 0
            return True

    def available_tokens(self) -> int:
        """Get number of available tokens (non-blocking)."""
        return int(self.tokens)


class RateLimiter:
    """Per-source rate limiting manager."""

    def __init__(self) -> None:
        self._limiters: dict[str, TokenBucket] = {}
        self._config: dict[str, dict] = {}

    def configure_source(self, source_id: str, requests_per_second: float = 1.0, burst_capacity: int = 10) -> None:
        """
        Configure rate limit for a specific source.

        Args:
            source_id: Source identifier.
            requests_per_second: Token refill rate.
            burst_capacity: Maximum token capacity.
        """
        self._config[source_id] = {"rate": requests_per_second, "capacity": burst_capacity}

    def get_limiter(self, source_id: str) -> TokenBucket:
        """Get or create rate limiter for source."""
        if source_id not in self._limiters:
            config = self._config.get(source_id, {})
            self._limiters[source_id] = TokenBucket(rate=config.get("rate", 1.0), capacity=config.get("capacity", 10))
        return self._limiters[source_id]

    async def check_limit(self, source_id: str, tokens: int = 1) -> bool:
        """
        Check if request is allowed under rate limit.

        Args:
            source_id: Source identifier.
            tokens: Number of tokens to consume (default: 1).

        Returns:
            True if request allowed.
        """
        limiter = self.get_limiter(source_id)
        return await limiter.acquire(tokens)

    def get_available_tokens(self, source_id: str) -> int:
        """
        Get number of available tokens for a source (non-blocking).

        Args:
            source_id: Source identifier.

        Returns:
            Number of available tokens.
        """
        limiter = self.get_limiter(source_id)
        return limiter.available_tokens()

    def reset(self, source_id: str) -> None:
        """Reset rate limiter for a source."""
        if source_id in self._limiters:
            del self._limiters[source_id]
