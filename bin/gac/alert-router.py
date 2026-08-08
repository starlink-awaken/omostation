#!/usr/bin/env python3
"""Alert Router — read anomaly-events.jsonl and emit alerts via configured channels.

Usage:
    python3 bin/gac/alert-router.py --config .omo/_truth/registry/governance-alerts.yaml
    python3 bin/gac/alert-router.py --dry-run
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_ANOMALY_FILE = WORKSPACE / ".omo" / "state" / "anomaly-events.jsonl"
DEFAULT_ALERT_CONFIG = WORKSPACE / ".omo/_truth/registry/governance-alerts.yaml"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_anomalies(anomaly_file: Path, window: int = 20) -> list[dict]:
    if not anomaly_file.is_file():
        return []
    lines = anomaly_file.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    if window > 0:
        entries = entries[-window:]
    return entries


def _load_config(config_path: Path) -> dict:
    if not config_path.is_file():
        return {}
    try:
        import yaml
        return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _route_log(alert: dict, config: dict) -> None:
    log_cfg = config.get("channels", {}).get("log", {})
    if not log_cfg.get("enabled", False):
        return
    path = log_cfg.get("path", "/tmp/governance-alerts.log")
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now_iso(), **alert}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _route_webhook(alert: dict, config: dict) -> None:
    webhook_cfg = config.get("channels", {}).get("webhook", {})
    if not webhook_cfg.get("enabled", False):
        return
    url = webhook_cfg.get("url", "")
    if not url:
        return
    try:
        import urllib.request
        payload = json.dumps({"ts": now_iso(), **alert}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=webhook_cfg.get("timeout", 10)) as resp:
            resp.read()
    except Exception:
        pass


def _route_email(alert: dict, config: dict) -> None:
    email_cfg = config.get("channels", {}).get("email", {})
    if not email_cfg.get("enabled", False):
        return
    # Email sending requires smtplib; keep minimal and non-blocking.
    try:
        import smtplib
        from email.mime.text import MIMEText
        subject = f"[Governance Alert] {alert.get('check', 'unknown')}"
        body = json.dumps(alert, ensure_ascii=False, indent=2)
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = email_cfg.get("username", "")
        msg["To"] = ", ".join(email_cfg.get("recipients", []))
        with smtplib.SMTP(email_cfg.get("smtp_host", ""), email_cfg.get("smtp_port", 587)) as s:
            if email_cfg.get("use_tls", True):
                s.starttls()
            if email_cfg.get("username") and email_cfg.get("password"):
                s.login(email_cfg["username"], email_cfg["password"])
            s.sendmail(msg["From"], email_cfg.get("recipients", []), msg.as_string())
    except Exception:
        pass


def route_alert(alert: dict, config: dict) -> None:
    _route_log(alert, config)
    _route_webhook(alert, config)
    _route_email(alert, config)


def main() -> int:
    parser = argparse.ArgumentParser(description="Alert Router")
    parser.add_argument("--anomaly-file", default=str(DEFAULT_ANOMALY_FILE), help="Anomaly events JSONL path")
    parser.add_argument("--config", default=str(DEFAULT_ALERT_CONFIG), help="Alert config YAML path")
    parser.add_argument("--window", type=int, default=20, help="Recent anomaly window")
    parser.add_argument("--dry-run", action="store_true", help="Print alerts without routing")
    args = parser.parse_args()

    anomaly_file = Path(args.anomaly_file)
    config = _load_config(Path(args.config))
    anomalies = _load_anomalies(anomaly_file, window=args.window)

    if args.dry_run:
        print(json.dumps({"anomalies": anomalies, "routed": 0}, ensure_ascii=False, indent=2))
        return 0

    routed = 0
    for alert in anomalies:
        route_alert(alert, config)
        routed += 1

    print(json.dumps({"anomalies": anomalies, "routed": routed}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
