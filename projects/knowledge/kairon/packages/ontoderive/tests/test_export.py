"""Tests for export — 导出模块"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import pytest
from ontoderive.core.export import to_html, to_json, to_markdown


@pytest.fixture
def sample_summary():
    return {
        "facts": 5,
        "entities": 3,
        "inferences": 2,
        "derived_conclusions": [
            {
                "source": "rule_engine",
                "derivation_trail": "R1: D-F1→D-F2",
                "conclusion": "测试结论A大于测试结论B",
                "confidence": 0.95,
            },
        ],
        "derivation_hints": ["测试提示1"],
        "confidence_distribution": {"mean": 0.85, "min": 0.7, "max": 0.95},
    }


def test_to_html(sample_summary):
    html = to_html(sample_summary, "test-project")
    assert "<!DOCTYPE html>" in html
    assert "test-project" in html
    assert "测试结论A" in html
    assert "95%" in html


def test_to_json(sample_summary):
    import json

    js = to_json(sample_summary)
    parsed = json.loads(js)
    assert parsed["facts"] == 5
    assert parsed["entities"] == 3


def test_to_markdown(sample_summary):
    md = to_markdown(sample_summary, "test")
    assert "OntoDerive" in md
    assert "测试结论A" in md
    assert "95%" in md
