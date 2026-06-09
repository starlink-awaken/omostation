"""
model_driven.management.okr — OKR 目标对齐管理

提供 OKR 的完整生命周期管理：
- OKR 创建/执行/完成/取消
- 进度追踪
- OKR → Phase → Task 自动分解
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import yaml

from model_driven.constants import (
    PRIORITY_P0_THRESHOLD,
    PRIORITY_P1_THRESHOLD,
    PRIORITY_P2_THRESHOLD,
    TASK_SPLIT_DIVISOR,
)
from model_driven.mof.m3_extended import KeyResult


class OKRStatus(Enum):
    """OKR 状态"""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


@dataclass
class OKR:
    """目标与关键结果"""

    id: str
    objective: str  # O: 目标描述
    key_results: list[KeyResult] = field(default_factory=list)
    status: OKRStatus = OKRStatus.DRAFT
    owner: str = ""
    deadline: str = ""
    parent_okr_id: str | None = None
    value_tier: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def progress(self) -> float:
        """整体进度 (0.0 - 1.0)"""
        if not self.key_results:
            return 0.0
        total_weight = sum(kr.weight for kr in self.key_results)
        if total_weight == 0:
            return 0.0
        weighted_progress = sum(kr.progress * kr.weight for kr in self.key_results)
        return min(weighted_progress / total_weight, 1.0)

    def activate(self) -> bool:
        """激活"""
        if self.status == OKRStatus.DRAFT:
            self.status = OKRStatus.ACTIVE
            self.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def complete(self) -> bool:
        """完成"""
        if self.status == OKRStatus.ACTIVE:
            self.status = OKRStatus.COMPLETED
            self.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def cancel(self) -> bool:
        """取消"""
        if self.status in (OKRStatus.DRAFT, OKRStatus.ACTIVE):
            self.status = OKRStatus.CANCELLED
            self.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def update_kr(self, kr_id: str, current_value: float) -> bool:
        """更新 KR 进度"""
        for kr in self.key_results:
            if kr.id == kr_id:
                kr.current_value = current_value
                self.updated_at = datetime.now(UTC).isoformat()
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict"""
        return {
            "id": self.id,
            "objective": self.objective,
            "key_results": [
                {"id": kr.id, "description": kr.description, "weight": kr.weight,
                 "target_value": kr.target_value, "current_value": kr.current_value}
                for kr in self.key_results
            ],
            "status": self.status.value,
            "owner": self.owner,
            "deadline": self.deadline,
            "parent_okr_id": self.parent_okr_id,
            "value_tier": self.value_tier,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        obj = self.objective[:40] + ("..." if len(self.objective) > 40 else "")
        return f"OKR(id={self.id!r}, objective={obj!r}, status={self.status.value})"


class OKRManager:
    """OKR 管理器"""

    def __init__(self):
        self._okrs: dict[str, OKR] = {}

    def create(self, okr_id: str, objective: str, **kwargs) -> OKR:
        """创建 OKR"""
        okr = OKR(id=okr_id, objective=objective, **kwargs)
        self._okrs[okr_id] = okr
        return okr

    def get(self, okr_id: str) -> OKR | None:
        """获取 OKR"""
        return self._okrs.get(okr_id)

    def list_by_status(self, status: OKRStatus) -> list[OKR]:
        """按状态列出"""
        return [o for o in self._okrs.values() if o.status == status]

    def list_all(self) -> list[OKR]:
        """列出所有"""
        return list(self._okrs.values())

    def get_stats(self) -> dict[str, Any]:
        """获取统计"""
        stats = {s.value: 0 for s in OKRStatus}
        total_progress = 0.0
        for okr in self._okrs.values():
            stats[okr.status.value] += 1
            total_progress += okr.progress
        stats["total"] = len(self._okrs)
        stats["avg_progress"] = round(total_progress / max(len(self._okrs), 1) * 100, 1)
        return stats

    def get_overdue(self) -> list[OKR]:
        """获取过期的 OKR"""
        now = datetime.now(UTC).isoformat()
        return [o for o in self._okrs.values() if o.status == OKRStatus.ACTIVE and o.deadline and o.deadline < now]

    # ── 持久化 ──────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict"""
        return {
            "okrs": {
                oid: {
                    "id": o.id,
                    "objective": o.objective,
                    "key_results": [{"id": kr.id, "description": kr.description, "weight": kr.weight, "target_value": kr.target_value, "current_value": kr.current_value} for kr in o.key_results],
                    "status": o.status.value,
                    "owner": o.owner,
                    "deadline": o.deadline,
                    "parent_okr_id": o.parent_okr_id,
                    "value_tier": o.value_tier,
                    "created_at": o.created_at,
                    "updated_at": o.updated_at,
                    "metadata": o.metadata,
                }
                for oid, o in self._okrs.items()
            }
        }

    def save(self, state_dir: str | None = None) -> bool:
        """持久化到文件"""
        from pathlib import Path

        if state_dir is None:
            from model_driven._paths import get_state_dir

            state_dir = str(get_state_dir())

        file_path = Path(state_dir) / "okrs.yaml"
        try:
            with open(file_path, "w") as f:
                yaml.dump(self.to_dict(), f, allow_unicode=True, sort_keys=False)
            return True
        except (OSError, yaml.YAMLError):
            return False

    @classmethod
    def load(cls, state_dir: str | None = None) -> OKRManager | None:
        """从文件加载"""
        from pathlib import Path

        if state_dir is None:
            from model_driven._paths import get_state_dir

            state_dir = str(get_state_dir())

        file_path = Path(state_dir) / "okrs.yaml"
        if not file_path.exists():
            return None

        try:
            with open(file_path) as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError):
            return None

        manager = cls()
        for oid, odata in (data or {}).get("okrs", {}).items():
            key_results = [
                KeyResult(
                    id=kr["id"],
                    description=kr.get("description", ""),
                    weight=kr.get("weight", 1.0),
                    target_value=kr.get("target_value", 100.0),
                    current_value=kr.get("current_value", 0.0),
                )
                for kr in odata.get("key_results", [])
            ]
            okr = OKR(
                id=odata["id"],
                objective=odata["objective"],
                key_results=key_results,
                status=OKRStatus(odata.get("status", "draft")),
                owner=odata.get("owner", ""),
                deadline=odata.get("deadline", ""),
                parent_okr_id=odata.get("parent_okr_id"),
                value_tier=odata.get("value_tier", 0),
                created_at=odata.get("created_at", ""),
                updated_at=odata.get("updated_at", ""),
                metadata=odata.get("metadata", {}),
            )
            manager._okrs[oid] = okr
        return manager


# ── OKR 自动分解 ──────────────────────────────────


class OKRDecomposer:
    """OKR 自动分解器 — 将 OKR 的 KeyResult 自动分解为 Phase 和 Task"""

    def __init__(self):
        self._decomposition_results: list[dict[str, Any]] = []

    # ── 推断辅助 ──────────────────────────────────

    @staticmethod
    def _infer_phase_from_kr(kr_description: str) -> tuple[str, str]:
        """根据 KR 描述推断 Phase (顺序重要: hardening 关键词优先检查)

        Returns:
            (phase_key, phase_name) — 如 ("cold_start", "冷启动")
        """
        kr_lower = kr_description.lower()

        if any(kw in kr_lower for kw in ["运营", "报告", "价值", "优化", "business", "report", "value"]):
            return ("hardening", "硬化")
        if any(kw in kr_lower for kw in ["运行", "运维", "监控", "run", "ops", "monitor"]):
            return ("hardening", "硬化")
        if any(kw in kr_lower for kw in ["部署", "上线", "deploy", "发布", "release"]):
            return ("evolution", "演进")
        if any(kw in kr_lower for kw in ["开发", "实现", "代码", "code", "build", "测试", "test"]):
            return ("evolution", "演进")
        if any(kw in kr_lower for kw in ["设计", "架构", "spec", "design", "adr"]):
            return ("cold_start", "冷启动")
        if any(kw in kr_lower for kw in ["规划", "计划", "目标", "plan", "goal", "okr"]):
            return ("cold_start", "冷启动")
        return ("evolution", "演进")

    @staticmethod
    def _infer_priority_from_weight(kr_weight: float) -> str:
        """根据 KR 权重推断优先级"""
        if kr_weight >= PRIORITY_P0_THRESHOLD:
            return "P0"
        if kr_weight >= PRIORITY_P1_THRESHOLD:
            return "P1"
        if kr_weight >= PRIORITY_P2_THRESHOLD:
            return "P2"
        return "P3"

    # ── 条目构建 ──────────────────────────────────

    @staticmethod
    def _create_phase_entry(
        phase_index: int,
        okr_id: str,
        kr: Any,
        phase: str,
        phase_name: str,
        priority: str,
        owner: str,
    ) -> dict[str, Any]:
        """为单个 KR 创建一个 Phase 条目"""
        return {
            "id": f"PHASE-{okr_id}-{phase_index + 1:02d}",
            "name": f"{phase_name}: {kr.description[:40]}",
            "phase": phase,
            "kr_id": kr.id,
            "kr_description": kr.description,
            "target_value": kr.target_value,
            "current_value": kr.current_value,
            "weight": kr.weight,
            "priority": priority,
            "owner": owner,
        }

    @staticmethod
    def _create_task_entries(
        phase_index: int,
        okr_id: str,
        kr: Any,
        priority: str,
        owner: str,
    ) -> list[dict[str, Any]]:
        """为单个 KR 创建 Task 条目列表"""
        task_count = max(1, int(kr.target_value / TASK_SPLIT_DIVISOR) if kr.target_value > 0 else 1)
        tasks: list[dict[str, Any]] = []
        for t in range(task_count):
            tasks.append(
                {
                    "id": f"TASK-{okr_id}-{phase_index + 1:02d}-{t + 1:02d}",
                    "title": f"[{priority}] {kr.description} — 第 {t + 1}/{task_count} 步",
                    "description": f"OKR: {okr_id}\nKR: {kr.description}\n目标值: {kr.target_value} {kr.unit}",
                    "phase_id": f"PHASE-{okr_id}-{phase_index + 1:02d}",
                    "kr_id": kr.id,
                    "priority": priority,
                    "assignee": owner,
                    "weight": kr.weight / task_count,
                    "target_progress": round((t + 1) / task_count * 100, 1),
                }
            )
        return tasks

    # ── 分解 ──────────────────────────────────────

    def decompose(self, okr: OKR, owner: str = "") -> dict[str, Any]:
        """将一个 OKR 分解为 Phase 和 Task 列表

        Args:
            okr: OKR 对象
            owner: 默认负责人

        Returns:
            分解结果，包含 phases 和 tasks
        """
        if not okr.key_results:
            return {
                "success": False,
                "error": "OKR 没有 KeyResult，无法分解",
                "okr_id": okr.id,
            }

        default_owner = owner or okr.owner
        phases: list[dict[str, Any]] = []
        tasks: list[dict[str, Any]] = []

        for i, kr in enumerate(okr.key_results):
            phase, phase_name = self._infer_phase_from_kr(kr.description)
            priority = self._infer_priority_from_weight(kr.weight)

            phases.append(
                self._create_phase_entry(i, okr.id, kr, phase, phase_name, priority, default_owner)
            )
            tasks.extend(
                self._create_task_entries(i, okr.id, kr, priority, default_owner)
            )

        result = {
            "success": True,
            "okr_id": okr.id,
            "okr_objective": okr.objective,
            "phase_count": len(phases),
            "task_count": len(tasks),
            "phases": phases,
            "tasks": tasks,
            "decomposed_at": datetime.now(UTC).isoformat(),
        }
        self._decomposition_results.append(result)
        return result

    def decompose_all(self, okrs: list[OKR], owner: str = "") -> dict[str, Any]:
        """批量分解多个 OKR"""
        results = []
        total_phases = 0
        total_tasks = 0

        for okr in okrs:
            result = self.decompose(okr, owner)
            results.append(result)
            if result["success"]:
                total_phases += result["phase_count"]
                total_tasks += result["task_count"]

        return {
            "success": True,
            "okr_count": len(okrs),
            "total_phases": total_phases,
            "total_tasks": total_tasks,
            "results": results,
        }

    def get_last_decomposition(self) -> dict[str, Any] | None:
        """获取最近一次分解结果"""
        return self._decomposition_results[-1] if self._decomposition_results else None

    def get_all_decompositions(self) -> list[dict[str, Any]]:
        """获取所有分解历史"""
        return self._decomposition_results.copy()
