"""Rate Limiter — sliding window token bucket with tpm/rpm dual dimensions.

Prevents bill shock by throttling requests per model/provider when
they exceed configured rate limits.

Usage::

    from llm_gateway.rate_limiter import RateLimiter

    limiter = RateLimiter()
    # Allow 100K tokens/min and 30 requests/min for gpt-4
    limiter.set_limit("gpt-4", tpm=100_000, rpm=30)

    async def handler(model: str, tokens: int) -> bool:
        if not await limiter.acquire(model, tokens):
            raise RateLimitError(f"Model {model} rate limit exceeded")
        # ... proceed with generation
        limiter.release(model, tokens)  # on success/error
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

_log = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when a rate limit is exceeded."""


@dataclass
class _Window:
    """Sliding window state for a single dimension (tpm or rpm)."""

    max_amount: int = 0  # max tokens/requests per window
    window_seconds: float = 60.0  # window duration
    current: float = 0.0  # current usage in this window
    window_start: float = 0.0  # timestamp when this window started

    def reset_if_expired(self) -> None:
        """Reset if the current window has expired."""
        if time.time() - self.window_start > self.window_seconds:
            self.current = 0.0
            self.window_start = time.time()

    def can_accept(self, amount: float) -> bool:
        """Check if *amount* fits within the limit."""
        self.reset_if_expired()
        return self.max_amount <= 0 or (self.current + amount) <= self.max_amount

    def acquire(self, amount: float) -> bool:
        """Try to consume *amount*. Returns True if accepted."""
        self.reset_if_expired()
        if self.max_amount <= 0:
            return True  # unlimited
        if self.current + amount > self.max_amount:
            return False
        self.current += amount
        return True

    def release(self, amount: float) -> None:
        """Release *amount* back to the bucket."""
        self.current = max(0.0, self.current - amount)


@dataclass
class _ModelLimit:
    """Rate limits for a single model."""

    tpm_window: _Window = field(default_factory=_Window)
    rpm_window: _Window = field(default_factory=_Window)

    @property
    def is_limited(self) -> bool:
        return self.tpm_window.max_amount > 0 or self.rpm_window.max_amount > 0


class RateLimiter:
    """Dual-dimension rate limiter per model.

    Thread-safe. Supports async and sync ``acquire``.

    Limits are set per model ID. Models without explicit limits are
    unlimited (pass-through).
    """

    def __init__(self) -> None:
        self._limits: dict[str, _ModelLimit] = {}
        self._default_tpm: int = 0
        self._default_rpm: int = 0
        self._lock = Lock()

    # ── Configuration ─────────────────────────────────────────────────────────

    def set_limit(
        self,
        model_id: str,
        tpm: int = 0,
        rpm: int = 0,
        window_seconds: float = 60.0,
    ) -> None:
        """Set rate limits for a model.

        Args:
            model_id: Model identifier (e.g. ``"gpt-4"``).
            tpm: Max tokens per minute (0 = unlimited).
            rpm: Max requests per minute (0 = unlimited).
            window_seconds: Sliding window duration in seconds.
        """
        with self._lock:
            existing = self._limits.get(model_id)
            if existing:
                existing.tpm_window.max_amount = tpm
                existing.tpm_window.window_seconds = window_seconds
                existing.rpm_window.max_amount = rpm
                existing.rpm_window.window_seconds = window_seconds
            else:
                self._limits[model_id] = _ModelLimit(
                    tpm_window=_Window(max_amount=tpm, window_seconds=window_seconds),
                    rpm_window=_Window(max_amount=rpm, window_seconds=window_seconds),
                )

    def set_default_limits(self, tpm: int = 0, rpm: int = 0) -> None:
        """Set default limits for any model without explicit limits."""
        self._default_tpm = tpm
        self._default_rpm = rpm

    def remove_limit(self, model_id: str) -> None:
        """Remove explicit limits for a model (becomes unlimited)."""
        with self._lock:
            self._limits.pop(model_id, None)

    def get_limit(self, model_id: str) -> dict[str, int]:
        """Get current limits for a model."""
        with self._lock:
            limit = self._limits.get(model_id)
            if limit:
                return {
                    "tpm": limit.tpm_window.max_amount,
                    "rpm": limit.rpm_window.max_amount,
                }
        return {"tpm": self._default_tpm, "rpm": self._default_rpm}

    # ── Acquire / Release ─────────────────────────────────────────────────────

    def _get_limit_for(self, model_id: str) -> _ModelLimit:
        """Get or create a limit entry for *model_id*."""
        with self._lock:
            limit = self._limits.get(model_id)
            if limit is None:
                limit = _ModelLimit(
                    tpm_window=_Window(max_amount=self._default_tpm),
                    rpm_window=_Window(max_amount=self._default_rpm),
                )
                self._limits[model_id] = limit
            return limit

    def acquire(self, model_id: str, tokens: int = 0) -> bool:
        """Try to acquire *tokens* for *model_id*.

        Returns ``True`` if within limits, ``False`` if throttled.
        """
        limit = self._get_limit_for(model_id)
        if not limit.is_limited:
            return True

        with self._lock:
            # Check both dimensions
            if not limit.tpm_window.can_accept(tokens):
                return False
            if not limit.rpm_window.can_accept(1):
                return False

            # Acquire both
            limit.tpm_window.acquire(tokens)
            limit.rpm_window.acquire(1)
        return True

    async def async_acquire(self, model_id: str, tokens: int = 0) -> bool:
        """Async version of :meth:`acquire`."""
        return self.acquire(model_id, tokens)

    def release(self, model_id: str, tokens: int = 0) -> None:
        """Release previously acquired *tokens*."""
        with self._lock:
            limit = self._limits.get(model_id)
            if limit:
                limit.tpm_window.release(tokens)

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Return current usage stats for all limited models."""
        with self._lock:
            return {
                mid: {
                    "tpm": {
                        "limit": l.tpm_window.max_amount,
                        "current": round(l.tpm_window.current, 0),
                        "usage_pct": round(
                            (l.tpm_window.current / l.tpm_window.max_amount * 100)
                            if l.tpm_window.max_amount > 0 else 0,
                            1,
                        ),
                    },
                    "rpm": {
                        "limit": l.rpm_window.max_amount,
                        "current": l.rpm_window.current,
                        "usage_pct": round(
                            (l.rpm_window.current / l.rpm_window.max_amount * 100)
                            if l.rpm_window.max_amount > 0 else 0,
                            1,
                        ),
                    },
                }
                for mid, l in self._limits.items()
                if l.is_limited
            }

    def reset(self) -> None:
        """Reset all limits and usage counters."""
        with self._lock:
            self._limits.clear()

    @property
    def total_limited_models(self) -> int:
        with self._lock:
            return sum(1 for l in self._limits.values() if l.is_limited)
