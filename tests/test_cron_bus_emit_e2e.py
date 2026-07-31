"""E2E: runtime.cron_service.scheduler publishes runtime:cron:fired.

Round 4 verification: when _run_job() finishes, _bus_emit_cron_fired
must (a) publish on bus-foundation, (b) use the correct topic per status,
(c) never raise.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest


def _wait_for(predicate: Callable[[], bool], timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_cron_emit_uses_bus_foundation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful cron run should emit runtime:cron:fired on the bus."""
    from bus_foundation.backends.eventbus import EventBusBackend
    from bus_foundation import _backends

    be = EventBusBackend()
    received: list = []
    be.subscribe("runtime:*", lambda env: received.append(env))
    monkeypatch.setitem(_backends, "eventbus", be)

    from runtime.cron_service.scheduler import _bus_emit_cron_fired

    _bus_emit_cron_fired(
        job_id="job-1",
        name="nightly-cleanup",
        status="ok",
        error=None,
        output="cleaned 42 files",
    )
    assert _wait_for(lambda: len(received) >= 1)
    env = received[0]
    assert env.topic == "runtime:cron:fired"
    assert env.payload["job_id"] == "job-1"
    assert env.payload["status"] == "ok"
    assert "nightly-cleanup" in env.payload["name"]


def test_cron_emit_failed_status() -> None:
    """A failed run should emit runtime:cron:failed."""
    from runtime.cron_service.scheduler import _bus_emit_cron_fired

    # Patch bus_event directly
    from bus_foundation.facade import event as bus_event

    captured: list = []
    original_publish = bus_event.publish

    def _spy(*args, **kwargs):
        captured.append((args, kwargs))

    bus_event.publish = _spy  # type: ignore[assignment]
    try:
        _bus_emit_cron_fired(
            job_id="job-2",
            name="bad-job",
            status="error",
            error="simulated failure",
            output="",
        )
    finally:
        bus_event.publish = original_publish  # type: ignore[assignment]

    assert len(captured) == 1
    args, kwargs = captured[0]
    assert kwargs["topic"] == "runtime:cron:failed"
    assert kwargs["payload"]["status"] == "error"


def test_cron_emit_survives_missing_bus_foundation() -> None:
    """If bus-foundation is not installed, _bus_emit_cron_fired must be silent."""
    import sys

    saved = sys.modules.pop("bus_foundation.facade", None)
    sys.modules["bus_foundation.facade"] = None  # type: ignore[assignment]
    try:
        from runtime.cron_service.scheduler import _bus_emit_cron_fired

        # Must not raise
        _bus_emit_cron_fired(job_id="x", name="x", status="ok", error=None, output="")
    finally:
        if saved is not None:
            sys.modules["bus_foundation.facade"] = saved


def test_cron_emit_survives_publish_exception() -> None:
    """If bus_event.publish() raises, _bus_emit_cron_fired must swallow."""
    from bus_foundation.facade import event as bus_event

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated")

    original = bus_event.publish
    bus_event.publish = _boom  # type: ignore[assignment]
    try:
        from runtime.cron_service.scheduler import _bus_emit_cron_fired

        # Must not raise
        _bus_emit_cron_fired(job_id="x", name="x", status="ok", error=None, output="")
    finally:
        bus_event.publish = original  # type: ignore[assignment]
