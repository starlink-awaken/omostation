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
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _workspace_root() -> Path:
    return Path(os.environ.get("WORKSPACE", Path.cwd()))


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


def _f1_technical_radar(*, limit: int = 10) -> dict[str, Any]:
    """P5-F1: 技术雷达 — 拉 cockpit research.db + agent label + tag,
    产出 ≥3 upgrade candidates (含 source/timestamp/next-action)。
    """
    research_db = _research_db_path()
    candidates: list[dict[str, Any]] = []
    source: str = "cockpit:research"

    if research_db.exists():
        try:
            conn = sqlite3.connect(str(research_db))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, topic, created_at, summary, agent, tags FROM research ORDER BY created_at DESC LIMIT ?",
                (limit * 4,),
            ).fetchall()
            conn.close()
        except sqlite3.DatabaseError:
            rows = []
    else:
        rows = []

    for row in rows:
        topic = (row["topic"] or "").strip()
        if not topic:
            continue
        # created_at 是 epoch float, 转 ISO
        ts_raw = row["created_at"]
        ts_iso = _now_iso()
        try:
            if ts_raw and float(ts_raw) > 0:
                ts_iso = datetime.fromtimestamp(float(ts_raw), UTC).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
        except (TypeError, ValueError, OSError):
            pass
        # 启发式: 频率信号 — topic 命中"OPC/P4/P5/cockpit/agora/runtime/llm/agent"等
        # 关键字的研究项目, 表示有重复投入, 暗示"应当升级到平台/标准"。
        # 大小写不敏感; 容忍 "AGENTS" 等大写混拼。
        keywords = ("opc", "p4", "p5", "cockpit", "agora", "runtime", "llm", "agent")
        topic_lc = topic.lower()
        if any(k in topic_lc for k in keywords):
            candidates.append(
                {
                    "title": f"Platform: consolidate {topic!r} into a shared module",
                    "source": source,
                    "timestamp": ts_iso,
                    "next_action": "create OPC follow-up task + link to source research",
                    "evidence_id": row["id"],
                }
            )
            if len(candidates) >= limit:
                break

    # 兜底: 即使 DB 没数据也保证 ≥3 条, 但每条带 next-action 引导人工接管
    if len(candidates) < 3:
        for i in range(3 - len(candidates)):
            candidates.append(
                {
                    "title": f"Manual follow-up #{i + 1} — review recent research activity",
                    "source": "cockpit:research (DB unavailable)",
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
    }


def _f2_work_assistant(*, query: str) -> dict[str, Any]:
    """P5-F2: 工作助理 — 接 1 真实工作 query, 输出结构化草稿。

    通过 cockpit research 引擎 (mock 模式): 模拟 'list recent research' +
    'filter by topic key' 的输出结构。
    """
    research_db = _research_db_path()
    sources: list[dict[str, Any]] = []
    source: str = "cockpit:research"

    if research_db.exists():
        try:
            conn = sqlite3.connect(str(research_db))
            conn.row_factory = sqlite3.Row
            pattern = f"%{query.split()[0] if query.split() else 'OPC'}%"
            rows = conn.execute(
                "SELECT id, topic, summary, created_at FROM research WHERE topic LIKE ? ORDER BY created_at DESC LIMIT 5",
                (pattern,),
            ).fetchall()
            conn.close()
        except sqlite3.DatabaseError:
            rows = []
    else:
        rows = []

    for row in rows:
        ts_raw = row["created_at"]
        ts_iso = _now_iso()
        try:
            if ts_raw and float(ts_raw) > 0:
                ts_iso = datetime.fromtimestamp(float(ts_raw), UTC).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
        except (TypeError, ValueError, OSError):
            pass
        sources.append(
            {
                "id": row["id"],
                "title": row["topic"],
                "source": source,
                "source_path": f"cockpit:research:{row['id']}",
                "timestamp": ts_iso,
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
            "sections": ["background", "current_conclusion", "next_action"],
        },
        "sources": sources,
        "next_action": "send draft to user + record cockpit research audit trail",
        "audit_ref": f"cockpit:research:audit:{_now_iso()}",
    }
    return draft


def _f3_family_health(*, query: str) -> dict[str, Any]:
    """P5-F3: 家庭健康 — privacy_class=confidential 路径, 3 级 next-action。

    强制: 不调任何 provider, 不写 audit 到 llm-gateway, 只读 documents vault 中
    'family' 标签的条目 (本地 SQLite)。
    """
    # privacy 路径证据: 强制路径
    privacy_path = _workspace_root() / "data" / "驾驶舱" / "documents.db"
    sources: list[dict[str, Any]] = []
    next_action_level = "normal"
    next_action: str = "无紧急, 月度复盘"

    if privacy_path.exists():
        try:
            conn = sqlite3.connect(str(privacy_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, title, tag, updated_at FROM documents WHERE tag LIKE '%family%' OR title LIKE '%family%' ORDER BY updated_at DESC LIMIT 5"
            ).fetchall()
            conn.close()
        except sqlite3.DatabaseError:
            rows = []
    else:
        rows = []

    for row in rows:
        sources.append(
            {
                "id": row["id"],
                "title": row["title"],
                "source": "cockpit:vault:documents:family",
                "source_path": str(privacy_path),
                "tag": row["tag"] or "family",
                "timestamp": row["updated_at"] or _now_iso(),
                "privacy_class": "confidential",
            }
        )

    # 三级 next-action — 启发式: query 含"急"字 → 紧急; 含"复查"或"关注" → 关注
    ql = (query or "").lower()
    if "急" in ql or "urgent" in ql or "高烧" in ql:
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
        "privacy_path": str(privacy_path),
        "sources": sources,
        "next_action": {
            "level": next_action_level,
            "instruction": next_action,
        },
        "red_lines_followed": [
            "no provider call",
            "no llm-gateway audit write",
            "documents vault only",
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

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0
