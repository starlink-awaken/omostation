"""
model_driven.management.spec — Spec 驱动管理

提供规格驱动的需求管理：
- Spec 创建/评审/审批/实现/完成
- Spec 与 ADR/OKR 的关联
- Spec 状态机
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SpecStatus(Enum):
    """Spec 状态"""

    DRAFT = "draft"  # 草稿
    REVIEW = "review"  # 评审中
    APPROVED = "approved"  # 已批准
    IMPLEMENTING = "implementing"  # 实现中
    DONE = "done"  # 已完成
    AMENDED = "amended"  # 已修订
    ARCHIVED = "archived"  # 已归档


@dataclass
class Spec:
    """规格定义"""

    id: str
    title: str
    description: str = ""
    author: str = ""
    status: SpecStatus = SpecStatus.DRAFT
    related_adrs: list[str] = field(default_factory=list)
    related_okrs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    reviewers: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def submit_for_review(self) -> bool:
        """提交评审"""
        if self.status == SpecStatus.DRAFT:
            self.status = SpecStatus.REVIEW
            self.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def approve(self) -> bool:
        """批准"""
        if self.status == SpecStatus.REVIEW:
            self.status = SpecStatus.APPROVED
            self.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def start_implementation(self) -> bool:
        """开始实现"""
        if self.status == SpecStatus.APPROVED:
            self.status = SpecStatus.IMPLEMENTING
            self.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def mark_done(self) -> bool:
        """标记完成"""
        if self.status == SpecStatus.IMPLEMENTING:
            self.status = SpecStatus.DONE
            self.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def amend(self) -> bool:
        """修订"""
        if self.status in (SpecStatus.APPROVED, SpecStatus.IMPLEMENTING):
            self.status = SpecStatus.AMENDED
            self.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def archive(self) -> bool:
        """归档"""
        if self.status == SpecStatus.DONE:
            self.status = SpecStatus.ARCHIVED
            self.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False


class SpecManager:
    """Spec 管理器"""

    def __init__(self):
        self._specs: dict[str, Spec] = {}

    def create(self, spec_id: str, title: str, **kwargs) -> Spec:
        """创建 Spec"""
        spec = Spec(id=spec_id, title=title, **kwargs)
        self._specs[spec_id] = spec
        return spec

    def get(self, spec_id: str) -> Spec | None:
        """获取 Spec"""
        return self._specs.get(spec_id)

    def list_by_status(self, status: SpecStatus) -> list[Spec]:
        """按状态列出 Spec"""
        return [s for s in self._specs.values() if s.status == status]

    def list_all(self) -> list[Spec]:
        """列出所有 Spec"""
        return list(self._specs.values())

    def link_adr(self, spec_id: str, adr_id: str) -> bool:
        """关联 ADR"""
        spec = self._specs.get(spec_id)
        if spec and adr_id not in spec.related_adrs:
            spec.related_adrs.append(adr_id)
            return True
        return False

    def link_okr(self, spec_id: str, okr_id: str) -> bool:
        """关联 OKR"""
        spec = self._specs.get(spec_id)
        if spec and okr_id not in spec.related_okrs:
            spec.related_okrs.append(okr_id)
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """获取统计"""
        stats = {s.value: 0 for s in SpecStatus}
        for spec in self._specs.values():
            stats[spec.status.value] += 1
        stats["total"] = len(self._specs)
        return stats
