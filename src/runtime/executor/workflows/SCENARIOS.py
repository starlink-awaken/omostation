#!/usr/bin/env python3
# ---  # noqa: N999
# domain: workflows
# layer: tool
# status: active
# ---
"""Named scenario registry — user-facing workflow combinations."""
from __future__ import annotations

SCENARIOS: dict[str, dict] = {
    "standard": {
        "name": "标准管线",
        "desc": "知识采集 → 冲突审议 → 智能分析",
        "steps": ["ingest", "council", "analyze"],
        "complexity": 3,
    },
    "quick-analysis": {
        "name": "快速分析",
        "desc": "仅智能分析，跳过采集和审议",
        "steps": ["analyze"],
        "complexity": 1,
    },
    "full-review": {
        "name": "完整审查",
        "desc": "采集 → 审议 → 分析 → 感知 → 反思",
        "steps": ["ingest", "council", "analyze", "perceive", "reflect"],
        "complexity": 5,
    },
    "learning-cycle": {
        "name": "学习循环",
        "desc": "分析现有知识 → 反思提炼模式",
        "steps": ["analyze", "reflect"],
        "complexity": 3,
    },
    "knowledge-refresh": {
        "name": "知识刷新",
        "desc": "采集新数据 → 外部感知 → 分析更新",
        "steps": ["ingest", "perceive", "analyze"],
        "complexity": 2,
    },
    "deep-analysis": {
        "name": "深度本质分析",
        "desc": "第一性原理拆解 → 智能分析 → 反思提炼",
        "steps": ["first_principles", "analyze", "reflect"],
        "complexity": 4,
    },
}


def list_scenarios() -> str:
    lines = ["Available scenarios:", ""]
    for slug, s in SCENARIOS.items():
        lines.append(
            f"  {slug:20s} | {'★' * s['complexity']}{'☆' * (5 - s['complexity'])} | {s['desc']}"
        )
    return "\n".join(lines)
