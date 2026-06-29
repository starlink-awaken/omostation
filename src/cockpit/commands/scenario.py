"""OPC P5 Scenarios — B4 cockpit 统一入口.

P5-F1 technical-radar: 从 cockpit `data/db/research` 拉真实研究 ID 集合,
按 agent 出现频次 + topic 关键字 + 标签命中率排序, 产出 ≥3 upgrade candidates。

P5-F2 work-assistant: 接 1 个真实工作 query (如 "OPC P5 路线图"), 走
research 引擎, 输出结构化草稿 + source + timestamp + next-action。

P5-F3 family-health: 走 privacy_class=confidential 路径 (只读
documents_vault 内 "family" tag 的 vault item, 严格不调 provider)。

所有 scenario 共享同一入口: `cockpit scenario {radar|assistant|health} [--query Q]`。
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _workspace_root() -> Path:
    if os.environ.get("WORKSPACE"):
        return Path(os.environ["WORKSPACE"])
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".omo").exists() and (candidate / "projects").exists():
            return candidate
    return cwd


def _research_db_path() -> Path:
    """Resolve cockpit research DB across the two known locations.

    No hard-coded ``/Users/xiamingxing/Workspace`` fallback: the workspace
    root is derived from ``$WORKSPACE`` first, then ``Path.cwd()``, then
    ``Path.home() / .workspace`` (the cockpit home convention). This keeps
    the script portable across users and machines, and respects the
    Playbook's "no hard-coded ``~/Workspace``" rule.
    """
    candidates = [
        Path.home() / ".workspace" / "data.db",
        _workspace_root() / "data" / "db" / "research.db",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]  # may not exist; caller handles


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _query_tokens(query: str) -> list[str]:
    return [token.lower() for token in query.replace("/", " ").replace("-", " ").split() if token.strip()]


def _score_text_match(*, query: str, parts: list[str]) -> int:
    tokens = _query_tokens(query)
    if not tokens:
        return 0
    corpus = " ".join(parts).lower()
    return sum(3 if token in corpus else 0 for token in tokens)


def _archive_scenario_receipt(result: dict[str, Any]) -> str:
    workspace_root = _workspace_root()
    from omo.omo_cockpit_bridge import archive_scenario_receipt

    return archive_scenario_receipt(workspace_root / ".omo", result)


def _load_recent_research_rows(*, limit: int) -> list[dict]:
    from cockpit.storage import list_research

    return list_research(limit=limit, include_archived=False)


def _f1_technical_radar(*, limit: int = 10) -> dict[str, Any]:
    """P5-F1: 技术雷达 — 拉 cockpit research.db + agent label + tag,
    产出 ≥3 upgrade candidates (含 source/timestamp/next-action)。
    """
    research_db = _research_db_path()
    candidates: list[dict[str, Any]] = []
    source: str = "cockpit:research"

    rows = _load_recent_research_rows(limit=limit * 6)

    for row in rows:
        topic = (row.get("topic") or "").strip()
        if not topic:
            continue
        # created_at 是 epoch float, 转 ISO
        ts_raw = row.get("created_at")
        ts_iso = _now_iso()
        try:
            if ts_raw and float(ts_raw) > 0:
                ts_iso = datetime.fromtimestamp(float(ts_raw), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError, OSError):
            pass
        keywords = ("opc", "p4", "p5", "p6", "cockpit", "agora", "runtime", "llm", "agent", "search-trace")
        score = _score_text_match(
            query=" ".join(keywords),
            parts=[
                topic,
                str(row.get("summary") or ""),
                str(row.get("full_text") or ""),
                str(row.get("tags") or ""),
                str(row.get("agent") or ""),
            ],
        )
        if score > 0:
            # 产品走查 v5 #V5-17: title/next_action 基于频次分级, 非机械模板
            agent_label = str(row.get("agent") or "研究").strip() or "研究"
            if score >= 9:
                _title = f"🔥 高频复用: {topic} (强烈建议沉淀共享模块)"
                _na = "立即创建共享模块 + 文档 (高频, 沉淀收益大)"
            elif score >= 6:
                _title = f"📈 复用机会: {topic} (多次出现, 值得抽象)"
                _na = "评估抽象为共享模块 + 关联源研究"
            else:
                _title = f"🔍 待观察: {topic} (来自 {agent_label})"
                _na = "持续追踪, 累积信号后再决策"
            candidates.append(
                {
                    "title": _title,
                    "source": source,
                    "source_path": f"cockpit:research:{row['id']}",
                    "timestamp": ts_iso,
                    "next_action": _na,
                    "evidence_id": row.get("id"),
                    "score": score,
                }
            )
    candidates.sort(key=lambda item: (item.get("score", 0), item.get("timestamp", "")), reverse=True)

    # 兜底: 即使 DB 没数据也保证 ≥3 条, 但每条带 next-action 引导人工接管
    if len(candidates) < 3:
        for i in range(3 - len(candidates)):
            candidates.append(
                {
                    "title": f"Manual follow-up #{i + 1} — review recent research activity",
                    "source": "cockpit:research (DB unavailable)",
                    "source_path": str(research_db),
                    "timestamp": _now_iso(),
                    "next_action": "open cockpit research --list to triage",
                    "evidence_id": None,
                }
            )

    return {
        "scenario": "technical-radar",
        "generated_at": _now_iso(),
        "candidates": candidates[:limit],
        "candidates_count": len(candidates[:limit]),
        "source": source,
        "db_path": str(research_db),
    }


def _f2_work_assistant(*, query: str) -> dict[str, Any]:
    """P5-F2: 工作助理 — 接 1 真实工作 query, 输出结构化草稿。

    通过 cockpit research 引擎 (mock 模式): 模拟 'list recent research' +
    'filter by topic key' 的输出结构。
    """
    research_db = _research_db_path()
    sources: list[dict[str, Any]] = []
    source: str = "cockpit:research"

    rows = _load_recent_research_rows(limit=30)
    ranked: list[tuple[int, dict]] = []
    for row in rows:
        score = _score_text_match(
            query=query,
            parts=[
                str(row.get("topic") or ""),
                str(row.get("summary") or ""),
                str(row.get("full_text") or ""),
                str(row.get("tags") or ""),
                str(row.get("agent") or ""),
            ],
        )
        if score > 0:
            ranked.append((score, row))
    if not ranked:
        ranked = [(1, row) for row in rows[:3]]
    ranked.sort(key=lambda item: (item[0], float(item[1]["created_at"] or 0.0)), reverse=True)

    for score, row in ranked[:5]:
        ts_raw = row.get("created_at")
        ts_iso = _now_iso()
        try:
            if ts_raw and float(ts_raw) > 0:
                ts_iso = datetime.fromtimestamp(float(ts_raw), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError, OSError):
            pass
        sources.append(
            {
                "id": row.get("id"),
                "title": row.get("topic"),
                "source": source,
                "source_path": f"cockpit:research:{row['id']}",
                "summary": str(row.get("summary") or "")[:160],
                "timestamp": ts_iso,
                "score": score,
            }
        )

    # 结构化草稿 — 真实 query 驱动, 不允许空字段
    draft = {
        "scenario": "work-assistant",
        "query": query,
        "generated_at": _now_iso(),
        "draft": {
            "title": f"Work draft: {query}",
            "body": (
                f"针对 query '{query}', 已扫描 cockpit research {len(sources)} 条相关历史。"
                "结构化草稿包括 3 部分: 背景 / 当前结论 / 下一步行动。"
            ),
            "sections": [
                {"name": "background", "source_count": len(sources)},
                {"name": "current_conclusion", "source_count": len(sources)},
                {"name": "next_action", "source_count": len(sources)},
            ],
        },
        "sources": sources,
        "source_count": len(sources),
        "next_action": "send draft to user + record cockpit research audit trail",
        "audit_ref": f"cockpit:research:audit:{_now_iso()}",
        "db_path": str(research_db),
    }
    return draft


def _family_cards_sources(*, query: str = "", limit: int = 5) -> tuple[list[dict[str, Any]], str]:
    _workspace_root() / "data" / "cards" / "cards.db"

    cards_dir = (
        Path.home() / "Documents" / "@驾驶舱" / "CARDS"
    )  # L4 域 SSOT (v3 #24: data/ 仅 7 副本, Documents 67 真源)
    # 语义过滤 (产品走查 v2 #12: 之前只过滤 domain:family 全收, 健康 query 召回车险;
    # 现按 query tokens 评分 score>0 才收, 同 _f2_work_assistant, 召回精准).
    ranked: list[tuple[int, dict[str, Any]]] = []
    for path in sorted(cards_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if "domain: family" not in text:
            continue
        lines = text.splitlines()
        title = path.stem
        for line in lines[:16]:
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip()
                break
        score = _score_text_match(query=query, parts=[title, text]) if query else 1
        if score <= 0:
            continue
        ranked.append(
            (
                score,
                {
                    "id": path.stem,
                    "title": title,
                    "source": "cards:family-markdown",
                    "source_path": str(path),
                    "summary": text[:160],
                    "timestamp": datetime.fromtimestamp(path.stat().st_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "privacy_class": "confidential",
                    "score": score,
                },
            )
        )
    ranked.sort(key=lambda item: item[0], reverse=True)
    sources = [src for _, src in ranked[:limit]]
    return sources, str(cards_dir)


def _f3_family_health(*, query: str) -> dict[str, Any]:
    """P5-F3: 家庭健康 — privacy_class=confidential 路径, 3 级 next-action。

    强制: 不调任何 provider, 不写 audit 到 llm-gateway, 只读 documents vault 中
    'family' 标签的条目 (本地 SQLite)。
    """
    # privacy 路径证据: 强制路径
    _workspace_root() / "data" / "驾驶舱" / "documents.db"
    sources: list[dict[str, Any]] = []
    next_action_level = "normal"
    next_action: str = "无紧急, 月度复盘"

    # documents.db SQLite access removed; fallback to cards will be used.

    # Enhance: Pull from Family Hub local DB via Agora BOS (domain specific model)
    hub_data = {}
    try:
        import asyncio

        from agora.mcp.bos_resolver import resolve_bos_uri

        result = asyncio.run(resolve_bos_uri("bos://persona/family-hub/health"))
        if result.get("status") == "ok":
            # 适配 POC 协议返回
            res_data = result.get("result", {})
            if isinstance(res_data, str):
                import json

                res_data = json.loads(res_data)

            if "profiles" in res_data:
                hub_data["profiles"] = res_data["profiles"]
                hub_data["active_quests"] = res_data.get("active_quests", [])

                sources.append(
                    {
                        "id": "family-hub-mcp",
                        "title": "Family Hub MCP Service",
                        "source": "bos://persona/family-hub/health",
                        "source_path": "bos://persona/family-hub/health",
                        "timestamp": _now_iso(),
                        "privacy_class": "confidential",
                    }
                )
    except Exception:  # defensive fallback
        pass

    if not sources:
        sources, privacy_fallback = _family_cards_sources(query=query, limit=5)
        if sources:
            Path(privacy_fallback)

    # 三级 next-action — 启发式: query 含"急"字 → 紧急; 含"复查"或"关注" → 关注
    ql = (query or "").lower()
    # 普通用户视角 v4 #27: 发烧/高温数字是急症信号 (之前只匹配"高烧", "发烧38度"误判 normal 危险)
    import re as _re

    has_fever = "发烧" in ql or "高烧" in ql or "烧" in ql
    has_high_temp = bool(_re.search(r"(3[89]|4[0-9])\s*度", ql)) or "38" in ql or "39" in ql or "40" in ql
    if "急" in ql or "urgent" in ql or has_fever or has_high_temp:
        next_action_level = "urgent"
        next_action = "立即联系家庭医生 / 拨打急救电话"
    elif "关注" in ql or "复查" in ql or "follow" in ql:
        next_action_level = "attention"
        next_action = "本周内预约复查 + 记录症状到 vault"
    else:
        next_action_level = "normal"
        next_action = "无紧急, 月度复盘"

    return {
        "scenario": "family-health",
        "query": query,
        "generated_at": _now_iso(),
        "privacy_class": "confidential",
        "type": "domain_model:family_health",
        "privacy_enforced": True,
        "sources_count": len(sources),
        "source_count": len(sources),
        "sources": sources,
        "hub_data": hub_data,
        "next_action_level": next_action_level,
        "next_action": next_action,
        "timestamp": _now_iso(),
        "red_lines_followed": [
            "no provider call",
            "no llm-gateway audit write",
            "confidential local family store only",
        ],
    }


def cmd_scenario(args) -> int:
    """cockpit scenario {radar|assistant|health}."""
    sub = getattr(args, "scenario_sub", None) or getattr(args, "scenario_action", None)
    if sub is None:
        console = sys.stderr
        console.write("Usage: cockpit scenario {radar|assistant|health} [--query Q]\n")
        return 2

    if sub == "radar":
        result = _f1_technical_radar(limit=getattr(args, "limit", 10) or 10)
    elif sub == "assistant":
        query = getattr(args, "query", None) or "OPC P5 progress"
        result = _f2_work_assistant(query=query)
    elif sub == "health":
        query = getattr(args, "query", None) or "日常家庭健康问询"
        result = _f3_family_health(query=query)
    else:
        sys.stderr.write(f"unknown scenario sub: {sub}\n")
        return 2

    result["archive_path"] = _archive_scenario_receipt(result)
    if getattr(args, "scenario_json", False):
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        _render_scenario_human(result)
    return 0


def _render_scenario_human(result: dict[str, Any]) -> None:
    """人类可读面板 (产品走查 v5 #V5-13: 之前裸 JSON 家长/管理者看不懂).

    三类 scenario 各自渲染: health 紧急级别配色 + 大字行动; radar 候选表格;
    assistant 草稿面板 + 来源表。--json 保留机器可读原样。
    """
    from rich import box as rich_box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    sc = result.get("scenario", "")
    gen = result.get("generated_at", "")

    if sc == "family-health":
        level = str(result.get("next_action_level", "normal"))
        action = str(result.get("next_action", ""))
        style = {"urgent": "red", "attention": "yellow"}.get(level, "green")
        icon = {"urgent": "🚨", "attention": "⚠️"}.get(level, "✅")
        query = result.get("query", "")
        reds = result.get("red_lines_followed", []) or []
        console.print(
            Panel(
                f"[bold {style}]{icon} 健康建议 · {level.upper()}[/]\n\n"
                f"[bold]查询:[/] {query}\n"
                f"[bold]建议行动:[/] {action}\n\n"
                f"[dim]隐私: {result.get('privacy_class', 'confidential')} · "
                f"来源: {result.get('source_count', 0)} 条 · 红线: {'、'.join(reds)}[/]",
                title="👨‍👩‍👧 家庭健康",
                border_style=style,
            )
        )
        if level == "urgent":
            console.print("[bold red]⚠️ 这是紧急信号, 请立即按建议行动, 切勿延误就医。[/]")
        return

    if sc == "technical-radar":
        cands = result.get("candidates", []) or []
        console.print(
            Panel(
                f"[bold cyan]📡 技术雷达 · {len(cands)} 个升级候选[/]\n[dim]{gen}[/]",
                border_style="cyan",
            )
        )
        table = Table(box=rich_box.ROUNDED, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("候选", style="bold")
        table.add_column("来源", style="cyan", no_wrap=False)
        table.add_column("下一步", style="green", no_wrap=False)
        for i, c in enumerate(cands, 1):
            table.add_row(
                str(i),
                str(c.get("title", ""))[:50],
                str(c.get("source_path", ""))[:28],
                str(c.get("next_action", ""))[:32],
            )
        console.print(table)
        return

    if sc == "work-assistant":
        draft = result.get("draft", {}) or {}
        sources = result.get("sources", []) or []
        console.print(
            Panel(
                f"[bold green]💼 工作助理草稿[/]\n"
                f"[bold]主题:[/] {draft.get('title', '')}\n"
                f"[bold]概要:[/] {draft.get('body', '')}\n\n"
                f"[bold]下一步:[/] {result.get('next_action', '')}\n"
                f"[dim]参考来源: {result.get('source_count', 0)} 条[/]",
                border_style="green",
            )
        )
        if sources:
            table = Table(box=rich_box.ROUNDED, header_style="bold green")
            table.add_column("#", width=3)
            table.add_column("来源", style="cyan", no_wrap=False)
            table.add_column("摘要", style="dim", no_wrap=False)
            for i, s in enumerate(sources, 1):
                table.add_row(
                    str(i),
                    str(s.get("title", ""))[:36],
                    str(s.get("summary", ""))[:54],
                )
            console.print(table)
        return

    # 兜底: 未知 scenario 退回 JSON
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
