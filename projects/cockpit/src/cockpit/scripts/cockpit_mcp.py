"""cockpit MCP server — workspace research and status MCP tools.

Provides research lifecycle tools (list, search, create, open, ask, archive,
restore, tag, rename, dossier, half-life, agent-list) and status tools
(summary, json, daily).
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

try:
    from fastmcp import FastMCP

    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False

if HAS_FASTMCP:
    mcp = FastMCP("cockpit")
    _tool = mcp.tool
else:
    mcp = None  # type: ignore[assignment]
    # no-op decorator when fastmcp is unavailable
    def _tool(*d_args, **d_kwargs):  # type: ignore[no-redef]
        def decorator(f):
            return f
        return decorator


# ══════════════════════════════════════════════════════════════
# Data access (injectable for testing)
# ══════════════════════════════════════════════════════════════

try:
    from cockpit.storage import DataAccess

    _da = DataAccess()
except Exception:
    _da = None  # type: ignore[assignment]


# ══════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════

_STALE_SECONDS = 72 * 3600  # 72 hours


def _now() -> float:
    return time.time()


def _enrich(item: dict) -> dict:
    """Add computed fields to a research item dict."""
    return {
        **item,
        "archived": item.get("archived_at") is not None,
        "follow_up_count": len(item.get("follow_ups", [])),
    }


# ══════════════════════════════════════════════════════════════
# Research tools
# ══════════════════════════════════════════════════════════════


@_tool()
def research_list(limit: int = 20, include_archived: bool = False) -> str:
    """列出最近的研究项。"""
    if _da is None:
        return json.dumps({"error": "DataAccess not available"})
    items = _da.list_research(limit=limit, include_archived=include_archived)
    return json.dumps([_enrich(i) for i in items], ensure_ascii=False, default=str)


@_tool()
def research_search(query: str = "", keyword: str = "", limit: int = 20) -> str:
    """按关键词搜索研究。"""
    if _da is None:
        return json.dumps("[]")
    q = query or keyword
    results = _da.search_research(q, limit)
    return json.dumps([_enrich(r) for r in results], ensure_ascii=False, default=str)


@_tool()
def research_create(
    topic: str = "",
    summary: str = "",
    full_text: str = "",
    source_count: int = 0,
    agent: str = "",
) -> str:
    """创建新的研究项。"""
    if _da is None:
        return json.dumps({"error": "DataAccess not available"})
    rid = _da.save_research(
        topic=topic,
        summary=summary,
        full_text=full_text,
        source_count=source_count,
        agent=agent,
    )
    return json.dumps({"id": rid, "topic": topic, "status": "created"})


@_tool()
def research_open(research_id: int = 0) -> str:
    """打开并查看研究详情。"""
    if _da is None:
        return json.dumps({"error": "DataAccess not available"})
    r = _da.get_research(research_id=research_id)
    if r is None:
        return json.dumps({"error": f"研究 #{research_id} 不存在"})
    return json.dumps(
        {
            "id": r.get("id"),
            "topic": r.get("topic"),
            "summary": r.get("summary"),
            "full_text": r.get("full_text"),
            "agent": r.get("agent"),
            "tags": r.get("tags"),
            "created_at": r.get("created_at"),
            "source_count": r.get("source_count"),
            "archived": r.get("archived_at") is not None,
            "follow_ups": r.get("follow_ups", []),
        },
        ensure_ascii=False,
        default=str,
    )


@_tool()
def research_ask(research_id: int = 0, question: str = "") -> str:
    """向研究添加追问。"""
    if _da is None:
        return json.dumps({"error": "DataAccess not available"})
    r = _da.get_research(research_id=research_id)
    if r is None:
        return json.dumps({"error": f"研究 #{research_id} 不存在"})
    _da.add_follow_up(research_id=research_id, question=question, answer="")
    return json.dumps({"status": "added", "question": question, "id": research_id})


@_tool()
def research_archive(research_id: int = 0) -> str:
    """归档指定的研究。"""
    if _da is None:
        return json.dumps({"error": "DataAccess not available"})
    ok, fail = _da.archive_research(research_ids=[research_id])
    if ok:
        return json.dumps({"status": "archived", "id": research_id})
    return json.dumps({"error": f"归档研究 #{research_id} 失败"})


@_tool()
def research_restore(research_id: int = 0) -> str:
    """恢复已归档的研究。"""
    if _da is None:
        return json.dumps({"error": "DataAccess not available"})
    ok, fail = _da.restore_archived_research(research_ids=[research_id])
    if ok:
        return json.dumps({"status": "restored", "id": research_id})
    return json.dumps({"error": f"恢复研究 #{research_id} 失败"})


@_tool()
def research_tag(research_id: int = 0, tags: str = "") -> str:
    """设置研究的标签。"""
    if _da is None:
        return json.dumps({"error": "DataAccess not available"})
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    result = _da.set_research_tags(research_id=research_id, tags=tag_list)
    return json.dumps({"id": research_id, "tags": result})


@_tool()
def research_rename(research_id: int = 0, topic: str = "") -> str:
    """重命名研究主题。"""
    if _da is None:
        return json.dumps({"error": "DataAccess not available"})
    ok = _da.rename_research(research_id=research_id, new_topic=topic)
    if ok:
        return json.dumps({"status": "renamed", "topic": topic, "id": research_id})
    return json.dumps({"error": f"重命名研究 #{research_id} 失败"})


@_tool()
def research_dossier(research_id: int = 0) -> str:
    """获取研究的完整档案（含关联信息）。"""
    if _da is None:
        return json.dumps({"error": "DataAccess not available"})
    data = _da.get_research_dossier(research_id)
    if data is None:
        return json.dumps({"error": f"研究 #{research_id} 不存在"})
    record = data.get("record", data)
    return json.dumps(
        {
            "id": record.get("id"),
            "topic": record.get("topic"),
            "summary": record.get("summary"),
            "agent": record.get("agent"),
            "tags": record.get("tags"),
            "archived_at": record.get("archived_at"),
            "archived": record.get("archived_at") is not None,
            "parents": data.get("parents", []),
            "children": data.get("children", []),
            "publications": data.get("publications", []),
        },
        ensure_ascii=False,
        default=str,
    )


@_tool()
def research_half_life(research_id: int = 0) -> str:
    """获取研究的半衰期统计。"""
    if _da is None:
        return json.dumps({"error": "DataAccess not available"})
    result = _da.compute_half_life(research_id)
    return json.dumps(result, default=str)


@_tool()
def research_agent_list(agent_name: str = "") -> str:
    """按 Agent 筛选研究列表。"""
    if _da is None:
        return json.dumps("[]")
    items = _da.list_research(limit=200)
    if agent_name:
        items = [r for r in items if r.get("agent") == agent_name]
    return json.dumps([_enrich(i) for i in items], ensure_ascii=False, default=str)


# ══════════════════════════════════════════════════════════════
# Status tools
# ══════════════════════════════════════════════════════════════


@_tool()
def status_summary() -> str:
    """获取工作区状态摘要。"""
    if _da is None:
        return json.dumps({"total": 0, "active": 0, "archived": 0, "stale": 0, "health": "idle"})
    items = _da.list_research(limit=200)
    now = _now()
    total = len(items)
    active = sum(1 for r in items if r.get("archived_at") is None)
    archived = sum(1 for r in items if r.get("archived_at") is not None)
    stale = sum(
        1 for r in items
        if r.get("archived_at") is None and (now - r.get("created_at", 0)) > _STALE_SECONDS
    )
    health = "idle" if total == 0 else "good" if active > 0 else "warning"
    return json.dumps({"total": total, "active": active, "archived": archived, "stale": stale, "health": health})


@_tool()
def status_json() -> str:
    """获取工作区详细 JSON 状态。"""
    if _da is None:
        return json.dumps({"status": "ok", "total": 0, "active": 0, "archived": 0, "stale": 0, "health": "idle", "recent": []})
    items = _da.list_research(limit=100)
    now = _now()
    total = len(items)
    active_count = 0
    archived_count = 0
    stale_count = 0
    recent = []
    for r in items:
        created = r.get("created_at", 0)
        if r.get("archived_at") is not None:
            archived_count += 1
        else:
            active_count += 1
            if now - created > _STALE_SECONDS:
                stale_count += 1
        recent.append(
            {
                "id": r.get("id"),
                "topic": r.get("topic"),
                "created_at": created,
                "archived_at": r.get("archived_at"),
                "follow_up_count": len(r.get("follow_ups", [])),
                "agent": r.get("agent", ""),
            }
        )
    recent.sort(key=lambda x: x["created_at"], reverse=True)
    health = "idle" if total == 0 else "good" if active_count > 0 else "ok"
    return json.dumps(
        {
            "status": "ok",
            "total": total,
            "active": active_count,
            "archived": archived_count,
            "stale": stale_count,
            "health": health,
            "recent": recent,
        },
        default=str,
    )


@_tool()
def daily_summary(days: int = 1) -> str:
    """获取最近 N 天的研究摘要。"""
    if _da is None:
        return json.dumps({"days": days, "total": 0, "items": []})
    items = _da.list_research(limit=50)
    now = _now()
    cutoff = now - days * 86400
    recent = [r for r in items if r.get("created_at", 0) >= cutoff]
    recent.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return json.dumps(
        {
            "days": days,
            "total": len(recent),
            "items": [
                {
                    "id": r.get("id"),
                    "topic": r.get("topic"),
                    "created_at": r.get("created_at"),
                    "follow_up_count": len(r.get("follow_ups", [])),
                }
                for r in recent
            ],
        },
        default=str,
    )


# ══════════════════════════════════════════════════════════════
# Module execution
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not HAS_FASTMCP or mcp is None:
        print("错误: 需安装 fastmcp 才能运行 MCP server", file=sys.stderr)
        sys.exit(1)
    mcp.run(transport="stdio")
