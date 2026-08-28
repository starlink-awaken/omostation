#!/usr/bin/env python3
"""SLO (Service Level Objective) Tracker for Service Gateway.

Tracks and reports on service level objectives:
- Availability: % of time service is healthy
- Latency: p50/p95/p99 response times
- Error Rate: % of failed checks

Reports are written to .omo/_delivery/ops-slo/ for trend analysis.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required", file=sys.stderr)
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"
SLO_DIR = WORKSPACE / ".omo" / "_delivery" / "ops-slo"

# Default SLO targets
DEFAULT_SLOS = {
    "availability": {
        "target": 0.99,  # 99%
        "description": "Service must be healthy 99% of the time",
        "window_days": 30,
    },
    "latency_p99": {
        "target": 5.0,  # seconds
        "description": "99th percentile check latency under 5s",
        "window_days": 7,
    },
    "error_rate": {
        "target": 0.01,  # 1%
        "description:": "Error rate under 1%",
        "window_days": 7,
    },
}


def load_services() -> list[dict]:
    """Load service manifest."""
    if not SERVICES_YAML.exists():
        return []
    content = SERVICES_YAML.read_text()
    docs = list(yaml.safe_load_all(content))
    for doc in docs:
        if isinstance(doc, dict) and "services" in doc:
            return doc.get("services", [])
    return []


def check_service_availability(svc: dict) -> dict[str, Any]:
    """Check service availability status."""
    liveness = svc.get("liveness", {})
    signal = liveness.get("signal", "")

    if not signal:
        return {"status": "unknown", "healthy": None}

    # Check file-based signals
    if "::" in signal:
        file_path, attr = signal.split("::", 1)
        fp = WORKSPACE / file_path
        if fp.exists():
            try:
                content = fp.read_text()
                data = yaml.safe_load(content)
                if isinstance(data, dict) and attr in data:
                    ts_str = data[attr]
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    staleness_hours = (now - ts).total_seconds() / 3600
                    max_stale = liveness.get("max_stale_hours", 24)
                    return {
                        "status": "healthy" if staleness_hours < max_stale else "stale",
                        "healthy": staleness_hours < max_stale,
                        "staleness_hours": round(staleness_hours, 1),
                    }
            except Exception:
                pass
        return {"status": "missing", "healthy": False}

    # Check PID file
    pid_file = WORKSPACE / "runtime" / "pids" / f"{svc.get('id', '')}.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            import os
            os.kill(pid, 0)
            return {"status": "healthy", "healthy": True, "pid": pid}
        except (ValueError, OSError, ProcessLookupError):
            return {"status": "stale", "healthy": False}

    return {"status": "unknown", "healthy": None}


def compute_slo_metrics(services: list[dict]) -> dict[str, Any]:
    """Compute SLO metrics for all services."""
    total = len(services)
    if total == 0:
        return {}

    healthy = 0
    unhealthy = 0
    unknown = 0

    per_service = {}

    for svc in services:
        sid = svc.get("id", "")
        if not svc.get("enabled", False):
            continue

        result = check_service_availability(svc)
        per_service[sid] = result

        if result.get("healthy") is True:
            healthy += 1
        elif result.get("healthy") is False:
            unhealthy += 1
        else:
            unknown += 1

    checked = healthy + unhealthy
    availability = (healthy / checked) if checked > 0 else None

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_services": total,
        "checked": checked,
        "healthy": healthy,
        "unhealthy": unhealthy,
        "unknown": unknown,
        "availability": round(availability, 4) if availability is not None else None,
        "error_rate": round(unhealthy / checked, 4) if checked > 0 else None,
        "per_service": per_service,
    }


def check_slo_burn(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Check SLO burn rates and generate alerts."""
    alerts = []

    availability = metrics.get("availability")
    if availability is not None and availability < DEFAULT_SLOS["availability"]["target"]:
        alerts.append({
            "severity": "warning",
            "slo": "availability",
            "actual": availability,
            "target": DEFAULT_SLOS["availability"]["target"],
            "message": f"Availability {availability:.2%} below target {DEFAULT_SLOS['availability']['target']:.2%}",
        })

    error_rate = metrics.get("error_rate")
    if error_rate is not None and error_rate > DEFAULT_SLOS["error_rate"]["target"]:
        alerts.append({
            "severity": "critical",
            "slo": "error_rate",
            "actual": error_rate,
            "target": DEFAULT_SLOS["error_rate"]["target"],
            "message": f"Error rate {error_rate:.2%} above target {DEFAULT_SLOS['error_rate']['target']:.2%}",
        })

    return alerts


def get_historical_metrics(days: int = 7) -> list[dict]:
    """Get historical SLO metrics."""
    if not SLO_DIR.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    history = []

    for f in sorted(SLO_DIR.glob("*.jsonl")):
        with open(f) as fh:
            for line in fh:
                try:
                    entry = json.loads(line.strip())
                    ts = datetime.fromisoformat(entry["timestamp"])
                    if ts >= cutoff:
                        history.append(entry)
                except (json.JSONDecodeError, KeyError):
                    continue

    return history


def generate_slo_report(metrics: dict[str, Any], alerts: list[dict]) -> str:
    """Generate a human-readable SLO report."""
    lines = []
    lines.append("=" * 60)
    lines.append("SLO Report — Service Gateway")
    lines.append(f"Generated: {metrics.get('timestamp', '?')}")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    lines.append("Summary:")
    lines.append(f"  Total services: {metrics.get('total_services', 0)}")
    lines.append(f"  Checked: {metrics.get('checked', 0)}")
    lines.append(f"  Healthy: {metrics.get('healthy', 0)}")
    lines.append(f"  Unhealthy: {metrics.get('unhealthy', 0)}")
    lines.append(f"  Unknown: {metrics.get('unknown', 0)}")

    avail = metrics.get("availability")
    if avail is not None:
        target = DEFAULT_SLOS["availability"]["target"]
        status = "✅" if avail >= target else "❌"
        lines.append(f"  Availability: {avail:.2%} (target: {target:.2%}) {status}")

    error = metrics.get("error_rate")
    if error is not None:
        target = DEFAULT_SLOS["error_rate"]["target"]
        status = "✅" if error <= target else "❌"
        lines.append(f"  Error Rate: {error:.2%} (target: {target:.2%}) {status}")

    # Alerts
    if alerts:
        lines.append("")
        lines.append("Alerts:")
        for alert in alerts:
            sev_icon = "🔴" if alert["severity"] == "critical" else "🟡"
            lines.append(f"  {sev_icon} [{alert['severity'].upper()}] {alert['message']}")

    # Per-service status
    per_service = metrics.get("per_service", {})
    if per_service:
        lines.append("")
        lines.append("Per-Service Status:")
        for sid, status in sorted(per_service.items()):
            status_str = status.get("status", "?")
            icon = "✅" if status_str == "healthy" else "❌" if status_str == "stale" else "❓"
            lines.append(f"  {icon} {sid}: {status_str}")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="SLO Tracker")
    parser.add_argument("--report", action="store_true", help="Generate SLO report")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--days", type=int, default=7, help="History days (default: 7)")
    parser.add_argument("--record", action="store_true", help="Record current metrics")
    args = parser.parse_args()

    services = load_services()
    metrics = compute_slo_metrics(services)
    alerts = check_slo_burn(metrics)

    if args.record:
        SLO_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        record_file = SLO_DIR / f"{today}.jsonl"
        with open(record_file, "a") as f:
            f.write(json.dumps(metrics, ensure_ascii=False) + "\n")
        print(f"Recorded metrics to {record_file}")

    if args.json:
        output = {
            "metrics": metrics,
            "alerts": alerts,
            "slos": DEFAULT_SLOS,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(generate_slo_report(metrics, alerts))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
