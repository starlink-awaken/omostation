#!/usr/bin/env python3
"""
eCOS v5 L3 — 入口价值对比 (ecos-entry-logger)
=============================================
Phase7.5 / v5 设计能力补全 — L3 各入口的使用频率和价值贡献统计。
记录每次 Agent 启动的入口、耗时和结果到事件流。

用法:
    # 记录 Agent 启动
    python3 ecos-entry-logger.py --entry claude_id --intent governance_check --result pass

    # 查看最近入口统计
    python3 ecos-entry-logger.py --report

    # 连续监听 Agent 入口变更
    python3 ecos-entry-logger.py --watch
"""

import sys
import json
import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path


ENTRY_LOG = Path.home() / ".ecos" / "events" / "entry-stream.jsonl"


def init_log():
    ENTRY_LOG.parent.mkdir(parents=True, exist_ok=True)


def log_entry(entry_type: str, intent: str, result: str = "pass",
              duration_ms: int = 0, detail: str = ""):
    """记录一次入口事件"""
    init_log()
    session_id = hashlib.md5(f"{datetime.now().isoformat()}{entry_type}".encode()).hexdigest()[:12]

    event = {
        "type": "entry.access",
        "session": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entry": entry_type,
        "intent": intent,
        "result": result,
        "duration_ms": duration_ms,
        "detail": detail,
    }

    with open(ENTRY_LOG, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return event


def read_entries(n: int = 50) -> list[dict]:
    """读取最近入口记录"""
    init_log()
    if not ENTRY_LOG.exists():
        return []

    events = []
    with open(ENTRY_LOG, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
                if evt.get("type") == "entry.access":
                    events.append(evt)
            except json.JSONDecodeError:
                continue

    return events[-n:]


def format_report(entries: list[dict]) -> str:
    """聚合统计报告"""
    from collections import Counter
    lines = []
    lines.append("=" * 64)
    lines.append("  eCOS v5 — L3 入口价值对比报告")
    lines.append("=" * 64)

    if not entries:
        lines.append("  暂无入口记录——Agent 启动后会自动记录")
        lines.append("")
        lines.append("=" * 64)
        return "\n".join(lines)

    # 按入口类型
    by_entry = Counter(e["entry"] for e in entries)
    # 按意图
    by_intent = Counter(e["intent"] for e in entries)
    # 按结果
    by_result = Counter(e["result"] for e in entries)
    # 平均耗时
    durations = [e.get("duration_ms", 0) for e in entries if e.get("duration_ms")]
    avg_duration = sum(durations) / len(durations) if durations else 0

    lines.append(f"  总记录: {len(entries)} 条")
    lines.append(f"  平均耗时: {avg_duration:.0f}ms")
    lines.append("")

    lines.append("  按入口:")
    for entry, count in by_entry.most_common():
        bar = "█" * count + "░" * (10 - min(count, 10))
        lines.append(f"    {entry:20s}  {count:3d} 次  {bar}")

    lines.append("")
    lines.append("  按意图:")
    for intent, count in by_intent.most_common():
        lines.append(f"    {intent:25s}  {count:3d} 次")

    lines.append("")
    lines.append("  按结果:")
    for result, count in by_result.most_common():
        icon = {"pass": "✅", "fail": "❌", "warn": "⚠️"}.get(result, "?")
        lines.append(f"    {icon} {result:10s}  {count:3d} 次")

    lines.append("")
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 L3 入口价值对比")
    parser.add_argument("--entry", type=str, help="入口类型 (claude_id / claude_code / codex / hermes / wechat / api)")
    parser.add_argument("--intent", type=str, help="意图分类 (governance_check / task_execution / knowledge_retrieval / domain_work)")
    parser.add_argument("--result", type=str, default="pass", help="结果 (pass/fail/warn)")
    parser.add_argument("--duration", type=int, default=0, help="耗时 ms")
    parser.add_argument("--detail", type=str, default="", help="补充信息")
    parser.add_argument("--report", action="store_true", help="查看入口统计报告")
    parser.add_argument("--watch", action="store_true", help="监听模式(每30s)")  # noqa: ARG001
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.report:
        entries = read_entries(100)
        if args.json:
            print(json.dumps(entries, ensure_ascii=False, indent=2))
        else:
            print(format_report(entries))
        return

    if args.entry:
        event = log_entry(args.entry, args.intent, args.result, args.duration, args.detail)
        if args.json:
            print(json.dumps(event, ensure_ascii=False, indent=2))
        else:
            print(f"  ✅ 入口已记录: {args.entry}/{args.intent} → {args.result}")
        return

    # 默认: 显示报告
    entries = read_entries(50)
    print(format_report(entries))


if __name__ == "__main__":
    main()
