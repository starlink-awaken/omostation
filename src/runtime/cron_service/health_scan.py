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
import subprocess
import time
from pathlib import Path

logger = logging.getLogger("cron-service.health-scan")

# How often to run a full health scan (in seconds)
HEALTH_SCAN_INTERVAL = 60  # 1 minute — reduced from 900s (15min) for faster convergence

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
    from runtime.scheduler import MatrixScheduler, OMO_STATE_FILE

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
        # Probe non-HTTP daemons
        _probe_daemons(sched.state)
        # Bug B 治本: probe 填的 health_check 落盘 (scan_once 已写过无 health_check 快照)
        _dump_probed_health(sched.state, OMO_STATE_FILE)
        return sched.state
    except Exception:  # noqa: BLE001  # defensive fallback
        logger.exception("Health scan failed")
        return None


def _probe_daemons(state: dict) -> None:
    """Fill health_check for daemons without HTTP endpoint via process probe."""
    services = state.get("services", {})
    probe_script = Path(__file__).parent.parent / "health" / "agora_gateway_probe.py"
    if not probe_script.exists():
        return
    for name, svc in services.items():
        if svc.get("type") != "daemon" or svc.get("health_check"):
            continue
        try:
            result = subprocess.run(
                ["python3", str(probe_script)],
                capture_output=True,
                text=True,
                timeout=10, check=False)
            if result.returncode == 0:
                svc["health_check"] = "healthy (probe)"
            elif result.returncode == 2:
                # degraded: PID 活但部分后端无心跳 (agora_gateway_probe 三态)
                svc["health_check"] = "degraded (probe)"
                svc.setdefault("runtime", {})["degraded_reason"] = (
                    result.stdout.strip() or "probe degraded"
                )
            else:
                svc["health_check"] = "unhealthy (probe)"
                svc.setdefault("runtime", {})["degraded_reason"] = (
                    result.stdout.strip() or "probe failed"
                )
        except subprocess.TimeoutExpired:
            svc["health_check"] = "stale (probe timeout)"


def _dump_probed_health(state: dict, omo_state_file: Path) -> None:
    """Bug B 治本: 把 _probe_daemons 填的 health_check 落盘到 system_health.yaml.

    scan_once() 在 _probe_daemons 之前已写盘(无 health_check), probe 填完内存后
    若不重写, health_check 永不落盘 (agora-gateway health_check 缺失→假绿灯根因).
    """
    import yaml  # noqa: PLC0415

    try:
        from runtime.scheduler import validate_runtime_health_snapshot

        validate_runtime_health_snapshot(state)
        omo_state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(omo_state_file, "w") as f:
            yaml.safe_dump(state, f, default_flow_style=False)
    except Exception:  # noqa: BLE001
        logger.exception("dump probed health to %s failed", omo_state_file)


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
