"""
model_driven.management.spec — Spec 驱动管理

提供规格驱动的需求管理：
- Spec 创建/评审/审批/实现/完成
- Spec 与 ADR/OKR 的关联
- Spec 状态机
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
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
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def submit_for_review(self) -> bool:
        """提交评审"""
        if self.status == SpecStatus.DRAFT:
            self.status = SpecStatus.REVIEW
            self.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def approve(self) -> bool:
        """批准"""
        if self.status == SpecStatus.REVIEW:
            self.status = SpecStatus.APPROVED
            self.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def start_implementation(self) -> bool:
        """开始实现"""
        if self.status == SpecStatus.APPROVED:
            self.status = SpecStatus.IMPLEMENTING
            self.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def mark_done(self) -> bool:
        """标记完成"""
        if self.status == SpecStatus.IMPLEMENTING:
            self.status = SpecStatus.DONE
            self.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def amend(self) -> bool:
        """修订"""
        if self.status in (SpecStatus.APPROVED, SpecStatus.IMPLEMENTING):
            self.status = SpecStatus.AMENDED
            self.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def archive(self) -> bool:
        """归档"""
        if self.status == SpecStatus.DONE:
            self.status = SpecStatus.ARCHIVED
            self.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "author": self.author,
            "status": self.status.value,
            "related_adrs": self.related_adrs,
            "related_okrs": self.related_okrs,
            "dependencies": self.dependencies,
            "reviewers": self.reviewers,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"Spec(id={self.id!r}, title={self.title!r}, status={self.status.value})"


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

    # ── 持久化 ──────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict"""
        return {
            "specs": {
                sid: {
                    "id": s.id,
                    "title": s.title,
                    "description": s.description,
                    "author": s.author,
                    "status": s.status.value,
                    "related_adrs": s.related_adrs,
                    "related_okrs": s.related_okrs,
                    "dependencies": s.dependencies,
                    "reviewers": s.reviewers,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                    "metadata": s.metadata,
                }
                for sid, s in self._specs.items()
            }
        }

    def save(self, state_dir: str | None = None) -> bool:
        """持久化到文件"""
        from pathlib import Path

        if state_dir is None:
            from model_driven._paths import get_state_dir

            state_dir = str(get_state_dir())

        file_path = Path(state_dir) / "specs.yaml"
        try:
            import yaml

            with open(file_path, "w") as f:
                yaml.dump(self.to_dict(), f, allow_unicode=True, sort_keys=False)
            return True
        except (OSError, ImportError, yaml.YAMLError):
            return False

    @classmethod
    def load(cls, state_dir: str | None = None) -> SpecManager | None:
        """从文件加载"""
        from pathlib import Path

        if state_dir is None:
            from model_driven._paths import get_state_dir

            state_dir = str(get_state_dir())

        file_path = Path(state_dir) / "specs.yaml"
        if not file_path.exists():
            return None

        try:
            import yaml

            with open(file_path) as f:
                data = yaml.safe_load(f)
        except (OSError, ImportError, yaml.YAMLError):
            return None

        manager = cls()
        for sid, sdata in (data or {}).get("specs", {}).items():
            spec = Spec(
                id=sdata["id"],
                title=sdata["title"],
                description=sdata.get("description", ""),
                author=sdata.get("author", ""),
                status=SpecStatus(sdata.get("status", "draft")),
                related_adrs=sdata.get("related_adrs", []),
                related_okrs=sdata.get("related_okrs", []),
                dependencies=sdata.get("dependencies", []),
                reviewers=sdata.get("reviewers", []),
                created_at=sdata.get("created_at", ""),
                updated_at=sdata.get("updated_at", ""),
                metadata=sdata.get("metadata", {}),
            )
            manager._specs[sid] = spec
        return manager
