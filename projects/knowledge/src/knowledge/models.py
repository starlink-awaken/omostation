"""Unified Knowledge Models and DTOs (Data Contract Layer)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    """统一知识文档契约."""

    doc_id: str = Field(description="全局唯一文档 ID")
    title: str = Field(description="文档标题")
    body: str = Field(description="文档正文内容")
    zone: str = Field(default="default", description="业务域分区 (e.g. work-weijian, work-transfer)")
    kind: str = Field(default="note", description="文档类别 (note, cards, regulation, code)")
    canonical_path: str = Field(default="", description="文件物理或逻辑路径")
    trust_level: int = Field(default=1, description="信任等级 (1-5)")
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="更新时间戳 (ISO8601)",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="结构化元数据")


class KnowledgeEntity(BaseModel):
    """统一知识实体契约."""

    entity_id: str = Field(description="实体 ID")
    label: str = Field(description="实体名称")
    category: str = Field(default="Concept", description="实体类别 (Domain, Policy, Project, Person, Tool)")
    domain: str = Field(default="common", description="归属领域")
    properties: dict[str, Any] = Field(default_factory=dict, description="实体属性")


class KnowledgeRelation(BaseModel):
    """统一实体关系契约."""

    source_id: str = Field(description="源实体 ID")
    target_id: str = Field(description="目标实体 ID")
    relation_type: str = Field(description="关系类型 (BELONGS_TO, REQUIRES, COMPLIES_WITH, DERIVES_FROM)")
    weight: float = Field(default=1.0, description="关系权重")


class RetrievalResult(BaseModel):
    """统一混合检索结果条目."""

    doc_id: str
    title: str
    snippet: str = ""
    zone: str = "default"
    score: float = 0.0
    source: str = "hybrid"  # keyword, semantic, graph, hybrid
    matched_entities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SyncEvent(BaseModel):
    """双擎写穿一致性事件."""

    event_id: str
    doc_id: str
    action: str  # upsert, delete, invalidate
    source: str  # kos, gbrain, external
    target: str  # gbrain_postgres, kos_cache
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "pending"  # pending, committed, failed
