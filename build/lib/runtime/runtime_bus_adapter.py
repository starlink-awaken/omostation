"""runtime bus adapter — bridges runtime cron jobs to agora.bus facade.

Phase A.1: runtime.cron_service still uses its own ThreadPoolExecutor +
SQLite job store (sub-second latency, custom delivery). This adapter
adds the bus-facade scheduling layer for *new* consumers, without
modifying the legacy cron_service internals.
"""
from __future__ import annotations

import logging
from typing import Callable

from bus_foundation import schedule as bus_schedule

logger = logging.getLogger(__name__)


def register_cron_job(expr: str, callback: Callable) -> Callable:
    """Register a cron-style recurring task via agora.bus facade.

    Returns the original callback (so it can still be wired into cron_service).

    Usage (in runtime consumers or new code):
        from runtime.runtime_bus_adapter import register_cron_job
        register_cron_job("every 5m", my_task)
    """
    @bus_schedule(expr)
    def _wrapper() -> None:
        callback()

    return callback
