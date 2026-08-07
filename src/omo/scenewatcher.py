"""scenewatcher.py — SceneWatcher resident-agent (v8 stub + α.5 cost_estimate + α.3续 tick).

守 ADR-0365: 不直接调 mesh (走 journey-runner).
守 ADR-0372: 决策日志入 bos://memory/mos/* (经 MOSBeliefManager.record_decision_outcome).
守 F2: 只处理复杂条件 (agent_decisions), 简单条件交 journey-runner.
守 F6: 低置信度 → human_veto (决策可逆, 架构原则).
守 F7: event_driven (邮件触发非 tick).
守 fabric 红线: lifecycle promote 走 scene-card-lifecycle.py (operator grant).

边界 (SRP):
- SceneWatcher 只决策 + 推进 lifecycle, 不执行 journey (journey-runner 的事)
- 本 stub 定义接口 + 决策骨架, 真实 event 监听卡 fabric 红线 (CDP 9222)

参见: docs/scene-cards/v2/scenewatcher-design.md
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from omo.model_router import ModelRouterProtocol, StubModelRouter
from omo.omo_belief import MOSBeliefManager

CONFIDENCE_THRESHOLD = 0.8  # 守 F6: 低于阈值 → human_veto (StubModelRouter 默认阈值)

WORKSPACE = Path(__file__).resolve().parents[4]
SCENE_CARD_LIFECYCLE = WORKSPACE / "bin" / "ssot" / "scene-card-lifecycle.py"


@dataclass
class DecisionResult:
    """SceneWatcher 决策结果 (守 F2 语义分级)."""

    action: str  # pass | escalate | human_veto
    confidence: float
    reason: str
    model_used: str = (
        "local-triage"  # local-triage | api | hybrid | aetherforge-triage:*
    )
    cost_estimate: float = 0.0  # 守 F11: 决策成本 (aetherforge tracker 记账, 可审计)


logger = logging.getLogger(__name__)


@dataclass
class SceneWatcher:
    """resident-agent: event 监听 + lifecycle 推进 + 复杂条件决策.

    本 stub 定义接口契约; 真实 event 监听 (iris poll) 卡 fabric 红线 (CDP 9222).
    ModelRouter 通过 Protocol 注入 (SOLID D), 默认 StubModelRouter (等 aetherforge).
    mos_manager 可选注入, 有则每次 evaluate_confidence 持久化 decision_outcome 到 MOS.
    """

    scene_id: str
    scene_path: Path
    operator: str = ""  # fabric 红线: promote 需 operator 显式
    model_router: ModelRouterProtocol = field(default_factory=StubModelRouter)
    decision_log: list[DecisionResult] = field(default_factory=list)
    mos_manager: MOSBeliefManager | None = None

    def promote_scene(self, *, dry_run: bool = True) -> dict[str, Any]:
        """推进 scene lifecycle (proposal → active 候选).

        调 scene-card-lifecycle.py promote (--dry-run 默认, 不写 overlay).
        真实激活需 operator 在生产环境跑 (fabric 红线).
        """
        cmd = [
            sys.executable,
            str(SCENE_CARD_LIFECYCLE),
            "promote",
            str(self.scene_path),
            "--operator",
            self.operator or "scenewatcher-stub",
        ]
        if dry_run:
            cmd.append("--dry-run")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "dry_run": dry_run,
        }

    def evaluate_confidence(
        self,
        node_output: dict[str, Any],
        *,
        node: str = "",
    ) -> DecisionResult:
        """复杂条件决策 (agent_decisions 回调, 守 F2/F6).

        通过 ModelRouter 评估 (SOLID D 注入; 默认 StubModelRouter,
        aetherforge 实现后替换为 AetherforgeTriageAdapter / HybridRouter, 守 F11 成本).
        若 mos_manager 已注入, 持久化 decision_outcome 到 MOS (ADR-0372).
        """
        model_decision = self.model_router.route(
            node, node_output, scene_id=self.scene_id
        )
        decision = DecisionResult(
            action=model_decision.action,
            confidence=model_decision.confidence,
            reason=model_decision.reason,
            model_used=model_decision.model_used,
            cost_estimate=model_decision.cost_estimate,
        )
        self.decision_log.append(decision)
        self._persist_decision_outcome(decision, node, node_output)
        return decision

    def _persist_decision_outcome(
        self,
        decision: DecisionResult,
        node: str,
        node_output: dict[str, Any],
    ) -> None:
        """持久化决策到 MOS decision_outcome 表 (best-effort)."""
        if self.mos_manager is None:
            return
        try:
            self.mos_manager.record_decision_outcome(
                decision_type=f"scene_watcher:{self.scene_id}",
                input_summary=f"node={node} output_keys={sorted(node_output.keys())}",
                expected_outcome=f"action={decision.action} confidence>={decision.confidence}",
                actual_outcome=f"action={decision.action} confidence={decision.confidence} reason={decision.reason}",
                delta=f"model={decision.model_used} cost={decision.cost_estimate}",
                source_run_id=self.agent_id,
            )
        except Exception:
            logger.warning("MOS decision_outcome write failed", exc_info=True)

    def on_journey_decision(
        self, node: str, node_output: dict[str, Any]
    ) -> DecisionResult:
        """journey-runner 回调入口 (复杂条件节点).

        journey-runner 跑到 agent_decisions node 时回调本方法.
        """
        return self.evaluate_confidence(node_output, node=node)

    @property
    def agent_id(self) -> str:
        """AgentProtocol 契约 (v10 α.3 续, 适配 AgentHost)."""
        return f"scene-watcher:{self.scene_id}"

    def tick(self) -> dict[str, Any]:
        """AgentProtocol 契约: 单次 tick (v10 α.3 续, stub).

        真实 trigger (读 active scene → iris poll → journey) 卡 fabric 红线 (α.2).
        stub 返回 noop (AgentHost 调度骨架就位, 真实触发留 α.2).
        """
        return {
            "action": "noop",
            "details": {
                "scene_id": self.scene_id,
                "note": "SceneWatcher tick stub (α.3 续, 真实 trigger 留 α.2)",
            },
        }


__all__ = ["CONFIDENCE_THRESHOLD", "DecisionResult", "SceneWatcher"]
