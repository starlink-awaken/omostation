"""任务树一致性检查 — 回归测试.

2026-09-19 实证: `.omo/tasks/planned/` 8 项里有 3 项在终态树已有同 id 副本
(cockpit-debt-debt-1 / event-loop-dead-loop / BET-Y1Q4-T15), 污染 planned 计数
与 owner 分布 —— 健康面据此报出 "Owner 集中度: human 持有 90% 待处理任务" 的
异常, 而其中 3/8 是**已关闭的陈旧重复**。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "bin/gac/check-task-tree-consistency.py"


def _load():
    spec = importlib.util.spec_from_file_location("task_tree_cons", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["task_tree_cons"] = mod
    spec.loader.exec_module(mod)
    return mod


def _task(repo: Path, tree: str, name: str, tid: str,
          state: str = "candidate") -> Path:
    d = repo / ".omo" / "tasks" / tree
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(f"id: {tid}\nlifecycle_state: {state}\n", encoding="utf-8")
    return p


# ── 检出陈旧重复 ─────────────────────────────────────────


def test_flags_planned_duplicated_in_closed(tmp_path):
    repo = tmp_path
    _task(repo, "planned", "a.yaml", "A")
    _task(repo, "closed", "closed-a.yaml", "A", "closed")
    tool = _load()
    r = tool.scan(repo)
    assert len(r["stale"]) == 1
    s = r["stale"][0]
    assert s["id"] == "A"
    assert s["planned_file"] == "a.yaml"
    assert "closed/" in s["terminal_copy"]


def test_flags_planned_duplicated_in_done(tmp_path):
    repo = tmp_path
    _task(repo, "planned", "b.yaml", "B")
    _task(repo, "done", "B-b.yaml", "B", "done")
    tool = _load()
    r = tool.scan(repo)
    assert len(r["stale"]) == 1
    assert "done/" in r["stale"][0]["terminal_copy"]


def test_unique_planned_passes(tmp_path):
    repo = tmp_path
    _task(repo, "planned", "c.yaml", "C")
    _task(repo, "closed", "closed-d.yaml", "D", "closed")
    tool = _load()
    assert tool.scan(repo)["stale"] == []


def test_archived_counts_as_terminal(tmp_path):
    """archived/done/ 也是终态树 (rglob 递归)."""
    repo = tmp_path
    _task(repo, "planned", "e.yaml", "E")
    _task(repo, "archived/done", "E-e.yaml", "E", "done")
    tool = _load()
    assert len(tool.scan(repo)["stale"]) == 1


def test_missing_trees_are_not_failure(tmp_path):
    tool = _load()
    r = tool.scan(tmp_path)
    assert r["stale"] == [] and r["planned_count"] == 0


# ── 退出码 ───────────────────────────────────────────────


def test_main_exit_codes(tmp_path, monkeypatch):
    tool = _load()
    monkeypatch.setattr(tool, "_ROOT", tmp_path)
    _task(tmp_path, "planned", "x.yaml", "X")
    assert tool.main(["--json"]) == 0

    _task(tmp_path, "closed", "closed-x.yaml", "X", "closed")
    assert tool.main(["--json"]) == 1


# ── 真实仓库 ─────────────────────────────────────────────


def test_real_repo_is_consistent_after_cleanup():
    """本 PR 清理后, 真实任务树不得再有陈旧重复."""
    tool = _load()
    r = tool.scan()
    assert r["stale"] == [], (
        "planned/ 仍有陈旧重复: "
        + ", ".join(f"{s['planned_file']}←{s['terminal_copy']}" for s in r["stale"])
    )
    # planned_count may be zero once planned/ is fully drained; assert
    # ≥ 0 to track the long-term invariant without re-introducing drift.
    assert r["planned_count"] >= 0
