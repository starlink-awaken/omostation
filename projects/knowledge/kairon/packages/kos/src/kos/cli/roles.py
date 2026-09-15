#!/usr/bin/env python3
"""
KOS Agent Role System (Phase 4.2)

Defines multi-agent roles and task routing for KOS.

Roles:
  - orchestrator : Cowork — always-on, global state, scheduled maintenance
  - worker       : Claude Code CLI — heavy compute, batch ops, file manipulation
  - specialist   : Codex / Gemini CLI — code review, domain expertise
  - capture      : WPS Note MCP — voice notes, quick capture

Usage:
    python3 agent-roles.py show         # Show current role assignments
    python3 agent-roles.py route <task> # Suggest which agent for a task
"""

from __future__ import annotations

import json
import sys
from typing import Any

# ── Role Definitions ─────────────────────────────────────

ROLES = {
    "orchestrator": {
        "label": "Orchestrator (Cowork)",
        "capabilities": [
            "persistent_memory",
            "scheduled_tasks",
            "mcp_connections",
            "multi_domain_awareness",
            "skill_execution",
            "state_management",
        ],
        "best_for": [
            "status queries",
            "knowledge governance",
            "cross-domain routing",
            "scheduled maintenance",
            "context bridging",
            "memory updates",
        ],
        "entry_point": "MEMORY.md → governance-state.md → route to domain",
    },
    "worker": {
        "label": "Worker (Claude Code CLI)",
        "capabilities": [
            "file_system_access",
            "batch_processing",
            "script_execution",
            "heavy_compute",
            "git_operations",
            "code_generation",
        ],
        "best_for": [
            "document generation",
            "bulk file operations",
            "index building",
            "pipeline execution",
            "data processing",
            "format conversion",
        ],
        "entry_point": "kos-mcp-server.py → search_knowledge → execute",
    },
    "specialist": {
        "label": "Specialist (Codex / Gemini CLI)",
        "capabilities": [
            "code_review",
            "architecture_analysis",
            "domain_expertise",
            "pattern_recognition",
            "optimization",
        ],
        "best_for": [
            "code review",
            "architecture review",
            "specialized analysis",
            "pattern discovery",
            "quality audit",
        ],
        "entry_point": "kos-mcp-server.py → get_knowledge → analyze",
    },
    "capture": {
        "label": "Capture (WPS Note MCP)",
        "capabilities": [
            "voice_transcription",
            "mobile_capture",
            "rich_text_editing",
            "quick_notes",
            "image_insertion",
        ],
        "best_for": [
            "meeting notes",
            "quick capture",
            "voice memos",
            "reading notes",
            "idea capture",
        ],
        "entry_point": "mcp__wpsnote__get_current_note → capture → tag route",
    },
}


def route_task(task: str) -> dict:  # type: ignore[type-arg]
    """Suggest agent role(s) for a given task description."""
    task_lower = task.lower()
    scores = {}

    keywords = {
        "orchestrator": [
            "状态",
            "巡检",
            "同步",
            "健康",
            "治理",
            "status",
            "sync",
            "health",
            "governance",
            "概览",
            "汇总",
        ],
        "worker": [
            "批量",
            "生成",
            "构建",
            "转换",
            "索引",
            "处理",
            "build",
            "generate",
            "batch",
            "convert",
            "index",
            "处理大量",
        ],
        "specialist": ["审查", "分析", "检查", "review", "audit", "analyze", "架构", "优化", "代码"],
        "capture": ["记录", "录音", "速记", "摘录", "笔记", "capture", "note", "随手", "记一下"],
    }

    for role, kws in keywords.items():
        scores[role] = sum(1 for kw in kws if kw in task_lower)

    best_role = max(scores, key=scores.get)  # type: ignore[arg-type]
    return {
        "task": task,
        "recommended_role": best_role,
        "role_info": ROLES[best_role],
        "all_scores": scores,
        "routing": f"Route to {best_role}: {ROLES[best_role]['entry_point']}",
    }


def show_roles() -> dict[str, Any]:
    """Display all agent roles."""
    result = {"roles": {}, "routing_rules": {}}  # type: ignore[var-annotated]
    for role_id, role_info in ROLES.items():
        result["roles"][role_id] = {
            "label": role_info["label"],
            "capabilities": role_info["capabilities"],
            "best_for": role_info["best_for"],
        }
    return result  # type: ignore[return-value]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps(show_roles(), ensure_ascii=False, indent=2))  # type: ignore[func-returns-value]
    elif sys.argv[1] == "route" and len(sys.argv) > 2:
        task = " ".join(sys.argv[2:])
        print(json.dumps(route_task(task), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(show_roles(), ensure_ascii=False, indent=2))  # type: ignore[func-returns-value]
