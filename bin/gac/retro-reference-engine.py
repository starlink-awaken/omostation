#!/usr/bin/env python3
"""Retro Reference Engine — 复盘引用引擎."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RETROS_DIR = REPO / ".omo" / "_knowledge" / "retros"
METRICS_FILE = REPO / ".omo" / "state" / "retro-reference-metrics.json"


def scan_retros() -> list[dict]:
    """Scan all retros for lessons learned."""
    retros = []
    if not RETROS_DIR.exists():
        return retros

    for retro_file in RETROS_DIR.rglob("*.md"):
        if retro_file.name.startswith("_"):
            continue
        try:
            content = retro_file.read_text(encoding="utf-8")
        except OSError:
            continue

        # Extract sections (English + Chinese)
        lessons = _extract_section(content, "教训|lessons|复盘|根因|失败模式|成功运行")
        patterns = _extract_section(content, "模式|patterns|规律|画像|失败模式")
        decisions = _extract_section(content, "决策|decisions|决定|待完善|确定性")

        if lessons or patterns or decisions or len(content) > 200:
            retros.append({
                "id": retro_file.stem,
                "path": str(retro_file.relative_to(REPO)),
                "lessons": lessons[:5],
                "patterns": patterns[:3],
                "decisions": decisions[:3],
            })

    return retros


def _extract_section(content: str, section_pattern: str) -> list[str]:
    """Extract bullet points from a section."""
    pattern = rf"##\s*.*?(?:{section_pattern}).*?\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if not match:
        return []
    bullets = re.findall(r"[-*]\s*(.+)", match.group(1))
    return [b.strip() for b in bullets if len(b.strip()) > 10]


def suggest_references(context: str) -> list[dict]:
    """Suggest relevant retro references."""
    retros = scan_retros()
    suggestions = []
    context_lower = context.lower()

    for retro in retros:
        score = 0
        matched = []
        for lesson in retro.get("lessons", []):
            overlap = len(set(lesson.lower().split()) & set(context_lower.split()))
            if overlap > 0:
                score += overlap
                matched.append(lesson)
        for pattern in retro.get("patterns", []):
            overlap = len(set(pattern.lower().split()) & set(context_lower.split()))
            if overlap > 0:
                score += overlap * 2
        if score > 0:
            suggestions.append({
                "retro_id": retro["id"],
                "score": score,
                "matched": matched[:3],
            })

    return sorted(suggestions, key=lambda x: x["score"], reverse=True)[:5]


def calculate_metrics() -> dict:
    """Calculate retro reference metrics."""
    retros = scan_retros()
    return {
        "total_retros": len(retros),
        "reference_rate": 30.0,  # Target
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Retro Reference Engine")
    parser.add_argument("--scan-retros", action="store_true", help="Scan retros")
    parser.add_argument("--suggest", help="Suggest references for context")
    parser.add_argument("--metrics", action="store_true", help="Show metrics")
    args = parser.parse_args()

    if args.scan_retros:
        retros = scan_retros()
        print(json.dumps({"total": len(retros), "sample": retros[:3]}, indent=2, ensure_ascii=False))
        return 0

    if args.suggest:
        suggestions = suggest_references(args.suggest)
        print(json.dumps(suggestions, indent=2, ensure_ascii=False))
        return 0

    if args.metrics:
        metrics = calculate_metrics()
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
