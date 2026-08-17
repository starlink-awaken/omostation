"""Eidos Meta-Model — SSOT-derived 8 MET-Type × 4 MET-Relation system."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MetaType(Enum):
    """SSOT 8-type meta-entity system.

    Each concrete Eidos type maps to one MetaType.
    """

    DOMAIN = "domain"  # 领域实体 → OntologyNode
    FACT = "fact"  # 事实断言 → Fact
    INFERENCE = "inference"  # 推导规则 → InferenceRule
    RELATION = "relation"  # 关系类型 → Relation
    STATE = "state"  # 状态机 → StateMachine
    DOCUMENT = "document"  # 文档知识 → KnowledgeCard
    CONSTRAINT = "constraint"  # 约束/规约 → Schema
    PROCESSOR = "processor"  # 处理器 → PipelineDef

    @classmethod
    def from_string(cls, s: str) -> MetaType:
        for mt in cls:
            if mt.value == s.lower():
                return mt
        raise ValueError(f"Unknown MetaType: {s}")

    def display_name(self) -> str:
        names = {
            "domain": "领域实体",
            "fact": "事实断言",
            "inference": "推导规则",
            "relation": "关系类型",
            "state": "状态机",
            "document": "文档知识",
            "constraint": "约束规约",
            "processor": "处理器",
        }
        return names.get(self.value, self.value)


class MetaRelationType(Enum):
    """SSOT 4-type meta-relation.

    Defines how MetaType instances can relate to each other.
    """

    STRUCT = "struct"  # 结构组成 (is_a, part_of, extends)
    DERIVE = "derive"  # 推导派生 (implies, entails, contradicts)
    BEHAVIOR = "behavior"  # 行为状态 (triggers, transitions_to)
    JUSTIFY = "justify"  # 归因溯源 (proves, supports, refutes)

    @classmethod
    def from_string(cls, s: str) -> MetaRelationType:
        for mr in cls:
            if mr.value == s.lower():
                return mr
        raise ValueError(f"Unknown MetaRelationType: {s}")


@dataclass
class MetaRelationConstraint:
    """Constraints on a relation between MetaTypes."""

    source_type: str
    target_type: str
    relation_type: str
    cardinality: str = "N:N"
    confidence: float = 1.0
    provenance: bool = False


BUILTIN_CONSTRAINTS: list[MetaRelationConstraint] = [
    MetaRelationConstraint(source_type="domain", target_type="domain", relation_type="struct", cardinality="N:N"),
    MetaRelationConstraint(source_type="fact", target_type="fact", relation_type="derive", cardinality="N:1"),
    MetaRelationConstraint(source_type="document", target_type="document", relation_type="justify", cardinality="1:N"),
    MetaRelationConstraint(source_type="state", target_type="state", relation_type="behavior", cardinality="1:1"),
]


def list_constraints() -> list[dict]:
    return [
        {
            "source": c.source_type,
            "target": c.target_type,
            "type": c.relation_type,
            "cardinality": c.cardinality,
            "confidence": c.confidence,
            "provenance": c.provenance,
        }
        for c in BUILTIN_CONSTRAINTS
    ]


# Default mapping: MetaType → concrete Eidos type names
TYPE_MAP: dict[MetaType, list[str]] = {
    MetaType.DOMAIN: ["OntologyNode"],
    MetaType.FACT: ["Fact"],
    MetaType.INFERENCE: ["InferenceRule"],
    MetaType.RELATION: ["Relation"],
    MetaType.STATE: ["StateMachine"],
    MetaType.DOCUMENT: ["KnowledgeCard", "Schema"],
    MetaType.CONSTRAINT: ["Schema"],
    MetaType.PROCESSOR: [],
}


def list_types(meta_type: MetaType | None = None) -> list[dict]:
    """List registered types, optionally filtered by MetaType."""
    results = []
    for mt, types in TYPE_MAP.items():
        if meta_type and mt != meta_type:
            continue
        for t in types:
            results.append(
                {
                    "meta_type": mt.value,
                    "meta_type_name": mt.display_name(),
                    "type_name": t,
                }
            )
    return results
