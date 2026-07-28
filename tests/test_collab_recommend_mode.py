"""Tests for P84 collab mode recommender (ADR-0253/0255)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin" / "collab"))
from recommend_mode import recommend  # noqa: E402


def test_independent_batch() -> None:
    r = recommend(task_type="independent_batch")
    assert r["recommended_mode"] == "collab_parallel"


def test_simple_analysis() -> None:
    r = recommend(task_type="simple_analysis")
    assert r["recommended_mode"] == "single_agent"


def test_describe_heuristic() -> None:
    r = recommend(describe="修 6 个 INTERFACE as_of 批量无共享写")
    assert r["recommended_mode"] == "collab_parallel"


def test_conflict_conservative() -> None:
    r = recommend(describe="产物分歧 double claim 冲突")
    assert "single" in r["recommended_mode"] or "detect" in r["recommended_mode"]
