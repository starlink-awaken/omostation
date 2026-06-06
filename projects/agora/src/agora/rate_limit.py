"""Token-bucket rate limiter — extracted from SharedBrain D_Gateway.

Provides rate limiting primitives for agora's MCP routing layer.
Thread-safe token bucket with configurable limits.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

DEFAULT_REQUESTS_PER_MINUTE: int = 100
BUCKET_IDLE_TTL_SECONDS: float = 3600.0


@dataclass
class RateLimitConfig:
    """Multi-dimensional rate limit configuration.

    Attributes:
        requests_per_second: Requests per second limit.
        requests_per_minute: Requests per minute limit.
        requests_per_hour: Requests per hour limit.
        burst: Extra burst capacity beyond the primary limit.
    """

    requests_per_second: int | None = None
    requests_per_minute: int | None = None
    requests_per_hour: int | None = None
    burst: int = 10

    def get_primary_limit(self) -> tuple[int, str]:
        if self.requests_per_second:
            return (self.requests_per_second, "second")
        elif self.requests_per_minute:
            return (self.requests_per_minute, "minute")
        elif self.requests_per_hour:
            return (self.requests_per_hour, "hour")
        return (DEFAULT_REQUESTS_PER_MINUTE, "minute")


@dataclass
class TokenBucket:
    """Thread-safe token bucket algorithm.

    Tokens refill at a fixed rate. Each request consumes one token.
    When the bucket is full, excess tokens are discarded.
    When the bucket is empty, requests are denied.
    """

    capacity: int
    tokens: float
    refill_rate: float
    last_refill: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def consume(self, tokens: int = 1) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def get_available_tokens(self) -> int:
        with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            current = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            return int(current)

    def get_wait_time(self, tokens: int = 1) -> float:
        with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            current = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            if current >= tokens:
                return 0.0
            return (tokens - current) / self.refill_rate


class RateLimiter:
    """Per-key rate limiter with automatic bucket cleanup."""

    def __init__(self, cleanup_interval: int = 300) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()

        thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        thread.start()

    def _cleanup_loop(self) -> None:
        while True:
            time.sleep(self._cleanup_interval)
            self._cleanup_old_buckets()

    def _cleanup_old_buckets(self) -> None:
        now = time.time()
        with self._lock:
            stale = [k for k, b in self._buckets.items() if now - b.last_refill > BUCKET_IDLE_TTL_SECONDS]
            for k in stale:
                del self._buckets[k]

    def is_allowed(self, key: str, config: RateLimitConfig) -> bool:
        bucket = self._get_or_create_bucket(key, config)
        return bucket.consume()

    def _get_or_create_bucket(self, key: str, config: RateLimitConfig) -> TokenBucket:
        with self._lock:
            if key not in self._buckets:
                limit_value, limit_type = config.get_primary_limit()
                if limit_type == "second":
                    capacity = limit_value + config.burst
                    refill_rate = float(limit_value)
                elif limit_type == "minute":
                    capacity = limit_value + config.burst
                    refill_rate = limit_value / 60.0
                else:
                    capacity = limit_value + config.burst
                    refill_rate = limit_value / 3600.0

                self._buckets[key] = TokenBucket(
                    capacity=capacity,
                    tokens=float(capacity),
                    refill_rate=refill_rate,
                )
            return self._buckets[key]

    def get_bucket_info(self, key: str) -> dict | None:
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket:
                return {
                    "available_tokens": bucket.get_available_tokens(),
                    "capacity": bucket.capacity,
                    "refill_rate": bucket.refill_rate,
                }
        return None

    def reset_bucket(self, key: str) -> None:
        with self._lock:
            if key in self._buckets:
                b = self._buckets[key]
                with b._lock:
                    b.tokens = float(b.capacity)
                    b.last_refill = time.time()

    def clear_all(self) -> None:
        with self._lock:
            self._buckets.clear()
