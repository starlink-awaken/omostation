from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

from .models import (
    SymphonyStage,
    Trigger,
    TriggerResult,
    TriggerType,
)


class StageManager(Protocol):
    """Stage manager protocol — injected at runtime by set_stage_manager()."""

    def transition_to(self, stage: SymphonyStage) -> None: ...

    def get_context(self) -> dict[str, Any]: ...


"""
Symphony Protocol 触发器引擎

实现阶段转换自动触发器、条件评估和动作执行。
"""

logger = logging.getLogger(__name__)


class TriggerEngine:
    """
    Symphony Protocol 触发器引擎

    职责:
    1. 注册和管理触发器
    2. 评估触发条件
    3. 执行触发动作
    4. 记录触发历史
    """

    def __init__(self, stage_manager: StageManager | None = None) -> None:
        """
        初始化触发器引擎

        Args:
            stage_manager: 阶段管理器实例
        """
        """Initialize the trigger engine."""
        self._stage_manager = stage_manager
        self._triggers: dict[str, Trigger] = {}
        self._history: list[TriggerResult] = []
        self._running = False
        self._monitor_task: asyncio.Task | None = None

    def set_stage_manager(self, stage_manager: StageManager) -> None:
        """设置阶段管理器"""
        self._stage_manager = stage_manager

    def register_trigger(self, trigger: Trigger) -> None:
        """
        注册触发器

        Args:
            trigger: 触发器定义
        """
        self._triggers[trigger.id] = trigger
        logger.info(f"触发器已注册：{trigger.name}")

    def unregister_trigger(self, trigger_id: str) -> None:
        """
        注销触发器

        Args:
            trigger_id: 触发器 ID
        """
        if trigger_id in self._triggers:
            del self._triggers[trigger_id]
            logger.info(f"触发器已注销：{trigger_id}")

    def enable_trigger(self, trigger_id: str) -> None:
        """启用触发器"""
        if trigger_id in self._triggers:
            self._triggers[trigger_id].enabled = True
            logger.info(f"触发器已启用：{trigger_id}")

    def disable_trigger(self, trigger_id: str) -> None:
        """禁用触发器"""
        if trigger_id in self._triggers:
            self._triggers[trigger_id].enabled = False
            logger.info(f"触发器已禁用：{trigger_id}")

    def evaluate_and_trigger(self, context: dict[str, Any] | None = None) -> list[TriggerResult]:
        """
        评估所有触发器并执行

        Args:
            context: 上下文数据（如果为 None 则从 stage_manager 获取）

        Returns:
            触发器执行结果列表
        """
        results = []

        # 获取上下文
        if context is None:
            if self._stage_manager:
                context = self._stage_manager.get_context()
            else:
                context = {}

        # 按优先级排序
        sorted_triggers = sorted(self._triggers.values(), key=lambda t: t.priority, reverse=True)

        for trigger in sorted_triggers:
            if not trigger.enabled:
                continue

            try:
                triggered = trigger.condition(context)

                if triggered:
                    # 执行触发动作
                    action_result = trigger.action()

                    result = TriggerResult(
                        trigger_id=trigger.id,
                        triggered=True,
                        action_result=action_result,
                        message=f"触发器 {trigger.name} 已触发",
                    )
                    logger.info(f"触发器已触发：{trigger.name}")
                else:
                    result = TriggerResult(
                        trigger_id=trigger.id,
                        triggered=False,
                        message=f"触发器 {trigger.name} 条件未满足",
                    )

                results.append(result)
                self._history.append(result)

            except Exception as e:
                logger.error(f"触发器 {trigger.name} 执行失败：{e}")
                results.append(TriggerResult(trigger_id=trigger.id, triggered=False, message=f"触发器执行失败：{e}"))

        return results

    def get_trigger(self, trigger_id: str) -> Trigger | None:
        """获取触发器"""
        return self._triggers.get(trigger_id)

    def get_all_triggers(self) -> list[Trigger]:
        """获取所有触发器"""
        return list(self._triggers.values())

    def get_history(self) -> list[TriggerResult]:
        """获取触发历史"""
        return self._history.copy()

    def clear_history(self) -> None:
        """清除历史"""
        self._history = []

    async def start_monitoring(self, interval: float = 1.0) -> None:
        """
        启动监控循环

        Args:
            interval: 检查间隔（秒）
        """
        self._running = True

        while self._running:
            # 评估并触发
            results = self.evaluate_and_trigger()

            # 记录有触发的结果
            triggered = [r for r in results if r.triggered]
            if triggered:
                logger.info(f"{len(triggered)} 个触发器被触发")

            await asyncio.sleep(interval)

    def stop_monitoring(self) -> None:
        """停止监控循环"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None

    async def start_monitoring_task(self, interval: float = 1.0) -> asyncio.Task:
        """
        启动监控任务

        Args:
            interval: 检查间隔（秒）

        Returns:
            监控任务
        """
        self._running = True  # set before task creation so callers see it immediately
        self._monitor_task = asyncio.create_task(self.start_monitoring(interval))
        return self._monitor_task

    def get_status(self) -> dict[str, Any]:
        """
        获取触发器引擎状态

        Returns:
            状态字典
        """
        return {
            "total_triggers": len(self._triggers),
            "enabled_triggers": sum(1 for t in self._triggers.values() if t.enabled),
            "disabled_triggers": sum(1 for t in self._triggers.values() if not t.enabled),
            "is_running": self._running,
            "history_count": len(self._history),
            "trigger_names": list(self._triggers.keys()),
        }


def create_default_triggers(stage_manager: StageManager) -> list[Trigger]:
    """
    创建默认的 Symphony 阶段转换触发器

    Args:
        stage_manager: 阶段管理器实例

    Returns:
        触发器列表
    """
    triggers = [
        # Anchoring -> Scaffolding
        Trigger(
            id="anchoring_to_scaffolding",
            name="Anchoring 完成 → Scaffolding 开始",
            trigger_type=TriggerType.CONDITION_MET,
            condition=lambda ctx: (
                ctx.get("context_completeness", 0) >= 0.95
                and len(ctx.get("ambiguities", [])) == 0
                and ctx.get("truth_locked", False) is True
            ),
            action=lambda: stage_manager.transition_to(SymphonyStage.SCAFFOLDING),
            priority=100,
        ),
        # Scaffolding -> Implementation
        Trigger(
            id="scaffolding_to_implementation",
            name="Scaffolding 完成 → Implementation 开始",
            trigger_type=TriggerType.CONDITION_MET,
            condition=lambda ctx: (
                ctx.get("architecture") is not None
                and ctx.get("contract_signed", False) is True
                and ctx.get("dependency_graph") is not None
            ),
            action=lambda: stage_manager.transition_to(SymphonyStage.IMPLEMENTATION),
            priority=100,
        ),
        # Implementation -> Polishing
        Trigger(
            id="implementation_to_polishing",
            name="Implementation 完成 → Polishing 开始",
            trigger_type=TriggerType.CONDITION_MET,
            condition=lambda ctx: (
                ctx.get("code_completion_rate", 0) >= 0.95
                and ctx.get("code_coverage", 0) >= 0.80
                and ctx.get("critical_issues", 0) == 0
            ),
            action=lambda: stage_manager.transition_to(SymphonyStage.POLISHING),
            priority=100,
        ),
        # Polishing -> Complete
        Trigger(
            id="polishing_to_complete",
            name="Polishing 完成 → Complete",
            trigger_type=TriggerType.CONDITION_MET,
            condition=lambda ctx: (
                ctx.get("tests_passed", False) is True
                and ctx.get("performance_score", 0) >= 0.90
                and ctx.get("self_review_score", 0) >= 0.85
            ),
            action=lambda: stage_manager.transition_to(SymphonyStage.COMPLETE),
            priority=100,
        ),
    ]

    return triggers


def setup_trigger_engine(stage_manager: StageManager) -> TriggerEngine:
    """
    设置触发器引擎

    Args:
        stage_manager: 阶段管理器实例

    Returns:
        配置好的触发器引擎
    """
    trigger_engine = TriggerEngine(stage_manager)

    # 注册默认触发器
    default_triggers = create_default_triggers(stage_manager)
    for trigger in default_triggers:
        trigger_engine.register_trigger(trigger)

    logger.info("触发器引擎已设置，注册了 4 个默认触发器")

    return trigger_engine
