"""Tests for lib/scene_card_document.py — shared scene card parser contract."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lib.scene_card_document import (
    SceneCardParseError,
    load_scene_card_document,
    parse_scene_card_document,
    sync_declared_mirrors,
    write_scene_card_document,
)


SINGLE_YAML = "scene_id: test-scene\nlifecycle: shadow\njourney_id: j-1\n"

TWO_DOC_YAML = (
    "---\n"
    "scene_id: test-scene\n"
    "lifecycle: shadow\n"
    "tags:\n"
    "  priority: high\n"
    "---\n"
    "scene_id: test-scene\n"
    "lifecycle: shadow\n"
    "tags:\n"
    "  priority: high\n"
    "body_field: hello\n"
)


class TestYamlCompatibility:
    def test_single_mapping(self):
        doc = parse_scene_card_document(SINGLE_YAML)
        assert doc.structure == "single"
        assert doc.canonical_index == 0
        assert doc.body == {"scene_id": "test-scene", "lifecycle": "shadow", "journey_id": "j-1"}
        assert doc.frontmatter is None

    def test_frontmatter_plus_body(self):
        doc = parse_scene_card_document(TWO_DOC_YAML)
        assert doc.structure == "frontmatter+body"
        assert doc.canonical_index == 1
        assert doc.frontmatter is not None
        assert doc.body["body_field"] == "hello"

    def test_unindented_sequence(self):
        text = "---\nitems:\n- a\n- b\n---\nitems:\n- a\n- b\nscene_id: s\n"
        doc = parse_scene_card_document(text)
        assert doc.body["items"] == ["a", "b"]

    def test_uri_scalar(self):
        text = "---\nurl: https://example.com\n---\nurl: https://example.com\nscene_id: s\n"
        doc = parse_scene_card_document(text)
        assert doc.body["url"] == "https://example.com"

    def test_block_scalar_and_multiline(self):
        text = "---\ndesc: |\n  multi\n  line\n---\ndesc: |\n  multi\n  line\nscene_id: s\n"
        doc = parse_scene_card_document(text)
        assert doc.body["desc"] == "multi\nline\n"

    def test_json_mapping(self):
        text = '{"scene_id": "s", "lifecycle": "shadow"}'
        doc = parse_scene_card_document(text)
        assert doc.structure == "single"
        assert doc.body == {"scene_id": "s", "lifecycle": "shadow"}

    def test_nested_mapping(self):
        text = "---\na:\n  b:\n    c: 1\n---\na:\n  b:\n    c: 1\nscene_id: s\n"
        doc = parse_scene_card_document(text)
        assert doc.body["a"]["b"]["c"] == 1


class TestRejection:
    def test_empty_document(self):
        with pytest.raises(SceneCardParseError, match="empty document"):
            parse_scene_card_document("")

    def test_all_null_documents(self):
        with pytest.raises(SceneCardParseError, match="all documents empty"):
            parse_scene_card_document("---\nnull\n---\nnull\n")

    def test_non_mapping(self):
        with pytest.raises(SceneCardParseError, match="not a mapping"):
            parse_scene_card_document("- 1\n- 2\n")

    def test_duplicate_key_top_level(self):
        with pytest.raises(SceneCardParseError, match="duplicate key"):
            parse_scene_card_document("scene_id: a\nscene_id: b\n")

    def test_duplicate_key_nested(self):
        with pytest.raises(SceneCardParseError, match="duplicate key.*a\\.k"):
            parse_scene_card_document("a:\n  k: 1\n  k: 2\n")

    def test_state_field_conflict_scene_id(self):
        text = "---\nscene_id: a\n---\nscene_id: b\n"
        with pytest.raises(SceneCardParseError, match="scene_id"):
            parse_scene_card_document(text)

    def test_state_field_conflict_lifecycle(self):
        text = "---\nlifecycle: shadow\n---\nlifecycle: routine\nscene_id: s\n"
        with pytest.raises(SceneCardParseError, match="lifecycle"):
            parse_scene_card_document(text)

    def test_semantic_dict_conflict(self):
        text = "---\ntags:\n  a: 1\n---\ntags:\n  b: 2\nscene_id: s\n"
        with pytest.raises(SceneCardParseError, match="tags"):
            parse_scene_card_document(text)

    def test_semantic_dict_equal_allowed(self):
        text = "---\ntags:\n  a: 1\n---\ntags:\n  a: 1\nscene_id: s\n"
        doc = parse_scene_card_document(text)
        assert doc.body["tags"] == {"a": 1}

    def test_dual_schema_detected_via_conflict(self):
        text = "---\nscene_id: a\n---\nscene_id: b\n"
        with pytest.raises(SceneCardParseError, match="scene_id"):
            parse_scene_card_document(text)

    def test_three_documents(self):
        with pytest.raises(SceneCardParseError, match="expected 1 or 2"):
            parse_scene_card_document("---\na: 1\n---\nb: 2\n---\nc: 3\n")


class TestThreeCallerConsistency:
    def test_same_scene_id_lifecycle(self):
        doc = parse_scene_card_document(TWO_DOC_YAML)
        assert doc.body["scene_id"] == "test-scene"
        assert doc.body["lifecycle"] == "shadow"

    def test_error_propagates_with_source(self):
        with pytest.raises(SceneCardParseError, match="my-card.yaml"):
            parse_scene_card_document("scene_id: a\nscene_id: b\n", source="my-card.yaml")

    def test_load_missing_file(self, tmp_path: Path):
        with pytest.raises(SceneCardParseError, match="not found"):
            load_scene_card_document(tmp_path / "missing.yaml")

    def test_load_file_roundtrip(self, tmp_path: Path):
        card = tmp_path / "card.yaml"
        card.write_text(TWO_DOC_YAML, encoding="utf-8")
        doc = load_scene_card_document(card)
        assert doc.body["scene_id"] == "test-scene"
        assert doc.source == card


class TestWriteBack:
    def test_shadow_to_assisted_roundtrip(self, tmp_path: Path):
        card = tmp_path / "card.yaml"
        card.write_text(TWO_DOC_YAML, encoding="utf-8")
        document = load_scene_card_document(card)

        sync_declared_mirrors(document, {"lifecycle": "assisted"})
        write_scene_card_document(card, document)

        reloaded = load_scene_card_document(card)
        assert reloaded.structure == "frontmatter+body"
        assert reloaded.body["lifecycle"] == "assisted"
        assert reloaded.frontmatter is not None
        assert reloaded.frontmatter["lifecycle"] == "assisted"
        assert reloaded.frontmatter["scene_id"] == "test-scene"
        assert reloaded.body["body_field"] == "hello"

    def test_no_mirror_added_when_not_declared(self, tmp_path: Path):
        card = tmp_path / "card.yaml"
        card.write_text(SINGLE_YAML, encoding="utf-8")
        document = load_scene_card_document(card)

        sync_declared_mirrors(document, {"lifecycle": "assisted"})
        write_scene_card_document(card, document)

        reloaded = load_scene_card_document(card)
        assert reloaded.structure == "single"
        assert reloaded.body["lifecycle"] == "assisted"
        assert reloaded.frontmatter is None

    def test_unrelated_metadata_preserved(self, tmp_path: Path):
        card = tmp_path / "card.yaml"
        card.write_text(TWO_DOC_YAML, encoding="utf-8")
        document = load_scene_card_document(card)

        sync_declared_mirrors(document, {"lifecycle": "assisted"})
        write_scene_card_document(card, document)

        reloaded = load_scene_card_document(card)
        assert reloaded.frontmatter is not None
        assert reloaded.frontmatter["tags"] == {"priority": "high"}
        assert reloaded.body["tags"] == {"priority": "high"}
        assert reloaded.body["body_field"] == "hello"

    def test_document_order_preserved(self, tmp_path: Path):
        card = tmp_path / "card.yaml"
        card.write_text(TWO_DOC_YAML, encoding="utf-8")
        document = load_scene_card_document(card)
        write_scene_card_document(card, document)

        raw = card.read_text(encoding="utf-8")
        parts = raw.split("---\n")
        docs = [yaml.safe_load(p) for p in parts if p.strip()]
        assert len(docs) == 2

    def test_parser_is_pure(self, tmp_path: Path):
        card = tmp_path / "card.yaml"
        card.write_text(TWO_DOC_YAML, encoding="utf-8")
        before = card.read_text(encoding="utf-8")

        doc = load_scene_card_document(card)
        assert doc.source_sha256 is not None

        after = card.read_text(encoding="utf-8")
        assert before == after
