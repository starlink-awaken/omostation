#!/usr/bin/env python3
"""Health Agent — 健康域感知+认知 agent.

扫描 Documents/_inbox/ 中的健康巡检报告,
LLM 分析趋势, 生成周度健康摘要.

Usage:
  python3 bin/ssot/health_agent.py              # 扫描+分析
  python3 bin/ssot/health_agent.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from _shared import utc_now
from _llm_helper import llm_ask

INBOX = Path.home() / "Documents" / "_inbox"
HEALTH_KEYWORDS = ["健康巡检", "health", "卫健委", "vault-health", "weijian"]


def scan_health_reports() -> list[dict[str, Any]]:
    """扫描 _inbox/ 中的健康报告."""
    reports = []
    if not INBOX.exists():
        return reports

    for f in sorted(INBOX.glob("*.md"), reverse=True):
        if not any(kw in f.name.lower() for kw in HEALTH_KEYWORDS):
            continue
        try:
            content = f.read_text(encoding="utf-8")[:1000]
            # 提取状态标记
            status_match = re.search(r"系统状态\s*\*\*(🟢|🟡|🔴)\*", content)
            status = status_match.group(1) if status_match else "❓"

            # 提取预警数
            warn_match = re.search(r"预警\s*(\d+)", content)
            warnings = int(warn_match.group(1)) if warn_match else 0

            # 提取正常数
            ok_match = re.search(r"正常\s*(\d+)", content)
            ok_count = int(ok_match.group(1)) if ok_match else 0

            reports.append({
                "file": f.name,
                "date": f.name[:10] if f.name[0:4].isdigit() else "",
                "status": status,
                "warnings": warnings,
                "ok": ok_count,
                "summary": content[:200],
            })
        except Exception:
            continue
        if len(reports) >= 10:
            break
    return reports


def analyze_trends(reports: list[dict]) -> dict[str, Any]:
    """LLM 分析健康趋势."""
    if not reports:
        return {"trend": "no_data", "analysis": "无健康报告数据"}

    # 准备数据摘要
    summary_lines = []
    for r in reports[:7]:
        summary_lines.append(
            f"- {r['date']} {r['status']} 预警:{r['warnings']} 正常:{r['ok']}"
        )

    prompt = (
        f"你是系统健康分析助手。以下是最近 {len(reports)} 天的健康巡检数据:\n"
        + "\n".join(summary_lines)
        + "\n\n请分析:\n"
        f"1. 整体趋势 (好转/稳定/恶化)\n"
        f"2. 主要风险点\n"
        f"3. 建议 (一句话)\n"
        f"输出 JSON: {{\"trend\":\"...\",\"risk\":\"...\",\"advice\":\"...\"}}"
    )

    response = llm_ask(prompt, timeout=30.0)
    if not response:
        return {"trend": "unknown", "analysis": "LLM 无响应"}

    m = re.search(r'\{[^{}]*"trend"[^{}]*\}', response)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return {"trend": "unknown", "analysis": response[:200]}


def generate_health_briefing(reports: list[dict], analysis: dict) -> str:
    """生成健康周报 Markdown."""
    date_str = utc_now()[:10]
    lines = [
        f"# 🏥 健康巡检摘要 — {date_str}",
        "",
        f"> 生成时间: {utc_now()}",
        f"> 报告数: {len(reports)}",
        "",
    ]

    # 状态分布
    status_counts = {}
    for r in reports:
        s = r["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    lines.append("## 📊 状态分布")
    for status, count in sorted(status_counts.items()):
        lines.append(f"- {status}: {count}天")
    lines.append("")

    # 最近报告
    lines.append("## 📋 最近报告")
    for r in reports[:5]:
        lines.append(f"- {r['date']} {r['status']} — 预警:{r['warnings']} 正常:{r['ok']}")
    lines.append("")

    # AI 分析
    lines.append("## 🧠 AI 趋势分析")
    lines.append(f"- **趋势**: {analysis.get('trend', '?')}")
    if analysis.get("risk"):
        lines.append(f"- **风险**: {analysis['risk']}")
    if analysis.get("advice"):
        lines.append(f"- **建议**: {analysis['advice']}")
    lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    reports = scan_health_reports()
    analysis = analyze_trends(reports)

    if args.json:
        print(json.dumps({"reports": reports, "analysis": analysis, "scanned_at": utc_now()}, ensure_ascii=False, indent=2))
    else:
        briefing = generate_health_briefing(reports, analysis)
        INBOX.mkdir(parents=True, exist_ok=True)
        path = INBOX / f"{utc_now()[:10]}-health-briefing.md"
        path.write_text(briefing, encoding="utf-8")
        print(f"✅ 健康摘要: {path}")
        print(f"   报告: {len(reports)} | 趋势: {analysis.get('trend', '?')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
