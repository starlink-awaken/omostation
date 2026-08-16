"""公文/政策文档数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PolicyDocument:
    """单个政策文档的结构化信息"""

    path: Path
    filename: str = ""
    title: str = ""
    doc_number: str = ""
    issuing_org: str = ""
    pub_date: str = ""
    level: str = "其他"
    domain: str = "通用政策"
    abstract: str = ""
    content_preview: str = ""
    byte_size: int = 0
    page_count: int = 0
    file_type: str = ""
    relationships: list[dict] = field(default_factory=list)
    error: str | None = None


@dataclass
class PolicyGraph:
    """政策文档项目的完整分析结果"""

    documents: list[PolicyDocument] = field(default_factory=list)
    level_groups: dict[str, list[PolicyDocument]] = field(default_factory=dict)
    domain_groups: dict[str, list[PolicyDocument]] = field(default_factory=dict)
    relationships: list[dict] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.documents)

    @property
    def summary(self) -> str:
        levels = ", ".join(f"{k}: {len(v)}" for k, v in self.level_groups.items())
        domains = ", ".join(f"{k}: {len(v)}" for k, v in self.domain_groups.items())
        return (
            f"✅ {self.total_count} 个政策文档\n"
            f"   层级分布: {levels}\n"
            f"   领域分布: {domains}\n"
            f"   关系: {len(self.relationships)} 条"
        )
