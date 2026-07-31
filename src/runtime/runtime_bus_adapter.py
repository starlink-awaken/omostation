"""runtime bus adapter — bridges runtime cron jobs to agora.bus facade.

Phase A.1: runtime.cron_service still uses its own ThreadPoolExecutor +
SQLite job store (sub-second latency, custom delivery). This adapter adds
the bus-facade scheduling layer for *new* consumers, without modifying
the legacy cron_service internals.

R94: wraps callback in bus-foundation trace context so each cron fire
gets a span with trace_id.
"""

from __future__ import annotations

import logging
from typing import Callable

from bus_foundation.facade import control as bus_control

logger = logging.getLogger(__name__)


def register_cron_job(expr: str, callback: Callable) -> Callable:
    """Register a cron-style recurring task via agora.bus facade.

    Returns the original callback (so it can still be wired into cron_service).

    Usage (in runtime consumers or new code):
        from runtime.runtime_bus_adapter import register_cron_job
        register_cron_job("every 5m", my_task)
    """

    def _traced() -> None:
        try:
            from bus_foundation.observability import trace

            with trace(f"cron:{expr}", backend="croniter"):
                callback()
        except ImportError:
            callback()

    def _wrapper() -> None:
        _traced()

    # 空/非法 expr: bus_foundation parse_schedule 可能抛 ValueError,
    # register_cron_job 不应抛 (test_empty_expr: bus_foundation 决定是否拒绝)
    try:
        bus_control.schedule_callback(expr)(_wrapper)
    except Exception as exc:  # noqa: BLE001
        logger.debug("runtime_cron_register_skipped expr=%r: %s", expr, exc)

    return callback
