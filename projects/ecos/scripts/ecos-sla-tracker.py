#!/usr/bin/env python3
"""
eCOS v5 Phase 7.6 — 健康 SLA 追踪器 (ecos-sla-tracker)
==========================================================
追踪 daemon 健康检查的历史记录，计算 uptime 和趋势。

用法:
    python3 ecos-sla-tracker.py              # 显示当前 SLA
    python3 ecos-sla-tracker.py --log result # 记录一次检查结果
    python3 ecos-sla-tracker.py --json
"""

import sys
import json
import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from collections import deque


SLA_DIR = Path.home() / ".ecos" / "sla"
SLA_FILE = SLA_DIR / "history.jsonl"
MAX_HISTORY = 100  # 保留最近 100 条记录


def init_sla():
    SLA_DIR.mkdir(parents=True, exist_ok=True)


def log_check(result: str, dim: str = "overall", detail: str = ""):
    """记录一次检查结果"""
    init_sla()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "dimension": dim,
        "detail": detail,
    }
    with open(SLA_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # 保留最近记录
    with open(SLA_FILE, "r") as f:
        lines = f.readlines()
    if len(lines) > MAX_HISTORY:
        with open(SLA_FILE, "w") as f:
            f.writelines(lines[-MAX_HISTORY:])

    return entry


def read_history() -> list[dict]:
    """读取历史记录"""
    init_sla()
    if not SLA_FILE.exists():
        return []
    entries = []
    with open(SLA_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def compute_sla(entries: list[dict]) -> dict:
    """计算 SLA 指标"""
    if not entries:
        return {
            "uptime": None, "consecutive_passes": 0,
            "consecutive_failures": 0, "total": 0, "passes": 0,
            "failures": 0, "last_failure": None, "last_check": None,
        }

    total = len(entries)
    passes = sum(1 for e in entries if e.get("result") == "pass")
    failures = total - passes

    # 连续通过/失败
    consecutive_passes = 0
    consecutive_failures = 0
    for e in reversed(entries):
        if e.get("result") == "pass":
            consecutive_passes += 1
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            consecutive_passes = 0

    # 最近失败
    last_failure = None
    for e in reversed(entries):
        if e.get("result") != "pass":
            last_failure = {
                "timestamp": e.get("timestamp"),
                "dimension": e.get("dimension"),
                "detail": e.get("detail"),
            }
            break

    return {
        "uptime": round(passes / total * 100, 1) if total > 0 else 0,
        "consecutive_passes": consecutive_passes,
        "consecutive_failures": consecutive_failures,
        "total": total,
        "passes": passes,
        "failures": failures,
        "last_failure": last_failure,
        "last_check": entries[-1]["timestamp"] if entries else None,
        "first_check": entries[0]["timestamp"] if entries else None,
    }


def format_report(sla: dict) -> str:
    """格式化 SLA 报告"""
    lines = []
    lines.append("=" * 56)
    lines.append("  eCOS v5 — 健康 SLA 报告")
    lines.append("=" * 56)

    if sla["total"] == 0:
        lines.append("  暂无数据 — 运行 daemon 后自动累积")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"  总检查次数: {sla['total']}")
    lines.append(f"  通过: {sla['passes']}  失败: {sla['failures']}")
    lines.append("")

    # uptime 条
    uptime_bar = "█" * int(sla["uptime"] / 10) + "░" * (10 - int(sla["uptime"] / 10))
    lines.append(f"  Uptime: {sla['uptime']}% [{uptime_bar}]")

    # 连续通过
    lines.append(f"  连续通过: {sla['consecutive_passes']} 次  "
                 f"(最差: {sla['consecutive_failures']} 次连续失败)")
    lines.append("")

    if sla["last_failure"]:
        lines.append(f"  最近失败:")
        lines.append(f"    {sla['last_failure']['timestamp'][:19]} "
                     f"[{sla['last_failure']['dimension']}] "
                     f"{sla['last_failure']['detail'][:60]}")
    else:
        lines.append("  ✅ 最近失败: 无")

    if sla["first_check"] and sla["last_check"]:
        from datetime import datetime
        try:
            first = datetime.fromisoformat(sla["first_check"])
            last = datetime.fromisoformat(sla["last_check"])
            span = (last - first).total_seconds() / 3600
            lines.append(f"  追踪时段: {span:.1f} 小时 ({sla['first_check'][:10]} ~ {sla['last_check'][:10]})")
        except (ValueError, TypeError):
            pass

    lines.append("")
    lines.append("=" * 56)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 健康 SLA 追踪器")
    parser.add_argument("--log", type=str, choices=["pass", "fail", "warn"],
                        help="记录一次检查结果")
    parser.add_argument("--dim", type=str, default="overall", help="维度")
    parser.add_argument("--detail", type=str, default="", help="详情")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.log:
        entry = log_check(args.log, args.dim, args.detail)
        if args.json:
            print(json.dumps(entry, ensure_ascii=False, indent=2))
        else:
            print(f"  ✅ 已记录: {args.log}/{args.dim}")
        return

    entries = read_history()
    sla = compute_sla(entries)

    if args.json:
        print(json.dumps(sla, ensure_ascii=False, indent=2))
    else:
        print(format_report(sla))


if __name__ == "__main__":
    main()
