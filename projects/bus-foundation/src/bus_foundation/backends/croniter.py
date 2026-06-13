"""CroniterBackend — cron-style scheduling as a bus backend.

Phase A.1: thin wrapper that exposes cron-style scheduling as a bus backend.
RETRY: passes through to underlying scheduler.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from bus_foundation.envelope import BusEnvelope

logger = logging.getLogger(__name__)


class CroniterBackend:
    """Schedules recurring tasks via croniter (cron syntax)."""

    name = "croniter"

    def __init__(self):
        self._jobs: dict[str, tuple[str, Callable, float]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def is_available(self) -> bool:
        return True

    def publish(self, envelope: BusEnvelope) -> str:
        """Publish is not the primary use of this backend; raises."""
        raise NotImplementedError("CroniterBackend does not support publish() — use add_cron_job()")

    def add_cron_job(self, job_id: str, cron_expr: str, callback: Callable) -> None:
        with self._lock:
            self._jobs[job_id] = (cron_expr, callback, 0.0)

    def remove_cron_job(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                return True
            return False

    def subscribe(self, pattern: str, callback: Callable) -> str:
        """For cron backend, subscribe = add_cron_job with cron expression."""
        job_id = f"cron-{len(self._jobs)}"
        self.add_cron_job(job_id, pattern, callback)
        return job_id

    def unsubscribe(self, sub_id: str) -> bool:
        return self.remove_cron_job(sub_id)

    def start(self) -> None:
        """Start the scheduler thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run_loop(self) -> None:
        while self._running:
            with self._lock:
                jobs_snapshot = list(self._jobs.items())
            now = time.time()
            for job_id, (cron_expr, callback, last_run) in jobs_snapshot:
                if self._is_due(cron_expr, last_run, now):
                    try:
                        callback()
                    except Exception as e:
                        logger.error("croniter_callback_error", job_id, e)
                    with self._lock:
                        if job_id in self._jobs:
                            expr, cb, _ = self._jobs[job_id]
                            self._jobs[job_id] = (expr, cb, now)
            time.sleep(30)

    @staticmethod
    def _is_due(cron_expr: str, last_run: float, now: float) -> bool:
        expr = cron_expr.strip().lower()
        if expr.startswith("every "):
            remainder = expr[6:].strip()
            if remainder.endswith("m") or "min" in remainder:
                num_str = remainder.split()[0].rstrip("ms")
                try:
                    interval = int(num_str) * 60
                except ValueError:
                    return False
            elif remainder.endswith("h") or "hour" in remainder:
                num_str = remainder.split()[0].rstrip("hs")
                try:
                    interval = int(num_str) * 3600
                except ValueError:
                    return False
            else:
                return False
            return (now - last_run) >= interval
        return False
