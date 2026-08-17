"""Eidos Meta — SSOT 4-type meta-relation and 8-type meta-type system.

MetaRelationType: STRUCT | DERIVE | BEHAVIOR | JUSTIFY
MetaType:         CONCEPT | RELATION | RULE | CARD | FACT | NODE | STATE | CONSTRAINT

Provides meta-model with basic registry support.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class MetaRelationType(Enum):
    """SSOT 4-type meta-relation classification."""

    STRUCT = "struct"
    DERIVE = "derive"
    BEHAVIOR = "behavior"
    JUSTIFY = "justify"

    @classmethod
    def from_string(cls, value: str) -> MetaRelationType:
        """Parse a string into a MetaRelationType, defaulting to STRUCT."""
        for member in cls:
            if member.value == value:
                return member
        return cls.STRUCT


class MetaType(Enum):
    """Eidos 8-type meta-model."""

    CONCEPT = "concept"
    RELATION = "relation"
    RULE = "rule"
    CARD = "card"
    FACT = "fact"
    NODE = "node"
    STATE = "state"
    CONSTRAINT = "constraint"

    def display_name(self) -> str:
        """Return a human-readable display name."""
        return self.value.capitalize()


_TYPE_REGISTRY: dict[str, dict[str, Any]] = {
    "concept": {"meta_type": "concept", "description": "Abstract or concrete concept"},
    "relation": {"meta_type": "relation", "description": "Typed relationship"},
    "rule": {"meta_type": "rule", "description": "Inference or transformation rule"},
    "card": {"meta_type": "card", "description": "Structured knowledge card"},
    "fact": {"meta_type": "fact", "description": "Atomic fact (subject-predicate-object)"},
    "node": {"meta_type": "node", "description": "Ontology node"},
    "state": {"meta_type": "state", "description": "State machine state"},
    "constraint": {"meta_type": "constraint", "description": "Formal constraint"},
}


def list_types() -> list[dict[str, Any]]:
    """List all registered meta types."""
    return [
        {"type_name": name, "meta_type": info["meta_type"], "description": info["description"]}
        for name, info in _TYPE_REGISTRY.items()
    ]


__all__ = [
    "MetaRelationType",
    "MetaType",
    "list_types",
]
