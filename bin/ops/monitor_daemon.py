#!/usr/bin/env python3
"""Continuous Monitoring Daemon for Service Gateway.

Runs health checks, auto-recovers services, records metrics, and alerts on SLO breaches.

Usage:
    python3 bin/ops/monitor_daemon.py [--interval 60] [--once]
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required", file=sys.stderr)
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"
METRICS_DIR = WORKSPACE / ".omo" / "_delivery" / "ops-metrics"
LOGS_DIR = WORKSPACE / "runtime" / "logs"
PIDS_DIR = WORKSPACE / "runtime" / "pids"

# Setup logging
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOGS_DIR / "monitor-daemon.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class ServiceMonitor:
    """Monitors and manages service health."""

    def __init__(self, check_interval: int = 60, auto_recover: bool = True):
        self.check_interval = check_interval
        self.auto_recover = auto_recover
        self.running = False
        self.metrics_history: list[dict] = []

    def load_services(self) -> list[dict]:
        """Load service manifest."""
        if not SERVICES_YAML.exists():
            return []
        content = SERVICES_YAML.read_text()
        docs = list(yaml.safe_load_all(content))
        for doc in docs:
            if isinstance(doc, dict) and "services" in doc:
                return doc.get("services", [])
        return []

    def check_service(self, svc: dict) -> dict[str, Any]:
        """Check health of a single service."""
        sid = svc.get("id", "")
        result = {
            "id": sid,
            "enabled": svc.get("enabled", False),
            "status": "unknown",
            "healthy": None,
        }

        if not result["enabled"]:
            result["status"] = "disabled"
            return result

        # Check PID file
        pid_file = PIDS_DIR / f"{sid}.pid"
        if not pid_file.exists():
            result["status"] = "down"
            result["healthy"] = False
            return result

        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            result["status"] = "running"
            result["healthy"] = True
            result["pid"] = pid
        except (ValueError, OSError, ProcessLookupError):
            result["status"] = "down"
            result["healthy"] = False
            pid_file.unlink(missing_ok=True)

        return result

    def recover_service(self, svc: dict) -> dict[str, Any]:
        """Attempt to recover a failed service."""
        sid = svc.get("id", "")
        result = {
            "id": sid,
            "recovered": False,
            "actions": [],
        }

        if not svc.get("enabled", False):
            result["actions"].append("Service disabled, skipping recovery")
            return result

        # Build command
        program = svc.get("program", {})
        entry = program.get("entrypoint", "")
        interpreter = program.get("interpreter", "python3")
        args = program.get("args", [])

        if interpreter == "uv":
            cmd = ["uv", "run", entry] + args
        elif interpreter == "stable-python3":
            cmd = [sys.executable, entry] + args
        elif interpreter.startswith("/"):
            cmd = [interpreter, entry] + args
        else:
            cmd = [interpreter, entry] + args

        try:
            log_file = LOGS_DIR / f"{sid}.log"
            with open(log_file, "a") as lf:
                proc = subprocess.Popen(
                    cmd,
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            pid_file = PIDS_DIR / f"{sid}.pid"
            pid_file.write_text(str(proc.pid))
            result["recovered"] = True
            result["pid"] = proc.pid
            result["actions"].append(f"Started with PID {proc.pid}")
            logger.info(f"Recovered {sid} with PID {proc.pid}")
        except Exception as e:
            result["actions"].append(f"Recovery failed: {e}")
            logger.error(f"Failed to recover {sid}: {e}")

        return result

    def run_health_checks(self) -> dict[str, Any]:
        """Run health checks on all enabled services."""
        services = self.load_services()
        timestamp = datetime.now(timezone.utc).isoformat()

        results = []
        healthy = 0
        unhealthy = 0
        disabled = 0

        for svc in services:
            check = self.check_service(svc)
            results.append(check)

            if check["healthy"]:
                healthy += 1
            elif check["status"] == "disabled":
                disabled += 1
            else:
                unhealthy += 1

            # Auto-recover if enabled and service is down
            if self.auto_recover and check["status"] == "down" and svc.get("enabled"):
                recovery = self.recover_service(svc)
                check["recovery"] = recovery

        summary = {
            "timestamp": timestamp,
            "total": len(services),
            "healthy": healthy,
            "unhealthy": unhealthy,
            "disabled": disabled,
            "availability": healthy / (healthy + unhealthy) if (healthy + unhealthy) > 0 else None,
            "services": results,
        }

        return summary

    def record_metrics(self, summary: dict[str, Any]) -> None:
        """Record metrics to history file."""
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        metrics_file = METRICS_DIR / f"{today}.jsonl"

        with open(metrics_file, "a") as f:
            f.write(json.dumps(summary, ensure_ascii=False) + "\n")

        self.metrics_history.append(summary)
        # Keep only last 100 entries in memory
        if len(self.metrics_history) > 100:
            self.metrics_history = self.metrics_history[-100:]

    def check_slo_breaches(self, summary: dict[str, Any]) -> list[dict]:
        """Check for SLO breaches."""
        alerts = []
        availability = summary.get("availability")

        if availability is not None and availability < 0.99:
            alerts.append({
                "severity": "warning",
                "slo": "availability",
                "actual": availability,
                "target": 0.99,
                "message": f"Availability {availability:.2%} below target 99%",
            })

        return alerts

    def run_once(self) -> dict[str, Any]:
        """Run a single monitoring cycle."""
        summary = self.run_health_checks()
        self.record_metrics(summary)
        alerts = self.check_slo_breaches(summary)

        if alerts:
            for alert in alerts:
                logger.warning(f"SLO breach: {alert['message']}")

        return summary

    def run(self) -> None:
        """Run the monitoring loop."""
        self.running = True
        logger.info(f"Monitor daemon started (interval={self.check_interval}s)")

        def signal_handler(signum, frame):
            logger.info("Received signal to stop")
            self.running = False

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        while self.running:
            try:
                summary = self.run_once()
                logger.info(
                    f"Health check: {summary['healthy']}/{summary['total']} healthy, "
                    f"availability={summary.get('availability', 'N/A')}"
                )
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")

            # Sleep in small increments to allow graceful shutdown
            for _ in range(self.check_interval):
                if not self.running:
                    break
                time.sleep(1)

        logger.info("Monitor daemon stopped")


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Service Gateway Monitor Daemon")
    parser.add_argument("--interval", type=int, default=60,
                        help="Check interval in seconds (default: 60)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--no-recover", action="store_true", help="Disable auto-recovery")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    monitor = ServiceMonitor(
        check_interval=args.interval,
        auto_recover=not args.no_recover,
    )

    if args.once:
        summary = monitor.run_once()
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            print(f"Health Check Summary:")
            print(f"  Total: {summary['total']}")
            print(f"  Healthy: {summary['healthy']}")
            print(f"  Unhealthy: {summary['unhealthy']}")
            print(f"  Disabled: {summary['disabled']}")
            avail = summary.get("availability")
            if avail is not None:
                print(f"  Availability: {avail:.2%}")
    else:
        monitor.run()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
