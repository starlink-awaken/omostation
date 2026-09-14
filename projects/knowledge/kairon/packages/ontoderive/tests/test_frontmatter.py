from pathlib import Path

"""Tests for frontmatter detection — extracted from SharedBrain D_Logos."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import datetime
import tempfile

from ontoderive.frontmatter import DetectionResult, FrontmatterBlock, FrontmatterDetector


def make_md(content: str) -> Path:
    p = Path(tempfile.mkstemp(suffix=".md")[1])
    p.write_text(content)
    return p


def test_single_valid_frontmatter():
    detector = FrontmatterDetector()
    blocks = detector.detect("---\ntitle: Test\ndate: 2026-01-01\n---\n\n# Content")
    assert len(blocks) == 1
    assert blocks[0].is_valid
    assert blocks[0].parsed_data["title"] == "Test"  # type: ignore[reportOptionalSubscript]
    # YAML parses dates as datetime.date objects
    assert blocks[0].parsed_data["date"] == datetime.date(2026, 1, 1)  # type: ignore[reportOptionalSubscript]


def test_no_frontmatter():
    blocks = FrontmatterDetector().detect("# Just a heading\n\nAnd some content.")
    assert len(blocks) == 0


def test_multiple_frontmatter():
    blocks = FrontmatterDetector().detect("---\na: 1\n---\n\nMiddle\n\n---\nb: 2\n---\n")
    assert len(blocks) == 2


def test_analyze_missing():
    p = make_md("# No frontmatter here")
    result = FrontmatterDetector().analyze(p)
    assert result.status == "MISSING"
    assert result.recommendation == "ADD_FRONTMATTER"


def test_analyze_ok():
    p = make_md("---\ntitle: Hello\n---\n\nContent here")
    result = FrontmatterDetector().analyze(p)
    assert result.status == "OK"


def test_analyze_invalid():
    p = make_md("---\nkey: value: bad\n---\n\nContent")
    result = FrontmatterDetector().analyze(p)
    assert result.status == "INVALID"


def test_block_to_dict():
    b = FrontmatterBlock(1, 3, 0, 20, "title: Test", True, {"title": "Test"})
    d = b.to_dict()
    assert d["fields"] == ["title"]
    assert d["is_valid"]


def test_detection_result_to_dict():
    r = DetectionResult(file_path=Path("test.md"), recommendation="OK")
    d = r.to_dict()
    assert d["status"] == "MISSING"
    assert d["file_path"] == "test.md"
