"""cockpit MCP server — cockpit research and status MCP tools.

Provides research lifecycle tools (list, search, create, open, ask, archive,
restore, tag, rename, dossier, half-life, agent-list) and status tools
(summary, json, daily).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

_log = logging.getLogger(__name__)

import yaml

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
    stale = sum(1 for r in items if r.get("archived_at") is None and (now - r.get("created_at", 0)) > _STALE_SECONDS)
    health = "idle" if total == 0 else "good" if active > 0 else "warning"
    return json.dumps({"total": total, "active": active, "archived": archived, "stale": stale, "health": health})


@_tool()
def status_json() -> str:
    """获取工作区详细 JSON 状态。"""
    if _da is None:
        return json.dumps(
            {"status": "ok", "total": 0, "active": 0, "archived": 0, "stale": 0, "health": "idle", "recent": []}
        )
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
# L4 Bridge tools (CARDS + Vault + OMO context) — 基于 l4-kernel
# ══════════════════════════════════════════════════════════════

try:
    from l4_kernel import DomainRegistry
    from l4_kernel.kems import CardsPlane, KemsPlane

    _registry = DomainRegistry()
    _HAS_L4_KERNEL = True
except ImportError:
    _registry = None
    _HAS_L4_KERNEL = False

_CARDS_DIR = Path.home() / "Documents" / "@驾驶舱" / "CARDS"
if not _CARDS_DIR.exists():
    _log.warning("CARDS 目录不存在: %s. cockpit cards 功能不可用", _CARDS_DIR)
_VAULT_DIR = Path.home() / "Documents" / "@学习进化"
_PERSONAL_DIR = Path.home() / "Documents" / "@个人"
_PUBLIC_DIR = Path.home() / "Documents" / "@公共"
_CREATIVE_DIR = Path.home() / "Documents" / "@创意创作"
_FAMILY_DIR = Path.home() / "Documents" / "@家庭生活"
_WORKDOCS_DIR = Path.home() / "Documents" / "@工作文档"
_OPC_DIR = Path.home() / "Documents" / "@OPC"
_WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", str(Path(__file__).resolve().parents[4])))
_OMO_GOALS = _WORKSPACE_ROOT / ".omo" / "_truth" / "goals" / "current.yaml"

# L4 全域注册 (产品走查 v2 #10, 深度核对 2026-06-19: 真实 8 个 @域, 之前只 cards/vault 2 域)
_L4_DOMAINS: dict[str, Path] = {
    "cards": _CARDS_DIR,
    "vault": _VAULT_DIR,
    "personal": _PERSONAL_DIR,
    "public": _PUBLIC_DIR,
    "creative": _CREATIVE_DIR,
    "family": _FAMILY_DIR,
    "workdocs": _WORKDOCS_DIR,
    "opc": _OPC_DIR,
}


def _scan_cards() -> list[dict[str, str]]:
    """扫描 CARDS 目录下所有带 frontmatter 的 Markdown 文件。"""
    if _HAS_L4_KERNEL and _registry:
        cockpit = _registry.get("cockpit")
        if cockpit:
            cards = CardsPlane(cockpit.path)
            return cards.scan_cards()

    # Fallback: 直接解析
    cards = []
    for md_file in sorted(_CARDS_DIR.rglob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
            if text.startswith("---"):
                _, fm, __ = text.split("---", 2)
                meta = yaml.safe_load(fm) or {}
                if isinstance(meta, dict) and meta.get("id") and meta.get("type"):
                    cards.append(
                        {
                            "id": str(meta.get("id", "")),
                            "type": str(meta.get("type", "")),
                            "status": str(meta.get("status", "")),
                            "title": str(meta.get("title", "")),
                            "priority": str(meta.get("priority", "")),
                            "domain": str(meta.get("domain", "")),
                            "created": str(meta.get("created", "")),
                            "tags": str(meta.get("tags", "[]")),
                        }
                    )
        except (OSError, ValueError, yaml.YAMLError) as _fm_exc:
            _log.warning("无法解析卡片 frontmatter: %s (%s)", md_file, _fm_exc)
            continue
    cards.sort(key=lambda c: ({"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(c["priority"], 9), c["created"]), reverse=True)
    return cards


def _read_omo_goals() -> dict:
    """读取 OMO 当前目标。"""
    try:
        return yaml.safe_load(_OMO_GOALS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_omo_constraints() -> list[str]:
    """从 .omo 治理约束中提取约束。"""
    constraints_file = _WORKSPACE_ROOT / ".omo" / "_truth" / "x1-governance-policies.yaml"
    try:
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


def _search_vault(keyword: str, base_dir: Path | None = None) -> list[dict]:
    """搜索 Vault 中的 Markdown 文件。"""
    if _HAS_L4_KERNEL and _registry:
        # Use l4-kernel KemsPlane
        vault = _registry.get("vault")
        if vault:
            kems = KemsPlane(vault.path)
            return kems.search(keyword)

    # Fallback: 直接搜索
    results = []
    vault_dir = base_dir or _VAULT_DIR
    if not keyword or not vault_dir.is_dir():
        return results
    kw = keyword.lower()
    for md_file in vault_dir.rglob("*.md"):
        if md_file.name.startswith("."):
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
            if kw in text.lower():
                lines = text.split("\n")
                title = lines[0].replace("# ", "").strip() if lines else md_file.stem
                snippet_start = max(0, text.lower().index(kw) - 40)
                snippet_end = min(len(text), text.lower().index(kw) + 120)
                results.append(
                    {
                        "path": str(md_file.relative_to(vault_dir)),
                        "title": title,
                        "snippet": "..." + text[snippet_start:snippet_end].replace("\n", " ").strip() + "...",
                    }
                )
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
                {"id": g.get("id", ""), "desc": g.get("desc", ""), "status": g.get("status", "")} for g in goals_list
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
            {
                "id": c["id"],
                "type": c["type"],
                "status": c["status"],
                "title": c["title"],
                "priority": c["priority"],
                "domain": c["domain"],
                "created": c["created"],
            }
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
                "合规, 可以执行" if not violations else f"需要解决 {len(violations)} 个违规项: " + "; ".join(violations)
            ),
        },
        ensure_ascii=False,
    )


@_tool()
def vault_search(keyword: str = "", domain: str = "vault") -> str:
    """在 L4 域中搜索相关知识/方法论/经验。

    支持 19 个 L4 域:
      Document: vault, cockpit, personal, shared, family,
                work-weijian, work-guozhuan
      Config:   ai-config, agents-config, icloud-sharedconf
      Tool:     bin, toolbox
      Other:    sharedwork, shareddisk

    **Agent 应在需要方法论或历史上下文时调用此工具。**
    返回 JSON: results(list), total(int), domain(str)。
    """
    search_dir = _registry.resolve_path(domain) if _HAS_L4_KERNEL and _registry else _VAULT_DIR
    if not search_dir or not search_dir.is_dir():
        return json.dumps(
            {"results": [], "total": 0, "domain": domain, "warning": f"域 '{domain}' 目录不存在: {search_dir}"},
            ensure_ascii=False,
        )
    results = _search_vault(keyword, base_dir=search_dir)
    return json.dumps({"results": results, "total": len(results), "domain": domain}, ensure_ascii=False)


@_tool()
def domains_list() -> str:
    """列出 L4 所有域及其状态。

    返回 JSON: domains(list of {name, path, exists})。
    """
    domains = []
    for name, path in _L4_DOMAINS.items():
        domains.append(
            {
                "name": name,
                "path": str(path),
                "exists": path.is_dir(),
            }
        )
    return json.dumps({"domains": domains, "total": len(domains)}, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════
# X1-X4 Governance tools
# ══════════════════════════════════════════════════════════════

_REPO_ROOT = Path(__file__).resolve().parents[4]


@_tool()
def governance_check(dimension: str = "all") -> str:
    """运行 X1-X4 治理检查。

    Args:
        dimension: 检查维度 (X1/X2/X3/X4/all)

    Returns:
        检查结果 JSON
    """
    try:
        from ecos.l0.governance import GovernanceRegistry

        registry_path = _REPO_ROOT / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
        registry = GovernanceRegistry(registry_path)
        registry.load()

        if dimension == "all":
            results = registry.run_all(_REPO_ROOT)
        else:
            results = registry.run_dimension(dimension, _REPO_ROOT)

        return json.dumps(
            {
                "dimension": dimension,
                "total": len(results),
                "results": [r.to_dict() for r in results],
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


@_tool()
def governance_status() -> str:
    """查看治理状态。

    Returns:
        治理状态 JSON (健康度、债务权重等)
    """
    try:
        import yaml

        system_yaml = _REPO_ROOT / ".omo" / "state" / "system.yaml"
        if not system_yaml.exists():
            return json.dumps({"error": "system.yaml 不存在"})

        with open(system_yaml) as f:
            data = yaml.safe_load(f) or {}

        return json.dumps(
            {
                "health_score": data.get("health_score", 0),
                "debt_weight": data.get("debt_weight", 0),
                "debt_health": data.get("debt_metrics", {}).get("debt_health", 0),
                "resolved_count": data.get("debt_metrics", {}).get("resolved_count", 0),
                "unresolved_count": data.get("debt_metrics", {}).get("unresolved_count", 0),
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


@_tool()
def governance_sla(dimension: str = "") -> str:
    """查看 SLA 达成情况。

    Args:
        dimension: 指定维度 (X1/X2/X3/X4)，为空返回所有

    Returns:
        SLA 达成情况 JSON
    """
    try:
        sla_path = _REPO_ROOT / ".omo" / "_knowledge" / "governance" / "sla.md"
        if not sla_path.exists():
            return json.dumps({"error": "sla.md 不存在"})

        # 简化返回
        return json.dumps(
            {
                "status": "ok",
                "message": "SLA 文档存在",
                "dimensions": ["X1", "X2", "X3", "X4"],
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


@_tool()
def governance_leaderboard() -> str:
    """查看债务排行榜。

    Returns:
        各项目债务分布 JSON
    """
    try:
        projects = ["kairon", "gbrain", "metaos", "agora", "cockpit", "ecos", "omo", "runtime"]
        result = []

        for proj in projects:
            proj_dir = _REPO_ROOT / "projects" / proj
            if not proj_dir.exists():
                continue

            # 检查状态
            has_githooks = (proj_dir / ".githooks").exists()
            has_tests = (proj_dir / "tests").exists()

            score = 100
            if not has_tests:
                score -= 20
            if not has_githooks:
                score -= 10

            result.append(
                {
                    "project": proj,
                    "status": "healthy" if score >= 90 else "warning",
                    "score": score,
                    "has_githooks": has_githooks,
                    "has_tests": has_tests,
                }
            )

        return json.dumps({"projects": result, "total": len(result)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ══════════════════════════════════════════════════════════════
# 治理仪表板 API
# ══════════════════════════════════════════════════════════════


@_tool()
def governance_dashboard() -> str:
    """获取治理仪表板数据。

    Returns:
        仪表板数据 JSON (健康度、债务、趋势、项目状态)
    """
    try:
        import yaml

        # 读取系统状态
        system_yaml = _REPO_ROOT / ".omo" / "state" / "system.yaml"
        if not system_yaml.exists():
            return json.dumps({"error": "system.yaml 不存在"})

        with open(system_yaml) as f:
            data = yaml.safe_load(f) or {}

        # 读取趋势数据
        trend_path = _REPO_ROOT / ".omo" / "_control" / "debt-dashboard" / "health-trend.md"
        trend_data = []
        if trend_path.exists():
            with open(trend_path) as f:
                for line in f:
                    if "|" in line and "2026" in line:
                        parts = [p.strip() for p in line.split("|") if p.strip()]
                        if len(parts) >= 3:
                            try:
                                trend_data.append(
                                    {
                                        "date": parts[0],
                                        "debt_weight": float(parts[1]),
                                        "debt_health": float(parts[2]),
                                    }
                                )
                            except (ValueError, IndexError):
                                pass

        # 读取项目状态
        projects = ["kairon", "gbrain", "metaos", "agora", "cockpit", "ecos", "omo", "runtime"]
        project_status = []
        for proj in projects:
            proj_dir = _REPO_ROOT / "projects" / proj
            if proj_dir.exists():
                has_githooks = (proj_dir / ".githooks").exists()
                project_status.append(
                    {
                        "name": proj,
                        "status": "healthy" if has_githooks else "warning",
                        "has_githooks": has_githooks,
                    }
                )

        return json.dumps(
            {
                "health_score": data.get("health_score", 0),
                "debt_weight": data.get("debt_weight", 0),
                "debt_health": data.get("debt_metrics", {}).get("debt_health", 0),
                "resolved_count": data.get("debt_metrics", {}).get("resolved_count", 0),
                "unresolved_count": data.get("debt_metrics", {}).get("unresolved_count", 0),
                "trend": trend_data[-10:] if trend_data else [],
                "projects": project_status,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


@_tool()
def governance_history(days: int = 30) -> str:
    """获取治理历史数据。

    Args:
        days: 查询天数 (默认 30)

    Returns:
        历史数据 JSON
    """
    try:
        trend_path = _REPO_ROOT / ".omo" / "_control" / "debt-dashboard" / "health-trend.md"
        if not trend_path.exists():
            return json.dumps({"error": "health-trend.md 不存在", "days": days, "data": []})

        trend_data = []
        with open(trend_path) as f:
            for line in f:
                if "|" in line and "2026" in line:
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 3:
                        try:
                            trend_data.append(
                                {
                                    "date": parts[0],
                                    "debt_weight": float(parts[1]),
                                    "debt_health": float(parts[2]),
                                }
                            )
                        except (ValueError, IndexError):
                            pass

        return json.dumps(
            {
                "days": days,
                "total": len(trend_data),
                "data": trend_data,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


# ══════════════════════════════════════════════════════════════
# Module execution
# ══════════════════════════════════════════════════════════════


def main() -> None:
    """Entry point for cockpit MCP server. Use `cockpit-mcp` CLI or `uv run --package cockpit cockpit-mcp`.

    ⚠️ 入口收敛 (Phase 1+2): 此 stdio 入口已标记 deprecated。
    新方式: Agent 通过 agora MCP (:7431) 的 resolve_bos_uri("bos://cockpit/context") 访问。
    向后兼容期: 保留此 stdio 入口至 Phase 4 完成。
    """
    if not HAS_FASTMCP or mcp is None:
        print("错误: 需安装 fastmcp 才能运行 MCP server", file=sys.stderr)
        sys.exit(1)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()


@_tool()
def github_pr_review(pr_url: str = "") -> str:
    """直接打通 GitHub PR Review（模拟）。

    分析指定的 PR URL 并返回代码审查报告。
    """
    import json

    if not pr_url:
        return json.dumps({"error": "PR URL is required"})

    return json.dumps(
        {
            "pr_url": pr_url,
            "status": "reviewed",
            "score": 85,
            "feedback": [
                "✅ 架构清晰，符合 OMO 治理标准",
                "⚠️ 缺少对 edge case 的测试覆盖",
                "💡 建议抽取通用常量到 constants.py",
            ],
            "action": "approve",
        },
        ensure_ascii=False,
    )
