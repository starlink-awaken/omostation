"""Cross-project data adapters — minerva → Eidos schema conversion.

遵循 AGENTS.md 约定：跨项目通信优先 MCP > REST > CLI subprocess > pip import。
此处提供纯数据转换，不直接依赖 Eidos 运行时。
"""

import datetime
import hashlib
from typing import Any

_CARD_CONTENT_MAX = 50000


def _make_card_id(source: str, title: str) -> str:
    """生成稳定的 KnowledgeCard ID（SHA256 前缀）。"""
    raw = f"{source}::{title}"
    return f"KC-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def research_result_to_card(result: Any) -> dict[str, Any]:
    """将 ResearchResult 对象转换为 Eidos KnowledgeCard 兼容的 dict。

    Args:
        result: ResearchResult 实例（或具有 task_id/summary/context 的结构）。

    Returns:
        可通过 KnowledgeCard.validate() 的 dict。
    """
    task_id = getattr(result, "task_id", "unknown")
    context = getattr(result, "context", None)
    query = context.query if context else "Untitled"
    report = context.report if context else None
    summary = getattr(result, "summary", "")

    # 组合 content
    content_parts = []
    if report:
        content_parts.append(report)
    elif summary:
        content_parts.append(summary)
    content = "\n".join(content_parts)[:_CARD_CONTENT_MAX]

    source = f"minerva:research:{task_id}"
    card_id = _make_card_id(source, query)

    return {
        "id": card_id,
        "title": query,
        "content": content,
        "source": source,
        "source_type": "research",
        "schema_type": "KnowledgeCard",
        "tags": ["minerva", f"research-{task_id}"],
        "created_at": getattr(result, "completed_at", "") or datetime.datetime.now().isoformat(),
        "updated_at": "",
    }


def ingest_to_card(
    source: str,
    source_type: str,
    content: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """将知识摄取的内容转换为 Eidos KnowledgeCard 兼容的 dict。

    Args:
        source: 来源 URL 或文件路径。
        source_type: 来源类型（url/pdf/markdown/code）。
        content: 可选，摄取的内容文本。
        title: 可选，提取的标题。

    Returns:
        可通过 KnowledgeCard.validate() 的 dict。
    """
    card_title = title or content.split("\n")[0][:80] if content else source.split("/")[-1]
    card_content = (content or "")[:_CARD_CONTENT_MAX]
    card_id = _make_card_id(source, card_title)

    return {
        "id": card_id,
        "title": card_title,
        "content": card_content,
        "source": source,
        "source_type": source_type or "auto",
        "schema_type": "KnowledgeCard",
        "tags": ["minerva", f"ingest-{source_type}"],
        "created_at": datetime.datetime.now().isoformat(),
        "updated_at": "",
    }
