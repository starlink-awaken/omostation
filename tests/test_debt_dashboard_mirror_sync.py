"""debt-dashboard-mirror-sync 刷新 tracked 镜像并送回 origin/main。

镜像 `.omo/_control/debt-dashboard/current.yaml` 由 `omo` 的 post-hook 刷新，
但没有环节提交它 —— origin/main 上那份腐烂 → A2/A5 恒红（2026-10-20 实测
817 小时 vs SLA 336）。既有的 `chore(auto)` cron 同样只 commit 不 push，
而 fullrefresh 每 180s `reset --hard origin/main` 把本地提交抹掉。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin/ssot/debt-dashboard-mirror-sync.py"


def _load(monkeypatch, ws: Path):
    """加载脚本, 把工作区根换成 fixture, 并记录 git/omo 调用。"""
    spec = importlib.util.spec_from_file_location("debt_mirror_sync", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "code_root", lambda: ws)
    # 入口文件必须存在, 否则 refresh_mirror 的缺失分支先触发。
    venv_entry = ws / module.OMO_BIN
    venv_entry.parent.mkdir(parents=True, exist_ok=True)
    venv_entry.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    calls: list[tuple] = []
    monkeypatch.setattr(module, "_git", lambda w, *a, check=True: calls.append(a) or _FakeRun(0, "", ""))
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: calls.append(a) or _FakeRun(0, "", ""))
    return module, calls


class _FakeRun:
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def ws(tmp_path, monkeypatch):
    root = tmp_path / "ws"
    root.mkdir()
    (root / ".omo/_control/debt-dashboard").mkdir(parents=True)
    (root / ".omo/debt/dashboard").mkdir(parents=True)
    (root / ".git").mkdir()
    monkeypatch.chdir(root)
    return root


def _git(calls, *args):
    """calls 记录的是 _git(ws, *args) 的 args（不含 "git" 前缀）。"""
    return any(isinstance(c, tuple) and tuple(c) == args for c in calls)


def test_non_main_branch_is_skipped(ws, monkeypatch):
    module, calls = _load(monkeypatch, ws)
    monkeypatch.setattr(module, "_git",
                        lambda w, *a, check=True: _FakeRun(0, "feature/x\n", ""))
    assert module.main([]) == 0
    assert not _git(calls, "commit", "-q", "-m", module.COMMIT_MESSAGE)
    assert not _git(calls, "push", "origin", "main")


def test_detached_head_is_skipped(ws, monkeypatch):
    module, calls = _load(monkeypatch, ws)
    monkeypatch.setattr(module, "_git", lambda w, *a, check=True: _FakeRun(0, "", ""))
    assert module.main([]) == 0
    assert not _git(calls, "commit", "-q", "-m", module.COMMIT_MESSAGE)


def test_dry_run_writes_nothing(ws, monkeypatch):
    module, calls = _load(monkeypatch, ws)
    monkeypatch.setattr(module, "_git",
                        lambda w, *a, check=True: _FakeRun(0, "main\n", ""))
    assert module.main(["--dry-run"]) == 0
    assert not _git(calls, "add", str(module.MIRROR_REL))
    assert not _git(calls, "commit", "-q", "-m", module.COMMIT_MESSAGE)
    assert not _git(calls, "push", "origin", "main")
    # 连刷新都不该发生
    assert not any(isinstance(c, tuple) and "debt" in c for c in calls)


def test_commits_only_the_mirror_and_pushes(ws, monkeypatch):
    module, calls = _load(monkeypatch, ws)
    # symbolic-ref 报 main; diff --cached 报「有差异」 -> 需要提交
    def fake_git(w, *a, check=True):
        calls.append(a)
        if tuple(a)[:1] == ("symbolic-ref",):
            return _FakeRun(0, "main\n", "")
        return _FakeRun(1 if tuple(a) == ("diff", "--cached", "--quiet") else 0, "", "")

    monkeypatch.setattr(module, "_git", fake_git)
    assert module.main([]) == 0
    assert _git(calls, "add", str(module.MIRROR_REL))
    assert _git(calls, "commit", "-q", "-m", module.COMMIT_MESSAGE)
    assert _git(calls, "push", "origin", "main")
    # 只暂存镜像, 不碰其它路径
    added = [c[1] for c in calls if isinstance(c, tuple) and c and c[0] == "add"]
    assert added == [str(module.MIRROR_REL)]


def test_no_change_skips_commit_and_push(ws, monkeypatch):
    module, calls = _load(monkeypatch, ws)
    monkeypatch.setattr(module, "_git",
                        lambda w, *a, check=True: _FakeRun(
                            0 if tuple(a) == ("diff", "--cached", "--quiet") else 0, "", ""))
    assert module.main([]) == 0
    assert not _git(calls, "commit", "-q", "-m", module.COMMIT_MESSAGE)
    assert not _git(calls, "push", "origin", "main")


def test_push_reports_failure_and_returns_nonzero(ws, monkeypatch):
    module, calls = _load(monkeypatch, ws)

    def fake_git(w, *a, check=True):
        calls.append(a)
        if tuple(a)[:1] == ("symbolic-ref",):
            return _FakeRun(0, "main\n", "")
        if tuple(a) == ("diff", "--cached", "--quiet"):
            return _FakeRun(1, "", "")
        if tuple(a) == ("push", "origin", "main"):
            return _FakeRun(1, "", "non-fast-forward")
        return _FakeRun(0, "", "")

    monkeypatch.setattr(module, "_git", fake_git)
    assert module.main([]) == 1
    assert _git(calls, "commit", "-q", "-m", module.COMMIT_MESSAGE)


def test_no_push_flag_skips_push(ws, monkeypatch):
    module, calls = _load(monkeypatch, ws)
    monkeypatch.setattr(module, "_git",
                        lambda w, *a, check=True: _FakeRun(
                            1 if tuple(a) == ("diff", "--cached", "--quiet") else 0, "", ""))
    assert module.main(["--no-push"]) == 0
    assert not _git(calls, "push", "origin", "main")


def test_refresh_failure_is_an_error(ws, monkeypatch):
    module, _ = _load(monkeypatch, ws)
    monkeypatch.setattr(module, "_git",
                        lambda w, *a, check=True: _FakeRun(0, "main\n", ""))

    def _boom(*a, **k):
        return _FakeRun(1, "", "debt refresh failed rc=1: boom")

    monkeypatch.setattr(module.subprocess, "run", _boom)
    assert module.main([]) == 1


def test_uses_repo_root_not_file_relative(monkeypatch, tmp_path):
    """AGENTS.md: 机器级配置不得硬编码工作区根。"""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "code_root()" in source
    assert 'REPO = Path(__file__).resolve().parents[2]' in source  # 仅用于定位 lib/


def test_script_is_invoked_without_uv_run(ws, monkeypatch):
    """cron 里每条都要省启动开销; 直接走 omo 的 venv 入口。"""
    module, _ = _load(monkeypatch, ws)
    assert module.OMO_BIN == "projects/omo/.venv/bin/omo"
    assert "uv" not in module.OMO_BIN


def test_missing_omo_venv_is_actionable_not_a_traceback(ws, monkeypatch):
    """端到端实测 (2026-10-21): 浅克隆未 init 子模块时入口缺失。

    原实现让 subprocess.run 抛 FileNotFoundError 一路冒到 cron 日志 —— 一条
    traceback 而不是可操作的话。缺的就是这个 venv, 必须说清怎么补。
    """
    module, _ = _load(monkeypatch, ws)
    monkeypatch.setattr(module, "_git",
                        lambda w, *a, check=True: _FakeRun(0, "main\n", ""))
    (ws / module.OMO_BIN).unlink()  # _load 会造一个假的, 这里撤掉
    assert module.main([]) == 1


def test_refresh_error_is_one_line_not_a_traceback(ws, monkeypatch, capsys):
    """cron 日志里只该有一行可操作的话。"""
    module, _ = _load(monkeypatch, ws)
    monkeypatch.setattr(module, "_git",
                        lambda w, *a, check=True: _FakeRun(0, "main\n", ""))
    (ws / module.OMO_BIN).unlink()
    assert module.main([]) == 1
    err = capsys.readouterr().err.strip()
    assert err.startswith("error: omo venv entry missing"), err
    assert "Traceback" not in err
    assert "run `git submodule update --init projects/omo`" in err
