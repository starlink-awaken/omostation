#!/usr/bin/env python3
"""OMO alert CLI — KEI audit threshold detection + notification.

Checks KEI audit logs for:
- Blocked rate > threshold (default: 10 blocked/hour)
- Failed service health checks
- Debt items past due

Round 4 (P1-2): 接入 AppendOnlyLog (第 4 个 consumer).
  - 读源: KEI_AUDIT (其他模块写) → 用 AppendOnlyLog.since(hour_ago) 替代手写时间过滤
  - 写汇: 新增 ALERT_LOG (自身写) → 每次 alert 触发落盘, 历史可查
"""
from __future__ import annotations

import argparse
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omo.omo_io import AppendOnlyLog

KEI_AUDIT = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime"))) / "data" / "kei_audit.jsonl"
NOTIFY_SCRIPT = Path.home() / "Workspace" / "projects" / "runtime" / "scripts" / "notify-alerts.sh"

# Round 4: 自身写的 alert 历史 (AppendOnlyLog consumer)
_WORKSPACE = Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace")))
ALERT_LOG = _WORKSPACE / ".omo" / "_knowledge" / "omo-alerts.jsonl"


def cmd_alert_check(threshold: int, notify: bool) -> int:
    """Check KEI audit for blocked/failed rates exceeding threshold."""
    if not KEI_AUDIT.exists():
        print("ℹ️  No KEI audit data")
        return 0

    # Round 4: 用 AppendOnlyLog.since 替代手写 read_text + 时间过滤 (8 行 → 2 行)
    now = datetime.now(timezone.utc)
    one_hour_ago = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = AppendOnlyLog(KEI_AUDIT).since(one_hour_ago)

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

    # Round 4: 每次 alert 触发, 落 ALERT_LOG 一行 (结构化, 便于事后审计)
    # Round 37 P0: 加 sort_keys=True 守 §12.1.4 跨仓 4 不变量
    alert_log = AppendOnlyLog(ALERT_LOG)
    for a in alerts:
        alert_log.append(
            {
                "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "kind": "kei_threshold",
                "severity": "high",
                "message": a,
                "blocked_rate": blocked_rate,
                "failed_rate": failed_rate,
                "threshold": threshold,
            },
            sort_keys=True,
        )

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
