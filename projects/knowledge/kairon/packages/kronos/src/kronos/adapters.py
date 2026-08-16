"""Cross-project data adapters — kronos → Eidos schema conversion.

遵循 AGENTS.md 约定：跨项目通信优先 MCP > REST > CLI subprocess > pip import。
此处提供纯数据转换，不直接依赖 Eidos 运行时。
"""

import hashlib
from collections.abc import Mapping
from typing import Any

# kronos 内部 content_type → Eidos KnowledgeCard source_type 映射
_CONTENT_TYPE_MAP: dict[str, str] = {
    "文章": "article",
    "论文": "paper",
    "快讯": "news",
    "技术文档": "documentation",
}


def to_knowledge_card(
    extraction: Mapping[str, Any],
    source: str,
    *,
    content: str | None = None,
    source_type: str | None = None,
) -> dict[str, Any]:
    """将 kronos 提取结果转换为 Eidos KnowledgeCard 兼容的 dict。

    Args:
        extraction: extract_with_rules() 或 _default_result() 的输出 dict。
        source: 内容来源标识（URL 或文件名）。
        content: 可选，覆盖自动组合的 content 字段。
        source_type: 可选，覆盖 content_type 映射结果。

    Returns:
        可通过 KnowledgeCard.validate() 的 dict。
    """
    title = extraction.get("title", "未命名") or "未命名"
    summary = extraction.get("summary", "")
    key_points = extraction.get("key_points", [])

    # 生成稳定 ID：source + title 的 SHA256 前缀
    raw_id = f"{source}::{title}"
    card_id = f"KC-{hashlib.sha256(raw_id.encode()).hexdigest()[:12]}"

    # 组合 content：优先使用传入的 content，否则从 summary + key_points 构建
    if content is not None:
        card_content = content
    else:
        parts = [summary] if summary else []
        if key_points:
            parts.append("")
            parts.append("## 要点")
            parts.extend(f"- {p}" for p in key_points)
        card_content = "\n".join(parts)

    # 映射 source_type
    kronos_ct = extraction.get("content_type", "")
    card_source_type = source_type or _CONTENT_TYPE_MAP.get(kronos_ct, "article")

    return {
        "id": card_id,
        "title": title,
        "content": card_content,
        "source": source,
        "source_type": card_source_type,
        "schema_type": "KnowledgeCard",
        "tags": extraction.get("tags", []),
        "created_at": "",
        "updated_at": "",
    }


def to_knowledge_card_from_browser_fetch(
    url: str,
    markdown: str,
    title: str,
    *,
    source_type: str = "article",
) -> dict[str, Any]:
    """将 browser_fetch 结果转换为 Eidos KnowledgeCard 兼容的 dict。

    Args:
        url: 来源 URL。
        markdown: 抓取到的 Markdown 内容。
        title: 提取的标题。
        source_type: 来源类型，默认 "article"。

    Returns:
        可通过 KnowledgeCard.validate() 的 dict。
    """
    raw_id = f"{url}::{title}"
    card_id = f"KC-{hashlib.sha256(raw_id.encode()).hexdigest()[:12]}"

    return {
        "id": card_id,
        "title": title or "Untitled",
        "content": markdown[:30000],
        "source": url,
        "source_type": source_type,
        "schema_type": "KnowledgeCard",
        "tags": [],
        "created_at": "",
        "updated_at": "",
    }
