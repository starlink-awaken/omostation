"""Kronos MCP Server (FastMCP) — 知识摄取管线 MCP 接口。

对外暴露 9 个 MCP 工具，供 Agent（Claude Code）调用。
"""

from __future__ import annotations

import sys
from typing import Any

from fastmcp import FastMCP

from kronos.extractor import check_ollama  # type: ignore[import-not-found]
from kronos.fetch_router import (  # type: ignore[import-not-found]
    _extract_title,
    _html_to_markdown,
    _strip_html,
    content_type_label,
    execute_fallback_chain,
    list_all_methods,
    plan_for_url,
)

mcp = FastMCP("kronos-mcp", mask_error_details=True)

FORMAT_VERSION = "kronos-v1"

PIPELINES: dict[str, dict[str, Any]] = {
    "link-pipeline": {
        "description": "单链接处理管线。适用于文章、公众号、博客、推文等",
        "steps": ["抓取", "解析摘要", "实体抽取", "Eidos校验", "分发存档"],
        "when": "用户给了一个链接",
    },
    "deep-read": {
        "description": "深度阅读管线。适用于学术论文、长文、书籍等",
        "steps": ["下载PDF", "全文精读", "结构化抽取", "知识交叉关联", "文献笔记"],
        "when": "用户给了论文/PDF/长文",
    },
    "batch-pipeline": {
        "description": "批量处理管线。适用于一次多个链接",
        "steps": ["收集", "排序", "逐条处理", "合并摘要报告"],
        "when": "用户给了2+个链接",
    },
}


def _error(msg: str) -> dict:
    return {"status": "error", "error": msg, "format_version": FORMAT_VERSION}


def _ok(data: dict) -> dict:
    return {"status": "ok", **data, "format_version": FORMAT_VERSION}


@mcp.tool()
def kronos_status() -> dict:
    """查询 Kronos 服务状态和集成情况。"""
    methods = list_all_methods()
    ollama_ok = check_ollama()
    return _ok(
        {
            "version": "0.4.0",
            "name": "kronos",
            "description": "知识摄取管线 — 6 层抓取引擎",
            "fetch_layers": 6,
            "total_methods": len(methods),
            "ollama_available": ollama_ok,
            "integrations": [
                {"name": "eidos", "purpose": "Schema 校验"},
                {"name": "kos", "purpose": "知识存储与索引"},
                {"name": "vault", "purpose": "Obsidian 知识化输出"},
                {"name": "wps_note", "purpose": "WPS Note 随手查阅"},
                {"name": "ollama", "purpose": "本地 LLM 提取"},
                {"name": "cloakbrowser", "purpose": "浏览器自动化反爬"},
            ],
            "pipeline_count": len(PIPELINES),
        }
    )


@mcp.tool()
def kronos_fetch(url: str) -> dict:
    """获取 URL 的完整 fallback 链方案（只返回方案，不实际抓取）。

    Args:
        url: 要抓取的 URL
    """
    chain = execute_fallback_chain(url)
    ctype = content_type_label(plan_for_url(url).content_type)
    return _ok(
        {
            "url": url,
            "content_type": ctype,
            "fallback_chain": chain,
            "total_layers": len(chain),
        }
    )


@mcp.tool()
def kronos_route(url: str) -> dict:
    """路由决策：分析 URL 类型、推荐管线、分发目标。

    Args:
        url: 要分析的 URL
    """
    chain = execute_fallback_chain(url)
    ctype = content_type_label(plan_for_url(url).content_type)
    recommended = "deep-read" if "paper" in ctype else "link-pipeline"
    dispatch = ["vault (Obsidian)"]
    if ctype in ("文章", "论文", "公众号"):
        dispatch.append("WPS Note")
    if ctype == "论文":
        dispatch.append("KOS (实体更新)")
    return _ok(
        {
            "url": url,
            "content_type": ctype,
            "recommended_pipeline": recommended,
            "dispatch_targets": dispatch,
            "fetch_layers": len(chain),
        }
    )


@mcp.tool()
def kronos_plan(url: str) -> dict:
    """完整的处理计划：URL 的全流程方案。

    Args:
        url: 要规划的 URL
    """
    route = kronos_route(url)
    pipeline = route.get("recommended_pipeline", "link-pipeline")
    return _ok(
        {
            "url": url,
            "plan": [
                {"step": 1, "action": "抓取内容", "method": "使用对应 MCP 工具"},
                {"step": 2, "action": f"走 {pipeline}", "detail": PIPELINES.get(pipeline, {}).get("steps", [])},
                {"step": 3, "action": "Eidos 校验"},
                {"step": 4, "action": "分发存档", "targets": route.get("dispatch_targets", [])},
            ],
            "pipeline": pipeline,
        }
    )


@mcp.tool()
def kronos_browser_fetch(url: str) -> dict:
    """用 CloakBrowser 真实抓取 URL（绕过反爬，需本地 CloakBrowser 环境）。

    Args:
        url: 要抓取的 URL
    """
    try:
        from kronos.fetch_router import _try_cloakbrowser

        content = _try_cloakbrowser(url)
        if content:
            text = _strip_html(content)
            md = _html_to_markdown(content)
            title = _extract_title(content)
            from kronos.adapters import to_knowledge_card_from_browser_fetch  # type: ignore[import-not-found]

            card = to_knowledge_card_from_browser_fetch(url, md, title)
            return _ok(
                {
                    "url": url,
                    "html_length": len(content),
                    "text_length": len(text),
                    "markdown_length": len(md),
                    "title": title,
                    "eidos_card": card,
                }
            )
        return _error("CloakBrowser 抓取失败")
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def kronos_tools() -> dict:
    """列出所有可用的抓取方法。"""
    methods = list_all_methods()
    return _ok({"fetch_methods": methods, "total": len(methods)})


@mcp.tool()
def kronos_pipelines() -> dict:
    """列出所有可用管线及其说明。"""
    result = [{"name": k, **v} for k, v in PIPELINES.items()]
    return _ok({"pipelines": result, "count": len(result)})


@mcp.tool()
def kronos_extract(text: str, source: str = "", content_type: str = "") -> dict:
    """从原始文本提取内容，输出 Eidos KnowledgeCard 兼容格式。

    Args:
        text: 原始文本内容
        source: 来源标识（URL 或文件名）
        content_type: 可选，覆盖 source_type（article/paper/news/documentation）
    """
    if not text:
        return _error("text is required")
    if not source:
        source = f"inline-{hash(text) % 10**8}"
    from kronos.adapters import to_knowledge_card
    from kronos.extractor import extract_with_rules

    extraction = extract_with_rules(text)
    card = to_knowledge_card(extraction, source=source, source_type=content_type or None)
    return _ok({"extraction": extraction, "eidos_card": card})


@mcp.tool()
def kronos_insight(title: str, content: str = "", importance: str = "medium") -> dict:
    """生成洞察报告：新内容 vs 已有概念的匹配/矛盾/缺口/灵感分析。

    Args:
        title: 新内容标题
        content: 新内容摘要/正文
        importance: high/medium/low
    """
    if not title:
        return _error("title is required")
    from kronos.insight_engine import generate_insight  # type: ignore[import-not-found]

    report = generate_insight(title, content, importance=importance)
    return _ok(
        {
            "source": report.source,
            "matched_concepts": len(report.matched_concepts),
            "new_concepts": report.new_concepts,
            "contradictions": report.contradictions,
            "gaps": report.gaps,
            "patterns": report.patterns,
            "inspirations": report.inspirations,
        }
    )


def main() -> None:
    """Run MCP server in stdio mode."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Kronos MCP Server (FastMCP)")
        print(
            "Tools: kronos_fetch, kronos_route, kronos_plan, kronos_status, kronos_tools, kronos_pipelines, kronos_browser_fetch, kronos_extract, kronos_insight"
        )
        return
    check_ollama()
    mcp.run()
