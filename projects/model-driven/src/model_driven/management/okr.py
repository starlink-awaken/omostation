"""
model_driven.management.okr — OKR 目标对齐管理

提供 OKR 的完整生命周期管理：
- OKR 创建/执行/完成/取消
- 进度追踪
- OKR → Phase → Task 自动分解
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

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
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
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
            self.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def complete(self) -> bool:
        """完成"""
        if self.status == OKRStatus.ACTIVE:
            self.status = OKRStatus.COMPLETED
            self.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def cancel(self) -> bool:
        """取消"""
        if self.status in (OKRStatus.DRAFT, OKRStatus.ACTIVE):
            self.status = OKRStatus.CANCELLED
            self.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def update_kr(self, kr_id: str, current_value: float) -> bool:
        """更新 KR 进度"""
        for kr in self.key_results:
            if kr.id == kr_id:
                kr.current_value = current_value
                self.updated_at = datetime.now(timezone.utc).isoformat()
                return True
        return False


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
        now = datetime.now(timezone.utc).isoformat()
        return [
            o for o in self._okrs.values()
            if o.status == OKRStatus.ACTIVE and o.deadline and o.deadline < now
        ]


# ── OKR 自动分解 ──────────────────────────────────


class OKRDecomposer:
    """OKR 自动分解器 — 将 OKR 的 KeyResult 自动分解为 Phase 和 Task"""

    def __init__(self):
        self._decomposition_results: list[dict[str, Any]] = []

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

        phases: list[dict[str, Any]] = []
        tasks: list[dict[str, Any]] = []

        for i, kr in enumerate(okr.key_results):
            # 根据 KR 描述推断 Phase 和 Task
            kr_lower = kr.description.lower()

            # 推断阶段 (顺序重要: hardening 关键词优先检查)
            if any(kw in kr_lower for kw in ["运营", "报告", "价值", "优化", "business", "report", "value"]):
                phase = "hardening"
                phase_name = "硬化"
            elif any(kw in kr_lower for kw in ["运行", "运维", "监控", "run", "ops", "monitor"]):
                phase = "hardening"
                phase_name = "硬化"
            elif any(kw in kr_lower for kw in ["部署", "上线", "deploy", "发布", "release"]):
                phase = "evolution"
                phase_name = "演进"
            elif any(kw in kr_lower for kw in ["开发", "实现", "代码", "code", "开发", "build", "测试", "test"]):
                phase = "evolution"
                phase_name = "演进"
            elif any(kw in kr_lower for kw in ["设计", "架构", "spec", "design", "adr"]):
                phase = "cold_start"
                phase_name = "冷启动"
            elif any(kw in kr_lower for kw in ["规划", "计划", "目标", "plan", "goal", "okr"]):
                phase = "cold_start"
                phase_name = "冷启动"
            else:
                phase = "evolution"
                phase_name = "演进"

            # 推断优先级
            if kr.weight >= 2.0:
                priority = "P0"
            elif kr.weight >= 1.0:
                priority = "P1"
            elif kr.weight >= 0.5:
                priority = "P2"
            else:
                priority = "P3"

            # 创建 Phase
            phase_id = f"PHASE-{okr.id}-{i + 1:02d}"
            phases.append({
                "id": phase_id,
                "name": f"{phase_name}: {kr.description[:40]}",
                "phase": phase,
                "kr_id": kr.id,
                "kr_description": kr.description,
                "target_value": kr.target_value,
                "current_value": kr.current_value,
                "weight": kr.weight,
                "priority": priority,
                "owner": owner or okr.owner,
            })

            # 创建 Task
            task_count = max(1, int(kr.target_value / 10) if kr.target_value > 0 else 1)
            for t in range(task_count):
                task_id = f"TASK-{okr.id}-{i + 1:02d}-{t + 1:02d}"
                tasks.append({
                    "id": task_id,
                    "title": f"[{priority}] {kr.description} — 第 {t + 1}/{task_count} 步",
                    "description": f"OKR: {okr.objective}\nKR: {kr.description}\n目标值: {kr.target_value} {kr.unit}",
                    "phase_id": phase_id,
                    "kr_id": kr.id,
                    "priority": priority,
                    "assignee": owner or okr.owner,
                    "weight": kr.weight / task_count,
                    "target_progress": round((t + 1) / task_count * 100, 1),
                })

        result = {
            "success": True,
            "okr_id": okr.id,
            "okr_objective": okr.objective,
            "phase_count": len(phases),
            "task_count": len(tasks),
            "phases": phases,
            "tasks": tasks,
            "decomposed_at": datetime.now(timezone.utc).isoformat(),
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
