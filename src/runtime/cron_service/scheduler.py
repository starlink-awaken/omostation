from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import config, db
from .health_scan import run_scan_if_due

logger = logging.getLogger("cron-service.scheduler")


class CronScheduler:
    """Thread-based cron scheduler.

    Uses a daemon thread to tick at TICK_INTERVAL. Avoids asyncio
    task lifecycle bugs (CancelledError, task GC, sleep deadlock).
    """

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        self.start_time: float = 0.0
        self.last_tick_time: float = 0.0
        self.tick_count: int = 0

    def start(self) -> None:
        """Start the scheduler thread (non-blocking)."""
        if self._running:
            return
        self._running = True
        self.start_time = time.time()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Cron scheduler started (thread, tick=%ds)", config.TICK_INTERVAL)

    def stop(self) -> None:
        """Stop the scheduler thread."""
        self._running = False
        if self._executor:
            self._executor.shutdown(wait=False)
        logger.info("Cron scheduler stopped")

    def _loop(self) -> None:
        """Main scheduler loop in a daemon thread."""
        while self._running:
            try:
                self._tick()
            except Exception as e:
                logger.error("Scheduler tick error: %s", e, exc_info=True)
            time.sleep(config.TICK_INTERVAL)

    def _tick(self) -> None:
        """Check for due jobs and run them. Also triggers periodic health scans."""
        self.last_tick_time = time.time()
        self.tick_count += 1
        jobs = db.list_jobs(enabled_only=True)

        for job in jobs:
            last = job.last_run_at
            if _is_due(job.id, job.schedule, last, created_at=job.created_at):
                _run_job_sync(job.id, self._executor)

        if run_scan_if_due is not None:
            try:
                run_scan_if_due()
            except Exception as e:
                logger.error("Health scan error: %s", e, exc_info=True)

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def force_tick(self) -> int:
        jobs = db.list_jobs(enabled_only=True)
        due = 0
        for job in jobs:
            last = job.last_run_at
            if _is_due(job.id, job.schedule, last, created_at=job.created_at):
                due += 1
        return due


# ── Standalone helpers ────────────────────────────────────────────


def _is_due(job_id: str, schedule: str, last_run, *, created_at) -> bool:
    if not schedule:
        return False
    if last_run is None:
        return True
    interval = _parse_interval(schedule)
    if interval is None:
        return False
    if hasattr(last_run, "timestamp"):
        last_ts = last_run.timestamp()
    else:
        last_ts = float(last_run)
    return (time.time() - last_ts) >= interval


def _parse_interval(schedule: str) -> float | None:
    s = schedule.strip().lower()
    if s.startswith("every "):
        rest = s[6:].strip()
        parts = rest.split()
        if len(parts) == 2:
            try:
                n = float(parts[0])
                unit = parts[1]
                if "min" in unit:
                    return n * 60
                if "hour" in unit or "hr" in unit:
                    return n * 3600
                if "sec" in unit or "s" in unit:
                    return n
                return n * 60
            except ValueError:
                return None
    return None


def _run_job_sync(job_id: str, executor: ThreadPoolExecutor) -> None:
    from .db import get_job, update_job, JobUpdate

    job = get_job(job_id)
    if not job or not job.script:
        return
    logger.info("Running job %s (script=%s)", job_id, job.script)
    import subprocess

    try:
        result = subprocess.run(
            job.script,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        status = "ok" if result.returncode == 0 else "error"
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        update_job(
            job_id, JobUpdate(last_status=status, last_output=output.strip()[:500])
        )
        if status == "error":
            logger.warning("Job %s failed: %s", job_id, output.strip()[:200])
    except subprocess.TimeoutExpired:
        logger.warning("Job %s timed out (>120s)", job_id)
        update_job(
            job_id, JobUpdate(last_status="timeout", last_output="timed out (>120s)")
        )
    except Exception as e:
        logger.error("Job %s error: %s", job_id, e)
        update_job(job_id, JobUpdate(last_status="error", last_output=str(e)[:500]))
