"""Kronos Insight Engine — 知识洞察引擎。

新内容导入后，自动触发洞察生成。
三层结构: 同化(Assimilate) → 连接(Connect) → 生成(Generate)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from kronos.config import get_config  # type: ignore[import-not-found]

CONCEPTS_DIR = os.path.join(get_config().vault_path, "99-系统", "knowledge", "concepts")


@dataclass
class InsightReport:
    """洞察报告"""

    source: str = ""
    matched_concepts: list[dict] = field(default_factory=list)
    new_concepts: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    inspirations: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    updated_files: list[str] = field(default_factory=list)


def scan_concepts() -> list[dict]:
    """扫描已有概念节点"""
    if not os.path.isdir(CONCEPTS_DIR):
        return []
    concepts = []
    for f in sorted(os.listdir(CONCEPTS_DIR)):
        if not f.endswith(".md"):
            continue
        path = os.path.join(CONCEPTS_DIR, f)
        with open(path) as fh:
            content = fh.read()
        title = ""
        tags = []
        for line in content.split("\n"):
            if line.startswith("title:"):
                title = line.replace("title:", "").strip().strip('"')
            if line.startswith("  - concept/"):
                tags.append(line.strip())
        concepts.append(
            {
                "name": f.replace(".md", ""),
                "title": title or f.replace(".md", ""),
                "path": path,
                "tags": tags,
                "word_count": len(content),
            }
        )
    return concepts


def match_concepts(text: str, concepts: list[dict]) -> dict:
    """将新文本与已有概念匹配（字符串包含 + fuzzy 双重匹配）"""
    matched = []
    keywords = []
    text_lower = text.lower()

    for c in concepts:
        name_lower = c["name"].replace("-", " ").lower()
        # 精确包含匹配
        if name_lower in text_lower:
            matched.append({**c, "match_type": "直接提及", "confidence": "high"})
            keywords.append(c["name"])
            continue
        # fuzzy 匹配（处理拼写变体/中英文混排）
        try:
            from rapidfuzz import fuzz  # type: ignore[import-not-found]

            words = text_lower.split()
            for w in words:
                if fuzz.ratio(name_lower, w) >= 85:
                    matched.append({**c, "match_type": "模糊匹配", "confidence": "medium"})
                    keywords.append(c["name"])
                    break
        except ImportError:
            pass

    return {
        "matched": matched,
        "unmatched": [c for c in concepts if c not in matched],
        "keywords": keywords,
    }


def generate_insight(
    title: str,
    content: str,
    content_type: str = "文章",
    importance: str = "medium",
) -> InsightReport:
    """生成洞察报告"""
    report = InsightReport(source=title)
    concepts = scan_concepts()

    if not concepts:
        report.gaps.append("尚无概念库，请先创建 99-系统/knowledge/concepts/")
        return report

    # Assimilate
    match_result = match_concepts(f"{title} {content[:2000]}", concepts)
    report.matched_concepts = match_result["matched"]

    # 新概念检测
    if not match_result["matched"]:
        # 没有任何匹配 → 可能是一个全新方向
        report.new_concepts.append("可能的新概念领域（无匹配）")

    # Connect - 弱信号检测
    weak_signals = [
        c
        for c in match_result["unmatched"]
        if any(w in c["name"].replace("-", " ") for w in ["agent", "skill", "model"])
    ]
    for s in weak_signals[:3]:
        report.patterns.append(f"弱关联: {s['title']}")

    # Generate
    if importance == "high":
        report.inspirations.append(f"{title} 是高质量内容，建议提取核心概念写入 concepts/")
        report.inspirations.append("建议运行 Eidos 校验确认实体合法性")

    if content_type == "论文":
        report.patterns.append("论文类内容，建议走 deep-read 管线精读")

    # 矛盾检测
    for c in match_result["matched"]:
        if c.get("tags") and "stable" in str(c["tags"]):
            report.contradictions.append(f"新内容可能与 {c['title']} (stable) 存在冲突或补充关系，需人工判断")

    return report


def format_insight_report(report: InsightReport) -> str:
    """格式化洞察报告"""
    lines = []
    lines.append("────────────────────────────")
    lines.append("💡 洞察报告")
    lines.append("────────────────────────────")
    lines.append("")
    lines.append(f"📥 来源: {report.source}")

    if report.matched_concepts:
        lines.append(f"\n🔗 已有概念匹配 ({len(report.matched_concepts)}):")
        for c in report.matched_concepts[:5]:
            lines.append(f"  • {c['title']} — {c.get('match_type', '匹配')}")

    if report.new_concepts:
        lines.append(f"\n⚡ 新概念 ({len(report.new_concepts)}):")
        for nc in report.new_concepts:
            lines.append(f"  • {nc}")

    if report.contradictions:
        lines.append(f"\n🔍 矛盾 ({len(report.contradictions)}):")
        for cont in report.contradictions:
            lines.append(f"  • {cont}")

    if report.gaps:
        lines.append(f"\n📋 缺口 ({len(report.gaps)}):")
        for g in report.gaps:
            lines.append(f"  • {g}")

    if report.patterns:
        lines.append(f"\n🔄 模式 ({len(report.patterns)}):")
        for p in report.patterns:
            lines.append(f"  • {p}")

    if report.inspirations:
        lines.append(f"\n💡 灵感 ({len(report.inspirations)}):")
        for i in report.inspirations:
            lines.append(f"  • {i}")

    lines.append("")
    lines.append("📎 建议操作:")
    if report.matched_concepts:
        lines.append("  • 检查匹配概念的引用是否需要更新")
    lines.append("  • 新概念写入 99-系统/knowledge/concepts/")
    lines.append("  • 更新 _index.md 域索引")
    lines.append("────────────────────────────")

    return "\n".join(lines)
