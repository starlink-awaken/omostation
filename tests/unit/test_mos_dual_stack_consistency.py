"""BET-Y1Q3-T3-01: MOS 双栈一致性观察器单元测试."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "bin" / "ssot" / "mos-dual-stack-consistency.py"
_spec = importlib.util.spec_from_file_location("mos_dual_stack_consistency", _SCRIPT)
mdc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mdc)


def test_jaccard_both_empty_is_consistent():
    assert mdc._jaccard([], []) == 1.0


def test_jaccard_identical_sets():
    assert mdc._jaccard(["a", "b", "c"], ["a", "b", "c"]) == 1.0


def test_jaccard_partial_overlap():
    sim = mdc._jaccard(["a", "b"], ["a", "c"])
    assert sim == pytest.approx(1 / 3)


def test_jaccard_disjoint():
    assert mdc._jaccard(["a"], ["b"]) == 0.0


def test_compare_one_structure(monkeypatch):
    def fake_mos(query):
        return {"ok": True, "count": 2, "ids": ["m1", "m2"], "backend": {}}

    def fake_kos(query):
        return {"ok": True, "count": 2, "ids": ["m1", "m2"]}

    monkeypatch.setattr(mdc, "_run_mos_recall", fake_mos)
    monkeypatch.setattr(mdc, "_run_kos_search", fake_kos)
    result = mdc._compare_one("q")
    assert result["query"] == "q"
    assert result["jaccard"] == 1.0
    assert result["consistent"] is True


def test_compare_one_divergence(monkeypatch):
    def fake_mos(query):
        return {"ok": True, "count": 1, "ids": ["m1"], "backend": {}}

    def fake_kos(query):
        return {"ok": True, "count": 1, "ids": ["k1"]}

    monkeypatch.setattr(mdc, "_run_mos_recall", fake_mos)
    monkeypatch.setattr(mdc, "_run_kos_search", fake_kos)
    result = mdc._compare_one("q")
    assert result["consistent"] is False
    assert result["jaccard"] == 0.0


def test_run_all_aggregates(monkeypatch):
    calls = {"n": 0}

    def fake_compare(query):
        calls["n"] += 1
        return {"query": query, "jaccard": 1.0, "consistent": True}

    monkeypatch.setattr(mdc, "_compare_one", fake_compare)
    report = mdc._run_all(["q1", "q2", "q3"])
    assert report["queries_count"] == 3
    assert report["consistent_count"] == 3
    assert report["consistency_ratio"] == 1.0
    assert report["week"] == mdc._week_tag()
    assert "schema" in report


def test_write_report_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr(mdc, "REPORT_DIR", tmp_path / "reports")
    path = mdc._write_report({"week": "2026-W32", "observed_at": "x", "results": []})
    assert path.exists()
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["week"] == "2026-W32"


def test_render_weekly_has_scroll_and_disclaimer():
    history = [
        {"week": "2026-W32", "consistency_ratio": 0.875, "consistent_count": 7, "queries_count": 8, "results": []},
    ]
    text = mdc._render_weekly(history)
    assert "8 周滚动" in text
    assert "永不记入价值指标" in text
    assert "2026-W32" in text
