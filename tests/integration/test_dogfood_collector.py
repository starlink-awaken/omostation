#!/usr/bin/env python3
"""dogfood-collector 测试 — BET-Y1Q2-T7-01 采集器语义固化."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bin" / "ssot"))

import importlib.util  # noqa: E402

import pytest  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "dogfood_collector", Path(__file__).resolve().parents[2] / "bin" / "ssot" / "dogfood-collector.py"
)
dc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dc)


def test_parse_since_units():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    assert (now - dc._parse_since("7d")).days >= 6
    assert (now - dc._parse_since("1w")).days >= 6
    assert (now - dc._parse_since("24h")).total_seconds() >= 23 * 3600


def test_collect_merged_prs_requires_gh(monkeypatch):
    """gh 失败 (空输出) → 空列表不炸 (shadow 语义: 采集失败不反噬)."""
    monkeypatch.setattr(dc, "_run", lambda cmd: "")
    assert dc.collect_merged_prs("7d") == []


def test_outcome_schema(tmp_path, monkeypatch):
    """写入的每条 outcome 满足 decision_outcome/v1 契约关键字段."""
    store = tmp_path / "store.jsonl"
    monkeypatch.setattr(dc, "STORE", store)
    monkeypatch.setattr(dc, "collect_merged_prs", lambda s: [
        {"number": 1, "title": "t", "mergedAt": "2026-08-16T00:00:00Z",
         "additions": 10, "deletions": 2, "files": []},
    ])
    dc.collect("7d", min_weekly=1)
    line = json.loads(store.read_text().splitlines()[0])
    assert line["schema"] == "decision_outcome/v1"
    assert line["namespace"] == "agent_belief"
    assert line["scene_id"] == "engineering-delivery-dogfood"
    assert line["payload"]["human_verdict"] == "accepted"
    assert line["payload"]["verdict_source"] == "merge_event"
    assert "永不计入 X3" in line["notes"]  # non_goal 标注强制


def test_idempotent_by_pr_number(tmp_path, monkeypatch):
    """同 PR 复采不重复写 (幂等)."""
    store = tmp_path / "store.jsonl"
    monkeypatch.setattr(dc, "STORE", store)
    prs = [{"number": 42, "title": "x", "mergedAt": "2026-08-16T00:00:00Z",
            "additions": 1, "deletions": 1, "files": []}]
    monkeypatch.setattr(dc, "collect_merged_prs", lambda s: prs)
    dc.collect("7d", min_weekly=1)
    dc.collect("7d", min_weekly=1)  # 第二轮同 PR
    n = len(store.read_text().splitlines())
    assert n == 1, f"expected 1 line after idempotent re-collect, got {n}"


def test_weekly_gate_threshold(tmp_path, monkeypatch, capsys):
    """gate 语义: 窗口 PR 数 < min → exit 1 (FAIL), >= min → exit 0 (PASS)."""
    store = tmp_path / "store.jsonl"
    monkeypatch.setattr(dc, "STORE", store)
    monkeypatch.setattr(dc, "collect_merged_prs", lambda s: [
        {"number": i, "title": "x", "mergedAt": "2026-08-16T00:00:00Z",
         "additions": 1, "deletions": 1, "files": []} for i in range(3)
    ])
    assert dc.collect("7d", min_weekly=20) == 1   # 3 < 20 FAIL
    assert dc.collect("7d", min_weekly=2) == 0    # 3 >= 2 PASS


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
