"""Hermetic regression tests for compass_radar concurrent-conflict counting.

BET-Y2Q4-T9-01: the signal decomposes into run_pressure (distinct active runs
in the MAIN checkout runs dir) + wt_pressure (git worktree count − 2 free
allowance). The N1 fix (count run records by status, not lock files) and the
free-allowance arithmetic are contract here — no host runtime state, no real git.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_WS = Path(__file__).resolve().parents[1]


def _load_module():
    spec = importlib.util.spec_from_file_location("compass_radar_under_test", _WS / "bin" / "compass_radar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_run(runs_dir: Path, name: str, status: str, run_id: str | None = None) -> None:
    body = f"run_id: {run_id or name}\nstatus: {status}\n"
    (runs_dir / f"{name}.yaml").write_text(body, encoding="utf-8")


def _mock_worktrees(count: int):
    """Return a subprocess.run stub emitting a porcelain list with `count` worktrees."""

    def fake_run(*args, **kwargs):
        out = "".join(f"worktree /tmp/wt{i}\n" for i in range(count))
        return subprocess.CompletedProcess(args, 0, stdout=out, stderr="")

    return fake_run


@pytest.fixture()
def radar(tmp_path: Path, monkeypatch):
    mod = _load_module()
    runs_dir = tmp_path / ".omo" / "_delivery" / "agent-workflows" / "runs"
    runs_dir.mkdir(parents=True)
    return mod, tmp_path


def test_run_pressure_counts_distinct_active_only(radar, monkeypatch):
    mod, ws = radar
    runs_dir = ws / ".omo" / "_delivery" / "agent-workflows" / "runs"
    _make_run(runs_dir, "r1", "active")
    _make_run(runs_dir, "r1-dup", "active", run_id="r1")  # 同 id 去重
    _make_run(runs_dir, "r2", "active")
    _make_run(runs_dir, "r3", "closed")  # 非 active 不计
    _make_run(runs_dir, "r4", "blocked")
    monkeypatch.setattr(mod.subprocess, "run", _mock_worktrees(2))  # 无 wt 压力
    assert mod._count_concurrent_conflict_signals(ws) == 1  # 2 distinct active − 1


def test_single_active_run_is_free(radar, monkeypatch):
    mod, ws = radar
    runs_dir = ws / ".omo" / "_delivery" / "agent-workflows" / "runs"
    _make_run(runs_dir, "only", "active")
    monkeypatch.setattr(mod.subprocess, "run", _mock_worktrees(2))
    assert mod._count_concurrent_conflict_signals(ws) == 0


def test_broken_yaml_is_skipped_not_counted(radar, monkeypatch):
    mod, ws = radar
    runs_dir = ws / ".omo" / "_delivery" / "agent-workflows" / "runs"
    (runs_dir / "broken.yaml").write_text("{ not: valid: yaml: [", encoding="utf-8")
    monkeypatch.setattr(mod.subprocess, "run", _mock_worktrees(2))
    assert mod._count_concurrent_conflict_signals(ws) == 0


def test_wt_pressure_free_allowance_is_two(radar, monkeypatch):
    mod, ws = radar
    runs_dir = ws / ".omo" / "_delivery" / "agent-workflows" / "runs"
    for i in range(3):  # 3 个 active run 也会被 wt 分量独立相加
        _make_run(runs_dir, f"act{i}", "active", run_id=f"act{i}")
    monkeypatch.setattr(mod.subprocess, "run", _mock_worktrees(5))
    # run_pressure = 3-1 = 2 ; wt_pressure = 5-2 = 3
    assert mod._count_concurrent_conflict_signals(ws) == 5


def test_wt_below_free_allowance_yields_zero_pressure(radar, monkeypatch):
    mod, ws = radar
    runs_dir = ws / ".omo" / "_delivery" / "agent-workflows" / "runs"
    monkeypatch.setattr(mod.subprocess, "run", _mock_worktrees(1))  # 只有 main
    assert mod._count_concurrent_conflict_signals(ws) == 0


def test_git_failure_degrades_wt_pressure_to_zero(radar, monkeypatch):
    mod, ws = radar
    runs_dir = ws / ".omo" / "_delivery" / "agent-workflows" / "runs"

    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=15)

    monkeypatch.setattr(mod.subprocess, "run", boom)
    assert mod._count_concurrent_conflict_signals(ws) == 0


def test_weights_untouched_contract(radar):
    """Redline (BET-Y2Q4-T9-01): 权重常量不在本 bet 变更——锚定当前值防顺手调参。"""
    mod, _ = radar
    surface = mod.collect_governance_execution_surface(_WS)
    assert surface["weights"] == {
        "orphan_worktrees": mod._W_ORPHAN_WORKTREE,
        "adr_renumber_events": mod._W_ADR_RENUMBER,
        "concurrent_conflicts": mod._W_CONCURRENT_CONFLICT,
    }
    # 快照锚点（2026-09-26）：如需变更权重必须走 ADR，本测试先红
    assert mod._W_CONCURRENT_CONFLICT == 8


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
