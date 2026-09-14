"""Adapter helpers that use Protocols for type safety instead of try/except.

Usage:
    from eidos.protocols.adapters import safe_validate
    errors = safe_validate(card)  # Returns [] if validation unavailable
"""

from __future__ import annotations

from typing import Any, cast

from eidos.protocols import (
    FactProtocol,
    KnowledgeCardProtocol,
    OntologyNodeProtocol,
    Validatable,
)


def safe_validate(obj: Any) -> list[str]:
    """Validate any object if it implements Validatable protocol.

    Returns empty list if object doesn't support validation.
    """

    if isinstance(obj, Validatable):
        return obj.validate()
    return []


def safe_to_dict(obj: Any) -> dict:
    """Convert to dict if object has to_dict method."""

    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return cast(dict, obj.to_dict())
    return {}


def is_knowledge_card(obj: Any) -> bool:
    """Check if object conforms to KnowledgeCardProtocol."""

    return isinstance(obj, KnowledgeCardProtocol)


def is_fact(obj: Any) -> bool:
    """Check if object conforms to FactProtocol."""

    return isinstance(obj, FactProtocol)


def is_ontology_node(obj: Any) -> bool:
    """Check if object conforms to OntologyNodeProtocol."""

    return isinstance(obj, OntologyNodeProtocol)
