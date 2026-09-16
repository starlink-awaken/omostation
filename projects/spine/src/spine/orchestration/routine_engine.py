"""RoutineEngine — 数字分身高可信 Routine 自动受托托管引擎。

状态机：pending → executing → verifying → done | hitl
熔断：confidence < 0.95 → HITL (Human-in-the-Loop)
"""

from __future__ import annotations

import dataclasses
import enum
import time
from typing import Any


# ── Category & Status Enums ──────────────────────────────────────────────

class RoutineCategory(enum.Enum):
    """Routine 事务分类。"""
    MEETING = "meeting"       # 例行会议排期
    DOC_REPLY = "doc_reply"   # 常规公文回执
    MAINT = "maint"           # 已知健康与财务维保


class RoutineStatus(enum.Enum):
    """Routine 任务状态机。"""
    PENDING = "pending"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    DONE = "done"
    HITL = "hitl"             # Human-in-the-Loop (熔断回退)


# ── Data Models ──────────────────────────────────────────────────────────

@dataclasses.dataclass
class ConfidenceBreakdown:
    """置信度分解（用于审计）。"""
    base_score: float
    history_factor: float      # 历史修订率修正
    rule_match: float          # 规则匹配置信度
    final_score: float         # 最终置信度 = min(base, history, rule_match)

    def is_above_threshold(self, threshold: float = 0.95) -> bool:
        return self.final_score >= threshold


@dataclasses.dataclass
class RoutineTask:
    """Routine 任务定义。"""
    task_id: str
    category: RoutineCategory
    payload: dict[str, Any]
    confidence: ConfidenceBreakdown | None = None
    status: RoutineStatus = RoutineStatus.PENDING
    result: dict[str, Any] | None = None
    created_at: float = dataclasses.field(default_factory=time.time)
    updated_at: float = dataclasses.field(default_factory=time.time)

    def transition(self, new_status: RoutineStatus) -> None:
        """状态机转换。"""
        valid_transitions = {
            RoutineStatus.PENDING: {RoutineStatus.EXECUTING, RoutineStatus.HITL},
            RoutineStatus.EXECUTING: {RoutineStatus.VERIFYING, RoutineStatus.HITL},
            RoutineStatus.VERIFYING: {RoutineStatus.DONE, RoutineStatus.HITL},
            RoutineStatus.DONE: set(),
            RoutineStatus.HITL: {RoutineStatus.PENDING},  # 可重试
        }
        if new_status not in valid_transitions.get(self.status, set()):
            raise ValueError(
                f"无效状态转换: {self.status.value} → {new_status.value}"
            )
        self.status = new_status
        self.updated_at = time.time()


class CircuitBreakerTripped(Exception):
    """熔断触发异常。"""

    def __init__(self, task_id: str, confidence: float, threshold: float = 0.95) -> None:
        self.task_id = task_id
        self.confidence = confidence
        self.threshold = threshold
        super().__init__(
            f"熔断: task={task_id} confidence={confidence:.3f} < threshold={threshold}"
        )


# ── RoutineEngine ────────────────────────────────────────────────────────

class RoutineEngine:
    """Routine 状态机引擎。

    核心能力：
    1. 任务分类：meeting / doc_reply / maint
    2. 置信度评估：规则 + 历史修订率
    3. 熔断：confidence < 0.95 → HITL
    4. 可观测性：auto_rate, revision_rate
    """

    # 熔断阈值（ADR-0203: 高可信要求）
    DEFAULT_CONFIDENCE_THRESHOLD = 0.95

    def __init__(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        revision_rate: float = 0.0,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.revision_rate = revision_rate
        self._tasks: dict[str, RoutineTask] = {}
        self._execution_count = 0
        self._hitl_count = 0

    # ── Public API ───────────────────────────────────────────────────────

    def submit(self, task: RoutineTask) -> RoutineStatus:
        """提交任务并评估置信度。低于阈值直接熔断到 HITL。"""
        # 评估置信度
        task.confidence = self._evaluate_confidence(task)
        self._tasks[task.task_id] = task

        if not task.confidence.is_above_threshold(self.confidence_threshold):
            task.transition(RoutineStatus.HITL)
            self._hitl_count += 1
            raise CircuitBreakerTripped(
                task_id=task.task_id,
                confidence=task.confidence.final_score,
                threshold=self.confidence_threshold,
            )

        task.transition(RoutineStatus.EXECUTING)
        return task.status

    def execute(self, task_id: str) -> RoutineTask:
        """执行已进入 EXECUTING 状态的任务。模拟执行 + 验证。"""
        task = self._get_task(task_id)
        if task.status != RoutineStatus.EXECUTING:
            raise ValueError(f"任务 {task_id} 未处于 EXECUTING 状态: {task.status.value}")

        # 模拟执行（实际对接 LoRA + 执行链）
        task.result = self._simulate_execution(task)
        task.transition(RoutineStatus.VERIFYING)

        # 验证结果
        if self._verify_result(task):
            task.transition(RoutineStatus.DONE)
            self._execution_count += 1
        else:
            task.transition(RoutineStatus.HITL)
            self._hitl_count += 1

        return task

    def execute_all(self) -> list[RoutineTask]:
        """批量执行所有 PENDING 中通过置信度评估的任务。"""
        results = []
        for task in list(self._tasks.values()):
            if task.status == RoutineStatus.PENDING:
                try:
                    self.submit(task)
                    result = self.execute(task.task_id)
                    results.append(result)
                except CircuitBreakerTripped:
                    results.append(task)
        return results

    def get_metrics(self) -> dict[str, float]:
        """返回可观测性指标。"""
        total = len(self._tasks)
        done = sum(1 for t in self._tasks.values() if t.status == RoutineStatus.DONE)
        hitl = self._hitl_count

        return {
            "total_tasks": total,
            "auto_done": done,
            "hitl_fallback": hitl,
            "auto_rate": done / total if total > 0 else 0.0,
            "revision_rate": hitl / total if total > 0 else 0.0,
            "threshold": self.confidence_threshold,
        }

    # ── Internal ─────────────────────────────────────────────────────────

    def _evaluate_confidence(self, task: RoutineTask) -> ConfidenceBreakdown:
        """评估任务置信度。"""
        # 基础分：类别匹配度
        base_scores = {
            RoutineCategory.MEETING: 0.97,
            RoutineCategory.DOC_REPLY: 0.96,
            RoutineCategory.MAINT: 0.98,
        }
        base = base_scores.get(task.category, 0.90)

        # 历史修订率修正
        history = max(0.0, 1.0 - self.revision_rate * 2)

        # 规则匹配（payload 中的确定性规则）
        rule = 0.99 if task.payload.get("rule_matched") else 0.85

        final = min(base, history, rule)

        return ConfidenceBreakdown(
            base_score=base,
            history_factor=history,
            rule_match=rule,
            final_score=round(final, 4),
        )

    def _simulate_execution(self, task: RoutineTask) -> dict[str, Any]:
        """模拟执行（MVP 占位，后续对接 LoRA Adapter）。"""
        return {
            "category": task.category.value,
            "action": "auto_hosted",
            "dry_run": True,
            "timestamp": time.time(),
        }

    def _verify_result(self, task: RoutineTask) -> bool:
        """验证执行结果（MVP: 基础 schema 校验）。"""
        if task.result is None:
            return False
        return task.result.get("action") == "auto_hosted"

    def _get_task(self, task_id: str) -> RoutineTask:
        if task_id not in self._tasks:
            raise KeyError(f"任务不存在: {task_id}")
        return self._tasks[task_id]
