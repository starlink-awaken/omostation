"""
model_driven.lifecycle.tracking — 全生命周期追踪

提供跨实体的生命周期追踪和聚合：
- 多实体生命周期管理
- 阶段进度聚合
- 阻塞项汇总
- 生命周期仪表板
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from model_driven.mof.m3_extended import LifecycleStage

from .stages import LifecycleTracker, StageStatus


@dataclass
class LifecycleDashboard:
    """全生命周期仪表板"""

    total_entities: int = 0
    entities_by_stage: dict[str, int] = field(default_factory=dict)
    entities_by_status: dict[str, int] = field(default_factory=dict)
    blockers: list[dict[str, Any]] = field(default_factory=list)
    avg_progress: float = 0.0
    stage_distribution: dict[str, list[str]] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LifecycleManager:
    """全生命周期管理器"""

    def __init__(self):
        self._trackers: dict[str, LifecycleTracker] = {}

    def create_tracker(self, entity_id: str, entity_type: str = "") -> LifecycleTracker:
        """创建实体的生命周期追踪器"""
        if entity_id in self._trackers:
            return self._trackers[entity_id]
        tracker = LifecycleTracker(entity_id=entity_id, entity_type=entity_type)
        self._trackers[entity_id] = tracker
        return tracker

    def get_tracker(self, entity_id: str) -> LifecycleTracker | None:
        """获取追踪器"""
        return self._trackers.get(entity_id)

    def remove_tracker(self, entity_id: str) -> bool:
        """移除追踪器"""
        if entity_id in self._trackers:
            del self._trackers[entity_id]
            return True
        return False

    def list_entities(self) -> list[str]:
        """列出所有实体"""
        return list(self._trackers.keys())

    def get_all_blockers(self) -> list[dict[str, Any]]:
        """获取所有阻塞项"""
        blockers = []
        for entity_id, tracker in self._trackers.items():
            for stage in LifecycleStage:
                instance = tracker.stages[stage]
                if instance.status == StageStatus.BLOCKED:
                    for issue in instance.issues:
                        blockers.append({
                            "entity_id": entity_id,
                            "stage": stage.value,
                            "issue": issue,
                        })
        return blockers

    def generate_dashboard(self) -> LifecycleDashboard:
        """生成全生命周期仪表板"""
        dashboard = LifecycleDashboard()
        dashboard.total_entities = len(self._trackers)

        # 按阶段统计
        stage_counts: dict[str, int] = {}
        stage_entities: dict[str, list[str]] = {}
        for stage in LifecycleStage:
            stage_counts[stage.value] = 0
            stage_entities[stage.value] = []

        for entity_id, tracker in self._trackers.items():
            if tracker.current_stage:
                stage_counts[tracker.current_stage.value] += 1
                stage_entities[tracker.current_stage.value].append(entity_id)

        dashboard.entities_by_stage = stage_counts
        dashboard.stage_distribution = stage_entities

        # 按状态统计
        status_counts: dict[str, int] = {
            "not_started": 0,
            "in_progress": 0,
            "blocked": 0,
            "completed": 0,
        }
        for tracker in self._trackers.values():
            for stage in LifecycleStage:
                status = tracker.stages[stage].status.value
                status_counts[status] = status_counts.get(status, 0) + 1
        dashboard.entities_by_status = status_counts

        # 阻塞项
        dashboard.blockers = self.get_all_blockers()

        # 平均进度
        if self._trackers:
            total_progress = sum(
                sum(1 for s in LifecycleStage if t.stages[s].status == StageStatus.COMPLETED)
                / len(LifecycleStage)
                for t in self._trackers.values()
            )
            dashboard.avg_progress = round(total_progress / len(self._trackers) * 100, 1)

        return dashboard

    def get_entities_in_stage(self, stage: LifecycleStage) -> list[str]:
        """获取处于某阶段的所有实体"""
        entities = []
        for entity_id, tracker in self._trackers.items():
            if tracker.current_stage == stage:
                entities.append(entity_id)
        return entities

    def get_stage_summary(self, entity_id: str) -> dict[str, Any] | None:
        """获取实体的阶段摘要"""
        tracker = self._trackers.get(entity_id)
        if not tracker:
            return None
        return tracker.get_progress()
