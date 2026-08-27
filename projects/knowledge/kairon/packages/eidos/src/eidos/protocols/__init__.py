"""Eidos Protocols — formal interface contracts for the type system.

All Eidos types implement these protocols. External tools (KOS, OntoDerive, Minerva)
can type-check against these protocols instead of using try/except ImportError.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from eidos.protocols.contracts import CONTRACT_REGISTRY, validate_contract_payload


@runtime_checkable
class Validatable(Protocol):
    """Any object that can validate itself."""

    def validate(self) -> list[str]: ...


@runtime_checkable
class Serializable(Protocol):
    """Any object that can serialize/deserialize."""

    def to_dict(self) -> dict: ...

    @classmethod
    def from_dict(cls, data: dict) -> Validatable: ...


@runtime_checkable
class KnowledgeCardProtocol(Validatable, Serializable, Protocol):
    """Protocol for KnowledgeCard-like objects."""

    id: str
    title: str
    content: str
    source: str
    source_type: str
    schema_type: str
    tags: list[str]


@runtime_checkable
class FactProtocol(Validatable, Serializable, Protocol):
    """Protocol for Fact-like objects."""

    id: str
    subject: str
    predicate: str
    object: str
    confidence: float


@runtime_checkable
class OntologyNodeProtocol(Validatable, Serializable, Protocol):
    """Protocol for OntologyNode-like objects."""

    id: str
    name: str
    node_type: str
    properties: dict
    aliases: list[str]


def validate(instance: Validatable) -> list[str]:
    """Validate any object implementing Validatable protocol."""

    return instance.validate()


def serialize(instance: Serializable) -> dict:
    """Serialize any object implementing Serializable protocol."""

    return instance.to_dict()


__all__ = [
    "Validatable",
    "Serializable",
    "KnowledgeCardProtocol",
    "FactProtocol",
    "OntologyNodeProtocol",
    "validate",
    "serialize",
    "CONTRACT_REGISTRY",
    "validate_contract_payload",
]
