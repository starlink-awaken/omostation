"""
model_driven.lifecycle.stages — 7 阶段定义与状态机

全生命周期阶段引擎的核心：
- 7 个标准阶段定义
- 阶段状态机
- 阶段间关系
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from model_driven.constants import SECONDS_PER_DAY
from model_driven.mof.m3_extended import LifecycleStage


class StageStatus(Enum):
    """阶段运行状态"""

    NOT_STARTED = "not_started"  # 未开始
    IN_PROGRESS = "in_progress"  # 进行中
    BLOCKED = "blocked"  # 被阻塞
    COMPLETED = "completed"  # 已完成
    SKIPPED = "skipped"  # 已跳过


@dataclass
class StageInstance:
    """阶段实例 — 跟踪某实体当前所处的生命周期阶段"""

    id: str
    entity_id: str  # 关联的实体 ID (项目/组件/服务)
    stage: LifecycleStage
    status: StageStatus = StageStatus.NOT_STARTED
    started_at: str = ""
    completed_at: str = ""
    deliverables: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        """开始阶段"""
        self.status = StageStatus.IN_PROGRESS
        self.started_at = datetime.now(UTC).isoformat()

    def complete(self) -> None:
        """完成阶段"""
        self.status = StageStatus.COMPLETED
        self.completed_at = datetime.now(UTC).isoformat()

    def block(self, reason: str) -> None:
        """阻塞阶段"""
        self.status = StageStatus.BLOCKED
        self.issues.append(reason)

    def unblock(self) -> None:
        """解除阻塞"""
        if self.status == StageStatus.BLOCKED:
            self.status = StageStatus.IN_PROGRESS

    @property
    def duration_days(self) -> float:
        """阶段持续天数"""
        if not self.started_at:
            return 0.0
        end = self.completed_at or datetime.now(UTC).isoformat()
        try:
            start_dt = datetime.fromisoformat(self.started_at)
            end_dt = datetime.fromisoformat(end)
            return (end_dt - start_dt).total_seconds() / SECONDS_PER_DAY
        except (ValueError, TypeError):
            return 0.0


@dataclass
class LifecycleTracker:
    """全生命周期追踪器 — 管理一个实体的完整生命周期"""

    entity_id: str
    entity_type: str = ""  # 实体类型 (project/service/component)
    stages: dict[LifecycleStage, StageInstance] = field(default_factory=dict)
    current_stage: LifecycleStage | None = None
    transitions: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化所有阶段实例"""
        if not self.stages:
            for stage in LifecycleStage:
                self.stages[stage] = StageInstance(
                    id=f"{self.entity_id}-{stage.value}",
                    entity_id=self.entity_id,
                    stage=stage,
                )

    def get_stage(self, stage: LifecycleStage) -> StageInstance:
        """获取阶段实例"""
        return self.stages[stage]

    def advance_to(self, target_stage: LifecycleStage) -> bool:
        """推进到目标阶段"""
        target_order = LifecycleStage.order(target_stage)

        # 检查前置阶段是否完成
        for stage in LifecycleStage:
            if LifecycleStage.order(stage) < target_order:
                instance = self.stages[stage]
                if instance.status != StageStatus.COMPLETED and instance.status != StageStatus.SKIPPED:
                    return False

        # 执行转换
        old_stage = self.current_stage
        self.current_stage = target_stage
        self.stages[target_stage].start()

        self.transitions.append(
            {
                "from": old_stage.value if old_stage else None,
                "to": target_stage.value,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        return True

    def complete_current(self) -> None:
        """完成当前阶段"""
        if self.current_stage:
            self.stages[self.current_stage].complete()

    def get_progress(self) -> dict[str, Any]:
        """获取生命周期进度"""
        total = len(LifecycleStage)
        completed = sum(1 for s in LifecycleStage if self.stages[s].status == StageStatus.COMPLETED)
        return {
            "entity_id": self.entity_id,
            "current_stage": self.current_stage.value if self.current_stage else "not_started",
            "completed_stages": completed,
            "total_stages": total,
            "progress_pct": round(completed / total * 100, 1),
            "stages": {
                s.value: {
                    "status": self.stages[s].status.value,
                    "started_at": self.stages[s].started_at,
                    "completed_at": self.stages[s].completed_at,
                    "duration_days": round(self.stages[s].duration_days, 1),
                    "issues": self.stages[s].issues,
                }
                for s in LifecycleStage
            },
        }

    def get_blockers(self) -> list[str]:
        """获取所有阻塞项"""
        blockers = []
        for stage in LifecycleStage:
            instance = self.stages[stage]
            if instance.status == StageStatus.BLOCKED:
                blockers.extend(instance.issues)
        return blockers

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict"""
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "current_stage": self.current_stage.value if self.current_stage else None,
            "stages": {
                s.value: {
                    "status": self.stages[s].status.value,
                    "started_at": self.stages[s].started_at,
                    "completed_at": self.stages[s].completed_at,
                    "issues": self.stages[s].issues,
                }
                for s in LifecycleStage
            },
            "created_at": self.created_at,
        }

    def __repr__(self) -> str:
        stage_name = self.current_stage.value if self.current_stage else "not_started"
        return f"LifecycleTracker(entity={self.entity_id!r}, stage={stage_name})"
