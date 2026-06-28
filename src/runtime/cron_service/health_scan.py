"""
Health scan integration — MatrixScheduler absorbed into cron-service (Route B).

Cron-service runs as a persistent launchd daemon with KeepAlive. It periodically
scans system service health and writes to .omo/state/system_health.yaml,
replacing the standalone MatrixScheduler daemon loop.

Usage (via cron_service.server lifespan):
    from .health_scan import health_scan_once
    health_scan_once()
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger("cron-service.health-scan")

# How often to run a full health scan (in seconds)
HEALTH_SCAN_INTERVAL = 900  # 15 minutes

# Track last scan time for periodic scheduling within CronScheduler ticks
_last_scan_ts: float = 0.0


def health_scan_once(force_write: bool = True) -> dict | None:
    """Run a single health scan and write results to system_health.yaml.

    Args:
        force_write: Always write to system_health.yaml even if no state
            transition is detected. Bypasses the old HealthPulse gate.

    Returns:
        The scan result dict, or None if the scan failed.
    """
    from runtime.scheduler import MatrixScheduler

    sched = MatrixScheduler()
    sched._force_write = force_write  # noqa: SLF001 — Route B contract

    # Inject RUNTIME_HOME if not set (needed by MatrixScheduler internals)
    if not Path.home().joinpath("runtime").is_dir():
        logger.warning("RUNTIME_HOME not found at ~/runtime/ — scan may be partial")

    try:
        sched.scan_once()
        logger.info(
            "Health scan completed (services=%d, last_scan=%.0f)",
            len(sched.state.get("services", {})),
            sched.state.get("last_scan", 0),
        )
        return sched.state
    except Exception:  # noqa: BLE001  # defensive fallback
        logger.exception("Health scan failed")
        return None


def should_scan(now: float | None = None) -> bool:
    """Check if enough time has passed since the last scan.

    Returns True if HEALTH_SCAN_INTERVAL seconds have elapsed since the
    last scan. Used by CronScheduler._tick() to determine when to scan.

    Args:
        now: Current timestamp (time.time()). Defaults to time.time().
    """
    global _last_scan_ts
    now = now or time.time()
    return (now - _last_scan_ts) >= HEALTH_SCAN_INTERVAL


def mark_scanned(now: float | None = None) -> None:
    """Record that a scan was just performed.

    Args:
        now: Current timestamp. Defaults to time.time().
    """
    global _last_scan_ts
    _last_scan_ts = now or time.time()


def run_scan_if_due(force: bool = False) -> bool:
    """Run a health scan if due (or if forced).

    Args:
        force: If True, always run the scan regardless of interval.

    Returns:
        True if a scan was run, False if it was skipped (not due).
    """
    if force or should_scan():
        health_scan_once(force_write=True)
        mark_scanned()
        return True
    return False
