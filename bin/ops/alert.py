#!/usr/bin/env python3
"""Alerting integration for Service Gateway.

Sends notifications when services become unhealthy.
Supports multiple channels: webhook, email, log.

Usage:
    python3 bin/ops/alert.py --check
    python3 bin/ops/alert.py --service resident.orchestrator --status unhealthy
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required", file=sys.stderr)
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"
ALERT_STATE_FILE = WORKSPACE / ".omo" / "_delivery" / "ops-alerting" / "state.json"
LOGS_DIR = WORKSPACE / "runtime" / "logs"

# Alert channels configuration
ALERT_CHANNELS = {
    "log": True,  # Always enabled
    "webhook": False,  # Enable by setting ALERT_WEBHOOK_URL env var
    "email": False,  # Enable by setting ALERT_EMAIL env var
}


def load_services() -> list[dict]:
    """Load service manifest."""
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
        pid_file = WORKSPACE / "runtime" / "pids" / f"{svc['id']}.pid"
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
                        now = datetime.now(timezone.utc)
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
            mtime = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            stale = (now - mtime).total_seconds() / 3600
            result["status"] = "healthy" if stale < max_stale else "stale"
        else:
            result["status"] = "missing"

    return result


def send_alert(service_id: str, status: str, previous_status: str | None = None) -> None:
    """Send alert for a service status change."""
    timestamp = datetime.now(timezone.utc).isoformat()

    alert = {
        "timestamp": timestamp,
        "service": service_id,
        "status": status,
        "previous_status": previous_status,
        "message": f"Service {service_id} is {status}",
    }

    # Log alert
    log_alert(alert)

    # Webhook alert
    if ALERT_CHANNELS["webhook"]:
        send_webhook_alert(alert)

    # Email alert
    if ALERT_CHANNELS["email"]:
        send_email_alert(alert)


def log_alert(alert: dict) -> None:
    """Log alert to file."""
    log_file = LOGS_DIR / "alerts.log"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as f:
        f.write(json.dumps(alert, ensure_ascii=False) + "\n")


def send_webhook_alert(alert: dict) -> None:
    """Send alert via webhook."""
    import os
    import urllib.request

    webhook_url = os.environ.get("ALERT_WEBHOOK_URL")
    if not webhook_url:
        return

    try:
        data = json.dumps(alert).encode()
        req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Webhook alert failed: {e}", file=sys.stderr)


def send_email_alert(alert: dict) -> None:
    """Send alert via email."""
    import os
    email = os.environ.get("ALERT_EMAIL")
    if not email:
        return

    try:
        subprocess.run(
            ["mail", "-s", f"[Ops Alert] {alert['service']} is {alert['status']}", email],
            input=alert["message"],
            text=True,
            timeout=10,
        )
    except Exception as e:
        print(f"Email alert failed: {e}", file=sys.stderr)


def load_alert_state() -> dict:
    """Load previous alert state."""
    if ALERT_STATE_FILE.exists():
        try:
            return json.loads(ALERT_STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_alert_state(state: dict) -> None:
    """Save alert state."""
    ALERT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALERT_STATE_FILE.write_text(json.dumps(state, indent=2))


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Service Gateway Alerting")
    parser.add_argument("--check", action="store_true", help="Check all services and alert on failures")
    parser.add_argument("--service", help="Alert for specific service")
    parser.add_argument("--status", help="Status to alert for")
    args = parser.parse_args()

    if args.service and args.status:
        send_alert(args.service, args.status)
        return 0

    if args.check:
        services = load_services()
        enabled = [s for s in services if s.get("enabled", False)]
        previous_state = load_alert_state()
        current_state: dict[str, str] = {}
        alerts_sent = 0

        for svc in enabled:
            sid = svc.get("id", "")
            health = check_service_health(svc)
            status = health["status"]
            current_state[sid] = status

            # Alert on status change to unhealthy
            if status in ("stale", "missing", "unreachable", "unhealthy"):
                prev = previous_state.get(sid)
                if prev != status:
                    send_alert(sid, status, prev)
                    alerts_sent += 1

        save_alert_state(current_state)
        print(f"Checked {len(enabled)} services, {alerts_sent} alerts sent")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
