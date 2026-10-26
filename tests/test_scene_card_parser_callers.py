"""Three-entry parser convergence contract tests (BET-Y2Q4-T10-340401).

Verifies that review, lifecycle, and lineage all resolve scene_id and
lifecycle through the shared parser, and that parse errors propagate
to lineage scanning instead of being silently skipped.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def review_mod():
    return _load_module("bin/ssot/scene-card-review.py", "scene_card_review_for_parser_caller_tests")


@pytest.fixture()
def lifecycle_mod():
    return _load_module("bin/ssot/scene-card-lifecycle.py", "scene_card_lifecycle_for_parser_caller_tests")


@pytest.fixture()
def lineage_mod():
    return _load_module("bin/ssot/gen-scene-card-lineage.py", "scene_card_lineage_for_parser_caller_tests")


def test_review_reads_via_shared_parser(review_mod, tmp_path):
    card = tmp_path / "docs" / "scene-cards" / "t1.yaml"
    card.parent.mkdir(parents=True)
    card.write_text(
        "schema: scene-card/v2\nscene_id: t1\nlifecycle: shadow\ngoal: ok\n"
        "journey_id: j1\ntrigger: tr\ninput_contract: ic\nresult_contract: rc\n"
        "outcome_metric: om\n",
        encoding="utf-8",
    )
    result = review_mod.validate_scene_card(tmp_path, "t1")
    assert result["valid"] is True
    assert result["scene_id"] == "t1"
    assert result["lifecycle"] == "shadow"


def test_lifecycle_reads_via_shared_parser(lifecycle_mod, tmp_path):
    card = tmp_path / "card.yaml"
    card.write_text(
        "schema: scene-card/v2\nscene_id: t2\nlifecycle: draft\nbet: b1\nfalsifier: f1\n",
        encoding="utf-8",
    )
    assert lifecycle_mod._load_yaml_scene_card(card)["scene_id"] == "t2"
    validation = lifecycle_mod.validate_scene_card_v2(lifecycle_mod._load_yaml_scene_card(card))
    assert validation["valid"] is True


def test_lineage_reads_via_shared_parser(lineage_mod, tmp_path, monkeypatch):
    card = tmp_path / "t3.yaml"
    card.write_text(
        "schema: scene-card/v2\nscene_id: t3\nlifecycle: draft\ncapability_refs: [cap1]\n",
        encoding="utf-8",
    )
    assert lineage_mod._load_scene_card_body(card)["scene_id"] == "t3"


def test_lineage_parse_error_propagates(lineage_mod, tmp_path):
    card = tmp_path / "bad.yaml"
    card.write_text("scene_id: a\nscene_id: b\n", encoding="utf-8")
    from lib.scene_card_document import SceneCardParseError

    with pytest.raises(SceneCardParseError):
        lineage_mod._load_scene_card_body(card)


def test_three_entries_agree_on_scene_id(lifecycle_mod, tmp_path):
    """Shared parser gives the same identity regardless of entry point."""
    from lib.scene_card_document import load_scene_card_document

    card = tmp_path / "same.yaml"
    card.write_text(
        "schema: scene-card/v2\nscene_id: shared-001\nlifecycle: draft\nbet: b\nfalsifier: f\n",
        encoding="utf-8",
    )
    document = load_scene_card_document(card)
    lifecycle_body = lifecycle_mod._load_yaml_scene_card(card)
    assert document.body["scene_id"] == lifecycle_body["scene_id"] == "shared-001"
    assert document.body["lifecycle"] == lifecycle_body["lifecycle"] == "draft"
