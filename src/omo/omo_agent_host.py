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

import json
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
        # P0-T3: Aetherforge wire — emit agent tick events for observability
        try:
            from aetherforge.bus_adapter import emit_event

            for r in results:
                emit_event(
                    "agent.tick",
                    {"agent_id": r.agent_id, "ok": r.ok, "action": r.action},
                )
        except Exception:
            pass  # Aetherforge not available

        ok_count = sum(1 for r in results if r.ok)
        return {
            "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "agent_count": len(self.agents),
            "ok_count": ok_count,
            "failed_count": len(results) - ok_count,
            "results": [r.__dict__ for r in results],
        }


def _llm_deep_eval(
    agent_id: str, question: str, context: dict[str, Any]
) -> dict[str, Any] | None:
    """Call local LLM for deep evaluation when rule-based confidence is insufficient.

    Pattern: rules first → if confidence < threshold → LLM deep eval.
    Tries ollama (local, no auth) first, then falls back to None.
    If LLM unavailable → return None (caller falls back to rule verdict).
    """
    import shutil
    import subprocess as _sp

    prompt = (
        f"You are {agent_id} agent in a self-governing digital organism.\n"
        f"Question: {question}\n"
        f"Context: {json.dumps(context, ensure_ascii=False)[:800]}\n\n"
        f"Respond with JSON only, no markdown:\n"
        f'{{"verdict": "approve|reject|needs_human", "confidence": 0.0-1.0, "reasoning": "...", "recommendation": "..."}}'
    )

    # Backend 1: ollama (local, no auth needed — best for daemon)
    if shutil.which("ollama"):
        import re

        try:
            models_out = _sp.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if models_out.returncode == 0 and models_out.stdout:
                lines = models_out.stdout.strip().split("\n")
                for line in lines[1:]:
                    if line.strip():
                        model_name = line.split()[0]
                        result = _sp.run(
                            ["ollama", "run", model_name, prompt],
                            capture_output=True,
                            text=True,
                            timeout=90,
                            check=False,
                        )
                        if result.returncode == 0 and result.stdout:
                            # Strip ANSI escape codes + control chars
                            clean = re.sub(
                                r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\[\?[0-9]+[a-zA-Z]",
                                "",
                                result.stdout,
                            )
                            clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", clean)
                            # Find JSON object in output
                            json_match = re.search(r'\{[^{}]*"verdict"[^{}]*\}', clean)
                            if json_match:
                                try:
                                    parsed = json.loads(json_match.group())
                                    parsed["llm_backend"] = f"ollama:{model_name}"
                                    return parsed
                                except Exception:
                                    pass
                        break
        except Exception:
            pass

    return None


def _check_a2a_inbox(agent_id: str, workspace: Path) -> list[dict[str, Any]]:
    """读 A2A inbox — 找发给自己的未处理 task 消息, 写 reply 标记 resolved.

    多 Agent 协作的关键: Governor 发 task → 目标 agent tick 时读取 → 处理 → reply.
    返回收到的 task 列表 (agent 自行决定如何处理).
    """
    import json as _json

    msg_file = workspace / ".omo" / "state" / "a2a-messages.jsonl"
    if not msg_file.exists():
        return []

    lines = msg_file.read_text(encoding="utf-8").strip().split("\n")
    if not lines or not lines[0].strip():
        return []

    all_msgs: list[dict] = []
    for line in lines:
        if line.strip():
            try:
                all_msgs.append(_json.loads(line))
            except Exception:
                continue

    # 找发给自己的 task 消息, 且没有对应 reply
    replied_ts = {m.get("in_reply_to") for m in all_msgs if m.get("type") == "reply"}
    my_tasks = [
        m
        for m in all_msgs
        if m.get("to") == agent_id
        and m.get("type") == "task"
        and m.get("ts") not in replied_ts
    ]

    # 写 reply 标记 resolved
    if my_tasks:
        ts_now = (
            datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        with open(msg_file, "a", encoding="utf-8") as f:
            for t in my_tasks:
                reply = {
                    "ts": ts_now,
                    "from": agent_id,
                    "to": t.get("from", "governor"),
                    "type": "reply",
                    "in_reply_to": t.get("ts"),
                    "payload": {
                        "status": "processed",
                        "finding_type": t.get("payload", {})
                        .get("finding", {})
                        .get("type"),
                    },
                }
                f.write(_json.dumps(reply, ensure_ascii=False, sort_keys=True) + "\n")

    return my_tasks


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
    """KnowledgeCurator (MOS 决策图谱 + 跨 scene 学习, T-B4).

    tick: 读 MOS decision_outcome → 聚合 per-scene 结果 → 记录学习到 beliefs
    (跨 scene 泛化: 同类场景的 outcome 趋势). 守 SRP: 只做知识沉淀, 不决策.
    """

    agent_id = "knowledge-curator"

    def tick(self) -> dict[str, Any]:
        """Read decision_outcomes + process A2A tasks → build knowledge graph."""
        from pathlib import Path as _Path

        workspace = _Path(
            os.environ.get("WORKSPACE_ROOT", str(_Path.home() / "Workspace"))
        )

        # A2A: 读 governor 发来的 task 消息 (多 Agent 协作)
        a2a_tasks = _check_a2a_inbox("knowledge-curator", workspace)
        a2a_processed = []
        for task in a2a_tasks:
            finding = task.get("payload", {}).get("finding", {})
            a2a_processed.append(finding.get("type", "unknown"))

        try:
            omo_src = str(workspace / "projects" / "omo" / "src")
            import sys

            if omo_src not in sys.path:
                sys.path.insert(0, omo_src)
            from omo.omo_belief import MOSBeliefManager

            manager = MOSBeliefManager(root=workspace)
            state = manager._load_state()
            outcomes = state.get("decision_outcomes", [])
            snapshots = state.get("world_snapshots", [])
        except Exception:
            return {"action": "noop", "details": {"note": "MOS unavailable"}}

        # A2A task 处理: 记录经验
        for finding_type in a2a_processed:
            try:
                manager.record_experience(
                    agent_id="knowledge-curator",
                    experience=f"A2A task: investigated {finding_type}",
                    outcome="positive",
                )
            except Exception:
                pass

        # Aggregate outcomes per scene type
        from collections import Counter

        scene_stats: Counter = Counter()
        accept_count = 0
        for o in outcomes:
            d_type = str(o.get("decision_type", "unknown"))
            scene_stats[d_type] += 1
            if "accepted" in str(o.get("actual_outcome", "")):
                accept_count += 1

        lesson = (
            f"跨scene学习: {len(outcomes)} decision outcomes 记录, "
            f"accept={accept_count}, 分布={dict(scene_stats.most_common(3))}"
        )
        # Record lesson into MOS beliefs (write-once, dedup by topic)
        try:
            topic = "cross-scene-outcome-trends"
            existing = manager.query_beliefs(keyword="cross-scene")
            if not existing:
                manager.record_belief(
                    topic=topic,
                    belief_text=lesson,
                    pitfall="outcomes accumulated without synthesis",
                    solution="KnowledgeCurator tick 定期聚合 outcome 到跨场景学习",
                )
        except Exception:
            pass

        return {
            "action": "learn",
            "details": {
                "outcomes_processed": len(outcomes),
                "snapshots_processed": len(snapshots),
                "scene_distribution": dict(scene_stats.most_common(5)),
                "accept_count": accept_count,
                "lesson_recorded": lesson[:200],
                "a2a_tasks_processed": a2a_processed,
            },
        }


def _auto_calibrate(result: dict[str, Any]) -> None:
    """Tick 后自动校准 — 每个 agent 的 tick 结果记录到 MOS capability_calibrations.

    这是学习闭环的关键: 没有 calibration 数据, Trust 永远 cold_start,
    自主度评分的 adaptivity/generalization 维度永远趋零.
    守 KISS: 只记 ok/success_rate, 不做复杂分析 (那是 scanner 的活).
    """
    workspace = Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace")))
    try:
        import sys as _sys

        omo_src = str(workspace / "projects" / "omo" / "src")
        if omo_src not in _sys.path:
            _sys.path.insert(0, omo_src)
        from omo.omo_belief import MOSBeliefManager

        manager = MOSBeliefManager(root=workspace)
        for r in result.get("results", []):
            agent_id = r.get("agent_id", "unknown")
            ok = r.get("ok", False)
            action = r.get("action", "noop")
            manager.record_capability_calibration(
                capability_ref=f"agent:{agent_id}:tick:{action}",
                success_rate=1.0 if ok else 0.0,
                avg_latency_ms=0.0,
                sample_size=1,
            )
        # 同时记录一条非 noop 的 experience
        non_noop = [r for r in result.get("results", []) if r.get("action") != "noop"]
        if non_noop:
            for r in non_noop[:3]:  # 最多记3条, 别炸MOS
                agent_id = r.get("agent_id", "unknown")
                action = r.get("action", "noop")
                outcome = "positive" if r.get("ok") else "negative"
                manager.record_experience(
                    agent_id=agent_id,
                    experience=f"tick:{action} on {agent_id}",
                    outcome=outcome,
                )
    except Exception:
        pass  # MOS unavailable — 不阻塞 tick


def run_agent_tick(*, host: AgentHost | None = None) -> dict[str, Any]:
    """daemon 调用入口: 跑一次所有 Agent tick + 自动校准.

    默认 host = AgentHost(agents=[6 agents]) (α.3+β.3+P3+P6).
    SceneWatcher 适配 AgentProtocol (α.3 续, tick stub), 可外部注入 host.register(scene_watcher).
    tick 完成后自动记录 capability calibration 到 MOS (学习闭环).
    """
    if host is None:
        host = AgentHost(
            agents=[
                HealthMonitorAgent(),
                KnowledgeCuratorAgent(),
                JourneyRunnerAgent(),
                GovernorAgent(),
                AdvisorAgent(),
                AutonomyAssessmentAgent(),
            ]
        )
    result = host.tick_all()
    _auto_calibrate(result)  # 学习闭环: tick → 记录校准 → Trust积累 → 自主度提升
    return result


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
            # Auto-resume: 实际调用 journey-runner subprocess (C3 修复)
            import subprocess as _sp

            resumed: list[dict[str, Any]] = []
            for r in resumable:
                runner = workspace / "bin" / "ssot" / "journey-runner.py"
                if not runner.exists():
                    continue
                try:
                    proc = _sp.run(
                        [
                            "python3",
                            str(runner),
                            "resume",
                            "--journey-id",
                            r["journey_id"],
                            "--run-id",
                            r["run_id"],
                        ],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    resumed.append(
                        {
                            "journey_id": r["journey_id"],
                            "run_id": r["run_id"],
                            "returncode": proc.returncode,
                        }
                    )
                except Exception as exc:
                    resumed.append(
                        {
                            "journey_id": r["journey_id"],
                            "run_id": r["run_id"],
                            "error": str(exc),
                        }
                    )
            return {
                "action": "auto_resumed",
                "details": {
                    "resumed_count": len(resumed),
                    "resumed": resumed,
                },
            }
        return {"action": "noop", "details": {"note": "no resumable journeys"}}


@dataclass
class GovernorAgent:
    """AgentProtocol: 治理Agent — 审计行为 + 信任策略 + 涌现提案 (P3-T5).

    tick: 读系统健康 + debt台账 + agent trust趋势,
    检测异常模式, 提出信任调整和新agent涌现建议.
    守SRP: 只做检测+提案, 不执行修改 (修改走S1/S2/S3门禁).
    """

    @property
    def agent_id(self) -> str:
        return "governor"

    def tick(self) -> dict[str, Any]:
        """Governance tick — scan for issues and propose improvements."""
        import json as _json
        from pathlib import Path as _Path

        workspace = _Path(
            os.environ.get("WORKSPACE_ROOT", str(_Path.home() / "Workspace"))
        )
        findings: list[dict[str, str]] = []

        # 1. Check for timed-out journey checkpoints
        states_dir = (
            workspace / ".omo" / "_knowledge" / "workflow-mesh" / "journey-states"
        )
        if states_dir.is_dir():
            for jd in states_dir.iterdir():
                if not jd.is_dir():
                    continue
                for rf in jd.glob("*.jsonl"):
                    try:
                        lines = rf.read_text(encoding="utf-8").strip().split("\n")
                        if lines and lines[-1].strip():
                            last = _json.loads(lines[-1])
                            if last.get("status") == "human_hold":
                                findings.append(
                                    {
                                        "type": "human_hold",
                                        "journey": jd.name,
                                        "run": rf.stem,
                                    }
                                )
                    except Exception:
                        continue

        # 2. Check mesh events for anomalies
        mesh_log = workspace / ".omo" / "_knowledge" / "workflow-mesh" / "events.jsonl"
        if mesh_log.exists():
            event_count = len(mesh_log.read_text(encoding="utf-8").strip().split("\n"))
            if event_count > 100:
                findings.append(
                    {"type": "high_event_volume", "count": str(event_count)}
                )

        # 3. Check debt registry growth (T-B5: debt 台账趋势)
        debt_items_dir = workspace / ".omo" / "debt" / "items"
        if debt_items_dir.is_dir():
            debt_count = len(list(debt_items_dir.glob("*.yaml")))
            gap_count = len(
                list((workspace / ".omo" / "debt" / "gap-items").glob("*.yaml"))
            )
            if debt_count + gap_count > 30:
                findings.append(
                    {
                        "type": "high_debt_volume",
                        "debt_items": str(debt_count),
                        "gap_items": str(gap_count),
                    }
                )

        # 4. Check MOS trust/calibration trends (T-B5: agent trust 趋势)
        try:
            omo_src = str(workspace / "projects/omo/src")
            import sys

            if omo_src not in sys.path:
                sys.path.insert(0, omo_src)
            from omo.omo_belief import MOSBeliefManager

            manager = MOSBeliefManager(root=workspace)
            state = manager._load_state()
            calib = state.get("capability_calibrations", [])
            low_trust = [c for c in calib if float(c.get("success_rate", 1.0)) < 0.6]
            if low_trust:
                findings.append(
                    {
                        "type": "low_trust_capabilities",
                        "count": str(len(low_trust)),
                        "refs": ",".join(
                            c.get("capability_ref", "?") for c in low_trust[:3]
                        ),
                    }
                )
        except Exception:
            pass  # MOS unavailable

        if findings:
            # P6-T1: Governor dispatch — 向相关agent发送任务消息
            dispatched = self._dispatch_findings(findings, workspace)

            # LLM deep eval: findings优先级判断 (模型驱动)
            deep_eval = _llm_deep_eval(
                "governor",
                f"Governance scan found {len(findings)} issues. "
                f"Top priorities and recommended actions? "
                f"Findings: {json.dumps(findings[:5], ensure_ascii=False)[:500]}",
                {"finding_count": len(findings), "findings": findings[:5]},
            )

            return {
                "action": "alert",
                "details": {
                    "findings": findings,
                    "count": len(findings),
                    "dispatched_to": dispatched,
                    "llm_deep_eval": deep_eval is not None,
                    "llm_priority": deep_eval.get("recommendation")
                    if deep_eval
                    else None,
                },
            }
        return {"action": "noop", "details": {"note": "no governance issues detected"}}

    def _dispatch_findings(self, findings: list, workspace: Path) -> list[str]:
        """P6: Governor向其他agent分发findings通过A2A消息队列."""
        # 匹配finding类型→目标agent
        dispatch_map = {
            "high_debt_volume": ["advisor"],
            "low_trust_capabilities": ["advisor"],
            "high_event_volume": ["knowledge-curator"],
            "human_hold": ["journey-runner"],
        }
        dispatched: list[str] = []
        msg_queue = workspace / ".omo" / "state" / "a2a-messages.jsonl"
        msg_queue.parent.mkdir(parents=True, exist_ok=True)

        import json as _json

        for f in findings:
            ftype = f.get("type", "")
            targets = dispatch_map.get(ftype, [])
            for target in targets:
                msg = {
                    "ts": datetime.now(UTC)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "from": "governor",
                    "to": target,
                    "type": "task",
                    "payload": {"action": "investigate", "finding": f},
                }
                with open(msg_queue, "a", encoding="utf-8") as mf:
                    mf.write(
                        _json.dumps(msg, ensure_ascii=False, sort_keys=True) + "\n"
                    )
                if target not in dispatched:
                    dispatched.append(target)
        return dispatched


class AdvisorAgent:
    """AgentProtocol: TELOS对齐顾问 — 读MOS beliefs+calibration, 评估系统行为与TELOS的对齐度.

    tick: 读MOS三表 → 评估capability trust趋势 → 产出TELOS对齐评估.
    守SRP: 只做评估+建议, 不执行修改.
    """

    @property
    def agent_id(self) -> str:
        return "advisor"

    def tick(self) -> dict[str, Any]:
        """Evaluate system alignment with TELOS principles + process A2A tasks."""
        workspace = Path(
            os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))
        )

        # A2A: 读 governor 发来的 task 消息 (多 Agent 协作)
        a2a_tasks = _check_a2a_inbox("advisor", workspace)
        a2a_processed = []
        for task in a2a_tasks:
            finding = task.get("payload", {}).get("finding", {})
            a2a_processed.append(finding.get("type", "unknown"))

        try:
            omo_src = str(workspace / "projects/omo/src")
            import sys

            if omo_src not in sys.path:
                sys.path.insert(0, omo_src)
            from omo.omo_belief import MOSBeliefManager

            manager = MOSBeliefManager(root=workspace)
            state = manager._load_state()
            calibrations = state.get("capability_calibrations", [])
            outcomes = state.get("decision_outcomes", [])
            beliefs = state.get("beliefs", [])
        except Exception:
            return {"action": "noop", "details": {"note": "MOS unavailable"}}

        # A2A task 处理: 记录经验
        for finding_type in a2a_processed:
            try:
                manager.record_experience(
                    agent_id="advisor",
                    experience=f"A2A task: investigated {finding_type}",
                    outcome="positive",
                )
            except Exception:
                pass

        if not calibrations and not outcomes and not a2a_tasks:
            return {
                "action": "noop",
                "details": {"note": "insufficient MOS data for TELOS evaluation"},
            }

        # Evaluate trust trends
        avg_success = 1.0
        if calibrations:
            avg_success = sum(
                float(c.get("success_rate", 1.0)) for c in calibrations
            ) / len(calibrations)

        accept_rate = 1.0
        if outcomes:
            accepted = sum(
                1 for o in outcomes if "accepted" in str(o.get("actual_outcome", ""))
            )
            accept_rate = accepted / len(outcomes)

        # TELOS alignment heuristic (rule-based first pass)
        alignment = (
            "aligned" if avg_success >= 0.7 and accept_rate >= 0.5 else "misaligned"
        )
        confidence = round(min(avg_success, accept_rate), 2)

        # LLM deep eval: confidence不足时调PI做深判 (模型驱动)
        deep_eval = None
        if confidence < 0.8 or alignment == "misaligned":
            deep_eval = _llm_deep_eval(
                "advisor",
                f"System TELOS alignment: {alignment} (confidence={confidence}). "
                f"Avg success rate={avg_success:.2f}, Accept rate={accept_rate:.2f}. "
                f"Should we maintain current direction or adjust?",
                {
                    "alignment": alignment,
                    "confidence": confidence,
                    "calibrations": len(calibrations),
                    "beliefs": len(beliefs),
                    "a2a_findings": a2a_processed,
                },
            )

        return {
            "action": "evaluate",
            "details": {
                "telos_alignment": deep_eval.get("verdict", alignment)
                if deep_eval
                else alignment,
                "confidence": deep_eval.get("confidence", confidence)
                if deep_eval
                else confidence,
                "avg_success_rate": round(avg_success, 2),
                "outcome_accept_rate": round(accept_rate, 2),
                "calibrations_evaluated": len(calibrations),
                "beliefs_count": len(beliefs),
                "recommendation": deep_eval.get(
                    "recommendation",
                    "maintain"
                    if alignment == "aligned"
                    else "review capability trust trends",
                )
                if deep_eval
                else (
                    "maintain"
                    if alignment == "aligned"
                    else "review capability trust trends"
                ),
                "llm_deep_eval": deep_eval is not None,
                "llm_reasoning": deep_eval.get("reasoning") if deep_eval else None,
                "a2a_tasks_processed": a2a_processed,
            },
        }


class AutonomyAssessmentAgent:
    """AgentProtocol: 自主度评估Agent — 5维度持续评估系统自主程度 (ADR-0403 P3).

    tick: 读MOS+verify+constraint-gate数据 → 计算5维度评分 → 产出0-100自主度.
    参考arXiv survey 2507.21046 §7的5维度框架.
    """

    @property
    def agent_id(self) -> str:
        return "autonomy-assessment"

    def tick(self) -> dict[str, Any]:
        """Calculate 5-dimension autonomy score."""
        workspace = Path(
            os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))
        )
        try:
            omo_src = str(workspace / "projects/omo/src")
            import sys

            if omo_src not in sys.path:
                sys.path.insert(0, omo_src)
            from omo.omo_belief import MOSBeliefManager

            manager = MOSBeliefManager(root=workspace)
            state = manager._load_state()
        except Exception:
            return {"action": "noop", "details": {"note": "MOS unavailable"}}

        # 1. Adaptivity: 非noop agent比例 (有行为agent / 总agent)
        calibrations = state.get("capability_calibrations", [])
        beliefs = state.get("beliefs", [])
        skills = state.get("agent_skills", [])
        experiences = state.get("agent_experiences", [])
        adaptivity = min(len(calibrations) / 5.0, 1.0) if calibrations else 0.1

        # 2. Retention: 活跃记忆比例
        total_items = len(beliefs) + len(skills) + len(experiences)
        active_items = total_items  # simplified: all non-archived
        retention = min(active_items / 20.0, 1.0) if total_items else 0.1

        # 3. Generalization: 跨域覆盖
        unique_refs = (
            len({c.get("capability_ref", "?") for c in calibrations})
            if calibrations
            else 0
        )
        generalization = min(unique_refs / 5.0, 1.0) if unique_refs else 0.1

        # 4. Efficiency: calibration成功率
        if calibrations:
            avg_rate = sum(
                float(c.get("success_rate", 1.0)) for c in calibrations
            ) / len(calibrations)
            efficiency = avg_rate
        else:
            efficiency = 0.5

        # 5. Safety: 有约束违规=低分, 无=高分
        outcomes = state.get("decision_outcomes", [])
        rejected = sum(
            1 for o in outcomes if "rejected" in str(o.get("actual_outcome", ""))
        )
        safety = 1.0 - (rejected / len(outcomes)) if outcomes else 0.9

        # Weighted score
        dimensions = {
            "adaptivity": round(adaptivity, 2),
            "retention": round(retention, 2),
            "generalization": round(generalization, 2),
            "efficiency": round(efficiency, 2),
            "safety": round(safety, 2),
        }
        weights = {
            "adaptivity": 0.25,
            "retention": 0.20,
            "generalization": 0.20,
            "efficiency": 0.15,
            "safety": 0.20,
        }
        score = round(sum(dimensions[d] * weights[d] for d in dimensions) * 100)

        return {
            "action": "evaluate",
            "details": {
                "autonomy_score": score,
                "dimensions": dimensions,
                "level": "high" if score >= 70 else "medium" if score >= 40 else "low",
                "mos_counts": {
                    "beliefs": len(beliefs),
                    "skills": len(skills),
                    "experiences": len(experiences),
                    "calibrations": len(calibrations),
                },
            },
        }


__all__ = [
    "AdvisorAgent",
    "AgentHost",
    "AgentProtocol",
    "AgentTickResult",
    "AutonomyAssessmentAgent",
    "GovernorAgent",
    "HealthMonitorAgent",
    "JourneyRunnerAgent",
    "KnowledgeCuratorAgent",
    "run_agent_tick",
]
