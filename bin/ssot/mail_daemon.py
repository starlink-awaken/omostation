#!/usr/bin/env python3
"""Mail Daemon — 工作域邮件感知+认知+规划 守护进程.

每30分钟: 读邮件 → LLM分类 → 任务提取 → 日报 → 高优任务生成草稿.
安全: 所有行动只生成草稿, 不自动发送.

Usage:
  python3 bin/ssot/mail_daemon.py --once
  python3 bin/ssot/mail_daemon.py --run --interval 1800
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
sys.path.insert(0, str(Path(__file__).parent))
from _shared import ROOT, utc_now, append_jsonl
from mail_reader import read_all
from mail_agent import classify_mail, extract_task, generate_briefing
from doc_generator import generate_doc, save_draft

INBOX = Path.home() / "Documents" / "_inbox"
HEARTBEAT = ROOT / ".omo" / "state" / "mail-daemon.jsonl"


def run_cycle() -> dict[str, Any]:
    ts = utc_now()
    mails = read_all(limit=20, unread_only=True)
    if not mails:
        result = {"ts": ts, "mails": 0, "status": "no_unread"}
        append_jsonl(HEARTBEAT, result)
        return result

    classifications = []
    tasks = []
    for mail in mails:
        cls = classify_mail(mail)
        classifications.append(cls)
        if cls.get("category") == "任务":
            task = extract_task(mail, cls)
            if task:
                tasks.append((mail, cls, task))

    briefing = generate_briefing(mails, classifications)
    INBOX.mkdir(parents=True, exist_ok=True)
    briefing_path = INBOX / f"{ts[:10]}-mail-briefing.md"
    briefing_path.write_text(briefing, encoding="utf-8")

    drafts = 0
    for mail, cls, task in tasks:
        if cls.get("priority") == "high":
            template_map = {"转发通知": "forward_notice", "收集数据": "data_collection", "提交报告": "summary_report"}
            template = template_map.get(task.get("task_type", ""), "work_plan")
            content = generate_doc(template, {"subject": mail.subject, "sender": mail.sender, "body": mail.body[:200], "deadline": task.get("deadline", ""), "task_detail": task})
            save_draft(template, content)
            drafts += 1

    result = {"ts": ts, "mails": len(mails), "tasks": len(tasks), "drafts": drafts, "briefing": str(briefing_path), "status": "ok"}
    append_jsonl(HEARTBEAT, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--interval", type=int, default=1800)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.once or not args.run:
        result = run_cycle()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"📧 邮件处理 ({result['ts']}): {result['mails']}封 {result['tasks']}任务 {result['drafts']}草稿")
        return 0

    import time
    print(f"Mail Daemon (interval={args.interval}s)", flush=True)
    try:
        while True:
            result = run_cycle()
            print(f"  [{result['ts'][:19]}] mails={result['mails']} tasks={result['tasks']}", flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n停止。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
