#!/usr/bin/env python3
"""weekly-ecosystem-report — 周度生态健康报告。

每周运行一次，生成 Skills/Workflows/Scripts/Governance 生态健康报告。
输出到 docs/generated/ecosystem-health.md。

Usage:
    python3 bin/gac/weekly-ecosystem-report.py [--output <path>] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO / "docs/generated/ecosystem-health.md"


def run_ecosystem_doctor() -> dict:
    """运行 ecosystem-doctor。"""
    result = subprocess.run(
        ["python3", "bin/gac/ecosystem-doctor.py", "--json"],
        capture_output=True, text=True, cwd=REPO,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"overall": "ERROR", "error": result.stderr}


def generate_markdown(report: dict) -> str:
    """生成 Markdown 报告。"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Ecosystem Health Report",
        "",
        f"> Generated: {now}",
        f"> Overall: **{report.get('overall', 'UNKNOWN')}**",
        "",
    ]

    for scope, data in report.get("scopes", {}).items():
        status = data.get("status", "unknown")
        icon = "✅" if status == "ok" else "⚠️"
        lines.append(f"## {icon} {scope.title()}")
        lines.append("")
        lines.append(f"- Status: {status}")

        if "total" in data:
            lines.append(f"- Total: {data['total']}")
        if "with_skill_md" in data:
            lines.append(f"- With SKILL.md: {data['with_skill_md']}/{data['total']}")
        if "runs" in data:
            lines.append(f"- Runs: {data['runs']}")
        if "registered" in data:
            lines.append(f"- Registered: {data['registered']}")

        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    lines.append("1. Review unregistered scripts and register or archive")
    lines.append("2. Clean up blocked workflow runs")
    lines.append("3. Activate or retire silent workflows")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="周度生态健康报告")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run_ecosystem_doctor()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    md = generate_markdown(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")

    print(f"Report written to: {args.output}")
    print(f"Overall: {report.get('overall', 'UNKNOWN')}")

    return 0 if report.get("overall") == "HEALTHY" else 1


if __name__ == "__main__":
    sys.exit(main())
