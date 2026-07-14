"""Tests for generate-brief.py write_brief_if_changed (ADR-0128 Phase 2).

Coverage gap from ADR-0119 S2-1: bin/ tools only 9% tested.
This covers write_brief_if_changed + normalize_brief_content to prevent
BRIEF.md dirty-storm regression when default main() path is switched.
"""
import importlib.util
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "generate_brief", str(WORKSPACE / "bin" / "mof" / "generate-brief.py")
)
generate_brief = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_brief)


def test_write_brief_if_changed_skips_when_only_generated_stamp_differs(tmp_path, monkeypatch):
    """Generated 时间戳变化不算内容变化 (normalize 后), 不写."""
    target = tmp_path / "BRIEF.md"
    target.write_text("> **Generated**: 2026-01-01T00:00:00Z\n\nbody", encoding="utf-8")
    monkeypatch.setattr(generate_brief, "BRIEF_MD", target)
    mtime_before = target.stat().st_mtime_ns

    changed = generate_brief.write_brief_if_changed(
        "> **Generated**: 2026-99-99T99:99:99Z\n\nbody"
    )

    assert changed is False
    assert target.stat().st_mtime_ns == mtime_before


def test_write_brief_if_changed_writes_when_body_differs(tmp_path, monkeypatch):
    """正文变化时写入."""
    target = tmp_path / "BRIEF.md"
    target.write_text("old body", encoding="utf-8")
    monkeypatch.setattr(generate_brief, "BRIEF_MD", target)

    changed = generate_brief.write_brief_if_changed("new body")

    assert changed is True
    assert target.read_text(encoding="utf-8") == "new body"


def test_write_brief_if_changed_writes_when_target_missing(tmp_path, monkeypatch):
    """目标不存在时写入."""
    target = tmp_path / "BRIEF.md"
    monkeypatch.setattr(generate_brief, "BRIEF_MD", target)

    changed = generate_brief.write_brief_if_changed("fresh content")

    assert changed is True
    assert target.read_text(encoding="utf-8") == "fresh content"


def test_normalize_brief_content_masks_generated_stamp():
    """normalize 把 Generated 行统一成 <runtime>, 消除时间戳噪音."""
    raw = "> **Generated**: 2026-07-05T01:00:00Z\nbody"
    other = "> **Generated**: 2099-12-31T23:59:59Z\nbody"

    assert generate_brief.normalize_brief_content(raw) == generate_brief.normalize_brief_content(other)
    assert "<runtime>" in generate_brief.normalize_brief_content(raw)
