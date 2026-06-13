"""Test CroniterBackend — add_cron_job + publish raises."""

from __future__ import annotations

import pytest

from bus_foundation.backends.croniter import CroniterBackend
from bus_foundation.envelope import BusEnvelope


def test_add_cron_job_registers() -> None:
    backend = CroniterBackend()
    called = []

    def cb() -> None:
        called.append(1)

    backend.add_cron_job("job-1", "every 5m", cb)
    assert backend.remove_cron_job("job-1") is True


def test_publish_raises_not_implemented() -> None:
    backend = CroniterBackend()
    env = BusEnvelope(type="cron:test", source="x")
    with pytest.raises(NotImplementedError):
        backend.publish(env)
