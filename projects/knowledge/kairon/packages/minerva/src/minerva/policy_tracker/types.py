"""Policy Tracker 类型定义 — PolicyItem dataclass。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PolicyItem:
    """单条卫生政策条目。"""

    title: str
    issuing_agency: str  # "国家卫健委" | "国家医保局" | "国家药监局"
    doc_number: str  # 政策文号
    published_at: str  # YYYY-MM-DD
    summary: str  # 200 字以内
    url: str
    tags: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
