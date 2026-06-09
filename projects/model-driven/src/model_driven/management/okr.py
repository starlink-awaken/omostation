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
