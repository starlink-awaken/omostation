"""
model_driven.toolchain.trigger_m0 — Trigger M0 运行时快照

从 derivation_engine.py 提取:
- TriggerRuntimeSnapshot: Trigger 的 M0 层运行时状态记录
- TriggerM0Manager: M0 快照管理 (保存/加载/漂移检测/健康聚合)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from model_driven.constants import (
    DEGRADED_CONSECUTIVE_FAILURES,
    HEALTH_PENALTY_DECREMENT,
    HEALTH_RECOVERY_INCREMENT,
    HEALTHY_CONSECUTIVE_SUCCESSES,
    MAX_HEALTH_SCORE,
    STOPPED_CONSECUTIVE_FAILURES,
)


@dataclass
class TriggerRuntimeSnapshot:
    """Trigger M0 运行时快照 — 记录 Trigger 的实际执行状态

    对应 MOF 四层模型中的 M0 层:
    - M3: BehavioralElement.Mechanism
    - M2: trigger
    - M1: TRIGGER-ECOS-DAEMON 等 10 个节点
    - M0: TriggerRuntimeSnapshot (本类)
    """

    trigger_id: str
    status: str = "unknown"  # healthy/degraded/stopped/unknown
    last_execution: str = ""
    last_duration_seconds: float = 0.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    health_score: float = MAX_HEALTH_SCORE  # 0-100
    snapshotted_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "status": self.status,
            "last_execution": self.last_execution,
            "last_duration_seconds": self.last_duration_seconds,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "health_score": self.health_score,
            "snapshotted_at": self.snapshotted_at,
            "metadata": self.metadata,
        }


class TriggerM0Manager:
    """Trigger M0 运行时管理器

    职责:
    1. 生成 Trigger 的 M0 运行时快照
    2. 保存快照到文件 (.omo/state/model-driven/trigger-m0-snapshot.yaml)
    3. 加载快照与 M1 声明对比检测漂移
    4. 更新 Trigger 健康分
    """

    def __init__(self, state_dir: str | None = None):
        if state_dir is None:
            from model_driven._paths import get_state_dir

            self._state_dir = get_state_dir()
        else:
            self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot_file = self._state_dir / "trigger-m0-snapshot.yaml"
        self._snapshots: dict[str, TriggerRuntimeSnapshot] = {}

    def record_execution(
        self,
        trigger_id: str,
        success: bool,
        duration_seconds: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> TriggerRuntimeSnapshot:
        """记录一次 Trigger 执行"""
        if trigger_id in self._snapshots:
            snap = self._snapshots[trigger_id]
        else:
            snap = TriggerRuntimeSnapshot(trigger_id=trigger_id)

        snap.last_execution = datetime.now(UTC).isoformat()
        snap.last_duration_seconds = duration_seconds
        snap.metadata.update(metadata or {})

        if success:
            snap.consecutive_successes += 1
            snap.consecutive_failures = 0
            snap.health_score = min(MAX_HEALTH_SCORE, snap.health_score + HEALTH_RECOVERY_INCREMENT)
            # 首次成功 → healthy; 或连续 3 次 → healthy (防御性)
            if snap.status == "unknown" or snap.consecutive_successes >= HEALTHY_CONSECUTIVE_SUCCESSES:
                snap.status = "healthy"
        else:
            snap.consecutive_failures += 1
            snap.consecutive_successes = 0
            snap.health_score = max(0.0, snap.health_score - HEALTH_PENALTY_DECREMENT)
            if snap.consecutive_failures >= DEGRADED_CONSECUTIVE_FAILURES:
                snap.status = "degraded"
            if snap.consecutive_failures >= STOPPED_CONSECUTIVE_FAILURES:
                snap.status = "stopped"

        snap.snapshotted_at = datetime.now(UTC).isoformat()
        self._snapshots[trigger_id] = snap
        return snap

    def get_snapshot(self, trigger_id: str) -> TriggerRuntimeSnapshot | None:
        return self._snapshots.get(trigger_id)

    def get_all_snapshots(self) -> dict[str, TriggerRuntimeSnapshot]:
        return self._snapshots.copy()

    def save(self) -> bool:
        """保存 M0 快照到文件"""
        try:
            data = {
                "m0_type": "trigger_runtime_snapshot",
                "generated_at": datetime.now(UTC).isoformat(),
                "triggers": {tid: snap.to_dict() for tid, snap in self._snapshots.items()},
            }
            with open(self._snapshot_file, "w") as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            return True
        except (OSError, yaml.YAMLError):
            return False

    def load(self) -> bool:
        """从文件加载 M0 快照"""
        if not self._snapshot_file.exists():
            return False
        try:
            with open(self._snapshot_file) as f:
                data = yaml.safe_load(f)
            if not data or "triggers" not in data:
                return False
            for tid, snap_data in data["triggers"].items():
                snap = TriggerRuntimeSnapshot(
                    trigger_id=tid,
                    status=snap_data.get("status", "unknown"),
                    last_execution=snap_data.get("last_execution", ""),
                    last_duration_seconds=snap_data.get("last_duration_seconds", 0.0),
                    consecutive_failures=snap_data.get("consecutive_failures", 0),
                    consecutive_successes=snap_data.get("consecutive_successes", 0),
                    health_score=snap_data.get("health_score", MAX_HEALTH_SCORE),
                    snapshotted_at=snap_data.get("snapshotted_at", ""),
                    metadata=snap_data.get("metadata", {}),
                )
                self._snapshots[tid] = snap
            return True
        except (OSError, yaml.YAMLError, KeyError):
            return False

    def detect_drift(self, m1_triggers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """M1 声明 vs M0 实际状态 漂移检测"""
        drifts = []
        for m1 in m1_triggers:
            tid = m1.get("id", "")
            m1_status = m1.get("status", "active")
            m0 = self._snapshots.get(tid)

            if m0 is None:
                drifts.append(
                    {
                        "trigger_id": tid,
                        "type": "missing_m0_snapshot",
                        "m1_status": m1_status,
                        "m0_status": "unknown",
                        "severity": "warning",
                        "message": f"Trigger {tid} 无 M0 运行时快照",
                    }
                )
            elif m0.status != "healthy" and m1_status == "active":
                drifts.append(
                    {
                        "trigger_id": tid,
                        "type": "status_drift",
                        "m1_status": m1_status,
                        "m0_status": m0.status,
                        "severity": "high",
                        "health_score": m0.health_score,
                        "consecutive_failures": m0.consecutive_failures,
                        "message": f"Trigger {tid}: M1={m1_status}, M0={m0.status} (health={m0.health_score})",
                    }
                )

        return drifts

    def get_health_summary(self) -> dict[str, Any]:
        """获取 Trigger M0 健康摘要"""
        total = len(self._snapshots)
        healthy = sum(1 for s in self._snapshots.values() if s.status == "healthy")
        degraded = sum(1 for s in self._snapshots.values() if s.status == "degraded")
        stopped = sum(1 for s in self._snapshots.values() if s.status == "stopped")

        return {
            "total_triggers": total,
            "healthy": healthy,
            "degraded": degraded,
            "stopped": stopped,
            "health_pct": round(healthy / total * 100, 1) if total > 0 else 0,
            "triggers": {
                tid: {
                    "status": snap.status,
                    "health_score": snap.health_score,
                    "consecutive_failures": snap.consecutive_failures,
                    "last_execution": snap.last_execution,
                }
                for tid, snap in self._snapshots.items()
            },
            "generated_at": datetime.now(UTC).isoformat(),
        }
