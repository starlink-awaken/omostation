"""
model_driven.lifecycle.transitions — 阶段转换规则

实现 7 阶段之间的转换逻辑：
- 转换条件检查
- 转换执行
- 转换历史追踪
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from model_driven.mof.m3_extended import LifecycleStage

from .gates import GateEngine, GateExecution
from .stages import LifecycleTracker


@dataclass
class TransitionRule:
    """阶段转换规则"""

    from_stage: LifecycleStage
    to_stage: LifecycleStage
    conditions: list[str] = field(default_factory=list)  # 人类可读的条件描述
    required: bool = True  # 是否为必经阶段


# 标准转换规则
STANDARD_TRANSITIONS: list[TransitionRule] = [
    TransitionRule(
        from_stage=LifecycleStage.PLANNING,
        to_stage=LifecycleStage.DESIGN,
        conditions=["OKR 已审批", "Spec 已起草", "关键 ADR 已记录"],
    ),
    TransitionRule(
        from_stage=LifecycleStage.DESIGN,
        to_stage=LifecycleStage.DEVELOPMENT,
        conditions=["Spec 已审批", "接口契约已定义", "设计评审通过"],
    ),
    TransitionRule(
        from_stage=LifecycleStage.DEVELOPMENT,
        to_stage=LifecycleStage.DEPLOYMENT,
        conditions=["测试通过率 >= 95%", "CI 绿灯", "Code Review 通过"],
    ),
    TransitionRule(
        from_stage=LifecycleStage.DEPLOYMENT,
        to_stage=LifecycleStage.RUNTIME,
        conditions=["部署成功", "冒烟测试通过", "监控已配置"],
    ),
    TransitionRule(
        from_stage=LifecycleStage.RUNTIME,
        to_stage=LifecycleStage.OPERATIONS,
        conditions=["告警触发 或 维护窗口"],
        required=False,
    ),
    TransitionRule(
        from_stage=LifecycleStage.OPERATIONS,
        to_stage=LifecycleStage.RUNTIME,
        conditions=["问题已解决 或 变更已完成"],
        required=False,
    ),
]


class TransitionEngine:
    """阶段转换引擎"""

    def __init__(self):
        self.gate_engine = GateEngine()
        self._transition_rules = STANDARD_TRANSITIONS.copy()
        self._history: list[dict[str, Any]] = []

    def get_allowed_transitions(self, current_stage: LifecycleStage) -> list[LifecycleStage]:
        """获取当前阶段允许转换到的阶段列表"""
        allowed = []
        for rule in self._transition_rules:
            if rule.from_stage == current_stage:
                allowed.append(rule.to_stage)
        return allowed

    def get_transition_rule(self, from_stage: LifecycleStage, to_stage: LifecycleStage) -> TransitionRule | None:
        """获取转换规则"""
        for rule in self._transition_rules:
            if rule.from_stage == from_stage and rule.to_stage == to_stage:
                return rule
        return None

    def try_transition(
        self,
        tracker: LifecycleTracker,
        target_stage: LifecycleStage,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, str, GateExecution | None]:
        """尝试执行阶段转换

        Returns:
            (success, message, gate_execution)
        """
        if tracker.current_stage is None:
            # 初始状态，直接推进
            tracker.advance_to(target_stage)
            return True, "初始阶段推进成功", None

        current = tracker.current_stage

        # 检查转换规则
        rule = self.get_transition_rule(current, target_stage)
        if rule is None:
            return False, f"不允许从 {current.value} 转换到 {target_stage.value}", None

        # 执行门禁检查
        passed, gate_exec = self.gate_engine.can_transition(current, target_stage, context)

        if not passed:
            msg = f"门禁检查未通过: {current.value} → {target_stage.value}"
            return False, msg, gate_exec

        # 执行转换
        success = tracker.advance_to(target_stage)
        if not success:
            return False, f"前置阶段未完成，无法推进到 {target_stage.value}", gate_exec

        # 记录历史
        self._history.append(
            {
                "entity_id": tracker.entity_id,
                "from": current.value,
                "to": target_stage.value,
                "timestamp": datetime.now(UTC).isoformat(),
                "gate_result": gate_exec.result.value if gate_exec else "no_gate",
            }
        )

        return True, f"成功从 {current.value} 转换到 {target_stage.value}", gate_exec

    def get_history(self, entity_id: str | None = None) -> list[dict[str, Any]]:
        """获取转换历史"""
        if entity_id:
            return [h for h in self._history if h["entity_id"] == entity_id]
        return self._history.copy()

    def is_valid_path(self, stages: list[LifecycleStage]) -> bool:
        """验证阶段路径是否有效"""
        for i in range(len(stages) - 1):
            rule = self.get_transition_rule(stages[i], stages[i + 1])
            if rule is None:
                return False
        return True
