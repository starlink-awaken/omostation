#!/usr/bin/env python3
"""test_integration_e2e.py — W1-D3 端到端集成测试.

验证 document-review → knowledge-ingest → human_review 全链路.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_BIN_GAC = Path(__file__).resolve().parent
sys.path.insert(0, str(_BIN_GAC))
sys.path.insert(0, str(_BIN_GAC.parents[1]))

router = importlib.import_module("signal_router")


def test_route_doc_review_signal(tmp_path, monkeypatch):
    """公文信号路由到 document-review."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "review-2026-08-19-001.md").write_text(
        "# 公文审查报告\n\n格式检查通过, 敏感项已标注"
    )
    routed = router.scan_and_route(inbox)
    assert len(routed) == 1
    assert routed[0]["source_scene"] == "document-review"
    assert routed[0]["signal_type"] == "doc"


def test_route_meeting_signal(tmp_path):
    """会议信号路由到 meeting-supervision."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "meeting-2026-08-19-001.md").write_text(
        "# 会议纪要\n\n决议: W1 启动执行闭环"
    )
    routed = router.scan_and_route(inbox)
    assert routed[0]["source_scene"] == "meeting-supervision"


def test_route_research_signal(tmp_path):
    """调研信号路由到 research-pipeline."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "research-2026-08-19-001.md").write_text(
        "# 调研报告\n\nQuery: knowledge_quality 算法"
    )
    routed = router.scan_and_route(inbox)
    assert routed[0]["source_scene"] == "research-pipeline"


def test_route_dedup(tmp_path):
    """重复信号不重复路由."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "note-001.md").write_text("test content 12345")
    first = router.scan_and_route(inbox)
    second = router.scan_and_route(inbox)
    assert len(first) == 1
    assert len(second) == 0  # 幂等


def test_route_mixed_signals(tmp_path):
    """混合信号按类型分流."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "review-x.md").write_text("公文审查")
    (inbox / "meeting-y.md").write_text("会议纪要")
    (inbox / "research-z.md").write_text("调研报告")
    (inbox / "insight-w.md").write_text("insight note")
    routed = router.scan_and_route(inbox)
    scenes = {r["source_scene"] for r in routed}
    assert "document-review" in scenes
    assert "meeting-supervision" in scenes
    assert "research-pipeline" in scenes
    assert "knowledge-ingest" in scenes


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))