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

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
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
    """HealthMonitor (α.3 续: 读 system_health.yaml 快照 + 异常服务告警).

    tick: 扫 system_health 服务快照, 检测非 healthy 服务, 返回 alert action.
    守 fabric 红线: 只读状态快照, 不伪造健康, 不直连凭据/webhook, 不落盘
    (持久化归上层 omo_daemon agent_host_result, 不污染 KEI omo-alerts.jsonl).
    守 F14: 单 tick 失败不炸 host (AgentHost try/except 兜底).
    """

    agent_id = "health-monitor"

    _WORKSPACE = Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace")))
    _HEALTH_YAML = _WORKSPACE / ".omo" / "state" / "system_health.yaml"

    def tick(self) -> dict[str, Any]:
        services = self._load_services()
        if services is None:
            return {
                "action": "noop",
                "details": {"note": "health snapshot unavailable"},
            }

        unhealthy = self._detect_unhealthy(services)
        if not unhealthy:
            return {
                "action": "noop",
                "details": {"healthy_count": len(services), "total": len(services)},
            }

        return {
            "action": "alert",
            "details": {
                "unhealthy_count": len(unhealthy),
                "total": len(services),
                "services": unhealthy,
            },
        }

    @classmethod
    def _load_services(cls) -> dict[str, Any] | None:
        """读 system_health.yaml 服务快照 (缺失/损坏返回 None, 守 F14)."""
        if not cls._HEALTH_YAML.exists():
            return None
        try:
            import yaml

            data = yaml.safe_load(cls._HEALTH_YAML.read_text(encoding="utf-8")) or {}
            services = data.get("services")
            return services if isinstance(services, dict) else None
        except Exception:
            return None

    @classmethod
    def _detect_unhealthy(cls, services: dict[str, Any]) -> list[dict[str, str]]:
        """检测异常服务 (health_check 非空且不以 healthy 开头/非 scheduled)."""
        unhealthy: list[dict[str, str]] = []
        for name, info in services.items():
            if not isinstance(info, dict):
                continue
            hc = str(info.get("health_check", "")).strip()
            # 正常 = "healthy" / "healthy (probe)" / "scheduled"; 其余有值即异常
            if hc and not (hc.startswith("healthy") or hc == "scheduled"):
                unhealthy.append(
                    {
                        "name": str(name),
                        "health_check": hc,
                        "status": str(info.get("runtime", {}).get("status", "")),
                    }
                )
        return unhealthy


class KnowledgeCuratorAgent:
    """KnowledgeCurator stub (MOS 决策图谱, β.3 MVP).

    tick: stub 返回 noop (真实实现 β.3 续: 决策入 bos://memory/mos/* + 图谱 + 跨 scene 泛化).
    骨架先就位, 真实 MOS 决策图谱 + 跨 scene 学习留续.
    """

    agent_id = "knowledge-curator"

    def tick(self) -> dict[str, Any]:
        return {
            "action": "noop",
            "details": {
                "note": "KnowledgeCurator stub (β.3 MVP, 真实 MOS 决策图谱留续)"
            },
        }


def run_agent_tick(*, host: AgentHost | None = None) -> dict[str, Any]:
    """daemon 调用入口: 跑一次所有 Agent tick.

    默认 host = AgentHost(agents=[HealthMonitorAgent, KnowledgeCuratorAgent]) (α.3+β.3).
    SceneWatcher 适配 AgentProtocol (α.3 续, tick stub), 可外部注入 host.register(scene_watcher).
    """
    if host is None:
        host = AgentHost(
            agents=[HealthMonitorAgent(), KnowledgeCuratorAgent(), JourneyRunnerAgent()]
        )
    return host.tick_all()


@dataclass
class JourneyRunnerAgent:
    """AgentProtocol: 扫描 pending journeys, 推进一步 (四面一脊 ③ daemon 集成).

    tick: 扫 journey-states/ 找 awaiting_human 状态的 run,
    若 context 含 human_approved=True 则调 journey-runner resume.
    守 SRP: 只做检测+触发, 不执行 journey 逻辑 (journey-runner 的事).
    """

    @property
    def agent_id(self) -> str:
        return "journey-runner"

    def tick(self) -> dict[str, Any]:
        """Scan for resumable journey runs."""
        import json as _json
        from pathlib import Path as _Path

        workspace = _Path(
            os.environ.get("WORKSPACE_ROOT", str(_Path.home() / "Workspace"))
        )
        states_dir = (
            workspace / ".omo" / "_knowledge" / "workflow-mesh" / "journey-states"
        )
        if not states_dir.is_dir():
            return {"action": "noop", "details": {"note": "no journey states dir"}}

        resumable: list[dict[str, str]] = []
        for journey_dir in states_dir.iterdir():
            if not journey_dir.is_dir():
                continue
            for run_file in journey_dir.glob("*.jsonl"):
                try:
                    lines = run_file.read_text(encoding="utf-8").strip().split("\n")
                    if not lines or not lines[-1].strip():
                        continue
                    last = _json.loads(lines[-1])
                    if last.get("status") == "awaiting_human":
                        ctx = last.get("context", {})
                        if isinstance(ctx, dict) and ctx.get("human_approved"):
                            resumable.append(
                                {
                                    "journey_id": last.get(
                                        "journey_id", journey_dir.name
                                    ),
                                    "run_id": run_file.stem,
                                    "state": last.get("state", "?"),
                                }
                            )
                except Exception:
                    continue

        if resumable:
            return {
                "action": "trigger",
                "details": {
                    "resumable_journeys": resumable,
                    "note": f"{len(resumable)} journey run(s) ready to resume",
                },
            }
        return {"action": "noop", "details": {"note": "no resumable journeys"}}


__all__ = [
    "AgentHost",
    "AgentProtocol",
    "AgentTickResult",
    "HealthMonitorAgent",
    "JourneyRunnerAgent",
    "KnowledgeCuratorAgent",
    "run_agent_tick",
]
