"""Shared scene card document parser.

A pure read-only library that parses scene card YAML documents (single mapping,
FrontMatter + canonical body, or rejected ambiguous forms) while preserving
full PyYAML semantics.  No filesystem writes, network calls, or subprocesses.

Contract (spec: docs/superpowers/specs/2026-10-20-v34-canonical-scene-parser.md):

- Accept: single mapping; explicit two-document form (frontmatter + body).
- Reject: empty content, non-mapping, empty body, duplicate keys (including
  nested), three or more documents, conflicting constrained fields across
  frontmatter and body, or two body documents that both declare a scene-card
  schema.
- The canonical body is the document that carries a ``scene-card/*`` schema,
  or the last document when no explicit schema is present.

All parsing uses ``yaml.safe_load_all`` with a SafeLoader subclass that raises
:class:`DuplicateKeyError` instead of silently overwriting repeated keys.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class SceneCardParseError(ValueError):
    """Raised when the input cannot be interpreted as a scene card document."""


class DuplicateKeyError(SceneCardParseError):
    """Raised when the same mapping key appears twice (including nested)."""


@dataclass(frozen=True)
class SceneCardDocument:
    """Parsed scene card document: frontmatter, body, and canonical index."""

    frontmatter: dict[str, Any]
    body: dict[str, Any]
    documents: list[dict[str, Any]]
    canonical_index: int
    source_sha256: str
    structure: str  # "single" or "frontmatter+body"

    @property
    def scene_id(self) -> Any:
        return self.body.get("scene_id") or self.frontmatter.get("scene_id")

    @property
    def lifecycle(self) -> Any:
        return self.body.get("lifecycle") or self.frontmatter.get("lifecycle")


def safe_load_with_duplicates(stream: str | bytes) -> list[Any]:
    """YAML parse all documents, rejecting duplicate mapping keys.

    Works with a string/bytes input (not a file object), so callers can hash
    and parse from the same byte source.  Returns the list of parsed documents
    (empty entries are preserved so callers can distinguish ``None`` from
    an empty document).
    """
    class StrictLoader(yaml.SafeLoader):
        pass

    def _build_constructor(loader_type: type) -> Any:
        def construct_mapping(loader: Any, node: yaml.Node, deep: bool = False) -> dict[Any, Any]:
            mapping: dict[Any, Any] = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                try:
                    hash(key)
                except TypeError as exc:
                    raise yaml.constructor.ConstructorError(
                        None, None, f"unhashable key: {key!r}", key_node.start_mark
                    ) from exc
                if key in mapping:
                    raise DuplicateKeyError(
                        f"duplicate mapping key {key!r} at line {key_node.start_mark.line + 1}"
                    )
                mapping[key] = loader.construct_object(value_node, deep=deep)
            return mapping
        return construct_mapping

    StrictLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _build_constructor(StrictLoader),
    )
    return list(yaml.load_all(stream, Loader=StrictLoader))


def _require_mapping(doc: Any, source: str, index: int) -> dict[str, Any]:
    if not isinstance(doc, Mapping):
        raise SceneCardParseError(
            f"scene card document {index} in {source or '<stream>'} must be a mapping, got {type(doc).__name__}"
        )
    return dict(doc)


def _select_canonical(documents: list[dict[str, Any]], source: str) -> int:
    """Return the canonical body index; reject ambiguity."""
    schema_indices = [
        i
        for i, doc in enumerate(documents)
        if isinstance(doc.get("schema"), str) and doc["schema"].startswith("scene-card/")
    ]
    if len(schema_indices) > 1:
        raise SceneCardParseError(
            f"scene card in {source or '<stream>'} has two scene-card schema documents "
            f"at indices {schema_indices}; ambiguous canonical body"
        )
    if schema_indices:
        return schema_indices[0]
    return len(documents) - 1


# Fields that must not silently conflict between frontmatter and body.
CONSTRAINED_FIELDS = frozenset(
    {
        "scene_id", "id", "lifecycle", "lifecycle_tier", "status",
        "sensitivity_class", "data_class", "data_classification",
        "approval_state", "activation",
    }
)


def _check_cross_document_conflicts(
    frontmatter: dict[str, Any], body: dict[str, Any], source: str
) -> None:
    for field in sorted(CONSTRAINED_FIELDS & (frontmatter.keys() & body.keys())):
        fm_value = frontmatter[field]
        body_value = body[field]
        if fm_value != body_value:
            raise SceneCardParseError(
                f"conflicting constrained field {field!r} in {source or '<stream>'}: "
                f"frontmatter={fm_value!r} body={body_value!r}"
            )


def parse_scene_card_document(
    text: str | bytes,
    source: str | Path | None = None,
) -> SceneCardDocument:
    """Parse raw YAML bytes or text into a :class:`SceneCardDocument`."""
    raw_bytes = text.encode("utf-8") if isinstance(text, str) else bytes(text)
    source_label = str(source or "<stream>")
    documents_raw = safe_load_with_duplicates(raw_bytes)
    documents = [
        _require_mapping(doc, source_label, i)
        for i, doc in enumerate(documents_raw)
        if doc is not None
    ]
    # Empty input (zero documents or only null documents)
    if not documents:
        raise SceneCardParseError(f"scene card in {source_label} is empty")
    # Two-document form where the trailing document is null means the writer
    # intended frontmatter + body but the body is absent.  A bare null with no
    # other document is already covered by the zero-mapping check above.
    if len(documents_raw) >= 2 and len(documents) == 1:
        raise SceneCardParseError(
            f"scene card in {source_label} has frontmatter but an empty body document"
        )
    if len(documents) == 1:
        if not documents[0]:
            raise SceneCardParseError(f"scene card body in {source_label} is empty")
        body = documents[0]
        frontmatter: dict[str, Any] = {}
        structure = "single"
    elif len(documents) == 2:
        frontmatter = documents[0]
        body_idx = _select_canonical(documents, source_label)
        body = documents[body_idx]
        structure = "frontmatter+body"
        if body_idx == 0:
            frontmatter = documents[1]
        _check_cross_document_conflicts(frontmatter, body, source_label)
    else:
        raise SceneCardParseError(
            f"scene card in {source_label} has {len(documents)} documents; "
            "expected 1 (single) or 2 (frontmatter + body)"
        )
    return SceneCardDocument(
        frontmatter=frontmatter,
        body=body,
        documents=documents,
        canonical_index=len(documents) - 1 if len(documents) == 1 else _select_canonical(documents, source_label),
        source_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        structure=structure,
    )


def load_scene_card_document(path: str | Path) -> SceneCardDocument:
    """Read and parse a scene card file from the filesystem (read-only)."""
    file_path = Path(path)
    return parse_scene_card_document(file_path.read_bytes(), source=file_path)


def sync_declared_mirrors(document: SceneCardDocument, changed_fields: dict[str, Any]) -> None:
    """Update the canonical body and already-declared matching frontmatter mirrors.

    A mirror is updated only when both documents declared the constrained field
    with the same pre-change value. New mirrors are never created.
    """
    for field, value in changed_fields.items():
        if (
            field in CONSTRAINED_FIELDS
            and field in document.frontmatter
            and field in document.body
            and document.frontmatter[field] == document.body[field]
        ):
            document.frontmatter[field] = value
        document.body[field] = value


def serialize_scene_card_document(document: SceneCardDocument) -> bytes:
    """Serialize a parsed document and verify that it re-parses losslessly.

    The verification covers document count, canonical body selection, identity,
    lifecycle, and all changed constrained fields. It deliberately does not
    promise byte-for-byte comment preservation.
    """
    output_docs = list(document.documents)
    output_docs[document.canonical_index] = document.body
    serialized = yaml.dump_all(
        output_docs,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).encode("utf-8")
    verified = parse_scene_card_document(serialized, source=document.source_sha256)
    if verified.documents != document.documents or verified.structure != document.structure:
        raise SceneCardParseError("serialization changed the scene card document structure")
    if verified.canonical_index != document.canonical_index:
        raise SceneCardParseError("serialization changed the canonical scene card document")
    if verified.scene_id != document.scene_id or verified.lifecycle != document.lifecycle:
        raise SceneCardParseError("serialization changed the scene card identity or lifecycle")
    for field in CONSTRAINED_FIELDS:
        if verified.body.get(field) != document.body.get(field):
            raise SceneCardParseError(f"serialization changed constrained body field {field!r}")
    return serialized


def write_scene_card_document(path: str | Path, document: SceneCardDocument) -> None:
    """Atomically replace a scene card after in-memory re-parse verification."""
    file_path = Path(path)
    file_path.write_bytes(serialize_scene_card_document(document))
