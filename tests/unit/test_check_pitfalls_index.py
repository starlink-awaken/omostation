#!/usr/bin/env python3
"""check-pitfalls-index.py 的 hermetic 单测 (BET-Y2Q4-T10-346).

全部用 tmp_path 造 AGENTS.md / docs/pitfalls.md, 不读真实仓 —— 用例断言 host
运行态 = 结构性失明 (docs/pitfalls.md「用例断言 host 运行态」)。
"""

from __future__ import annotations

import datetime
import importlib.util
import pathlib

MOD_PATH = pathlib.Path(__file__).resolve().parents[2] / "bin" / "gac" / "check-pitfalls-index.py"


def _mod():
    spec = importlib.util.spec_from_file_location("check_pitfalls_index", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tree(tmp_path, agents_rows, body_entries, *, with_body=True):
    ws = tmp_path / "ws"
    (ws / "docs").mkdir(parents=True)
    agents = "# Head\n\n## 7. Common Pitfalls\n\n| 簇 | 条目 |\n|---|---|\n"
    agents += "".join(f"| {r} |\n" for r in agents_rows)
    agents += "\n## 8. Testing\n"
    (ws / "AGENTS.md").write_text(agents, encoding="utf-8")
    if with_body:
        (ws / "docs" / "pitfalls.md").write_text(
            "# Body\n\n" + "".join(f"- **{e}**：证据\n" for e in body_entries), encoding="utf-8"
        )
    return ws


def test_all_phrases_hit(tmp_path):
    m = _mod()
    ws = _tree(tmp_path, ["「甲形状」 · 「乙形状」"], ["甲形状（2026-01-01 实测）", "乙形状"])
    r = m.check(ws)
    assert r["error"] is None
    assert (r["total"], r["dead"], r["hittable"], r["body_entries"]) == (2, 0, 2, 2)
    assert r["ok"] is True
    assert m.should_block(r, datetime.date.today(), strict=False) is False


def test_paraphrase_counts_dead_and_escalates(tmp_path):
    m = _mod()
    ws = _tree(tmp_path, ["「改写后的说法」"], ["原判据的完整条首原文（2026-01-01 实测）"])
    r = m.check(ws)
    assert r["ok"] is False and r["dead"] == 1
    assert r["dead_list"][0]["phrase"] == "改写后的说法"
    assert r["dead_list"][0]["line"] > 0
    assert m.should_block(r, datetime.date(2026, 11, 11), strict=False) is False
    assert m.should_block(r, m.ENFORCE_AFTER, strict=False) is True
    assert m.should_block(r, datetime.date(2026, 11, 11), strict=True) is True


def test_literally_equal_but_whitespace_different_is_dead(tmp_path):
    m = _mod()
    ws = _tree(tmp_path, ["「判据 A · 判据 B」"], ["判据 A 判据 B"])
    r = m.check(ws)
    assert r["dead"] == 1


def test_missing_body_file_is_instrument_error_not_green(tmp_path):
    m = _mod()
    ws = _tree(tmp_path, ["「甲」"], ["甲"], with_body=False)
    r = m.check(ws)
    assert r["error"].startswith("missing_required_files:")
    assert r["ok"] is False and r["total"] == 0
    assert m.should_block(r, datetime.date(2026, 11, 11), strict=False) is True


def test_section_without_table_phrases_is_instrument_error(tmp_path):
    m = _mod()
    ws = _tree(tmp_path, ["散文里提到「甲」但不进表"], ["甲"])
    (ws / "AGENTS.md").write_text(
        "# Head\n\n## 7. Common Pitfalls\n\n只有散文「甲」，没有表行。\n\n## 8. Testing\n",
        encoding="utf-8",
    )
    r = m.check(ws)
    assert r["error"].startswith("index_section_not_found:")
    assert m.should_block(r, datetime.date(2026, 11, 11), strict=False) is True


def test_code_spans_and_fullwidth_brackets_are_matched_verbatim(tmp_path):
    m = _mod()
    phrase = "`git grep <rev>` 的输出行带 `rev:path` 前缀 —— 按路径前缀分类的复算会静默全 0"
    ws = _tree(tmp_path, [f"「{phrase}」"], [phrase + "（2026-11-09 实测）"])
    r = m.check(ws)
    assert (r["total"], r["dead"]) == (1, 0)
