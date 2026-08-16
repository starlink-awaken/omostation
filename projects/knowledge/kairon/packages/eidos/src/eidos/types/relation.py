"""Relation — MET-RELATION type with SSOT 4-type meta-relation system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from eidos.meta import MetaRelationType


@dataclass
class Relation:
    """A typed relationship between two instances.

    relation_type: user-defined label (e.g. "is_a", "part_of", "implies")
    meta_relation: SSOT meta-classification (STRUCT | DERIVE | BEHAVIOR | JUSTIFY)
    cardinality: relationship density (1:1, 1:N, N:1, N:N)
    provenance: source trace for justification
    """

    id: str
    source_id: str
    target_id: str
    relation_type: str
    meta_relation: MetaRelationType = MetaRelationType.STRUCT
    weight: float = 1.0
    cardinality: str = "N:N"
    provenance: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "meta_relation": self.meta_relation.value,
            "cardinality": self.cardinality,
            "provenance": self.provenance,
            "weight": self.weight,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Relation:
        mr = d.get("meta_relation", "struct")
        if isinstance(mr, str):
            mr = MetaRelationType.from_string(mr)
        return cls(
            id=d["id"],
            source_id=d["source_id"],
            target_id=d["target_id"],
            relation_type=d.get("relation_type", ""),
            meta_relation=mr,
            cardinality=d.get("cardinality", "N:N"),
            provenance=d.get("provenance", ""),
            weight=d.get("weight", 1.0),
            properties=d.get("properties", {}),
        )

    def validate(self) -> list[str]:
        errs = []
        if not self.id:
            errs.append("id is required")
        if not self.source_id:
            errs.append("source_id is required")
        if not self.target_id:
            errs.append("target_id is required")
        if not self.relation_type:
            errs.append("relation_type is required")
        if self.cardinality not in ("1:1", "1:N", "N:1", "N:N"):
            errs.append(f"invalid cardinality: {self.cardinality}")
        return errs
