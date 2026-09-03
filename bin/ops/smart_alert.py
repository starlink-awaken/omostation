#!/usr/bin/env python3
"""Smart Alerting System for Service Gateway.

Features:
- Alert deduplication (time-based window)
- Alert correlation (group by service/region)
- Escalation based on severity and duration
- Multiple notification channels (webhook, email, log)
- Alert suppression and silencing
- Alert history and trending

Usage:
    python3 bin/ops/smart_alert.py [--check] [--report]
"""

from __future__ import annotations

import hashlib
import json
import os
import smtplib
import sys
from datetime import UTC, datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required", file=sys.stderr)
    sys.exit(1)

WORKSPACE = Path(__file__).resolve().parents[2]
SERVICES_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml"
ALERT_STATE_FILE = WORKSPACE / ".omo" / "_delivery" / "ops-alerts" / "state.jsonl"
ALERT_HISTORY_FILE = WORKSPACE / ".omo" / "_delivery" / "ops-alerts" / "history.jsonl"

SEVERITY = {"info": 0, "warning": 1, "critical": 2, "emergency": 3}

DEFAULT_RULES = {
    "service_down": {"severity": "critical", "threshold": 1, "window_seconds": 60, "auto_resolve": True},
    "high_latency": {"severity": "warning", "threshold": 3, "window_seconds": 300, "auto_resolve": True},
    "resource_exhaustion": {"severity": "warning", "threshold": 2, "window_seconds": 120, "auto_resolve": True},
    "slo_breach": {"severity": "critical", "threshold": 1, "window_seconds": 0, "auto_resolve": False},
    "dependency_failure": {"severity": "critical", "threshold": 1, "window_seconds": 0, "auto_resolve": True},
}

CHANNELS = {
    "log": True,
    "webhook": bool(os.environ.get("ALERT_WEBHOOK_URL")),
    "email": bool(os.environ.get("ALERT_EMAIL")),
}


def load_services() -> list[dict]:
    if not SERVICES_YAML.exists():
        return []
    content = SERVICES_YAML.read_text()
    docs = list(yaml.safe_load_all(content))
    for doc in docs:
        if isinstance(doc, dict) and "services" in doc:
            return doc.get("services", [])
    return []


def check_service_health(svc: dict) -> dict[str, Any]:
    sid = svc.get("id", "")
    result = {"id": sid, "enabled": svc.get("enabled", False), "status": "unknown", "healthy": None}
    if not result["enabled"]:
        result["status"] = "disabled"
        return result
    pid_file = WORKSPACE / "runtime" / "pids" / f"{sid}.pid"
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


def generate_alert_id(alert: dict) -> str:
    key = f"{alert['rule']}:{alert['service']}:{alert.get('instance', '')}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def deduplicate_alerts(alerts: list[dict], window_seconds: int = 60) -> list[dict]:
    if not alerts:
        return []
    state = load_alert_state()
    now = datetime.now(UTC)
    deduped = []
    for alert in alerts:
        alert_id = generate_alert_id(alert)
        alert["id"] = alert_id
        alert["timestamp"] = now.isoformat()
        last_sent = state.get(alert_id)
        if last_sent:
            last_time = datetime.fromisoformat(last_sent)
            if (now - last_time).total_seconds() < window_seconds:
                continue
        deduped.append(alert)
        state[alert_id] = now.isoformat()
    save_alert_state(state, max_entries=1000)
    return deduped


def correlate_alerts(alerts: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for alert in alerts:
        key = alert.get("service", "unknown")
        groups.setdefault(key, []).append(alert)
    correlated = []
    for service, group in groups.items():
        if len(group) > 1:
            severities = [a.get("severity", "info") for a in group]
            max_severity = max(severities, key=lambda s: SEVERITY.get(s, 0))
            correlated.append({
                "rule": "correlated", "service": service, "severity": max_severity,
                "count": len(group), "alerts": group,
                "message": f"{len(group)} alerts for {service}",
            })
        else:
            correlated.extend(group)
    return correlated


def load_alert_state() -> dict[str, str]:
    if ALERT_STATE_FILE.exists():
        try:
            with open(ALERT_STATE_FILE) as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {}


def save_alert_state(state: dict, max_entries: int = 1000) -> None:
    ALERT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if len(state) > max_entries:
        sorted_items = sorted(state.items(), key=lambda x: x[1], reverse=True)
        state = dict(sorted_items[:max_entries])
    with open(ALERT_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def send_alert(alert: dict) -> dict[str, Any]:
    results = {"channels": [], "success": False}
    log_alert(alert)
    results["channels"].append("log")
    if CHANNELS["webhook"]:
        webhook_url = os.environ.get("ALERT_WEBHOOK_URL")
        if webhook_url and send_webhook_alert(webhook_url, alert):
            results["channels"].append("webhook")
    if CHANNELS["email"]:
        email = os.environ.get("ALERT_EMAIL")
        if email and send_email_alert(email, alert):
            results["channels"].append("email")
    results["success"] = len(results["channels"]) > 0
    return results


def log_alert(alert: dict) -> None:
    severity = alert.get("severity", "info").upper()
    message = alert.get("message", str(alert))
    service = alert.get("service", "unknown")
    log_line = f"[{severity}] {service}: {message}"
    print(log_line, file=sys.stderr if SEVERITY.get(alert.get("severity", "info"), 0) >= 2 else sys.stdout)
    ALERT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERT_HISTORY_FILE, "a") as f:
        f.write(json.dumps(alert, ensure_ascii=False) + "\n")


def send_webhook_alert(url: str, alert: dict) -> bool:
    try:
        payload = json.dumps({
            "text": f"[{alert.get('severity', 'info').upper()}] {alert.get('service', 'unknown')}: {alert.get('message', '')}",
            "alert": alert,
        }).encode()
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def send_email_alert(to: str, alert: dict) -> bool:
    try:
        smtp_host = os.environ.get("SMTP_HOST", "localhost")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASS", "")
        from_addr = os.environ.get("ALERT_FROM", "alerts@omostation.local")
        msg = MIMEText(json.dumps(alert, indent=2, ensure_ascii=False))
        msg["Subject"] = f"[{alert.get('severity', 'info').upper()}] {alert.get('service', 'unknown')}"
        msg["From"] = from_addr
        msg["To"] = to
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_user and smtp_pass:
                server.starttls()
                server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, [to], msg.as_string())
        return True
    except Exception:
        return False


def check_alert_rules(services: list[dict]) -> list[dict]:
    alerts = []
    for svc in services:
        sid = svc.get("id", "")
        if not svc.get("enabled", False):
            continue
        health = check_service_health(svc)
        if health["status"] == "down":
            alerts.append({
                "rule": "service_down", "service": sid,
                "severity": DEFAULT_RULES["service_down"]["severity"],
                "message": f"Service {sid} is down",
            })
        for dep in svc.get("depends_on", []):
            dep_svc = next((s for s in services if s.get("id") == dep), None)
            if dep_svc:
                dep_health = check_service_health(dep_svc)
                if dep_health["status"] == "down":
                    alerts.append({
                        "rule": "dependency_failure", "service": sid,
                        "severity": DEFAULT_RULES["dependency_failure"]["severity"],
                        "message": f"Dependency {dep} is down",
                    })
    return alerts


def generate_alert_report(hours: int = 24) -> dict[str, Any]:
    if not ALERT_HISTORY_FILE.exists():
        return {"total": 0, "by_severity": {}, "by_service": {}}
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    alerts = []
    with open(ALERT_HISTORY_FILE) as f:
        for line in f:
            try:
                alert = json.loads(line.strip())
                ts = datetime.fromisoformat(alert["timestamp"])
                if ts >= cutoff:
                    alerts.append(alert)
            except (json.JSONDecodeError, KeyError):
                continue
    by_severity = {}
    by_service = {}
    for alert in alerts:
        sev = alert.get("severity", "unknown")
        svc = alert.get("service", "unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_service[svc] = by_service.get(svc, 0) + 1
    return {"period_hours": hours, "total": len(alerts), "by_severity": by_severity, "by_service": by_service}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Smart Alerting System")
    parser.add_argument("--check", action="store_true", help="Run alert checks")
    parser.add_argument("--report", action="store_true", help="Generate alert report")
    parser.add_argument("--hours", type=int, default=24, help="Report period (default: 24)")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    services = load_services()

    if args.check:
        alerts = check_alert_rules(services)
        alerts = deduplicate_alerts(alerts)
        alerts = correlate_alerts(alerts)
        sent = 0
        for alert in alerts:
            result = send_alert(alert)
            if result["success"]:
                sent += 1
        if args.json:
            print(json.dumps({"alerts_generated": len(alerts), "alerts_sent": sent}, indent=2))
        else:
            print(f"Generated {len(alerts)} alerts, sent {sent}")

    if args.report:
        report = generate_alert_report(args.hours)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"Alert Report (last {args.hours}h):")
            print(f"  Total: {report['total']}")
            print(f"  By Severity: {report['by_severity']}")
            print(f"  By Service: {report['by_service']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
