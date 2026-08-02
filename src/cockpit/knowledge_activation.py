"""知识激活引擎 — 根据工作上下文推荐 KOS 知识.

触发场景:
    - 写周报/研究时 → 检索相关 KOS 文档
    - 写公文时 → 推荐相关法规/格式规范
    - 日常笔记时 → 推荐相关历史笔记
"""

from __future__ import annotations

from enum import StrEnum

from cockpit.brain_core import kos_search


class ActivationContext(StrEnum):
    """知识激活触发场景."""

    WEEKLY_REPORT = "weekly_report"
    DOCUMENT = "document"
    NOTE = "note"
    RESEARCH = "research"


# 场景 → 搜索 query 模板
_QUERY_TEMPLATES: dict[ActivationContext, str] = {
    ActivationContext.WEEKLY_REPORT: "周报 工作总结 进展 计划 {content}",
    ActivationContext.DOCUMENT: "公文 格式 规范 法规 {content}",
    ActivationContext.NOTE: "笔记 相关 参考 {content}",
    ActivationContext.RESEARCH: "研究 调研 方法论 分析 {content}",
}

# 场景 → 显示名称
_CONTEXT_LABELS: dict[ActivationContext, str] = {
    ActivationContext.WEEKLY_REPORT: "周报",
    ActivationContext.DOCUMENT: "公文",
    ActivationContext.NOTE: "笔记",
    ActivationContext.RESEARCH: "研究",
}


def recommend_for_context(
    context_type: ActivationContext,
    content: str = "",
    limit: int = 5,
    user: str | None = None,
) -> list[dict]:
    """根据当前工作上下文推荐相关知识.

    Args:
        context_type: 触发场景类型
        content: 当前工作内容（可选，用于增强搜索）
        limit: 返回结果数量上限
        user: 用户标识（可选，用于偏好注入）

    Returns:
        推荐结果列表，每项包含 id, title, score, snippet
    """
    template = _QUERY_TEMPLATES.get(context_type, "{content}")
    query = template.format(content=content[:100] if content else "")

    # 偏好注入: 如果有用户偏好，追加关键词 (Phase 49 T1)
    if user:
        try:
            from cockpit.brain_core import get_preferences

            prefs = get_preferences(user=user, top_n=3)
            if prefs:
                pref_keywords = " ".join([p["value"] for p in prefs if p.get("value")])
                if pref_keywords:
                    query = f"{query} {pref_keywords}"
        except Exception:
            pass  # 偏好加载失败时静默降级

    # 低分过滤阈值
    score_threshold = 0.2

    result = kos_search(query, limit=limit)
    results = result.get("results", [])

    # 过滤低分结果 (Phase 49 T1)
    filtered = [r for r in results if (r.get("score") or 0) >= score_threshold or r.get("score") is None]

    return filtered or results  # 若全被过滤则返回原始结果


def format_recommendations(results: list[dict], context_type: ActivationContext) -> str:
    """格式化推荐结果为 CLI 输出."""
    if not results:
        return ""

    label = _CONTEXT_LABELS.get(context_type, "相关")
    lines = [f"📚 {label}知识推荐:"]

    for i, r in enumerate(results[:5], 1):
        title = r.get("title") or r.get("name") or "未知文档"
        score = r.get("score")
        score_str = f" ({score:.2f})" if isinstance(score, (int, float)) else ""
        snippet = (r.get("snippet") or r.get("content") or "")[:80]
        lines.append(f"  {i}. {title}{score_str}")
        if snippet:
            lines.append(f"     {snippet}")

    return "\n".join(lines)


def get_top_suggestions(
    context_type: ActivationContext,
    content: str = "",
    limit: int = 3,
) -> list[str]:
    """获取 top N 推荐文档标题（简洁接口）."""
    results = recommend_for_context(context_type, content, limit=limit)
    return [r.get("title") or r.get("name") or "" for r in results if r.get("title") or r.get("name")]
