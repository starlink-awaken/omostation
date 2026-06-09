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
from datetime import UTC, datetime
from typing import Any

import yaml

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
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


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
                        blockers.append(
                            {
                                "entity_id": entity_id,
                                "stage": stage.value,
                                "issue": issue,
                            }
                        )
        return blockers

    def generate_dashboard(self) -> LifecycleDashboard:
        """生成全生命周期仪表板"""
        dashboard = LifecycleDashboard()
        dashboard.total_entities = len(self._trackers)

        # 单次遍历: 阶段统计 + 状态统计 + 平均进度
        stage_counts: dict[str, int] = {stage.value: 0 for stage in LifecycleStage}
        stage_entities: dict[str, list[str]] = {stage.value: [] for stage in LifecycleStage}
        status_counts: dict[str, int] = {"not_started": 0, "in_progress": 0, "blocked": 0, "completed": 0}
        total_progress = 0.0
        num_stages = len(LifecycleStage)

        for entity_id, tracker in self._trackers.items():
            if tracker.current_stage:
                stage_counts[tracker.current_stage.value] += 1
                stage_entities[tracker.current_stage.value].append(entity_id)

            for stage in LifecycleStage:
                status = tracker.stages[stage].status.value
                status_counts[status] = status_counts.get(status, 0) + 1

            completed = sum(1 for s in LifecycleStage if tracker.stages[s].status == StageStatus.COMPLETED)
            total_progress += completed / num_stages

        dashboard.entities_by_stage = stage_counts
        dashboard.stage_distribution = stage_entities
        dashboard.entities_by_status = status_counts

        # 阻塞项
        dashboard.blockers = self.get_all_blockers()

        # 平均进度
        if self._trackers:
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

    # ── 持久化 ──────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict"""
        return {
            "trackers": {
                eid: t.to_dict() if hasattr(t, "to_dict") else {"entity_id": t.entity_id, "entity_type": t.entity_type}
                for eid, t in self._trackers.items()
            }
        }

    def save(self, state_dir: str | None = None) -> bool:
        """持久化到文件"""
        from pathlib import Path

        if state_dir is None:
            from model_driven._paths import get_state_dir

            state_dir = str(get_state_dir())

        file_path = Path(state_dir) / "lifecycle.yaml"
        try:
            with open(file_path, "w") as f:
                yaml.dump(self.to_dict(), f, allow_unicode=True, sort_keys=False)
            return True
        except (OSError, yaml.YAMLError):
            return False

    @classmethod
    def load(cls, state_dir: str | None = None) -> LifecycleManager | None:
        """从文件加载"""
        from pathlib import Path

        if state_dir is None:
            from model_driven._paths import get_state_dir

            state_dir = str(get_state_dir())

        file_path = Path(state_dir) / "lifecycle.yaml"
        if not file_path.exists():
            return None

        try:
            with open(file_path) as f:
                data = yaml.safe_load(f)
        except (OSError, ImportError, yaml.YAMLError):
            return None

        manager = cls()
        for eid, tdata in (data or {}).get("trackers", {}).items():
            tracker = LifecycleTracker(entity_id=tdata["entity_id"], entity_type=tdata.get("entity_type", ""))
            manager._trackers[eid] = tracker
        return manager
