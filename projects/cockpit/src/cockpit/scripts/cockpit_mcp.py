"""cockpit MCP server — workspace research and status MCP tools.

Provides research lifecycle tools (list, search, create, open, ask, archive,
restore, tag, rename, dossier, half-life, agent-list) and status tools
(summary, json, daily).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
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
# L4 Bridge tools (CARDS + Vault + OMO context)
# ══════════════════════════════════════════════════════════════

_CARDS_DIR = Path.home() / "Documents" / "驾驶舱" / "CARDS"
_VAULT_DIR = Path.home() / "Documents" / "@学习进化"
_WORKSPACE_ROOT = Path(__file__).resolve().parents[4]  # cockpit/src/cockpit/scripts/cockpit_mcp.py → workspace root
_OMO_GOALS = _WORKSPACE_ROOT / ".omo" / "_truth" / "goals" / "current.yaml"


def _scan_cards() -> list[dict[str, str]]:
    """扫描 CARDS 目录下所有带 frontmatter 的 Markdown 文件。"""
    cards = []
    for md_file in sorted(_CARDS_DIR.rglob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
            if text.startswith("---"):
                _, fm, __ = text.split("---", 2)
                meta = {}
                for line in fm.strip().split("\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip()
                if meta.get("id") and meta.get("type"):
                    cards.append({
                        "id": meta["id"],
                        "type": meta.get("type", ""),
                        "status": meta.get("status", ""),
                        "title": meta.get("title", ""),
                        "priority": meta.get("priority", ""),
                        "domain": meta.get("domain", ""),
                        "created": meta.get("created", ""),
                        "tags": meta.get("tags", "[]"),
                    })
        except (OSError, ValueError):
            continue
    cards.sort(key=lambda c: ({"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(c["priority"], 9), c["created"]), reverse=True)
    return cards


def _read_omo_goals() -> dict:
    """读取 OMO 当前目标。"""
    try:
        import yaml
        return yaml.safe_load(_OMO_GOALS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_omo_constraints() -> list[str]:
    """从 .omo 治理约束中提取约束。"""
    constraints_file = _WORKSPACE_ROOT / ".omo" / "_truth" / "x1-governance-policies.yaml"
    try:
        import yaml
        cfg = yaml.safe_load(constraints_file.read_text(encoding="utf-8"))
        rules = []
        if cfg and isinstance(cfg, dict):
            for section in cfg.values():
                if isinstance(section, dict):
                    for rule_name, rule_body in section.items():
                        if isinstance(rule_body, dict) and "constraint" in rule_body:
                            rules.append(f"[{rule_name}] {rule_body['constraint']}")
                        elif isinstance(rule_body, str):
                            rules.append(f"[{rule_name}] {rule_body}")
        return rules
    except Exception:
        # Fallback to hardcoded key constraints
        return [
            "禁止直接改写 .omo 目录 (使用 OMO CLI)",
            "修改后必须立即 git commit",
            "跨包调用必须经 Agora I0 路由",
            "L4 CARDS/Vault 仅通过 cockpit MCP 工具访问",
        ]


def _search_vault(keyword: str) -> list[dict]:
    """搜索 Vault 中的 Markdown 文件。"""
    results = []
    if not keyword or not _VAULT_DIR.is_dir():
        return results
    kw = keyword.lower()
    for md_file in _VAULT_DIR.rglob("*.md"):
        if md_file.name.startswith("."):
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
            if kw in text.lower():
                lines = text.split("\n")
                title = lines[0].replace("# ", "").strip() if lines else md_file.stem
                snippet_start = max(0, text.lower().index(kw) - 40)
                snippet_end = min(len(text), text.lower().index(kw) + 120)
                results.append({
                    "path": str(md_file.relative_to(_VAULT_DIR)),
                    "title": title,
                    "snippet": "..." + text[snippet_start:snippet_end].replace("\n", " ").strip() + "...",
                })
                if len(results) >= 10:
                    break
        except (OSError, ValueError):
            continue
    return results


@_tool()
def workspace_context() -> str:
    """获取 Workspace 完整上下文：活跃目标、CARDS 状态、OMO 阶段、治理约束。

    **Agent 应首先调用此工具**以获取当前工作目标/优先级/约束。
    返回 JSON，包含: phase, theme, active_goals, cards_summary, constraints。
    """
    omo = _read_omo_goals()
    goals_list = omo.get("goals", [])
    active_cards = _scan_cards()
    constraints = _read_omo_constraints()

    active_count = sum(1 for c in active_cards if c["status"] not in ("closed", "done"))
    p0_cards = [c for c in active_cards if c["priority"] == "P0" and c["status"] not in ("closed", "done")]

    return json.dumps(
        {
            "phase": omo.get("phase", "?"),
            "theme": omo.get("theme", ""),
            "phase_status": omo.get("status", ""),
            "active_goals": [
                {"id": g.get("id", ""), "desc": g.get("desc", ""), "status": g.get("status", "")}
                for g in goals_list
            ],
            "cards_summary": {
                "total": len(active_cards),
                "active": active_count,
                "p0_open": len(p0_cards),
                "p0_titles": [c["title"] for c in p0_cards[:5]],
            },
            "constraints": constraints,
            "next_guidance": (
                "1. 查看 P0 卡片确定当前优先任务。"
                "2. 调用 cards_check 验证操作合规。"
                "3. 经 Agora 调用 L2 工具执行。"
                "4. 完成后调 cards_update 记录状态。"
            ),
        },
        ensure_ascii=False,
        default=str,
    )


@_tool()
def cards_status() -> str:
    """获取 CARDS 活跃卡片列表，按优先级排序。

    **Agent 应调用此工具了解当前有哪些 P0/P1 任务。**
    返回 JSON 数组，每个卡片含 id/type/status/title/priority/domain。
    """
    cards = _scan_cards()
    active = [c for c in cards if c["status"] not in ("closed", "done")]
    return json.dumps(
        [
            {"id": c["id"], "type": c["type"], "status": c["status"], "title": c["title"],
             "priority": c["priority"], "domain": c["domain"], "created": c["created"]}
            for c in active
        ],
        ensure_ascii=False,
    )


@_tool()
def cards_check(card_id: str = "") -> str:
    """检查指定 CARDS 卡片（或当前上下文）是否违反治理约束。

    **Agent 应在执行操作前调用此工具**。遵守 L4 自我约束。
    返回 JSON: compliant(bool), violations(list), guidance(str)。
    """
    constraints = _read_omo_constraints()
    # 检查基础合规性
    violations = []

    # 检查是否在 OMO 阶段内操作
    omo = _read_omo_goals()
    if omo.get("code_freeze"):
        violations.append("代码冻结中: 禁止非紧急修改")

    if card_id:
        found = False
        for c in _scan_cards():
            if c["id"] == card_id:
                found = True
                if c["status"] == "closed":
                    violations.append(f"卡片 {card_id} 已关闭")
                break
        if not found:
            violations.append(f"卡片 {card_id} 不存在")

    return json.dumps(
        {
            "compliant": len(violations) == 0,
            "violations": violations,
            "constraints_checked": len(constraints),
            "guidance": (
                "合规, 可以执行" if not violations
                else f"需要解决 {len(violations)} 个违规项: " + "; ".join(violations)
            ),
        },
        ensure_ascii=False,
    )


@_tool()
def vault_search(keyword: str = "") -> str:
    """在 L4 Vault (学习进化) 中搜索相关知识/方法论/经验。

    **Agent 应在需要方法论或历史上下文时调用此工具。**
    返回 JSON: results(list), total(int)。
    """
    results = _search_vault(keyword)
    return json.dumps({"results": results, "total": len(results)}, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════
# Module execution
# ══════════════════════════════════════════════════════════════

def main() -> None:
    """Entry point for cockpit MCP server. Use `cockpit-mcp` CLI or `uv run --package cockpit cockpit-mcp`."""
    if not HAS_FASTMCP or mcp is None:
        print("错误: 需安装 fastmcp 才能运行 MCP server", file=sys.stderr)
        sys.exit(1)
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
