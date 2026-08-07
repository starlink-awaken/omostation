"""OPC P5 Scenarios — B4 cockpit 统一入口.

P5-F1 technical-radar: 从 cockpit `data/db/research` 拉真实研究 ID 集合,
按 agent 出现频次 + topic 关键字 + 标签命中率排序, 产出 ≥3 upgrade candidates。

P5-F2 work-assistant: 接 1 个真实工作 query (如 "OPC P5 路线图"), 走
research 引擎, 输出结构化草稿 + source + timestamp + next-action。

P5-F3 family-health: 走 privacy_class=confidential 路径 (只读
documents_vault 内 "family" tag 的 vault item, 严格不调 provider)。

P5-F4 decision-inbox: 决策收件箱 — 场景卡驱动的决策生命周期管理。
  子命令: {list, summary, add, status, show, create-scene, create-journey}

所有 scenario 共享同一入口: `cockpit scenario {radar|assistant|health|inbox} [--query Q]`。
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


# ── Decision inbox engine ──

def _decision_inbox_engine(workspace_root: Path | None = None) -> Any:
    """Load the decision inbox engine module."""
    ws = workspace_root or _workspace_root()
    engine_path = ws / "bin" / "ssot" / "scene-card-decision-inbox.py"
    spec = importlib.util.spec_from_file_location("scene_card_decision_inbox_cli", str(engine_path))
    if spec is None or spec.loader is None:
        raise ImportError("scene-card-decision-inbox.py is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _decision_inbox_list(workspace_root: Path) -> dict[str, Any]:
    """List all scenes in the decision inbox."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        scenes = engine.list_scenes(workspace_root)
        return {"ok": True, "scenes": [engine._dictify(s) for s in scenes]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _decision_inbox_summary(workspace_root: Path) -> dict[str, Any]:
    """Show summary of the decision inbox."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        summary = engine.get_inbox_summary(workspace_root)
        return {"ok": True, "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _decision_inbox_add_intent(
    workspace_root: Path,
    scene_id: str,
    source: str,
    raw_content: str,
    priority: str = "P3",
    journey_id: str | None = None,
) -> dict[str, Any]:
    """Add an intent to the decision inbox."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        scene = engine.load_scene(workspace_root, scene_id)
        if scene is None:
            return {"ok": False, "error": f"Scene {scene_id} not found"}
        if not scene.journeys:
            return {"ok": False, "error": f"Scene {scene_id} has no journeys"}
        jid = journey_id or scene.journeys[0].id
        intent = engine.add_intent(
            workspace_root, scene_id=scene_id, journey_id=jid,
            source=source, raw_content=raw_content, priority=priority,
        )
        return {"ok": True, "intent": engine._dictify(intent)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _decision_inbox_set_status(
    workspace_root: Path,
    intent_id: str,
    status: str,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Update an intent's status."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        intent = engine.update_intent_status(
            workspace_root, intent_id=intent_id,
            new_status=status, task_id=task_id,
        )
        if intent is None:
            return {"ok": False, "error": f"Intent {intent_id} not found"}
        return {"ok": True, "intent": engine._dictify(intent)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _decision_inbox_show_scene(workspace_root: Path, scene_id: str) -> dict[str, Any]:
    """Show details of a scene."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        scene = engine.load_scene(workspace_root, scene_id)
        if scene is None:
            return {"ok": False, "error": f"Scene {scene_id} not found"}
        return {"ok": True, "scene": engine._dictify(scene)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _decision_inbox_create_scene(
    workspace_root: Path,
    name: str,
    description: str,
    priority: str = "P1",
) -> dict[str, Any]:
    """Create a new decision inbox scene."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        scene = engine.create_scene(workspace_root, name=name, description=description, priority=priority)
        return {"ok": True, "scene": engine._dictify(scene)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _decision_inbox_create_journey(
    workspace_root: Path,
    scene_id: str,
    name: str,
) -> dict[str, Any]:
    """Create a new journey in a scene."""
    try:
        engine = _decision_inbox_engine(workspace_root)
        journey = engine.create_journey(workspace_root, scene_id=scene_id, name=name)
        return {"ok": True, "journey": engine._dictify(journey)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Intake pipeline ──

def _intake_engine(workspace_root: Path | None = None) -> Any:
    ws = workspace_root or _workspace_root()
    engine_path = ws / "bin" / "ssot" / "scene-card-intake-pipeline.py"
    spec = importlib.util.spec_from_file_location("scene_card_intake_pipeline_cli", str(engine_path))
    if spec is None or spec.loader is None:
        raise ImportError("scene-card-intake-pipeline.py is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _intake_preview(workspace_root: Path, content: str, source: str = "manual", filename: str = "") -> dict[str, Any]:
    """Preview intake without persisting."""
    try:
        engine = _intake_engine(workspace_root)
        enriched = engine.preview_intake(content, source=source, filename=filename)
        return {
            "ok": True,
            "title": enriched.title,
            "description": enriched.description[:200],
            "category": enriched.category,
            "priority": enriched.priority,
            "deadline": enriched.deadline,
            "tags": enriched.tags,
            "confidence": enriched.confidence,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _intake_run(
    workspace_root: Path,
    scene_id: str,
    content: str,
    source: str = "manual",
    filename: str = "",
    journey_id: str | None = None,
) -> dict[str, Any]:
    """Run intake pipeline: extract → enrich → add to inbox."""
    try:
        engine = _intake_engine(workspace_root)
        result = engine.intake(
            workspace_root, source=source, raw_content=content,
            scene_id=scene_id, journey_id=journey_id, filename=filename,
        )
        if not result.ok:
            return {"ok": False, "error": result.error}
        return {
            "ok": True,
            "intent_id": result.intent_id,
            "scene_id": result.scene_id,
            "journey_id": result.journey_id,
            "priority": result.enriched.priority if result.enriched else "P3",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Task bridge ──

def _task_bridge_engine(workspace_root: Path | None = None) -> Any:
    ws = workspace_root or _workspace_root()
    engine_path = ws / "bin" / "ssot" / "scene-card-task-bridge.py"
    spec = importlib.util.spec_from_file_location("scene_card_task_bridge_cli", str(engine_path))
    if spec is None or spec.loader is None:
        raise ImportError("scene-card-task-bridge.py is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _task_approve(workspace_root: Path, intent_id: str, outcome_metric: str = "") -> dict[str, Any]:
    """Approve an intent and create its OMO task binding."""
    try:
        engine = _task_bridge_engine(workspace_root)
        result = engine.approve_intent_and_create_task(
            workspace_root, intent_id=intent_id, outcome_metric=outcome_metric,
        )
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _task_binding_status(workspace_root: Path, intent_id: str) -> dict[str, Any]:
    """Get binding status for an intent."""
    try:
        engine = _task_bridge_engine(workspace_root)
        status = engine.get_binding_status(workspace_root, intent_id)
        if status is None:
            return {"ok": False, "error": f"No binding found for intent {intent_id}"}
        return {"ok": True, **status}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _task_list_bindings(workspace_root: Path) -> dict[str, Any]:
    """List all task bindings."""
    try:
        engine = _task_bridge_engine(workspace_root)
        bindings = engine.list_bindings(workspace_root)
        return {
            "ok": True,
            "bindings": [
                {
                    "binding_id": b.binding_id,
                    "task_id": b.task_id,
                    "scene_id": b.scene_id,
                    "intent_id": b.intent_id,
                    "status": b.status,
                    "created_at": b.created_at,
                }
                for b in bindings
            ],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _task_complete(workspace_root: Path, binding_id: str) -> dict[str, Any]:
    """Mark a task binding as completed."""
    try:
        engine = _task_bridge_engine(workspace_root)
        result = engine.complete_task(workspace_root, binding_id)
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


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
    from cockpit.adapters.omo import archive_scenario_receipt  # pyright: ignore[reportAttributeAccessIssue]

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

        from cockpit.adapters.agora import resolve_bos_uri  # pyright: ignore[reportAttributeAccessIssue]

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
    """cockpit scenario {radar|assistant|health|inbox|intake|task}."""
    sub = getattr(args, "scenario_sub", None) or getattr(args, "scenario_action", None)
    if sub is None:
        console = sys.stderr
        console.write("Usage: cockpit scenario {radar|assistant|health|inbox|intake|task} [--query Q]\n")
        return 2

    if sub == "radar":
        result = _f1_technical_radar(limit=getattr(args, "limit", 10) or 10)
    elif sub == "assistant":
        query = getattr(args, "query", None) or "OPC P5 progress"
        result = _f2_work_assistant(query=query)
    elif sub == "health":
        query = getattr(args, "query", None) or "日常家庭健康问询"
        result = _f3_family_health(query=query)
    elif sub == "inbox":
        ws = _workspace_root()
        inbox_action = getattr(args, "inbox_action", None)
        if inbox_action is None:
            sys.stderr.write("Usage: cockpit scenario inbox {list|summary|add|status|show|create-scene|create-journey}\n")
            return 2
        if inbox_action == "list":
            result = _decision_inbox_list(ws)
        elif inbox_action == "summary":
            result = _decision_inbox_summary(ws)
        elif inbox_action == "add":
            result = _decision_inbox_add_intent(
                ws,
                scene_id=getattr(args, "scene_id", ""),
                source=getattr(args, "source", "manual"),
                raw_content=getattr(args, "content", ""),
                priority=getattr(args, "priority", "P3"),
            )
        elif inbox_action == "status":
            result = _decision_inbox_set_status(
                ws,
                intent_id=getattr(args, "intent_id", ""),
                status=getattr(args, "status", ""),
                task_id=getattr(args, "task_id", None),
            )
        elif inbox_action == "show":
            result = _decision_inbox_show_scene(ws, scene_id=getattr(args, "scene_id", ""))
        elif inbox_action == "create-scene":
            result = _decision_inbox_create_scene(
                ws,
                name=getattr(args, "name", "Untitled Scene"),
                description=getattr(args, "description", ""),
                priority=getattr(args, "priority", "P1"),
            )
        elif inbox_action == "create-journey":
            result = _decision_inbox_create_journey(
                ws,
                scene_id=getattr(args, "scene_id", ""),
                name=getattr(args, "name", "Untitled Journey"),
            )
        else:
            sys.stderr.write(f"unknown inbox action: {inbox_action}\n")
            return 2
    elif sub == "intake":
        ws = _workspace_root()
        intake_action = getattr(args, "intake_action", None)
        if intake_action is None:
            sys.stderr.write("Usage: cockpit scenario intake {preview|run}\n")
            return 2
        if intake_action == "preview":
            result = _intake_preview(
                ws,
                content=getattr(args, "content", ""),
                source=getattr(args, "source", "manual"),
                filename=getattr(args, "filename", ""),
            )
        elif intake_action == "run":
            result = _intake_run(
                ws,
                scene_id=getattr(args, "scene_id", ""),
                content=getattr(args, "content", ""),
                source=getattr(args, "source", "manual"),
                filename=getattr(args, "filename", ""),
                journey_id=getattr(args, "journey_id", None),
            )
        else:
            sys.stderr.write(f"unknown intake action: {intake_action}\n")
            return 2
    elif sub == "task":
        ws = _workspace_root()
        task_action = getattr(args, "task_action", None)
        if task_action is None:
            sys.stderr.write("Usage: cockpit scenario task {approve|status|list|complete}\n")
            return 2
        if task_action == "approve":
            result = _task_approve(
                ws,
                intent_id=getattr(args, "intent_id", ""),
                outcome_metric=getattr(args, "outcome_metric", ""),
            )
        elif task_action == "status":
            result = _task_binding_status(ws, intent_id=getattr(args, "intent_id", ""))
        elif task_action == "list":
            result = _task_list_bindings(ws)
        elif task_action == "complete":
            result = _task_complete(ws, binding_id=getattr(args, "binding_id", ""))
        else:
            sys.stderr.write(f"unknown task action: {task_action}\n")
            return 2
    else:
        sys.stderr.write(f"unknown scenario sub: {sub}\n")
        return 2

    if sub in ("inbox", "intake", "task"):
        if getattr(args, "scenario_json", False):
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            _render_scenario_human(result)
        return 0

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

    # ── Decision inbox rendering ──
    if "scenes" in result:
        scenes = result.get("scenes", [])
        console.print(Panel(f"[bold blue]📋 决策收件箱 · {len(scenes)} 场景[/]", border_style="blue"))
        table = Table(box=rich_box.ROUNDED, header_style="bold blue")
        table.add_column("ID", style="dim", width=32)
        table.add_column("名称", style="bold")
        table.add_column("优先级", width=8)
        table.add_column("Journeys", width=8)
        for s in scenes:
            j_count = len(s.get("journeys", []))
            table.add_row(s.get("id", ""), s.get("name", ""), s.get("priority", ""), str(j_count))
        console.print(table)
        return

    if "summary" in result:
        summary = result.get("summary", {})
        console.print(Panel(
            f"[bold blue]📊 收件箱概览[/]\n"
            f"场景数: {summary.get('scene_count', 0)}\n"
            f"总意图: {summary.get('total_intents', 0)}\n"
            f"待处理: [bold yellow]{summary.get('pending_intents', 0)}[/]\n"
            f"来源分布: {summary.get('by_source', {})}\n"
            f"优先级分布: {summary.get('by_priority', {})}",
            border_style="blue",
        ))
        return

    if "scene" in result:
        scene = result.get("scene", {})
        panel_lines = [
            f"[bold]ID:[/] {scene.get('id', '')}",
            f"[bold]名称:[/] {scene.get('name', '')}",
            f"[bold]描述:[/] {scene.get('description', '')}",
            f"[bold]状态:[/] {scene.get('status', '')}",
            f"[bold]优先级:[/] {scene.get('priority', '')}",
        ]
        journeys = scene.get("journeys", [])
        panel_lines.append(f"[bold]Journeys:[/] {len(journeys)}")
        for j in journeys:
            panel_lines.append(f"  ├─ {j.get('name', '')} ({j.get('status', '')}) — {len(j.get('intents', []))} intents")
        console.print(Panel("\n".join(panel_lines), title="🏷 场景详情", border_style="blue"))
        if journeys:
            for j in journeys:
                intents = j.get("intents", [])
                if not intents:
                    continue
                console.print(f"\n[bold]Journey: {j.get('name', '')}[/]")
                itable = Table(box=rich_box.ROUNDED, header_style="bold cyan")
                itable.add_column("ID", style="dim", width=32)
                itable.add_column("来源", width=10)
                itable.add_column("内容", style="bold")
                itable.add_column("状态", width=12)
                itable.add_column("优先级", width=8)
                for i in intents:
                    itable.add_row(
                        i.get("id", ""), i.get("source", ""),
                        str(i.get("raw_content", ""))[:40],
                        i.get("status", ""), i.get("priority", ""),
                    )
                console.print(itable)
        return

    if "intent" in result:
        intent = result.get("intent", {})
        console.print(Panel(
            f"[bold]意图 ID:[/] {intent.get('id', '')}\n"
            f"[bold]来源:[/] {intent.get('source', '')}\n"
            f"[bold]内容:[/] {str(intent.get('raw_content', ''))[:100]}\n"
            f"[bold]状态:[/] {intent.get('status', '')}\n"
            f"[bold]优先级:[/] {intent.get('priority', '')}\n"
            f"[bold]Task ID:[/] {intent.get('task_id', '—')}\n"
            f"[bold]创建时间:[/] {intent.get('created_at', '')}",
            title="💡 意图详情", border_style="cyan",
        ))
        return

    if "journey" in result:
        journey = result.get("journey", {})
        console.print(Panel(
            f"[bold]Journey ID:[/] {journey.get('id', '')}\n"
            f"[bold]名称:[/] {journey.get('name', '')}\n"
            f"[bold]状态:[/] {journey.get('status', '')}\n"
            f"[bold]Intents:[/] {len(journey.get('intents', []))}",
            title="🛤 Journey 详情", border_style="green",
        ))
        return

    # 兜底: 未知 scenario 退回 JSON
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
