"""E2E: omo_daemon.run_once publishes omo:audit:completed to bus-foundation.

Round 1 verification: the new `_publish_tick_event` hook in omo_daemon
must (a) not break the existing tick, (b) actually publish a bus-foundation
envelope that another consumer can receive.

This is a true cross-module e2e: omo → bus-foundation → test subscriber.
We don't spin up a real omo daemon; we call run_once() directly with
the same env vars the daemon would set.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest

# bus-foundation imports — these are the consumer side
from bus_foundation.backends.eventbus import EventBusBackend
from bus_foundation.envelope import BusEnvelope


def _wait_for(predicate: Callable[[], bool], timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def skip_agora_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the audit step doesn't try to talk to a real agora server."""
    # The audit code reads ENV_SKIP_AGORA; setting it disables agora HTTP.
    from omo.omo_health import ENV_SKIP_AGORA

    monkeypatch.setenv(ENV_SKIP_AGORA, "1")


@pytest.fixture
def bus_collector() -> tuple[EventBusBackend, list[BusEnvelope]]:
    """Provide a fresh in-process eventbus + collector list."""
    be = EventBusBackend()
    received: list[BusEnvelope] = []
    return be, received


def test_run_once_publishes_omo_audit_completed(
    skip_agora_env: None,
    monkeypatch: pytest.MonkeyPatch,
    bus_collector: tuple[EventBusBackend, list[BusEnvelope]],
) -> None:
    """run_once should emit omo:audit:completed (or :failed) on the bus."""
    be, received = bus_collector

    # Patch bus-foundation's global eventbus backend to use our collector
    # instance — so the publish from omo lands in our subscriber list.
    from bus_foundation import _backends

    original = _backends.get("eventbus")
    _backends["eventbus"] = be
    be.subscribe("omo:*", lambda env: received.append(env))
    try:
        from omo.omo_daemon import run_once

        result = run_once()
        # Tick may fail in this minimal env (no audit_report available),
        # but it MUST publish something to the bus.
        assert _wait_for(lambda: len(received) >= 1, timeout=3.0), (
            f"run_once did not publish within 3s. result={result}"
        )
        env = received[0]
        assert env.topic.startswith("omo:audit:"), f"unexpected topic: {env.topic!r}"
        assert env.topic in ("omo:audit:completed", "omo:audit:failed")
        # payload sanity
        assert "timestamp" in env.payload
        assert "audit_score" in env.payload
        assert "sync_diff_count" in env.payload
    finally:
        # Restore the original backend
        if original is not None:
            _backends["eventbus"] = original


def test_publish_helper_handles_missing_bus_foundation(
    skip_agora_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If bus-foundation is unavailable, _publish_tick_event must not raise."""
    # Block the import inside the publish helper
    import sys

    # The helper imports `from bus_foundation.facade import event as bus_event`.
    # We can simulate the import failure by setting facade to None in sys.modules.
    real_facade = sys.modules.pop("bus_foundation.facade", None)
    sys.modules["bus_foundation.facade"] = None  # type: ignore[assignment]
    try:
        from omo.omo_daemon import TickResult, _publish_tick_event

        result = TickResult(
            timestamp="2026-01-01T00:00:00+00:00",
            audit_score=99.0,
            audit_grade="A",
            sync_diff_count=0,
            history_appended=True,
        )
        # Should not raise even though bus_foundation.facade is "None".
        _publish_tick_event(result)
    finally:
        if real_facade is not None:
            sys.modules["bus_foundation.facade"] = real_facade


def test_publish_helper_handles_publish_exception(
    skip_agora_env: None,
) -> None:
    """If publish() raises, _publish_tick_event must swallow the error."""

    class _Boom:
        def publish(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated publish failure")

    import bus_foundation.facade.event as facade_event

    original_publish = facade_event.publish
    facade_event.publish = _Boom().publish  # type: ignore[assignment]
    try:
        from omo.omo_daemon import TickResult, _publish_tick_event

        result = TickResult(
            timestamp="2026-01-01T00:00:00+00:00",
            audit_score=99.0,
            audit_grade="A",
            sync_diff_count=0,
            history_appended=True,
        )
        # Must not raise.
        _publish_tick_event(result)
    finally:
        facade_event.publish = original_publish  # type: ignore[assignment]
