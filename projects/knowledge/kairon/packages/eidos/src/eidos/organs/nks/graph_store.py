"""NKS graph store — entity and relation data models for NKS tree-sitter extractor.

Provides graph store with basic persistence and querying support.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CandidateEntity:
    """A candidate entity extracted during NKS pipeline processing."""

    entity_id: str
    name: str
    properties: dict = field(default_factory=dict)
    source_file: str = ""
    embedding: list[float] | None = None


@dataclass
class CandidateRelation:
    """A candidate relation extracted during NKS pipeline processing."""

    source_id: str
    target_id: str
    relation_type: str
    properties: dict = field(default_factory=dict)
    source_file: str = ""
    weight: float = 1.0
    confidence: float = 1.0


__all__ = [
    "CandidateEntity",
    "CandidateRelation",
]
