"""model_router.py — ModelRouter interface (v8 A.3, 卡 aetherforge 未实现).

守 F11: 本地优先 (aetherforge/triage) + API 复杂, 成本控制 + 配额.
守 ADR-0372: 决策日志入 MOS (bos://memory/mos/*).
守 F6: 低置信度 → human_veto (决策可逆).
守 SOLID D (依赖倒置): SceneWatcher 通过 Protocol 注入, 不绑死实现.

依赖: aetherforge/triage/router (未实现, v9 候选). 本文件只定义 interface.
实现路径: StubModelRouter (规则, 当前) → AetherforgeTriageAdapter (HTTP 接入) → HybridRouter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ModelDecision:
    """ModelRouter 决策结果."""

    action: str  # pass | escalate | human_veto
    confidence: float
    model_used: str  # local-triage | api | hybrid | aetherforge-triage:*
    cost_estimate: float = 0.0  # 守 F11: 成本追踪
    reason: str = ""


class ModelRouterProtocol(Protocol):
    """ModelRouter 接口契约 (依赖倒置, 等 aetherforge 实现).

    实现候选:
    - StubModelRouter (规则, 当前)
    - AetherforgeTriageAdapter (HTTP 接入 aetherforge triage, v9 A.1)
    - HybridRouter (本地优先 + API 升级, 守 F11)
    """

    def route(
        self, node: str, node_output: dict[str, Any], *, scene_id: str
    ) -> ModelDecision:
        """评估复杂条件节点, 返回决策 (含置信度 + 成本)."""
        ...


class StubModelRouter:
    """stub 实现 (规则评估, 等 aetherforge 接入).

    本地无 model serving, 用 confidence 阈值评估.
    aetherforge 实现后替换为 AetherforgeTriageAdapter / HybridRouter.
    """

    def __init__(self, *, threshold: float = 0.8):
        self.threshold = threshold
        self.model_used = "local-triage"

    def route(
        self, node: str, node_output: dict[str, Any], *, scene_id: str
    ) -> ModelDecision:
        confidence = float(node_output.get("confidence", 0.0))
        if confidence >= self.threshold:
            return ModelDecision(
                action="pass",
                confidence=confidence,
                model_used=self.model_used,
                cost_estimate=0.0,  # stub 无成本
                reason=(
                    f"[{scene_id}/{node}] confidence {confidence:.2f}"
                    f" >= {self.threshold}"
                ),
            )
        return ModelDecision(
            action="human_veto",
            confidence=confidence,
            model_used=self.model_used,
            cost_estimate=0.0,
            reason=(
                f"[{scene_id}/{node}] confidence {confidence:.2f}"
                f" < {self.threshold} (守 F6: 决策可逆, 升级人工)"
            ),
        )


__all__ = ["ModelDecision", "ModelRouterProtocol", "StubModelRouter"]
