"""Tests for kairon_lib.utils.rate_limiter — TokenBucket, RateLimiter."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import pytest
from kairon_utils.rate_limiter import RateLimiter, TokenBucket


class TestTokenBucket:
    @pytest.mark.asyncio
    async def test_acquire_immediate(self):
        """Acquire when tokens are available."""
        bucket = TokenBucket(rate=10.0, capacity=10)
        result = await bucket.acquire(1)
        assert result is True
        # One token consumed
        assert bucket.available_tokens() == 9

    @pytest.mark.asyncio
    async def test_acquire_exact_capacity(self):
        """Acquire exactly capacity tokens."""
        bucket = TokenBucket(rate=10.0, capacity=5)
        result = await bucket.acquire(5)
        assert result is True
        assert bucket.available_tokens() == 0

    @pytest.mark.asyncio
    async def test_acquire_waits_when_empty(self):
        """Acquire waits when not enough tokens, but eventually succeeds."""
        bucket = TokenBucket(rate=100.0, capacity=1)
        await bucket.acquire(1)  # drain
        assert bucket.available_tokens() == 0
        # Need to wait for refill; rate is high so should succeed quickly
        result = await bucket.acquire(1)
        assert result is True

    def test_available_tokens_initial(self):
        bucket = TokenBucket(rate=5.0, capacity=20)
        assert bucket.available_tokens() == 20

    def test_custom_params(self):
        bucket = TokenBucket(rate=0.5, capacity=3)
        assert bucket.rate == 0.5
        assert bucket.capacity == 3
        assert bucket.tokens == 3.0


class TestRateLimiter:
    def test_configure_source(self):
        limiter = RateLimiter()
        limiter.configure_source("src1", requests_per_second=2.0, burst_capacity=5)
        bucket = limiter.get_limiter("src1")
        assert bucket.rate == 2.0
        assert bucket.capacity == 5

    def test_get_limiter_default_config(self):
        """Unconfigured source gets default rate/capacity."""
        limiter = RateLimiter()
        bucket = limiter.get_limiter("unknown")
        assert bucket.rate == 1.0
        assert bucket.capacity == 10

    def test_get_limiter_cached(self):
        """Same source returns same limiter instance."""
        limiter = RateLimiter()
        b1 = limiter.get_limiter("src")
        b2 = limiter.get_limiter("src")
        assert b1 is b2

    @pytest.mark.asyncio
    async def test_check_limit(self):
        limiter = RateLimiter()
        limiter.configure_source("src", requests_per_second=10.0, burst_capacity=5)
        assert await limiter.check_limit("src") is True

    def test_get_available_tokens(self):
        limiter = RateLimiter()
        limiter.configure_source("src", requests_per_second=10.0, burst_capacity=5)
        assert limiter.get_available_tokens("src") == 5

    def test_reset_source(self):
        limiter = RateLimiter()
        limiter.configure_source("src", requests_per_second=1.0, burst_capacity=1)
        b1 = limiter.get_limiter("src")
        limiter.reset("src")
        b2 = limiter.get_limiter("src")
        # After reset, a new limiter is created
        assert b1 is not b2

    def test_reset_nonexistent_source(self):
        """Resetting a source that was never configured does not error."""
        limiter = RateLimiter()
        limiter.reset("nonexistent")  # should not raise
