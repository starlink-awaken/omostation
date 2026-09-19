"""任务所有权强制 — 回归测试.

2026-09-19 实证: 债务项 UNASSIGNED_ENTROPY 声称"任务所有权已由 bet-ledger +
task schema 强制 (owner/phase 必填字段校验)" —— 而该强制**不存在** (唯一相关实现
bin/_archive/bet-to-task.py 已归档; 证据引用悬空的 P43-ARCH-ANALYSIS-002)。

实测反而更精确: 非终态 omo-schema 任务 (active/planned/blocked) **100% 有 owner**;
缺 owner 的全是终态历史记录, 或 remediation/ (另一套 schema, 用 assigned_to);
`phase` 也不是 omo 任务 schema 的字段 (active 0/1, closed 0/15, done 0/11 使用)。

本工具把"声称存在的强制"真正落地, 范围按实测收敛 —— 只要求非终态任务有 owner,
不虚设 phase 要求。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "bin/gac/check-task-ownership.py"


def _load():
    spec = importlib.util.spec_from_file_location("task_ownership", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["task_ownership"] = mod
    spec.loader.exec_module(mod)
    return mod


def _task(root: Path, tree: str, name: str, **fields) -> Path:
    d = root / ".omo" / "tasks" / tree
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    body = "\n".join(f"{k}: {v}" for k, v in fields.items()) + "\n"
    p.write_text(body, encoding="utf-8")
    return p


# ── 检出 ─────────────────────────────────────────────────


def test_flags_unowned_active_task(tmp_path):
    _task(tmp_path, "active", "a.yaml", id="A", lifecycle_state="active")
    tool = _load()
    r = tool.scan(tmp_path)
    assert len(r["unowned"]) == 1
    assert r["unowned"][0]["id"] == "A"
    assert r["unowned"][0]["tree"] == "active"


def test_flags_unowned_planned_task(tmp_path):
    _task(tmp_path, "planned", "b.yaml", id="B", status="candidate")
    assert len(_load().scan(tmp_path)["unowned"]) == 1


def test_owned_task_passes(tmp_path):
    _task(tmp_path, "active", "c.yaml", id="C", owner="governance-team")
    assert _load().scan(tmp_path)["unowned"] == []


def test_blank_owner_is_treated_as_missing(tmp_path):
    _task(tmp_path, "active", "d.yaml", id="D", owner='""')
    assert len(_load().scan(tmp_path)["unowned"]) == 1, '空串 owner 不算有主'


# ── 范围收敛 (不虚设要求) ────────────────────────────────


def test_terminal_trees_are_out_of_scope(tmp_path):
    """closed/done 是历史终态, 所有权不再可行动 → 不在本检查范围."""
    _task(tmp_path, "closed", "e.yaml", id="E", lifecycle_state="closed")
    _task(tmp_path, "done", "f.yaml", id="F", lifecycle_state="done")
    r = _load().scan(tmp_path)
    assert r["unowned"] == []
    assert r["scanned"] == 0


def test_remediation_tree_is_out_of_scope(tmp_path):
    """remediation/ 用另一套 schema (status/assigned_to), 不适用 owner 要求."""
    _task(tmp_path, "remediation", "g.yaml", id="G", status="review")
    assert _load().scan(tmp_path)["unowned"] == []


def test_phase_is_not_required(tmp_path):
    """phase 非 omo 任务 schema 字段 (实测 active/closed/done 均不用) → 不要求."""
    _task(tmp_path, "active", "h.yaml", id="H", owner="agent")  # 无 phase
    assert _load().scan(tmp_path)["unowned"] == []


# ── 退出码与边界 ─────────────────────────────────────────


def test_main_exit_codes(tmp_path, monkeypatch):
    tool = _load()
    monkeypatch.setattr(tool, "_ROOT", tmp_path)
    _task(tmp_path, "active", "ok.yaml", id="OK", owner="agent")
    assert tool.main(["--json"]) == 0
    _task(tmp_path, "active", "bad.yaml", id="BAD")
    assert tool.main(["--json"]) == 1


def test_missing_trees_are_not_failure(tmp_path):
    r = _load().scan(tmp_path)
    assert r["unowned"] == [] and r["scanned"] == 0


def test_files_without_id_are_skipped(tmp_path):
    _task(tmp_path, "active", "noise.yaml", status="weird")
    assert _load().scan(tmp_path)["scanned"] == 0


# ── 真实仓库 ─────────────────────────────────────────────


def test_real_repo_non_terminal_tasks_all_owned():
    """本仓非终态任务必须全部有 owner (即债务项声称的强制现已落地)."""
    tool = _load()
    r = tool.scan()
    assert r["unowned"] == [], (
        "非终态任务缺 owner: "
        + ", ".join(f"{u['tree']}/{u['id']}" for u in r["unowned"])
    )
    assert r["scanned"] > 0, "应扫到至少一个非终态任务"
