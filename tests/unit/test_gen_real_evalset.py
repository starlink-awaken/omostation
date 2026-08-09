"""BET-Y1Q4-T4-01: 真实评测集 v1 生成器单元测试."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "bin" / "ssot" / "gen-real-evalset.py"
_spec = importlib.util.spec_from_file_location("gen_real_evalset", _SCRIPT)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def test_classify_positive():
    assert gen._classify("accepted", 10, 5) == "positive"


def test_classify_negative():
    assert gen._classify("rejected", 100, 50) == "negative"


def test_classify_boundary_small_rejected():
    # 小改动被拒 = 决策边界
    assert gen._classify("rejected", 10, 5) == "boundary"


def test_classify_boundary_large_accepted():
    # 大改动通过 = 决策边界
    assert gen._classify("accepted", 400, 0) == "boundary"


def test_read_jsonl_skips_invalid(tmp_path):
    p = tmp_path / "d.jsonl"
    p.write_text('{"a": 1}\nnot-json\n{"b": 2}\n', encoding="utf-8")
    recs = gen._read_jsonl(p)
    assert len(recs) == 2


def test_evalset_has_three_classes(monkeypatch):
    # 用假数据构造, 确保三类齐全
    monkeypatch.setattr(gen, "PR_HARVEST", Path("/nonexistent/pr.jsonl"))
    monkeypatch.setattr(gen, "ADJUDICATIONS", Path("/nonexistent/adj.jsonl"))
    monkeypatch.setattr(gen, "_fetch_closed_unmerged", lambda repo: [
        {"number": 1, "title": "closed", "state": "closed", "closed_at": "x", "user": {"login": "a"}}
    ])
    monkeypatch.setattr(gen, "_fetch_merged", lambda repo, max_pages: [
        {"number": 100, "title": "m1", "merged_at": "x", "user": {"login": "a"}, "additions": 10, "deletions": 2},
        {"number": 101, "title": "m2", "merged_at": "x", "user": {"login": "a"}, "additions": 400, "deletions": 0},
    ])
    evalset = gen._build_evalset()
    classes = set(evalset["distribution"])
    assert {"positive", "negative", "boundary"} <= classes
    assert evalset["count"] >= 3
    # 非合成标注
    assert all(not i["synthetic"] for i in evalset["items"])
