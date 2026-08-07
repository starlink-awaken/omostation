#!/usr/bin/env python3
"""Governance Summarizer — turn GaC gate reports into readable Markdown summaries.

Usage:
    python3 bin/gac/governance-summarizer.py --report report.json
    python3 bin/gac/governance-summarizer.py --report report.json --llm-endpoint http://localhost:8000/summarize
"""

import argparse
import json
import sys
from pathlib import Path


def summarize_report(report: dict) -> str:
    lines: list[str] = []
    lines.append("# Governance Gate Summary\n")
    status = "PASS" if report.get("ok") else "FAIL"
    lines.append(f"**Status:** {status}\n")
    scope = report.get("scope", "unknown")
    lines.append(f"**Scope:** {scope}\n")
    run_id = report.get("run_id")
    if run_id:
        lines.append(f"**Run ID:** {run_id}\n")

    checks = report.get("checks", [])
    hard_fails = report.get("hard_fails", [])
    soft_warns = report.get("soft_warns", [])
    lines.append(f"**Checks:** {len(checks)} total, {len(hard_fails)} hard fails, {len(soft_warns)} soft warns\n")

    if hard_fails:
        lines.append("## Hard Failures\n")
        for item in hard_fails:
            name = item.get("name", "unknown")
            stderr = item.get("stderr", "")
            stdout = item.get("stdout", "")
            lines.append(f"- **{name}**: {stderr or stdout or 'check failed'}")
        lines.append("")

    if soft_warns:
        lines.append("## Soft Warnings\n")
        for item in soft_warns:
            name = item.get("name", "unknown")
            stderr = item.get("stderr", "")
            stdout = item.get("stdout", "")
            lines.append(f"- **{name}**: {stderr or stdout or 'check warned'}")
        lines.append("")

    topics = report.get("finding_topics", [])
    if topics:
        lines.append("## Finding Topics\n")
        for topic in topics:
            severity = topic.get("severity", "info")
            topic_name = topic.get("topic", "unknown")
            summary = topic.get("summary", "")
            lines.append(f"- [{severity.upper()}] {topic_name}: {summary}")
        lines.append("")

    change_lane = report.get("change_lane_files", [])
    if change_lane:
        lines.append(f"**Change lane files:** {len(change_lane)}\n")

    return "\n".join(lines)


def llm_enhance(summary: str, endpoint: str | None = None) -> str:
    if not endpoint:
        return summary
    try:
        import urllib.request
        payload = json.dumps({"text": summary}).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("summary") or summary
    except Exception:
        return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Governance Summarizer")
    parser.add_argument("--report", required=True, help="Path to gate report JSON")
    parser.add_argument("--llm-endpoint", default="", help="Optional LLM endpoint for summary enhancement")
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.is_file():
        print(f"error: report not found: {report_path}", file=sys.stderr)
        return 1

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON: {exc}", file=sys.stderr)
        return 1

    summary = summarize_report(report)
    if args.llm_endpoint:
        summary = llm_enhance(summary, args.llm_endpoint)
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
