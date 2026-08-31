#!/usr/bin/env python3
"""Retro Reference Engine — 复盘引用引擎.

提升复盘引用率 (6.7% → 30%):
- 扫描历史复盘中的经验教训
- 自动建议相关引用
- 跟踪引用率

Usage:
    python3 bin/gac/retro-reference-engine.py --scan-retros
    python3 bin/gac/retro-reference-engine.py --suggest <context>
    python3 bin/gac/retro-reference-engine.py --link <retro_id> <target_id>
    python3 bin/gac/retro-reference-engine.py --metrics
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
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

        # Extract key sections (English + Chinese)
        lessons = _extract_section(content, "教训|lessons|复盘|根因|失败模式|成功运行")
        patterns = _extract_section(content, "模式|patterns|规律|画像|失败模式")
        decisions = _extract_section(content, "决策|decisions|决定|待完善|确定性")

        # Include retro if it has any content
        if lessons or patterns or decisions or len(content) > 200:
            retros.append({
                "id": retro_file.stem,
                "path": str(retro_file.relative_to(REPO)),
                "lessons": lessons[:5],
                "patterns": patterns[:3],
                "decisions": decisions[:3],
                "hash": hash(content) % 100000,
            })

    return retros


def _extract_section(content: str, section_pattern: str) -> list[str]:
    """Extract bullet points from a section."""
    # Find section
    pattern = rf"##\s*.*?(?:{section_pattern}).*?\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if not match:
        return []

    # Extract bullets
    bullets = re.findall(r"[-*]\s*(.+)", match.group(1))
    result = [b.strip() for b in bullets if len(b.strip()) > 10]

    # Also extract from YAML frontmatter
    fm_pattern = rf"(?:{section_pattern}).*?:\s*\n((?:\s*[-*].*\n)+)"
    fm_match = re.search(fm_pattern, content, re.DOTALL | re.IGNORECASE)
    if fm_match:
        fm_bullets = re.findall(r"\s*[-*]\s*(.+)", fm_match.group(1))
        result.extend([b.strip() for b in fm_bullets if len(b.strip()) > 10])

    return result


def suggest_references(context: str, retros: list[dict] | None = None) -> list[dict]:
    """Suggest relevant retro references for a given context."""
    if retros is None:
        retros = scan_retros()

    suggestions = []
    context_lower = context.lower()

    for retro in retros:
        score = 0
        matched_lessons = []

        # Check lessons for relevance
        for lesson in retro.get("lessons", []):
            # Simple keyword overlap
            lesson_words = set(lesson.lower().split())
            context_words = set(context_lower.split())
            overlap = len(lesson_words & context_words)
            if overlap > 0:
                score += overlap
                matched_lessons.append(lesson)

        # Check patterns
        for pattern in retro.get("patterns", []):
            pattern_words = set(pattern.lower().split())
            overlap = len(pattern_words & context_words)
            if overlap > 0:
                score += overlap * 2  # Patterns weighted higher

        if score > 0:
            suggestions.append({
                "retro_id": retro["id"],
                "path": retro["path"],
                "score": score,
                "matched_lessons": matched_lessons[:3],
            })

    return sorted(suggestions, key=lambda x: x["score"], reverse=True)[:5]


def link_retro_to_target(retro_id: str, target_id: str) -> dict:
    """Create a link between a retro and a target work item."""
    metrics = _load_metrics()

    link = {
        "retro_id": retro_id,
        "target_id": target_id,
        "linked_at": datetime.now(timezone.utc).isoformat(),
    }

    metrics.setdefault("links", []).append(link)
    _save_metrics(metrics)

    return {"ok": True, "link": link}


def _load_metrics() -> dict:
    if METRICS_FILE.exists():
        try:
            return json.loads(METRICS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"links": [], "references": [], "version": "1.0"}


def _save_metrics(data: dict) -> None:
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    METRICS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def calculate_metrics() -> dict:
    """Calculate retro reference metrics."""
    retros = scan_retros()
    metrics = _load_metrics()

    links = metrics.get("links", [])
    total_retros = len(retros)
    linked_retros = len(set(l["retro_id"] for l in links))

    return {
        "total_retros": total_retros,
        "linked_retros": linked_retros,
        "total_links": len(links),
        "reference_rate": round(linked_retros / total_retros * 100, 1) if total_retros > 0 else 0,
        "target_rate": 30.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Retro Reference Engine")
    parser.add_argument("--scan-retros", action="store_true", help="Scan all retros")
    parser.add_argument("--suggest", help="Suggest references for context")
    parser.add_argument("--link", nargs=2, metavar=("RETRO", "TARGET"), help="Link retro to target")
    parser.add_argument("--metrics", action="store_true", help="Show metrics")
    args = parser.parse_args()

    if args.scan_retros:
        retros = scan_retros()
        print(f"✓ Scanned {len(retros)} retros")
        for r in retros[:10]:
            print(f"  - {r['id']}: {len(r['lessons'])} lessons, {len(r['patterns'])} patterns")
        return 0

    if args.suggest:
        suggestions = suggest_references(args.suggest)
        print(json.dumps(suggestions, indent=2, ensure_ascii=False))
        return 0

    if args.link:
        result = link_retro_to_target(args.link[0], args.link[1])
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.metrics:
        metrics = calculate_metrics()
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
