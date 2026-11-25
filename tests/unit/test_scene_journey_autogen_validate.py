"""Unit tests for scene-journey-autogen template expansion & cycle checks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_autogen():
    spec = importlib.util.spec_from_file_location(
        "scene_journey_autogen_under_test",
        ROOT / "bin" / "ssot" / "scene-journey-autogen.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(spec.name, None)
    return mod


def test_validate_all_accepts_template_backed_specs(monkeypatch, tmp_path: Path) -> None:
    mod = _load_autogen()
    spec_file = tmp_path / "intake-review-deliver-sample.yaml"
    spec_file.write_text(
        "\n".join(
            [
                "schema: journey-spec/v1",
                "journey_id: intake-review-deliver-sample",
                "template: intake-review-deliver",
                "params:",
                "  entry_scene: unified-inbox",
                "  review_scene: document-review",
                "  deliver_scene: engineering-delivery",
                "  capture_scene: knowledge-curation",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "JOURNEYS_DIR", tmp_path)

    valid, invalid = mod.validate_all()
    assert (valid, invalid) == (1, 0)


def test_validate_all_fails_closed_on_missing_template(monkeypatch, tmp_path: Path) -> None:
    mod = _load_autogen()
    spec_file = tmp_path / "broken-template.yaml"
    spec_file.write_text(
        "schema: journey-spec/v1\njourney_id: broken\ntemplate: nonexistent-template-xyz\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "JOURNEYS_DIR", tmp_path)

    valid, invalid = mod.validate_all()
    assert (valid, invalid) == (0, 1)


def test_validate_all_rejects_cyclic_backedges(monkeypatch, tmp_path: Path) -> None:
    mod = _load_autogen()
    spec_file = tmp_path / "cyclic.yaml"
    spec_file.write_text(
        "\n".join(
            [
                "schema: journey-spec/v1",
                "journey_id: cyclic",
                "states:",
                "  - name: a",
                "    next: [b]",
                "  - name: b",
                "    next: [a]",
                "transitions:",
                "  - from: a",
                "    to: b",
                "  - from: b",
                "    to: a",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "JOURNEYS_DIR", tmp_path)

    valid, invalid = mod.validate_all()
    assert (valid, invalid) == (0, 1)
