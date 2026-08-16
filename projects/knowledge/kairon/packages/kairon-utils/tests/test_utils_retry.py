"""Tests for kairon_lib.utils.retry — RetryPolicy, RetryExecutor, CircuitBreaker."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import asyncio
from unittest.mock import AsyncMock

import pytest
from kairon_utils.retry import CircuitBreaker, RetryExecutor, RetryPolicy


class TestRetryPolicy:
    def test_defaults(self):
        p = RetryPolicy()
        assert p.max_attempts == 3
        assert p.backoff_multiplier == 2.0
        assert p.initial_delay == 1.0
        assert TimeoutError in p.retryable_errors
        assert ConnectionError in p.retryable_errors
        assert asyncio.TimeoutError in p.retryable_errors

    def test_custom_policy(self):
        p = RetryPolicy(max_attempts=5, backoff_multiplier=3.0, initial_delay=0.5)
        assert p.max_attempts == 5
        assert p.backoff_multiplier == 3.0
        assert p.initial_delay == 0.5


class TestRetryExecutor:
    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        """Operation succeeds on first attempt — no retry needed."""
        op = AsyncMock(return_value="ok")
        executor = RetryExecutor()
        result = await executor.execute_with_retry(op, "test-source")
        assert result == "ok"
        op.assert_awaited_once_with("test-source")

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        """Operation fails twice then succeeds."""
        op = AsyncMock(side_effect=[TimeoutError("timeout"), ConnectionError("refused"), "ok"])
        executor = RetryExecutor(RetryPolicy(max_attempts=3, initial_delay=0.01))
        result = await executor.execute_with_retry(op, "test-source")
        assert result == "ok"
        assert op.await_count == 3

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        """All retry attempts fail — raises ConnectionError."""
        op = AsyncMock(side_effect=TimeoutError("always timeout"))
        executor = RetryExecutor(RetryPolicy(max_attempts=3, initial_delay=0.01))
        with pytest.raises(ConnectionError, match="test-source after 3 attempts"):
            await executor.execute_with_retry(op, "test-source")
        assert op.await_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        """Non-retryable error raises immediately without retry."""
        op = AsyncMock(side_effect=ValueError("bad data"))
        executor = RetryExecutor(RetryPolicy(max_attempts=3, initial_delay=0.01))
        with pytest.raises(ConnectionError):
            await executor.execute_with_retry(op, "test-source")
        # Only called once — non-retryable breaks immediately
        assert op.await_count == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        """on_retry callback is invoked after each retry."""
        op = AsyncMock(side_effect=[TimeoutError("t1"), TimeoutError("t2"), "ok"])
        on_retry = AsyncMock()
        executor = RetryExecutor(RetryPolicy(max_attempts=3, initial_delay=0.01))
        result = await executor.execute_with_retry(op, "test-source", on_retry=on_retry)
        assert result == "ok"
        # Called twice (2 retries)
        assert on_retry.await_count == 2

    @pytest.mark.asyncio
    async def test_single_attempt_no_retry(self):
        """max_attempts=1 means no retry at all."""
        op = AsyncMock(side_effect=TimeoutError("fail"))
        executor = RetryExecutor(RetryPolicy(max_attempts=1))
        with pytest.raises(ConnectionError):
            await executor.execute_with_retry(op, "test-source")
        assert op.await_count == 1


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
        assert cb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_acquire_when_closed(self):
        cb = CircuitBreaker()
        assert await cb.acquire("src") is True

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
        for _ in range(3):
            await cb.record_failure("src")
        assert cb.state == "OPEN"
        assert await cb.acquire("src") is False

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=0.01)
        await cb.record_failure("src")
        await cb.record_failure("src")
        assert cb.state == "OPEN"

        # Wait for timeout to pass
        await asyncio.sleep(0.02)
        assert await cb.acquire("src") is True
        assert cb.state == "HALF_OPEN"

    @pytest.mark.asyncio
    async def test_closes_after_success_with_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, timeout_seconds=0.01)
        await cb.record_failure("src")
        await cb.record_failure("src")
        await asyncio.sleep(0.02)
        await cb.acquire("src")  # transitions to HALF_OPEN

        cb.record_success("src")
        assert cb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_record_success_resets_failures(self):
        cb = CircuitBreaker(failure_threshold=5)
        await cb.record_failure("src")
        cb.record_success("src")
        assert cb.failures == 0
        assert cb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_acquire_no_failure_time_returns_true(self):
        """When last_failure_time is None, acquire returns True even if OPEN."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=60)
        cb.state = "OPEN"
        cb.last_failure_time = None
        assert await cb.acquire("src") is True
