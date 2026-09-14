"""End-to-end pipeline test using presets."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_pipeline_presets_loaded():
    from eidos.pipeline.presets import PRESETS

    assert len(PRESETS) >= 2
    assert "knowledge-base" in PRESETS
    assert "reasoning" in PRESETS


def test_knowledge_base_steps():
    from eidos.pipeline.presets import KNOWLEDGE_BASE

    assert len(KNOWLEDGE_BASE.steps) >= 2
    assert KNOWLEDGE_BASE.steps[0].tool == "eidos"
