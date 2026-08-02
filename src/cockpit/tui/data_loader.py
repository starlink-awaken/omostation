"""
cockpit.tui.data_loader — TUI 数据加载层

功能:
  · 从 OMO 本地存储加载研究课题列表（reuse 现有 storage.py）
  · 失败时返回空列表（防止 TUI 崩溃）
  · 结构标准化为 TUI 通用 dict 格式
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def load_research_topics() -> list[dict]:
    """加载研究课题列表，供 TUI 列表面板使用."""
    try:
        from cockpit.storage import Storage
        storage = Storage()
        topics = storage.list_research(limit=200, include_archived=True)
        return [_normalize(t) for t in topics]
    except Exception as e:
        logger.debug("TUI data_loader: load_research_topics 失败: %s", e)
        return _mock_topics()  # 开发期 mock 数据


def _normalize(raw: dict) -> dict:
    """将 Storage 返回的原始对象标准化为 TUI 期望的 dict."""
    return {
        "id": raw.get("id") or raw.get("research_id", "?"),
        "topic": raw.get("topic") or raw.get("title", "未知主题"),
        "status": raw.get("status", "active"),
        "ask_count": raw.get("ask_count", 0) or len(raw.get("asks", [])),
        "created_at": _fmt_date(raw.get("created_at", "")),
        "updated_at": _fmt_date(raw.get("updated_at", "")),
        "summary": raw.get("summary", ""),
        "asks": raw.get("asks", []),
    }


def _fmt_date(raw: str) -> str:
    if not raw:
        return "未知"
    try:
        return raw[:16].replace("T", " ")
    except Exception:
        return raw


def _mock_topics() -> list[dict]:
    """开发期 mock 数据（当 storage 不可用时使用）."""
    return [
        {"id": "1", "topic": "transformer architecture evolution", "status": "active", "ask_count": 3,
         "created_at": "2026-08-01 10:00", "updated_at": "2026-08-02 19:00", "summary": "深度研究 Transformer 架构演进路径", "asks": []},
        {"id": "2", "topic": "BOS URI routing design patterns", "status": "active", "ask_count": 7,
         "created_at": "2026-07-28 09:00", "updated_at": "2026-08-01 15:00", "summary": "BOS 路由器架构与设计模式研究", "asks": []},
        {"id": "3", "topic": "Textual TUI framework evaluation", "status": "active", "ask_count": 2,
         "created_at": "2026-08-02 18:00", "updated_at": "2026-08-02 19:30", "summary": "Textual 框架能力评估与集成方案", "asks": []},
        {"id": "4", "topic": "OMO governance audit patterns", "status": "archived", "ask_count": 5,
         "created_at": "2026-07-20 14:00", "updated_at": "2026-07-30 11:00", "summary": "治理审计模式与自动化工作流", "asks": []},
        {"id": "5", "topic": "LLM inference scheduling at edge", "status": "active", "ask_count": 0,
         "created_at": "2026-08-02 17:00", "updated_at": "2026-08-02 17:30", "summary": "边缘端 LLM 推理调度与性能优化", "asks": []},
    ]
