#!/usr/bin/env python3
"""Deadline Tracker — 任务截止时间追踪 + 回复状态检测.

监控已发送任务的回复状态, 临近截止时告警, 截止后自动汇总.

数据源: ~/Documents/@工作文档/卫健委/_drafts/ 中已发送的任务记录
输出: 告警到 _inbox/, 超时任务汇总

Usage:
  python3 bin/ssot/deadline_tracker.py              # 检查一次
  python3 bin/ssot/deadline_tracker.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from _shared import ROOT, utc_now, append_jsonl
from mail_reader import read_netease_mail, Mail

DRAFTS_DIR = Path.home() / "Documents" / "@工作文档" / "卫健委" / "_drafts"
INBOX = Path.home() / "Documents" / "_inbox"
TASKS_FILE = ROOT / ".omo" / "state" / "tracked-tasks.json"
HEARTBEAT = ROOT / ".omo" / "state" / "deadline-tracker.jsonl"


def load_tasks() -> list[dict[str, Any]]:
    """加载追踪中的任务."""
    if not TASKS_FILE.exists():
        return []
    try:
        return json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_tasks(tasks: list[dict[str, Any]]) -> None:
    """保存任务列表."""
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TASKS_FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def register_task(subject: str, deadline: str, target: str, task_type: str) -> None:
    """注册新任务到追踪列表."""
    tasks = load_tasks()
    tasks.append({
        "subject": subject,
        "deadline": deadline,
        "target": target,
        "task_type": task_type,
        "registered_at": utc_now(),
        "status": "pending",  # pending → replied → compiled
        "replies": [],
    })
    save_tasks(tasks)


def check_replies(task: dict) -> list[Mail]:
    """检查是否有回复邮件 (匹配标题关键词)."""
    keywords = task.get("subject", "")[:10]
    if not keywords:
        return []
    # 读最近邮件, 找包含关键词的回复
    recent = read_netease_mail("work", limit=30, unread_only=False)
    replies = [m for m in recent if keywords in m.subject and m.sender != "ws-xxk@bjfsh.gov.cn"]
    return replies


def check_deadlines() -> dict[str, Any]:
    """检查所有追踪任务的截止状态."""
    ts = utc_now()
    tasks = load_tasks()
    if not tasks:
        return {"ts": ts, "checked": 0, "alerts": []}

    now = datetime.now(timezone.utc)
    alerts = []

    for task in tasks:
        if task.get("status") != "pending":
            continue

        # 检查回复
        replies = check_replies(task)
        if replies:
            task["status"] = "replied"
            task["replies"] = [{"subject": r.subject, "sender": r.sender, "date": r.date} for r in replies]
            alerts.append({
                "task": task["subject"][:40],
                "type": "reply_received",
                "detail": f"收到 {len(replies)} 条回复",
                "severity": "info",
            })

        # 检查截止时间
        deadline_str = task.get("deadline", "")
        if deadline_str:
            try:
                deadline_dt = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
                time_left = deadline_dt - now
                hours_left = time_left.total_seconds() / 3600

                if hours_left < 0:
                    alerts.append({
                        "task": task["subject"][:40],
                        "type": "overdue",
                        "detail": f"已超时 {abs(hours_left):.0f} 小时",
                        "severity": "critical",
                    })
                elif hours_left < 24:
                    alerts.append({
                        "task": task["subject"][:40],
                        "type": "approaching",
                        "detail": f"剩余 {hours_left:.0f} 小时",
                        "severity": "high",
                    })
            except Exception:
                pass

    save_tasks(tasks)

    result = {"ts": ts, "checked": len(tasks), "alerts": alerts}
    append_jsonl(HEARTBEAT, result)

    # 生成告警报报到 _inbox/
    if alerts:
        INBOX.mkdir(parents=True, exist_ok=True)
        alert_lines = [f"# ⏰ 截止时间告警 — {ts[:10]}", ""]
        for a in alerts:
            icon = {"critical": "🔴", "high": "🟡", "info": "🔵"}.get(a["severity"], "⚪")
            alert_lines.append(f"- {icon} **{a['task']}** — {a['detail']}")
        alert_path = INBOX / f"{ts[:10]}-deadline-alerts.md"
        alert_path.write_text("\n".join(alert_lines), encoding="utf-8")

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--register", action="store_true", help="register a new task")
    parser.add_argument("--subject", default="")
    parser.add_argument("--deadline", default="")
    parser.add_argument("--target", default="")
    parser.add_argument("--type", default="收集数据")
    args = parser.parse_args(argv)

    if args.register:
        register_task(args.subject, args.deadline, args.target, args.type)
        print(f"✅ 任务已注册: {args.subject}")
        return 0

    result = check_deadlines()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"⏰ 截止检查 ({result['ts']}): {result['checked']}任务, {len(result['alerts'])}告警")
        for a in result["alerts"]:
            print(f"  [{a['severity']}] {a['task']}: {a['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
