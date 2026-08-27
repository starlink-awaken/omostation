"""Digital Brain Agent Profiles — AgentCard + Capability registry.

Defines the digital brain agents (mail, health, admin workflow, etc.)
as Swarm Engine AgentCard entries with capability descriptors.

These profiles enable:
  - Agent discovery via CapabilityCatalog
  - Hatcher spawning via internal_thread handler
  - IntelligentAgent routing by domain

Usage::

    from swarm_engine.agent_profiles import DIGITAL_BRAIN_AGENTS, get_agent_by_id

    profile = get_agent_by_id("mail-agent")
    # profile["capabilities"] → ["read_mail", "classify_mail", ...]
"""

from __future__ import annotations

from typing import Any

# ── Digital Brain Agent Definitions ────────────────────────────────────────

DIGITAL_BRAIN_AGENTS: list[dict[str, Any]] = [
    {
        "id": "mail-agent",
        "name": "邮件感知代理",
        "description": "读取 Apple Mail + 网易邮箱大师，LLM 分类，提取任务，生成日报",
        "capabilities": ["read_mail", "classify_mail", "extract_task", "generate_briefing"],
        "domain": "work",
        "handler_type": "internal_thread",
        "module": "bin.ssot.mail_agent",
        "risk_profile": {
            "read_mail": "L0",
            "classify_mail": "L0",
            "extract_task": "L0",
            "generate_briefing": "L1",
        },
    },
    {
        "id": "health-agent",
        "name": "健康趋势代理",
        "description": "扫描健康报告，LLM 趋势分析，生成每周健康简报",
        "capabilities": ["scan_health_reports", "analyze_trends", "generate_weekly_briefing"],
        "domain": "health",
        "handler_type": "internal_thread",
        "module": "bin.ssot.health_agent",
        "risk_profile": {
            "scan_health_reports": "L0",
            "analyze_trends": "L0",
            "generate_weekly_briefing": "L1",
        },
    },
    {
        "id": "admin-workflow",
        "name": "行政流程代理",
        "description": "9步行政流程：通知→转发→收集→汇总→审阅→提交",
        "capabilities": ["forward_notice", "collect_data", "compile_report", "review_submit"],
        "domain": "work",
        "handler_type": "internal_thread",
        "module": "bin.ssot.admin_scenes",
        "risk_profile": {
            "forward_notice": "L2",
            "collect_data": "L1",
            "compile_report": "L1",
            "review_submit": "L3",
        },
    },
    {
        "id": "doc-generator",
        "name": "文档生成代理",
        "description": "从模板生成通知/表格/报告/会议纪要/工作计划草稿",
        "capabilities": ["generate_doc", "save_draft"],
        "domain": "work",
        "handler_type": "internal_thread",
        "module": "bin.ssot.doc_generator",
        "risk_profile": {
            "generate_doc": "L0",
            "save_draft": "L1",
        },
    },
    {
        "id": "deadline-tracker",
        "name": "截止日期追踪代理",
        "description": "注册任务截止日期，检查邮件回复，提醒逾期",
        "capabilities": ["register_task", "check_replies", "check_deadlines"],
        "domain": "work",
        "handler_type": "internal_thread",
        "module": "bin.ssot.deadline_tracker",
        "risk_profile": {
            "register_task": "L0",
            "check_replies": "L0",
            "check_deadlines": "L1",
        },
    },
]


# ── Lookup utilities ───────────────────────────────────────────────────────


def get_agent_by_id(agent_id: str) -> dict[str, Any] | None:
    """Find an agent profile by ID."""
    for agent in DIGITAL_BRAIN_AGENTS:
        if agent["id"] == agent_id:
            return dict(agent)
    return None


def get_agents_by_domain(domain: str) -> list[dict[str, Any]]:
    """Find all agents in a specific domain."""
    return [dict(a) for a in DIGITAL_BRAIN_AGENTS if a["domain"] == domain]


def get_agents_by_capability(capability: str) -> list[dict[str, Any]]:
    """Find all agents that have a specific capability."""
    return [dict(a) for a in DIGITAL_BRAIN_AGENTS if capability in a.get("capabilities", [])]


def get_all_capabilities() -> set[str]:
    """Return the full set of capabilities across all agents."""
    caps: set[str] = set()
    for agent in DIGITAL_BRAIN_AGENTS:
        caps.update(agent.get("capabilities", []))
    return caps


# ── Swarm AgentCard conversion ─────────────────────────────────────────────


def to_agent_cards() -> list[dict[str, Any]]:
    """Convert profiles to Swarm Engine AgentCard format for discovery."""
    cards = []
    for agent in DIGITAL_BRAIN_AGENTS:
        cards.append({
            "id": agent["id"],
            "name": agent["name"],
            "description": agent.get("description", ""),
            "capabilities": agent.get("capabilities", []),
            "domain": agent.get("domain", "work"),
            "handler_type": agent.get("handler_type", "internal_thread"),
            "module": agent.get("module", ""),
        })
    return cards
