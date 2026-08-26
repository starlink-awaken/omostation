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
import shlex
import sys
from pathlib import Path
from typing import Any

from _shared import ROOT, append_jsonl, utc_now

sys.path.insert(0, str(Path(__file__).parent))
from _llm_helper import llm_ask
from mail_reader import Mail, read_all

INBOX = Path.home() / "Documents" / "_inbox"

# 积累回路 (2026-08-26, P0 数字大脑红线: 分类不能是无状态直连 LLM):
# 每次分类落库 jsonl, 后续同发件人分类注入最近历史 → 一致性 + 可统计。
HISTORY = ROOT / ".omo" / "state" / "mail-classification-history.jsonl"

# 规则预分类 (2026-08-26, 首批积累数据实证: github 通知占 16/20 = 80% 的
# LLM 调用花在固定模式上 — 机器通知发件人无需 LLM, 直接短路省钱省时)。
RULE_PRECLASSIFY = {
    "notifications@github.com": {"category": "参考", "priority": "low"},
    "noreply@redditmail.com": {"category": "参考", "priority": "low"},
    "hi@news.kilocode.ai": {"category": "垃圾", "priority": "low"},
}

VALID_CATEGORIES = {"通知", "任务", "参考", "垃圾", "个人", "未分类"}


def _persist_history(mail: Mail, result: dict[str, Any]) -> None:
    """分类结果落库(失败不阻塞主流程)."""
    try:
        append_jsonl(
            HISTORY,
            {
                "ts": utc_now(),
                "subject": (mail.subject or "")[:80],
                "sender": (mail.sender or "")[:60],
                "category": result.get("category"),
                "priority": result.get("priority"),
                "source": result.get("_source", "llm"),
            },
        )
    except Exception:
        pass


def _recent_history_for(sender: str, limit: int = 3) -> list[dict]:
    """读同发件人最近分类记录(倒序扫, 早停)."""
    if not sender or not HISTORY.exists():
        return []
    out: list[dict] = []
    for line in reversed(HISTORY.read_text(errors="replace").splitlines()):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("sender") == sender:
            out.append(rec)
            if len(out) >= limit:
                break
    return out


def classify_mail(mail: Mail) -> dict[str, Any]:
    # 规则短路: 机器通知发件人不进 LLM(首批数据实证 80% 调用浪费在此)
    for sender_key, preset in RULE_PRECLASSIFY.items():
        if sender_key in (mail.sender or ""):
            result = {
                "category": preset["category"],
                "priority": preset["priority"],
                "summary": (mail.subject or "")[:60],
                "action_needed": "",
                "_source": "rule",
            }
            _persist_history(mail, result)
            return result

    hist = _recent_history_for(mail.sender or "")
    hist_lines = "\n".join(
        f"- [{h.get('category')}/{h.get('priority')}] {h.get('subject', '')[:30]}"
        for h in hist
    )
    prompt = (
        f"你是邮件分类助手。请将以下邮件分类为:\n"
        f"- 通知 (上级通知/政策文件/会议通知)\n- 任务 (需要执行: 收集数据/提交报告/转发文件)\n"
        f"- 参考 (资讯/学术)\n- 垃圾 (广告)\n- 个人\n\n"
        + (f"该发件人历史分类(保持一致性):\n{hist_lines}\n\n" if hist_lines else "")
        + f"标题: {mail.subject}\n发件人: {mail.sender}\n正文: {mail.body[:300]}\n\n"
        f'输出 JSON: {{"category":"...","priority":"high/medium/low","summary":"摘要","action_needed":"动作或空"}}'
    )
    response = llm_ask(prompt, timeout=30.0, model="qwen-3.8-27b")
    if not response:
        result = {
            "category": "未分类",
            "priority": "low",
            "summary": mail.subject[:60],
            "action_needed": "",
        }
    else:
        m = re.search(r'\{[^{}]*"category"[^{}]*\}', response)
        if m:
            try:
                result = json.loads(m.group())
            except Exception:
                result = {
                    "category": "未分类",
                    "priority": "low",
                    "summary": response[:100],
                    "action_needed": "",
                }
        else:
            result = {
                "category": "未分类",
                "priority": "low",
                "summary": response[:100],
                "action_needed": "",
            }
    # 脏值防御(首批数据实证: LLM 偶发把枚举列表原文当 category 返回)
    if result.get("category") not in VALID_CATEGORIES:
        result["category"] = "未分类"
    _persist_history(mail, result)
    return result


def extract_task(mail: Mail, classification: dict) -> dict[str, Any] | None:
    if classification.get("category") != "任务":
        return None
    prompt = (
        f"这封邮件需要执行什么任务?\n标题: {mail.subject}\n发件人: {mail.sender}\n正文: {mail.body[:400]}\n\n"
        f'输出 JSON: {{"task_type":"转发通知/收集数据/提交报告/其他","deadline":"截止时间","target":"对象","required_docs":"文档","steps":"步骤"}}'
    )
    response = llm_ask(prompt, timeout=30.0, model="qwen-3.8-27b")
    if not response:
        return None
    m = re.search(r"\{.*\}", response, re.DOTALL)
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

    lines = [
        f"# 📧 邮件日报 — {date_str}",
        "",
        f"> 生成时间: {utc_now()}",
        f"> 邮件总数: {len(mails)} | 任务: {len(by_cat.get('任务', []))} | 通知: {len(by_cat.get('通知', []))}",
        "",
    ]

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
# 2026-08-25 断点桥接(全链勘测结论) + 2026-08-26 转义修正:
                # journey-runner dry-run 默认开(--live 才真 dispatch);
                # payload 用 shlex.quote(json.dumps(...)) 保 shell 安全。
                _payload = shlex.quote(json.dumps(
                    {"subject": (mail.subject or "")[:40], "sender": (mail.sender or "")[:30]},
                    ensure_ascii=False,
                ))
                lines.append(
                    f"- 🚀 处理: cd ~/Workspace && python3 bin/ssot/journey-runner.py run "
                    f"--journey admin-notification-workflow --input {_payload}"
                    f"  (dry-run 默认, 确认后加 --live)"
                )
            else:
                lines.append(f"- **{mail.subject[:50]}** — {cls.get('summary', '')}")
            lines.append("")

    if by_cat.get("任务"):
        advice = llm_ask(f"今天有{len(by_cat['任务'])}个任务，给出优先排序建议(一句话)。", model="qwen-3.8-27b")
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
        print(
            json.dumps(
                {
                    "total": len(mails),
                    "classifications": classifications,
                    "tasks": tasks,
                    "scanned_at": utc_now(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        briefing = generate_briefing(mails, classifications)
        INBOX.mkdir(parents=True, exist_ok=True)
        path = INBOX / f"{utc_now()[:10]}-mail-briefing.md"
        path.write_text(briefing, encoding="utf-8")
        print(f"✅ 邮件日报: {path} ({len(mails)}封, {len(tasks)}任务)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
