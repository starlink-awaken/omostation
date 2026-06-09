"""
model_driven.management.adr — ADR (架构决策记录) 管理

提供架构决策的完整生命周期管理：
- ADR 提议/采纳/废弃/取代
- ADR 与 Spec 的双向关联
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ADRStatus(Enum):
    """ADR 状态"""

    PROPOSED = "proposed"  # 提议中
    ACCEPTED = "accepted"  # 已采纳
    REJECTED = "rejected"  # 已拒绝
    DEPRECATED = "deprecated"  # 已废弃
    SUPERSEDED = "superseded"  # 被取代
    ARCHIVED = "archived"  # 已归档


@dataclass
class ADR:
    """架构决策记录"""

    id: str
    title: str
    context: str = ""  # 背景
    decision: str = ""  # 决策
    consequences: str = ""  # 后果
    status: ADRStatus = ADRStatus.PROPOSED
    alternatives: list[str] = field(default_factory=list)  # 替代方案
    related_specs: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    author: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def accept(self) -> bool:
        """采纳"""
        if self.status == ADRStatus.PROPOSED:
            self.status = ADRStatus.ACCEPTED
            self.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def reject(self) -> bool:
        """拒绝"""
        if self.status == ADRStatus.PROPOSED:
            self.status = ADRStatus.REJECTED
            self.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def deprecate(self) -> bool:
        """废弃"""
        if self.status in (ADRStatus.ACCEPTED, ADRStatus.PROPOSED):
            self.status = ADRStatus.DEPRECATED
            self.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def supersede(self, by_adr_id: str) -> bool:
        """被取代"""
        if self.status == ADRStatus.ACCEPTED:
            self.status = ADRStatus.SUPERSEDED
            self.superseded_by = by_adr_id
            self.updated_at = datetime.now(UTC).isoformat()
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict"""
        return {
            "id": self.id,
            "title": self.title,
            "context": self.context,
            "decision": self.decision,
            "consequences": self.consequences,
            "status": self.status.value,
            "alternatives": self.alternatives,
            "related_specs": self.related_specs,
            "superseded_by": self.superseded_by,
            "author": self.author,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"ADR(id={self.id!r}, title={self.title!r}, status={self.status.value})"


class ADRManager:
    """ADR 管理器"""

    def __init__(self):
        self._adrs: dict[str, ADR] = {}

    def create(self, adr_id: str, title: str, **kwargs) -> ADR:
        """创建 ADR"""
        adr = ADR(id=adr_id, title=title, **kwargs)
        self._adrs[adr_id] = adr
        return adr

    def get(self, adr_id: str) -> ADR | None:
        """获取 ADR"""
        return self._adrs.get(adr_id)

    def list_by_status(self, status: ADRStatus) -> list[ADR]:
        """按状态列出"""
        return [a for a in self._adrs.values() if a.status == status]

    def list_all(self) -> list[ADR]:
        """列出所有"""
        return list(self._adrs.values())

    def get_stats(self) -> dict[str, Any]:
        """获取统计"""
        stats = {s.value: 0 for s in ADRStatus}
        for adr in self._adrs.values():
            stats[adr.status.value] += 1
        stats["total"] = len(self._adrs)
        return stats

    def find_by_spec(self, spec_id: str) -> list[ADR]:
        """查找关联到某 Spec 的所有 ADR"""
        return [a for a in self._adrs.values() if spec_id in a.related_specs]

    # ── 持久化 ──────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict"""
        return {
            "adrs": {
                aid: {
                    "id": a.id,
                    "title": a.title,
                    "context": a.context,
                    "decision": a.decision,
                    "consequences": a.consequences,
                    "status": a.status.value,
                    "alternatives": a.alternatives,
                    "related_specs": a.related_specs,
                    "superseded_by": a.superseded_by,
                    "author": a.author,
                    "created_at": a.created_at,
                    "updated_at": a.updated_at,
                    "metadata": a.metadata,
                }
                for aid, a in self._adrs.items()
            }
        }

    def save(self, state_dir: str | None = None) -> bool:
        """持久化到文件"""
        from pathlib import Path

        if state_dir is None:
            from model_driven._paths import get_state_dir

            state_dir = str(get_state_dir())

        file_path = Path(state_dir) / "adrs.yaml"
        try:
            import yaml

            with open(file_path, "w") as f:
                yaml.dump(self.to_dict(), f, allow_unicode=True, sort_keys=False)
            return True
        except (OSError, ImportError, yaml.YAMLError):
            return False

    @classmethod
    def load(cls, state_dir: str | None = None) -> ADRManager | None:
        """从文件加载"""
        from pathlib import Path

        if state_dir is None:
            from model_driven._paths import get_state_dir

            state_dir = str(get_state_dir())

        file_path = Path(state_dir) / "adrs.yaml"
        if not file_path.exists():
            return None

        try:
            import yaml

            with open(file_path) as f:
                data = yaml.safe_load(f)
        except (OSError, ImportError, yaml.YAMLError):
            return None

        manager = cls()
        for aid, adata in (data or {}).get("adrs", {}).items():
            adr = ADR(
                id=adata["id"],
                title=adata["title"],
                context=adata.get("context", ""),
                decision=adata.get("decision", ""),
                consequences=adata.get("consequences", ""),
                status=ADRStatus(adata.get("status", "proposed")),
                alternatives=adata.get("alternatives", []),
                related_specs=adata.get("related_specs", []),
                superseded_by=adata.get("superseded_by"),
                author=adata.get("author", ""),
                created_at=adata.get("created_at", ""),
                updated_at=adata.get("updated_at", ""),
                metadata=adata.get("metadata", {}),
            )
            manager._adrs[aid] = adr
        return manager
