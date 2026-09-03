#!/usr/bin/env python3
"""Health check cron — periodically check services and auto-recover.

This script is designed to be run as a cron job every 5 minutes:
    */5 * * * * python3 bin/ops/health-check-cron.py

It checks all enabled services and attempts to recover any that are unhealthy.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required", file=sys.stderr)
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"
LOGS_DIR = WORKSPACE / "runtime" / "logs"
PIDS_DIR = WORKSPACE / "runtime" / "pids"
HEARTBEAT_FILE = WORKSPACE / ".omo" / "_delivery" / "health-check-cron" / "heartbeat.json"

# Setup logging
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOGS_DIR / "health-check-cron.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_services() -> list[dict]:
    """Load service manifest from services.yaml."""
    content = SERVICES_YAML.read_text(encoding="utf-8")
    docs = list(yaml.safe_load_all(content))
    for doc in docs:
        if isinstance(doc, dict) and "services" in doc:
            return doc.get("services", [])
    return []


def check_service_health(svc: dict) -> dict:
    """Check health of a single service."""
    liveness = svc.get("liveness", {})
    signal = liveness.get("signal", "")
    max_stale = liveness.get("max_stale_hours", 24)

    result = {"status": "unknown", "signal": signal}

    if not signal:
        return result

    # HTTP check
    if signal == "http" and liveness.get("endpoint"):
        import urllib.request
        try:
            req = urllib.request.Request(liveness["endpoint"], method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                result["status"] = "healthy" if resp.status == 200 else "unhealthy"
        except Exception:
            result["status"] = "unreachable"
        return result

    # PID check
    if signal == "pid":
        pid_file = PIDS_DIR / f"{svc['id']}.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                import os
                os.kill(pid, 0)
                result["status"] = "healthy"
            except (ValueError, OSError, ProcessLookupError):
                result["status"] = "stale"
                pid_file.unlink(missing_ok=True)
        else:
            result["status"] = "missing"
        return result

    # File-based check
    if "::" in signal:
        file_path, attr = signal.split("::", 1)
        fp = WORKSPACE / file_path
        if fp.exists():
            try:
                content = fp.read_text()
                data = yaml.safe_load(content)
                if isinstance(data, dict) and attr in data:
                    ts_str = data[attr]
                    if isinstance(ts_str, str):
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        now = datetime.now(UTC)
                        stale = (now - ts).total_seconds() / 3600
                        result["status"] = "healthy" if stale < max_stale else "stale"
                    else:
                        result["status"] = "healthy"
                else:
                    result["status"] = "stale"
            except Exception:
                result["status"] = "error"
        else:
            result["status"] = "missing"
    else:
        fp = WORKSPACE / signal
        if fp.exists():
            mtime = datetime.fromtimestamp(fp.stat().st_mtime, tz=UTC)
            now = datetime.now(UTC)
            stale = (now - mtime).total_seconds() / 3600
            result["status"] = "healthy" if stale < max_stale else "stale"
        else:
            result["status"] = "missing"

    return result


def recover_service(svc: dict) -> bool:
    """Attempt to recover a failed service."""
    sid = svc.get("id", "")
    program = svc.get("program", {})
    entry = program.get("entrypoint", "")
    interpreter = program.get("interpreter", "python3")
    args = program.get("args", [])

    if interpreter == "uv":
        cmd = ["uv", "run", entry] + args
    elif interpreter == "stable-python3":
        import sys
        cmd = [sys.executable, entry] + args
    elif interpreter.startswith("/"):
        cmd = [interpreter, entry] + args
    else:
        cmd = [interpreter, entry] + args

    try:
        log_file = LOGS_DIR / f"{sid}.log"
        with open(log_file, "a") as lf:
            proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, start_new_session=True)
        (PIDS_DIR / f"{sid}.pid").write_text(str(proc.pid))
        logger.info(f"Recovered {sid} (pid={proc.pid})")
        return True
    except Exception as e:
        logger.error(f"Failed to recover {sid}: {e}")
        return False


def main() -> int:
    """Main entry point."""
    services = load_services()
    enabled = [s for s in services if s.get("enabled", False)]

    healthy = 0
    recovered = 0
    failed = 0
    skipped = 0

    for svc in enabled:
        sid = svc.get("id", "")
        health = check_service_health(svc)

        if health["status"] == "healthy":
            healthy += 1
            continue

        # Try to recover unhealthy services
        if health["status"] in ("stale", "missing", "unreachable"):
            if recover_service(svc):
                recovered += 1
            else:
                failed += 1
        else:
            skipped += 1

    # Write heartbeat
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    heartbeat = {
        "timestamp": datetime.now(UTC).isoformat(),
        "total": len(enabled),
        "healthy": healthy,
        "recovered": recovered,
        "failed": failed,
        "skipped": skipped,
    }
    HEARTBEAT_FILE.write_text(json.dumps(heartbeat, indent=2))

    logger.info(f"Health check complete: {healthy} healthy, {recovered} recovered, {failed} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
