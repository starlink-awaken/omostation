"""Auto-crystallized test for skill sema-terminology-replace (SEMA, BET-Y2Q2-T6-01)."""

import re

from sema_terminology_replace import run  # skill entry contract


def test_pattern_is_detected():
    violating = "含 高度重视 的草稿"
    assert run(violating)["violation_found"] is True


def test_clean_draft_passes():
    assert run("无该模式的干净草稿")["violation_found"] is False
