"""Contract tests for the shared scene card parser (BET-Y2Q4-T10-340401).

Covers legal inputs (v1/v2, frontmatter+body, nested structures, URI scalars,
block scalars, JSON mappings), and explicit rejections (empty content, non-
mapping, duplicate keys including nested, cross-document conflicts, dual
scene-card schemas, three-document forms, empty body).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.scene_card_document import (  # noqa: E402
    DuplicateKeyError,
    SceneCardParseError,
    load_scene_card_document,
    parse_scene_card_document,
    safe_load_with_duplicates,
    sync_declared_mirrors,
    write_scene_card_document,
)

# ── legal inputs ──────────────────────────────────────────────────────────

V2_BODY = """schema: scene-card/v2
scene_id: test-001
lifecycle: shadow
goal: sample goal
"""

V1_BODY = """schema: scene-card/v1
scene_id: test-v1
lifecycle: draft
"""


def test_single_mapping_parses() -> None:
    doc = parse_scene_card_document(V2_BODY)
    assert doc.structure == "single"
    assert doc.canonical_index == 0
    assert doc.scene_id == "test-001"
    assert doc.lifecycle == "shadow"
    assert doc.body["schema"] == "scene-card/v2"
    assert doc.frontmatter == {}


def test_frontmatter_body_parses() -> None:
    text = f"""---
review_note: "weekly check"
scene_id: test-001
lifecycle: shadow
---
{V2_BODY}"""
    doc = parse_scene_card_document(text)
    assert doc.structure == "frontmatter+body"
    assert doc.frontmatter["review_note"] == "weekly check"
    assert doc.body["schema"] == "scene-card/v2"
    assert doc.canonical_index == 1


def test_nested_mapping_and_unindented_list() -> None:
    text = """schema: scene-card/v2
scene_id: test-nested
inputs:
  - name: alpha
    type: string
  - name: beta
    type: int
nested:
  deep:
    key: [1, 2, 3]
"""
    doc = parse_scene_card_document(text)
    assert doc.body["inputs"][0]["name"] == "alpha"
    assert doc.body["inputs"][1]["type"] == "int"
    assert doc.body["nested"]["deep"]["key"] == [1, 2, 3]


def test_uri_and_block_scalar() -> None:
    text = """schema: scene-card/v2
scene_id: test-uri
source: https://example.com/api
description: |
  Multi-line
  block scalar.
"""
    doc = parse_scene_card_document(text)
    assert doc.body["source"] == "https://example.com/api"
    assert doc.body["description"] == "Multi-line\nblock scalar.\n"


def test_json_mapping_body() -> None:
    import json

    payload = {"schema": "scene-card/v2", "scene_id": "test-json", "lifecycle": "draft"}
    doc = parse_scene_card_document(json.dumps(payload))
    assert doc.body["scene_id"] == "test-json"
    assert isinstance(doc.body, dict)


def test_v1_and_v2_schema_both_accepted() -> None:
    for text, expected in ((V1_BODY, "v1"), (V2_BODY, "v2")):
        doc = parse_scene_card_document(text)
        assert doc.body["schema"].endswith(expected)


def test_load_scene_card_document_from_file(tmp_path: Path) -> None:
    p = tmp_path / "card.yaml"
    p.write_text(V2_BODY, encoding="utf-8")
    doc = load_scene_card_document(p)
    assert doc.scene_id == "test-001"
    assert doc.source_sha256
    assert len(doc.source_sha256) == 64


# ── explicit rejections ───────────────────────────────────────────────────


def test_empty_content_rejected() -> None:
    with pytest.raises(SceneCardParseError, match="empty"):
        parse_scene_card_document("")


def test_empty_body_rejected() -> None:
    # "empty body" means the second document in the two-document form is
    # null (frontmatter present but no canonical body).
    text = "---\nnote: meta\n---\n"
    with pytest.raises(SceneCardParseError, match="empty"):
        parse_scene_card_document(text)

    # a bare single mapping is always legal
    doc = parse_scene_card_document("only: mapping\n")
    assert doc.structure == "single"
    assert doc.body == {"only": "mapping"}


def test_non_mapping_rejected() -> None:
    with pytest.raises(SceneCardParseError, match="must be a mapping"):
        parse_scene_card_document("- just a list\n")


def test_duplicate_key_rejected() -> None:
    with pytest.raises(DuplicateKeyError, match="duplicate"):
        parse_scene_card_document("scene_id: a\nscene_id: b\n")


def test_nested_duplicate_key_rejected() -> None:
    text = """scene_id: test-dup
nested:
  inner: 1
  inner: 2
"""
    with pytest.raises(DuplicateKeyError, match="duplicate"):
        parse_scene_card_document(text)


def test_conflicting_constrained_field_rejected() -> None:
    text = f"""---
lifecycle: draft
---
{V2_BODY}"""
    with pytest.raises(SceneCardParseError, match="conflicting constrained field 'lifecycle'"):
        parse_scene_card_document(text)


def test_same_value_constrained_field_allowed() -> None:
    text = f"""---
lifecycle: shadow
---
{V2_BODY}"""
    doc = parse_scene_card_document(text)
    assert doc.frontmatter["lifecycle"] == doc.body["lifecycle"] == "shadow"


def test_dual_scene_card_schema_rejected() -> None:
    text = f"""{V2_BODY}
---
{V2_BODY}"""
    with pytest.raises(SceneCardParseError, match="two scene-card schema"):
        parse_scene_card_document(text)


def test_three_documents_rejected() -> None:
    text = f"""---
note: meta
---
{V2_BODY}
---
extra: mapping
"""
    with pytest.raises(SceneCardParseError, match="3 documents"):
        parse_scene_card_document(text)


def test_safe_load_with_duplicates_returns_list() -> None:
    result = safe_load_with_duplicates("a: 1\n---\nb: 2\n")
    assert result == [{"a": 1}, {"b": 2}]


def test_write_back_updates_declared_mirror_and_preserves_order(tmp_path: Path) -> None:
    card = tmp_path / "card.yaml"
    card.write_text(
        "---\ntitle: retained\nlifecycle: shadow\n---\nbody_only: kept\nschema: scene-card/v2\n"
        "scene_id: shared\nlifecycle: shadow\n",
        encoding="utf-8",
    )
    document = load_scene_card_document(card)
    sync_declared_mirrors(document, {"lifecycle": "assisted"})
    write_scene_card_document(card, document)

    reloaded = load_scene_card_document(card)
    assert reloaded.structure == "frontmatter+body"
    assert reloaded.canonical_index == 1
    assert reloaded.frontmatter == {"title": "retained", "lifecycle": "assisted"}
    assert reloaded.body["body_only"] == "kept"
    assert reloaded.body["lifecycle"] == "assisted"


def test_write_back_does_not_add_undeclared_mirror(tmp_path: Path) -> None:
    card = tmp_path / "card.yaml"
    card.write_text("---\ntitle: retained\n---\nscene_id: shared\nlifecycle: shadow\n", encoding="utf-8")
    document = load_scene_card_document(card)
    sync_declared_mirrors(document, {"lifecycle": "assisted"})
    write_scene_card_document(card, document)

    reloaded = load_scene_card_document(card)
    assert reloaded.frontmatter == {"title": "retained"}
    assert reloaded.body["lifecycle"] == "assisted"
