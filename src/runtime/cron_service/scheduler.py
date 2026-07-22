from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

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
                self._executor.submit(_run_job_sync, job.id)

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

    s = schedule.strip().lower()

    # "every X" → interval 判断
    if s.startswith("every "):
        interval = _parse_interval(schedule)
        if interval is None:
            return False
        if hasattr(last_run, "timestamp"):
            last_ts = last_run.timestamp()
        else:
            last_ts = float(last_run)
        return (time.time() - last_ts) >= interval

    # cron 表达式 → croniter 精确计算下次触发时间
    ts = _next_cron_ts(schedule, last_run)
    return ts is not None and time.time() >= ts


def _next_cron_ts(schedule: str, after: datetime | float) -> float | None:
    """用 croniter 精确计算 cron 表达式在 after 之后的首次触发时间戳。"""
    from croniter import croniter

    try:
        if isinstance(after, datetime):
            if after.tzinfo is not None:
                base = after.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                base = after
        else:
            base = datetime.fromtimestamp(after, tz=timezone.utc).replace(tzinfo=None)
        cron = croniter(schedule, base)
        next_dt = cron.get_next(datetime)
        return next_dt.replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        logger.warning(
            "croniter failed for schedule=%r, last_run=%r",
            schedule,
            after,
            exc_info=True,
        )
        return None


def _parse_interval(schedule: str) -> float | None:
    """解析 'every Xm'/'every Xh'/'every Xs'(单段) 或 'every X unit'(两段) → 秒数。

    单段格式 (ScheduleConfig.expression 默认 'every 5m') 此前未被支持,
    导致默认 schedule 的 job 永不触发 (interval=None→_is_due False)。此处补齐。
    """
    s = schedule.strip().lower()
    if not s.startswith("every "):
        return None
    rest = s[6:].strip()
    parts = rest.split()

    def _seconds(n: float, unit: str) -> float | None:
        if "min" in unit or unit == "m":
            return n * 60
        if "hour" in unit or "hr" in unit or unit == "h":
            return n * 3600
        if "sec" in unit or unit == "s":
            return n
        return None

    # 两段格式: "5 min" / "2 hours" / "10 s"
    if len(parts) == 2:
        try:
            n = float(parts[0])
        except ValueError:
            return None
        return _seconds(n, parts[1])
    # 单段格式: "5m" / "2h" / "30s" — 分离数字前缀与单位后缀
    if len(parts) == 1:
        token = parts[0]
        i = 0
        while i < len(token) and (token[i].isdigit() or token[i] == "."):
            i += 1
        if i == 0:
            return None
        try:
            n = float(token[:i])
        except ValueError:
            return None
        unit = token[i:]
        return _seconds(n, unit) if unit else None
    return None


def _run_job_sync(job_id: str) -> None:
    from pathlib import Path
    from .config import SCRIPTS_DIR
    from .db import get_job, record_run

    job = get_job(job_id)
    if not job or not job.script:
        return

    # 裸文件名 → 从 SCRIPTS_DIR 补全
    script = job.script
    if "/" not in script:
        candidate = Path(SCRIPTS_DIR).expanduser() / script
        if candidate.exists():
            script = str(candidate)
            logger.debug("Resolved script %s → %s", job.script, script)
        else:
            logger.warning(
                "Script %s not found in SCRIPTS_DIR=%s", job.script, SCRIPTS_DIR
            )

    logger.info("Running job %s (script=%s)", job_id, script)
    import subprocess

    try:
        result = subprocess.run(
            script,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        status = "ok" if result.returncode == 0 else "error"
        record_run(job_id, status, result.stdout or "", result.stderr or "")
        if status == "error":
            logger.warning(
                "Job %s failed (exit=%d): %s",
                job_id,
                result.returncode,
                (result.stderr or "")[:200],
            )
    except subprocess.TimeoutExpired:
        logger.warning("Job %s timed out (>120s)", job_id)
        record_run(job_id, "timeout", "", "Timed out after 120s")
    except Exception as e:
        logger.error("Job %s error: %s", job_id, e)
        record_run(job_id, "error", "", str(e)[:500])
