#!/usr/bin/env python3
"""Mail Agent — LLM 邮件分类 + 任务提取 + 日报生成.

Usage:
  python3 bin/ssot/mail-agent.py              # 处理未读邮件, 生成日报
  python3 bin/ssot/mail-agent.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from _shared import ROOT, utc_now

sys.path.insert(0, str(Path(__file__).parent))
from _llm_helper import llm_ask
from mail_reader import Mail, read_all

INBOX = Path.home() / "Documents" / "_inbox"


def classify_mail(mail: Mail) -> dict[str, Any]:
    prompt = (
        f"你是邮件分类助手。请将以下邮件分类为:\n"
        f"- 通知 (上级通知/政策文件/会议通知)\n- 任务 (需要执行: 收集数据/提交报告/转发文件)\n"
        f"- 参考 (资讯/学术)\n- 垃圾 (广告)\n- 个人\n\n"
        f"标题: {mail.subject}\n发件人: {mail.sender}\n正文: {mail.body[:300]}\n\n"
        f'输出 JSON: {{"category":"...","priority":"high/medium/low","summary":"摘要","action_needed":"动作或空"}}'
    )
    response = llm_ask(prompt, timeout=30.0)
    if not response:
        return {"category": "未分类", "priority": "low", "summary": mail.subject[:60], "action_needed": ""}
    m = re.search(r'\{[^{}]*"category"[^{}]*\}', response)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return {"category": "未分类", "priority": "low", "summary": response[:100], "action_needed": ""}


def extract_task(mail: Mail, classification: dict) -> dict[str, Any] | None:
    if classification.get("category") != "任务":
        return None
    prompt = (
        f"这封邮件需要执行什么任务?\n标题: {mail.subject}\n发件人: {mail.sender}\n正文: {mail.body[:400]}\n\n"
        f'输出 JSON: {{"task_type":"转发通知/收集数据/提交报告/其他","deadline":"截止时间","target":"对象","required_docs":"文档","steps":"步骤"}}'
    )
    response = llm_ask(prompt, timeout=30.0)
    if not response:
        return None
    m = re.search(r'\{.*\}', response, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return {"raw_analysis": response[:300]}


def generate_briefing(mails: list[Mail], classifications: list[dict]) -> str:
    date_str = utc_now()[:10]
    by_cat: dict[str, list[tuple[Mail, dict]]] = {}
    for mail, cls in zip(mails, classifications):
        by_cat.setdefault(cls.get("category", "未分类"), []).append((mail, cls))

    lines = [f"# 📧 邮件日报 — {date_str}", f"", f"> 生成时间: {utc_now()}", f"> 邮件总数: {len(mails)} | 任务: {len(by_cat.get('任务', []))} | 通知: {len(by_cat.get('通知', []))}", f""]

    for cat, icon in [("任务", "🔴"), ("通知", "📋"), ("参考", "📎"), ("个人", "👤")]:
        items = by_cat.get(cat, [])
        if not items:
            continue
        lines.append(f"## {icon} {cat}")
        lines.append("")
        for mail, cls in items:
            if cat == "任务":
                priority = cls.get("priority", "medium")
                icon2 = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
                lines.append(f"### {icon2} {mail.subject[:60]}")
                lines.append(f"- 发件人: {mail.sender} | 优先级: {priority}")
                lines.append(f"- 摘要: {cls.get('summary', '')}")
                action = cls.get("action_needed", "")
                if action:
                    lines.append(f"- **需执行**: {action}")
            else:
                lines.append(f"- **{mail.subject[:50]}** — {cls.get('summary', '')}")
            lines.append("")

    if by_cat.get("任务"):
        advice = llm_ask(f"今天有{len(by_cat['任务'])}个任务，给出优先排序建议(一句话)。")
        if advice:
            lines += ["## 💡 AI 建议", advice[:200], ""]

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--unread-only", action="store_true", default=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)

    mails = read_all(args.limit, args.unread_only)
    if not mails:
        print("无未读邮件")
        return 0

    classifications = [classify_mail(m) for m in mails]
    tasks = [extract_task(m, c) for m, c in zip(mails, classifications)]
    tasks = [t for t in tasks if t]

    if args.json:
        print(json.dumps({"total": len(mails), "classifications": classifications, "tasks": tasks, "scanned_at": utc_now()}, ensure_ascii=False, indent=2))
    else:
        briefing = generate_briefing(mails, classifications)
        INBOX.mkdir(parents=True, exist_ok=True)
        path = INBOX / f"{utc_now()[:10]}-mail-briefing.md"
        path.write_text(briefing, encoding="utf-8")
        print(f"✅ 邮件日报: {path} ({len(mails)}封, {len(tasks)}任务)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
