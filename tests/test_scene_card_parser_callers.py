"""Caller-level regression tests for the shared scene-card parser.

The lifecycle entry point owns dedicated aggregate-gate coverage.  These tests
pin the three remaining integration surfaces: review promotion, lifecycle
transitions, and lineage generation.  All fixtures are synthetic and confined
to temporary directories.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

import lib.scene_card_document as parser_module


ROOT = Path(__file__).resolve().parents[1]


def _load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


review = _load_script(ROOT / "bin/ssot/scene-card-review.py", "scene_card_review_for_parser_tests")
lifecycle = _load_script(ROOT / "bin/ssot/scene-card-lifecycle.py", "scene_card_lifecycle_for_parser_tests")
lineage = _load_script(ROOT / "bin/ssot/gen-scene-card-lineage.py", "scene_card_lineage_for_parser_tests")


def _write_two_document_card(path: Path) -> None:
    frontmatter = "title: Synthetic Card\nlifecycle: draft\n"
    body = (
        "scene_id: caller-scene\n"
        "journey_id: caller-journey\n"
        "goal: test goal\n"
        "trigger: test trigger\n"
        "input_contract: test input\n"
        "result_contract: test result\n"
        "outcome_metric: test_metric\n"
        "owner: test-owner\n"
        "failure_cost: test failure\n"
        "data_classification: internal\n"
        "rollback_plan: test rollback\n"
        "lifecycle: draft\n"
        "review_metadata:\n  priority: high\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")


def test_review_promotes_and_syncs_declared_mirror(tmp_path: Path) -> None:
    card = tmp_path / "docs/scene-cards/caller-scene.yaml"
    _write_two_document_card(card)

    result = review.promote_scene_card(tmp_path, "caller-scene", "assisted")

    assert result == {"success": True, "scene_id": "caller-scene", "lifecycle": "assisted"}
    reloaded = parser_module.load_scene_card_document(card)
    assert reloaded.structure == "frontmatter+body"
    assert reloaded.frontmatter is not None
    assert reloaded.body["lifecycle"] == "assisted"
    assert reloaded.frontmatter["lifecycle"] == "assisted"
    assert reloaded.body["review_metadata"] == {"priority": "high"}


def test_lifecycle_transitions_and_preserves_document_order(tmp_path: Path) -> None:
    card = tmp_path / "caller-card.yaml"
    _write_two_document_card(card)

    result = lifecycle.transition_scene_card(card, "shadow", "test-actor", root=tmp_path)

    assert result == {"ok": True, "scene_id": "caller-scene", "from": "draft", "to": "shadow"}
    reloaded = parser_module.load_scene_card_document(card)
    assert reloaded.structure == "frontmatter+body"
    assert reloaded.body["lifecycle"] == "shadow"
    assert reloaded.frontmatter is not None
    assert reloaded.frontmatter["lifecycle"] == "shadow"
    assert reloaded.frontmatter["title"] == "Synthetic Card"
    assert reloaded.body["review_metadata"] == {"priority": "high"}


def test_lineage_reads_shared_body_and_rejects_ambiguous_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    valid_card = tmp_path / "valid-card.yaml"
    _write_two_document_card(valid_card)
    monkeypatch.setattr(lineage, "WORKSPACE", tmp_path)
    monkeypatch.setattr(lineage, "SCENE_CARDS_DIR", tmp_path)

    assert lineage.scan_scene_cards() == [
        {
            "scene_id": "caller-scene",
            "journey_id": "caller-journey",
            "lifecycle": "draft",
            "approval_state": "unknown",
            "outcome_metric": "test_metric",
            "capability_refs": [],
            "source": "valid-card.yaml",
        }
    ]

    ambiguous_card = tmp_path / "ambiguous-card.yaml"
    ambiguous_card.write_text("---\ntitle: one\n---\nscene_id: one\n---\nscene_id: two\n")
    with pytest.raises(parser_module.SceneCardParseError, match="expected 1 or 2 documents"):
        lineage.scan_scene_cards()
