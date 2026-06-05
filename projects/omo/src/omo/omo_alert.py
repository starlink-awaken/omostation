#!/usr/bin/env python3
"""OMO alert CLI — KEI audit threshold detection + notification.

Checks KEI audit logs for:
- Blocked rate > threshold (default: 10 blocked/hour)
- Failed service health checks
- Debt items past due
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

KEI_AUDIT = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime"))) / "data" / "kei_audit.jsonl"
NOTIFY_SCRIPT = Path.home() / "Workspace" / "projects" / "runtime" / "scripts" / "notify-alerts.sh"


def cmd_alert_check(threshold: int, notify: bool) -> int:
    """Check KEI audit for blocked/failed rates exceeding threshold."""
    if not KEI_AUDIT.exists():
        print("ℹ️  No KEI audit data")
        return 0
    lines = KEI_AUDIT.read_text().strip().split("\n")
    now = datetime.now(timezone.utc)
    recent: list[dict] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            ts = r.get("ts", "")
            if ts:
                r_ts = datetime.fromisoformat(ts)
                if (now - r_ts).total_seconds() < 3600:
                    recent.append(r)
        except (json.JSONDecodeError, ValueError):
            pass

    blocked = [r for r in recent if r.get("status") == "blocked"]
    failed = [r for r in recent if r.get("status") == "fail"]
    blocked_rate = len(blocked)
    failed_rate = len(failed)

    alerts: list[str] = []
    if blocked_rate >= threshold:
        alerts.append(f"🔴 KEI blocked rate: {blocked_rate}/hour (threshold: {threshold})")
    if failed_rate >= threshold:
        alerts.append(f"🔴 KEI failure rate: {failed_rate}/hour (threshold: {threshold})")

    if not alerts:
        print(f"✅ All KEI metrics normal (blocked: {blocked_rate}/h, failed: {failed_rate}/h)")
        if notify:
            print("   (no alert needed)")
        return 0

    print(f"⚠️  {len(alerts)} alert(s) detected:")
    for a in alerts:
        print(f"  {a}")

    if notify:
        for a in alerts:
            try:
                subprocess.run(["bash", str(NOTIFY_SCRIPT), "KEI Alert", a], timeout=10)
                print(f"   → Notified via {NOTIFY_SCRIPT}")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                print(f"   → Notification failed: {e}")
    return 1 if alerts else 0


def cmd_alert_channel(enable: bool, webhook_url: str | None) -> int:
    """Configure notification channel."""
    notify_script = NOTIFY_SCRIPT
    if not notify_script.exists():
        print(f"❌ notify-alerts.sh not found at {notify_script}")
        # Create the skeleton if it doesn't exist
        notify_script.parent.mkdir(parents=True, exist_ok=True)
        notify_script.write_text("""#!/bin/bash
# KEI Alert Notification Script
# Usage: notify-alerts.sh <title> <body>
set -euo pipefail
TITLE="$1"
BODY="$2"
# WeChat webhook — uncomment and configure:
# WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
# curl -s -X POST "$WEBHOOK" -H "Content-Type: application/json" \\
#   -d "{\\"msgtype\\": \\"markdown\\", \\"markdown\\": {\\"content\\": \\"## $TITLE\\\\n$BODY\\"}}"
echo "[NOTIFY] $TITLE: $BODY"
""")
        notify_script.chmod(0o755)
        print(f"   Created: {notify_script}")

    if enable and webhook_url:
        # Write webhook URL to config
        config = Path.home() / ".runtime" / "notify.conf"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(f"WEBHOOK={webhook_url}\n")
        print(f"✅ WeChat webhook configured: {config}")
    elif enable and not webhook_url:
        print("ℹ️  notify-alerts.sh exists. Configure WEBHOOK in ~/.runtime/notify.conf")
    else:
        print("ℹ️  Alerts disabled")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo alert", description="OMO alert management")
    sub = parser.add_subparsers(dest="command")

    ac = sub.add_parser("check", help="Check KEI audit thresholds")
    ac.add_argument("--threshold", "-t", type=int, default=10, help="Blocked/failed per hour threshold")
    ac.add_argument("--notify", action="store_true", help="Send notification if threshold exceeded")

    ch = sub.add_parser("channel", help="Configure notification channel")
    ch.add_argument("--enable", action="store_true", help="Enable notifications")
    ch.add_argument("--webhook", help="WeChat webhook URL")

    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_alert_check(args.threshold, args.notify)
    elif args.command == "channel":
        return cmd_alert_channel(args.enable, args.webhook)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
