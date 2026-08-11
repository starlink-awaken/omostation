from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

import anyio
import pytest


class RecordingEngine:
    def __init__(self) -> None:
        self.calls = 0

    async def reconcile_many(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        del args, kwargs
        self.calls += 1
        return {}


@pytest.mark.asyncio
async def test_reconcile_loop_consumes_wait_failure_and_can_restart_stop_repeatedly() -> None:
    from omlxc.autonomy import ReconcileLoop

    engine = RecordingEngine()
    wait_failed = anyio.Event()
    block_restart = anyio.Event()
    errors: list[str] = []
    waits = 0

    async def wait_next(_seconds: float) -> None:
        nonlocal waits
        waits += 1
        if waits == 1:
            wait_failed.set()
            raise RuntimeError("pacer failed")
        await block_restart.wait()

    loop = ReconcileLoop(
        engine,  # type: ignore[arg-type]
        targets_provider=lambda: _async_value(()),
        memory_probe=lambda: _async_value(None),
        monotonic_clock=lambda: 1.0,
        interval_seconds=1.0,
        wait_next=wait_next,
        error_sink=errors.append,
    )
    await loop.start()
    await wait_failed.wait()
    for _ in range(20):
        if not loop.running:
            break
        await asyncio.sleep(0)
    assert not loop.running
    assert errors == ["RuntimeError"]
    await loop.stop()
    await loop.stop()

    await loop.start()
    await asyncio.sleep(0)
    assert loop.running
    await loop.stop()
    await loop.stop()
    assert not loop.running
    assert engine.calls == 2


@pytest.mark.asyncio
async def test_reconcile_loop_isolates_error_sink_failures_without_busy_loop() -> None:
    from omlxc.autonomy import ReconcileLoop

    provider_calls = 0
    wait_calls = 0
    sink_calls = 0

    async def failing_provider() -> tuple[Any, ...]:
        nonlocal provider_calls
        provider_calls += 1
        raise RuntimeError("provider failed")

    async def failing_wait(_seconds: float) -> None:
        nonlocal wait_calls
        wait_calls += 1
        raise RuntimeError("pacer failed")

    def failing_sink(_error: str) -> None:
        nonlocal sink_calls
        sink_calls += 1
        raise RuntimeError("sink failed")

    loop = ReconcileLoop(
        RecordingEngine(),  # type: ignore[arg-type]
        targets_provider=failing_provider,  # type: ignore[arg-type]
        memory_probe=lambda: _async_value(None),
        monotonic_clock=lambda: 1.0,
        interval_seconds=1.0,
        wait_next=failing_wait,
        error_sink=failing_sink,
    )
    await loop.start()
    for _ in range(10):
        await asyncio.sleep(0)
        if not loop.running:
            break
    try:
        assert provider_calls == 1
        assert wait_calls == 1
        assert sink_calls == 2
        assert not loop.running
        await loop.stop()
        await loop.stop()
        await loop.start()
        for _ in range(10):
            await asyncio.sleep(0)
            if not loop.running:
                break
        await loop.stop()
        assert provider_calls == 2
        assert wait_calls == 2
        assert sink_calls == 4
    finally:
        with suppress(RuntimeError):
            await loop.stop()


async def _async_value(value: Any) -> Any:
    return value


@pytest.mark.asyncio
async def test_cancelled_half_open_call_can_release_probe_capacity() -> None:
    from omlxc.health import CircuitBreaker, CircuitConfig, CircuitState, FailureClass

    now = 10.0
    breaker = CircuitBreaker(
        CircuitConfig(failure_threshold=1, cooldown_seconds=1.0, half_open_probes=1),
        monotonic_clock=lambda: now,
    )
    initial = await breaker.acquire()
    await breaker.record_failure(initial, FailureClass.RETRYABLE)
    now = 11.0
    acquired = anyio.Event()
    hold = anyio.Event()

    async def cancelled_call() -> None:
        permit = await breaker.acquire()
        acquired.set()
        try:
            await hold.wait()
        finally:
            await breaker.release(permit)

    task = asyncio.create_task(cancelled_call())
    await acquired.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert breaker.state is CircuitState.HALF_OPEN
    replacement = await breaker.acquire()
    await breaker.record_success(replacement)
    assert breaker.state is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_cancel_scope_cannot_interrupt_probe_release_or_lease_cleanup() -> None:
    from omlxc.health import CircuitBreaker, CircuitConfig, CircuitOpenError, FailureClass

    now = 10.0
    breaker = CircuitBreaker(
        CircuitConfig(failure_threshold=1, cooldown_seconds=1.0, half_open_probes=1),
        monotonic_clock=lambda: now,
    )
    initial = await breaker.acquire()
    await breaker.record_failure(initial, FailureClass.RETRYABLE)
    now = 11.0

    permit = await breaker.acquire()
    with anyio.CancelScope() as cancelled:
        cancelled.cancel()
        await breaker.release(permit)
    replacement = await breaker.acquire()
    await breaker.release(replacement)

    with anyio.CancelScope() as lease_cancelled:
        async with breaker.lease():
            lease_cancelled.cancel()
            await anyio.sleep_forever()
    assert lease_cancelled.cancel_called
    final_probe = await breaker.acquire()
    with pytest.raises(CircuitOpenError):
        await breaker.acquire()
    await breaker.record_success(final_probe)
