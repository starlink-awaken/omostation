"""
model_driven.toolchain.mof_extract — 资产 → M1 逆向提炼

从现有资产中自动识别和提炼 M1 节点 (lessons/decisions/conventions/specs)。
移植自 ecos/ssot/tools/mof-extract.py，改为纯函数 + 可配置路径模式。

提炼类型:
  1. Lesson — 从复盘/经验文档中提炼教训
  2. Decision — 从架构决策文档中提炼 ADR
  3. Convention — 从代码规范/标准中提炼约定
  4. Specification — 从 CLAUDE.md/AGENTS.md 中提炼规范
  5. Pattern — 从代码模式中提炼设计模式
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ExtractResult:
    """提炼结果"""

    source: str
    extracted_type: str
    nodes: list[dict[str, Any]]
    confidence: float = 0.0  # 0.0-1.0


def extract_lessons_from_markdown(
    file_path: str | Path,
    section_patterns: list[str] | None = None,
) -> ExtractResult:
    """从 Markdown 文件中提炼 Lesson 节点

    识别复盘/经验/教训类文档中的结构化内容。
    """
    path = Path(file_path)
    if not path.exists():
        return ExtractResult(source=str(path), extracted_type="lesson", nodes=[])

    section_patterns = section_patterns or [
        "教训", "经验", "复盘", "问题", "修复", "Lesson", "Root Cause",
        "根因", "原因", "解决方案", "预防措施",
    ]

    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return ExtractResult(source=str(path), extracted_type="lesson", nodes=[])

    nodes = []
    lines = content.split("\n")
    current_section = ""
    current_content: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("##") or stripped.startswith("###"):
            # 保存上一个 section
            if current_section and current_content:
                if any(pat in current_section for pat in section_patterns):
                    nodes.append({
                        "id": f"LESSON-EXTRACT-{path.stem}-{len(nodes):03d}",
                        "type": "lesson",
                        "name": current_section.strip("# "),
                        "description": "\n".join(current_content[:5]),
                        "status": "recorded",
                        "source": str(path),
                        "created": now(),
                        "version": "1.0.0",
                        "properties": {
                            "source_file": str(path),
                            "section": current_section.strip("# "),
                            "content_preview": "\n".join(current_content[:3]),
                        },
                    })
            current_section = stripped
            current_content = []
        else:
            current_content.append(line)

    # 最后一个 section
    if current_section and current_content:
        if any(pat in current_section for pat in section_patterns):
            nodes.append({
                "id": f"LESSON-EXTRACT-{path.stem}-{len(nodes):03d}",
                "type": "lesson",
                "name": current_section.strip("# "),
                "description": "\n".join(current_content[:5]),
                "status": "recorded",
                "source": str(path),
                "created": now(),
                "version": "1.0.0",
                "properties": {
                    "source_file": str(path),
                    "section": current_section.strip("# "),
                },
            })

    confidence = min(len(nodes) / 5.0, 1.0) if nodes else 0.0
    return ExtractResult(
        source=str(path),
        extracted_type="lesson",
        nodes=nodes,
        confidence=confidence,
    )


def extract_decisions_from_markdown(
    file_path: str | Path,
) -> ExtractResult:
    """从 Markdown 文件中提炼 Decision/ADR 节点"""
    path = Path(file_path)
    if not path.exists():
        return ExtractResult(source=str(path), extracted_type="decision", nodes=[])

    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return ExtractResult(source=str(path), extracted_type="decision", nodes=[])

    nodes = []
    decision_patterns = [
        "决策", "决定", "Decision", "ADR", "选择", "方案",
    ]

    lines = content.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("##") or stripped.startswith("###"):
            if any(pat in stripped for pat in decision_patterns):
                # 提取后续内容作为决策描述
                desc_lines = []
                for j in range(i + 1, min(i + 10, len(lines))):
                    nl = lines[j].strip()
                    if nl.startswith("##") or nl.startswith("###"):
                        break
                    if nl:
                        desc_lines.append(nl)

                if desc_lines:
                    nodes.append({
                        "id": f"DECISION-EXTRACT-{path.stem}-{len(nodes):03d}",
                        "type": "decision",
                        "name": stripped.strip("# ")[:80],
                        "description": " ".join(desc_lines[:3])[:200],
                        "status": "proposed",
                        "source": str(path),
                        "created": now(),
                        "version": "1.0.0",
                        "properties": {
                            "source_file": str(path),
                            "title": stripped.strip("# "),
                            "content": " ".join(desc_lines[:5]),
                        },
                    })

    confidence = min(len(nodes) / 3.0, 1.0) if nodes else 0.0
    return ExtractResult(
        source=str(path),
        extracted_type="decision",
        nodes=nodes,
        confidence=confidence,
    )


def extract_specs_from_agent_contract(
    file_path: str | Path,
) -> ExtractResult:
    """从 Agent 契约文件 (CLAUDE.md/AGENTS.md) 中提炼 Specification 节点"""
    path = Path(file_path)
    if not path.exists():
        return ExtractResult(source=str(path), extracted_type="specification", nodes=[])

    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return ExtractResult(source=str(path), extracted_type="specification", nodes=[])

    nodes = []
    lines = content.split("\n")
    current_rules: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            current_rules.append(stripped[2:])
        elif stripped.startswith("##") and current_rules:
            if len(current_rules) >= 3:
                nodes.append({
                    "id": f"SPEC-EXTRACT-{path.stem}-{len(nodes):03d}",
                    "type": "specification",
                    "name": f"规则组: {path.name}",
                    "description": f"从 {path.name} 提炼的规范组",
                    "status": "active",
                    "source": str(path),
                    "created": now(),
                    "version": "1.0.0",
                    "properties": {
                        "source_file": str(path),
                        "rules": current_rules.copy(),
                        "rule_count": len(current_rules),
                    },
                })
            current_rules = []

    confidence = min(len(nodes) / 2.0, 1.0) if nodes else 0.0
    return ExtractResult(
        source=str(path),
        extracted_type="specification",
        nodes=nodes,
        confidence=confidence,
    )


def extract_all(
    directory: str | Path,
    file_pattern: str = "*.md",
    extract_lessons: bool = True,
    extract_decisions: bool = True,
    extract_specs: bool = True,
) -> dict[str, Any]:
    """统一提炼入口 — 从目录中批量提炼 M1 节点"""
    root = Path(directory)
    if not root.exists():
        return {"success": False, "error": f"目录不存在: {root}"}

    all_results: list[ExtractResult] = []

    for md_file in sorted(root.rglob(file_pattern)):
        if "__pycache__" in str(md_file) or ".venv" in str(md_file):
            continue

        if extract_lessons:
            result = extract_lessons_from_markdown(md_file)
            if result.nodes:
                all_results.append(result)

        if extract_decisions:
            result = extract_decisions_from_markdown(md_file)
            if result.nodes:
                all_results.append(result)

        if extract_specs and md_file.name in ("CLAUDE.md", "AGENTS.md", "CODEBUDDY.md"):
            result = extract_specs_from_agent_contract(md_file)
            if result.nodes:
                all_results.append(result)

    total_nodes = sum(len(r.nodes) for r in all_results)
    by_type: dict[str, int] = {}
    for r in all_results:
        by_type[r.extracted_type] = by_type.get(r.extracted_type, 0) + len(r.nodes)

    return {
        "success": True,
        "total_nodes": total_nodes,
        "by_type": by_type,
        "results": [
            {
                "source": r.source,
                "type": r.extracted_type,
                "count": len(r.nodes),
                "confidence": r.confidence,
            }
            for r in all_results
        ],
        "nodes": [node for r in all_results for node in r.nodes],
        "extracted_at": now(),
    }
