"""Shared read-only parser for scene card YAML documents.

This module provides a single canonical entry point for review, lifecycle and
lineage callers.  It accepts either a single YAML mapping or an explicit
frontmatter + canonical body two-document stream.  Duplicate keys, conflicting
state fields and ambiguous document counts raise ``SceneCardParseError`` with
source context.  No filesystem side effects happen inside the parser itself.

The parser does not validate business readiness or lifecycle transitions.
Those remain the caller's contract.  Write-back helpers keep the canonical
body as the single mutation target and only mirror already-declared identical
frontmatter state fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml


class SceneCardParseError(ValueError):
    """Raised when a scene card document is ambiguous, malformed or conflicting."""


CONSTRAINED_FIELDS = (
    "scene_id",
    "id",
    "lifecycle",
    "lifecycle_tier",
    "status",
    "sensitivity_class",
    "data_class",
    "data_classification",
    "approval_state",
    "activation",
)


@dataclass
class SceneCardDocument:
    """Parsed scene card document with provenance and structural metadata."""

    body: dict[str, Any]
    frontmatter: dict[str, Any] | None
    documents: list[dict[str, Any]]
    canonical_index: int
    source_sha256: str
    structure: str
    source: Path | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


def _describe_location(node: Any, path: str) -> str:
    if isinstance(node, yaml.Node):
        line = node.start_mark.line + 1
        column = node.start_mark.column + 1
        return f"{path} (line {line}, column {column})"
    return path


def _check_duplicate_keys(
    loader: yaml.SafeLoader,
    node: yaml.MappingNode,
    prefix: str = "",
    source_label: str = "<inline>",
) -> None:
    if isinstance(node, yaml.SequenceNode):
        for child in node.value:
            if isinstance(child, (yaml.MappingNode, yaml.SequenceNode)):
                _check_duplicate_keys(loader, child, prefix)
        return
    seen: dict[str, yaml.Node] = {}
    for key_node, _ in node.value:
        key_repr = str(key_node.value) if isinstance(key_node, yaml.ScalarNode) else "<complex>"
        path = f"{prefix}.{key_repr}" if prefix else key_repr
        if key_repr in seen:
            raise SceneCardParseError(
                f"{source_label}: {path!r} duplicate key in mapping: "
                f"first at {_describe_location(seen[key_repr], path)}, "
                f"second at {_describe_location(key_node, path)}"
            )
        seen[key_repr] = key_node
        if isinstance(key_node.value, dict) or isinstance(node.value, dict):
            pass
    for key_node, value_node in node.value:
        if isinstance(value_node, (yaml.MappingNode, yaml.SequenceNode)):
            key_repr = str(key_node.value) if isinstance(key_node, yaml.ScalarNode) else "<complex>"
            path = f"{prefix}.{key_repr}" if prefix else key_repr
            _check_duplicate_keys(loader, value_node, path, source_label)


class DuplicateKeySafeLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys at any nesting level."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[str, Any]:
        _check_duplicate_keys(self, node, source_label=getattr(self, "_source_label", "<inline>"))
        return super().construct_mapping(node, deep=deep)


def _compare_semantic(left: Any, right: Any) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        if left.keys() != right.keys():
            return False
        return all(_compare_semantic(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False
        return all(_compare_semantic(a, b) for a, b in zip(left, right))
    return left == right


def parse_scene_card_document(text: str, source: str | Path | None = None) -> SceneCardDocument:
    """Parse scene card YAML from text.  See module docstring for contract."""
    source_label = str(source) if source is not None else "<inline>"
    loader_class = type("DuplicateKeySafeLoader", (DuplicateKeySafeLoader,), {})
    loader_class._source_label = source_label
    try:
        yaml.scan(text, Loader=loader_class)
    except (yaml.YAMLError, SceneCardParseError) as exc:
        raise SceneCardParseError(f"YAML syntax error in {source_label}: {exc}") from exc

    raw_documents = list(yaml.load_all(text, Loader=loader_class))
    for doc_index, raw_doc in enumerate(raw_documents):
        if raw_doc is None:
            continue
        if not isinstance(raw_doc, dict):
            raise SceneCardParseError(
                f"document {doc_index} in {source_label} is not a mapping "
                f"(got {type(raw_doc).__name__})"
            )
    if len(raw_documents) == 0:
        raise SceneCardParseError(f"empty document: {source_label}")

    normalized: list[dict[str, Any] | None] = []
    for index, doc in enumerate(raw_documents):
        if doc is None:
            normalized.append(None)
            continue
        if not isinstance(doc, dict):
            raise SceneCardParseError(
                f"document {index} in {source_label} is not a mapping (got {type(doc).__name__})"
            )
        normalized.append(doc)

    nonempty = [doc for doc in normalized if doc is not None]
    if len(nonempty) == 0:
        raise SceneCardParseError(f"all documents empty or null: {source_label}")
    if len(nonempty) > 2:
        raise SceneCardParseError(
            f"expected 1 or 2 documents in {source_label}, got {len(nonempty)}"
        )

    frontmatter: dict[str, Any] | None = None
    if len(nonempty) == 2:
        frontmatter = normalized[0]
        if frontmatter is None:
            raise SceneCardParseError(f"frontmatter document is null: {source_label}")
        body = normalized[1]
        canonical_index = next(i for i, doc in enumerate(normalized) if doc is body)
        structure = "frontmatter+body"
    else:
        body = nonempty[0]
        canonical_index = normalized.index(body)
        structure = "single"

    if not body:
        raise SceneCardParseError(f"canonical body is empty in {source_label}")

    conflicts: list[str] = []
    if frontmatter is not None:
        for key in CONSTRAINED_FIELDS:
            if key in frontmatter and key in body:
                if not _compare_semantic(frontmatter[key], body[key]):
                    conflicts.append(
                        f"state field {key!r} conflicts: frontmatter={frontmatter[key]!r} "
                        f"body={body[key]!r}"
                    )
        for key in frontmatter:
            if key not in CONSTRAINED_FIELDS and key in body and not _compare_semantic(frontmatter[key], body[key]):
                conflicts.append(
                    f"non-constrained field {key!r} conflicts: frontmatter={frontmatter[key]!r} "
                    f"body={body[key]!r}"
                )
    if conflicts:
        raise SceneCardParseError(
            f"state field conflict(s) in {source_label}: " + "; ".join(conflicts)
        )

    return SceneCardDocument(
        body=body,
        frontmatter=frontmatter,
        documents=[doc for doc in normalized if doc is not None],
        canonical_index=canonical_index,
        source_sha256=sha256(text.encode("utf-8")).hexdigest(),
        structure=structure,
        source=Path(source) if isinstance(source, (str, Path)) and source is not None else None,
        diagnostics={"conflict_fields": [] if not conflicts else conflicts},
    )


def load_scene_card_document(path: str | Path) -> SceneCardDocument:
    """Read and parse a scene card file.  Read-only; raises on missing file."""
    file_path = Path(path)
    if not file_path.exists():
        raise SceneCardParseError(f"scene card file not found: {file_path}")
    text = file_path.read_text(encoding="utf-8")
    return parse_scene_card_document(text, source=file_path)


def sync_declared_mirrors(
    document: SceneCardDocument,
    changed_fields: dict[str, Any],
) -> None:
    """Update canonical body fields and existing identical frontmatter mirrors.

    Only fields already declared in both documents with matching values are
    mirrored.  New mirrors are never created.  Mutates in-place; caller must
    re-parse and validate before writing back.
    """
    for key, value in changed_fields.items():
        original_body_value = document.body.get(key)
        if (
            document.frontmatter is not None
            and key in document.frontmatter
            and key in CONSTRAINED_FIELDS
            and _compare_semantic(document.frontmatter[key], original_body_value)
        ):
            document.frontmatter[key] = value
        document.body[key] = value


def write_scene_card_document(
    path: str | Path,
    document: SceneCardDocument,
    comments_preserved: bool = False,
) -> None:
    """Serialize document back to YAML.  Caller must re-parse before trusting result.

    ``comments_preserved`` is informational; serialization does not retain raw
    comments.  Write-back targets the canonical body and retains document order.
    """
    del comments_preserved
    target = Path(path)
    if document.structure == "frontmatter+body" and document.frontmatter is not None:
        payload: list[dict[str, Any]] = [document.frontmatter, document.body]
    else:
        payload = [document.body]
    target.write_text(
        yaml.dump_all(payload, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
