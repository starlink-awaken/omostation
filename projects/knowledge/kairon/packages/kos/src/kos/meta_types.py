"""Canonical KOS MetaType definitions and inference helpers."""

from __future__ import annotations

from pathlib import Path

CANONICAL_META_TYPES: tuple[str, ...] = (
    "domain",
    "fact",
    "document",
    "relation",
    "inference",
    "state",
    "constraint",
    "processor",
    "unknown",
)

FILTERABLE_META_TYPES: tuple[str, ...] = CANONICAL_META_TYPES[:-1]
FILTERABLE_META_TYPES_HELP = "/".join(FILTERABLE_META_TYPES)

_PATH_META_TYPE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("fact", ("facts", "fact")),
    ("inference", ("inferences", "inference")),
    ("relation", ("relations", "relation", "graph", "edges")),
    ("state", ("state", "states", "_state")),
    ("constraint", ("schemas", "schema", "constraints", "constraint", "protocols")),
    ("processor", ("processors", "processor", "pipelines", "pipeline")),
    ("domain", ("domains", "domain")),
)


def infer_meta_type(schema_type: str, source_path: str | Path) -> str:
    """Infer the canonical KOS MetaType from record kind and source path."""

    normalized_parts = {part.lower() for part in Path(source_path).parts}

    if schema_type in {"json_schema", "Schema"}:
        return "constraint"

    for meta_type, hints in _PATH_META_TYPE_HINTS:
        if normalized_parts.intersection(hints):
            return meta_type

    if schema_type in {"KnowledgeCard", "RawDocument"}:
        return "document"

    return "unknown"
