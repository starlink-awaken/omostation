"""omo_agent_host.py — v10 Stage α.3 daemon Agent host (多 Agent 调度骨架) + β.3 KnowledgeCurator.

守 D3: 基于 omo_daemon 现有扩展 (不从零建), agent_host 是独立模块.
守 SOLID D: Agent 通过 AgentProtocol 注入 (AgentHost 不绑死实现).
守 F14: Agent 并发资源争抢 → 错误隔离 (单 Agent 失败不炸 host).
守 L2 (plan 务实): omo_daemon run_once 集成 (α.3 续已交付, run_once agent_host hook).

Agent 矩阵:
- HealthMonitorAgent (α.3): 系统健康 stub
- KnowledgeCuratorAgent (β.3): MOS 决策图谱 stub
- SceneWatcher (α.3 续, 外部注入): scene trigger stub (tick 在 scenewatcher.py)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


class AgentProtocol(Protocol):
    """Agent 注入契约 (SOLID D, AgentHost 调度)."""

    @property
    def agent_id(self) -> str:
        """Agent 唯一标识."""
        ...

    def tick(self) -> dict[str, Any]:
        """单次 tick (Agent 自主检查 + 决策).

        返回 {"action": "noop"|"trigger"|"alert"|..., "details": {...}}.
        """
        ...


@dataclass
class AgentTickResult:
    """单 Agent tick 结果 (audit trail)."""

    agent_id: str
    ok: bool
    action: str = "noop"
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class AgentHost:
    """Agent host: 注册 Agent + tick 调度 (错误隔离, 守 F14).

    AgentHost 是 daemon Agent 调度骨架 (α.3). omo_daemon run_once agent_host hook
    调 host.tick_all() (α.3 续已交付).
    """

    agents: list[AgentProtocol] = field(default_factory=list)

    def register(self, agent: AgentProtocol) -> None:
        """注册 Agent (运行时动态加)."""
        self.agents.append(agent)

    def tick_all(self) -> dict[str, Any]:
        """调度所有 Agent tick (错误隔离: 单 Agent 失败不炸 host, 守 F14)."""
        results: list[AgentTickResult] = []
        for agent in self.agents:
            try:
                out = agent.tick()
                results.append(
                    AgentTickResult(
                        agent_id=agent.agent_id,
                        ok=True,
                        action=str(out.get("action", "noop")),
                        details=out.get("details", {}),
                    )
                )
            except Exception as exc:  # 错误隔离 (F14): 单 Agent 失败不炸 host
                results.append(
                    AgentTickResult(
                        agent_id=agent.agent_id,
                        ok=False,
                        error=str(exc),
                    )
                )
        ok_count = sum(1 for r in results if r.ok)
        return {
            "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "agent_count": len(self.agents),
            "ok_count": ok_count,
            "failed_count": len(results) - ok_count,
            "results": [r.__dict__ for r in results],
        }


class HealthMonitorAgent:
    """HealthMonitor stub (系统健康 + 主动告警, α.3 MVP).

    tick: stub 返回 noop (真实实现 α.3 续: 读 system.yaml health + alert).
    骨架先就位, 真实健康检查接 omo_health + omo_alert 留续.
    """

    agent_id = "health-monitor"

    def tick(self) -> dict[str, Any]:
        return {
            "action": "noop",
            "details": {"note": "HealthMonitor stub (α.3 MVP, 真实接 omo_health 留续)"},
        }


class KnowledgeCuratorAgent:
    """KnowledgeCurator stub (MOS 决策图谱, β.3 MVP).

    tick: stub 返回 noop (真实实现 β.3 续: 决策入 bos://memory/mos/* + 图谱 + 跨 scene 泛化).
    骨架先就位, 真实 MOS 决策图谱 + 跨 scene 学习留续.
    """

    agent_id = "knowledge-curator"

    def tick(self) -> dict[str, Any]:
        return {
            "action": "noop",
            "details": {"note": "KnowledgeCurator stub (β.3 MVP, 真实 MOS 决策图谱留续)"},
        }


def run_agent_tick(*, host: AgentHost | None = None) -> dict[str, Any]:
    """daemon 调用入口: 跑一次所有 Agent tick.

    默认 host = AgentHost(agents=[HealthMonitorAgent, KnowledgeCuratorAgent]) (α.3+β.3).
    SceneWatcher 适配 AgentProtocol (α.3 续, tick stub), 可外部注入 host.register(scene_watcher).
    """
    if host is None:
        host = AgentHost(agents=[HealthMonitorAgent(), KnowledgeCuratorAgent()])
    return host.tick_all()


__all__ = [
    "AgentHost",
    "AgentProtocol",
    "AgentTickResult",
    "HealthMonitorAgent",
    "KnowledgeCuratorAgent",
    "run_agent_tick",
]
