"""generate-submodule-health-report: 未初始化子模块不得借用父仓读数。

缺陷背景 (2026-11-10 实测): 该报告逐子模块执行 `git -C <path> …`，但当子模块**未初始化**
（目录下没有自己的 `.git` 条目）时，git 会**向上回落到父仓** —— 于是 `branch -r` / `tag` /
`rev-parse origin/main` 全部返回**父仓**的数值，`main_tip` 与 `head_tip` 都非空，
`未初始化` 分支永远不触发。实测在一个未 init 子模块的检出里跑，16 个子模块全部报成
同一组父仓数字（79 分支 / 489 tags / +2），概览还写 `未初始化 | 0`。

本测试锁住两件事：
1. 未初始化子模块必须如实报 `❌ 未初始化`，而不是父仓的读数；
2. 判据仍有牙齿：已初始化子模块仍走真实测量（正向对照），且概览计数跟着变。
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


def _load(monkeypatch, tmp_path: Path):
    script = Path(__file__).resolve().parents[3] / "bin" / "gac" / "generate-submodule-health-report.py"
    spec = importlib.util.spec_from_file_location("gen_submodule_health", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    return module


def _write_gitmodules(tmp_path: Path) -> None:
    (tmp_path / ".gitmodules").write_text(
        '[submodule "sub"]\n\tpath = projects/sub\n\turl = https://example.invalid/sub.git\n',
        encoding="utf-8",
    )


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_parent_repo(tmp_path: Path) -> None:
    """Make the workspace a Git repository, so `git -C <uninitialized>` walks up.

    Without a parent repository the fallback never happens and the defective
    code path reports "未初始化" anyway — the test would pass with or without
    the guard (measured: mutating the guard to `True` left all cases green).
    """
    _git("init", "-q", cwd=tmp_path)
    _git("-c", "user.email=t@example.invalid", "-c", "user.name=t",
         "commit", "-q", "--allow-empty", "-m", "init", cwd=tmp_path)
    _git("update-ref", "refs/remotes/origin/main", "HEAD", cwd=tmp_path)


def test_uninitialized_submodule_is_reported_not_parent_data(monkeypatch, tmp_path):
    _write_gitmodules(tmp_path)
    _init_parent_repo(tmp_path)
    (tmp_path / "projects" / "sub").mkdir(parents=True)
    module = _load(monkeypatch, tmp_path)

    infos = module.gather_submodule_info()

    assert infos == [{"path": "projects/sub", "name": "sub", "remote_branches": 0,
                      "tags": 0, "status": "❌ 未初始化", "last_commit": "N/A"}]


def test_summary_counts_uninitialized(monkeypatch, tmp_path):
    _write_gitmodules(tmp_path)
    _init_parent_repo(tmp_path)
    (tmp_path / "projects" / "sub").mkdir(parents=True)
    module = _load(monkeypatch, tmp_path)

    report = module.generate_report(module.gather_submodule_info())

    assert "| 未初始化 | 1 |" in report
    assert "| 指针漂移 | 0 |" in report


def test_initialized_submodule_still_measured(monkeypatch, tmp_path):
    _write_gitmodules(tmp_path)
    sub = tmp_path / "projects" / "sub"
    sub.mkdir(parents=True)
    _git("init", "-q", cwd=sub)
    _git("-c", "user.email=t@example.invalid", "-c", "user.name=t",
         "commit", "-q", "--allow-empty", "-m", "init", cwd=sub)
    _git("update-ref", "refs/remotes/origin/main", "HEAD", cwd=sub)
    module = _load(monkeypatch, tmp_path)

    infos = module.gather_submodule_info()

    assert infos[0]["status"] == "✅ 对齐"
    assert infos[0]["last_commit"][0:4].isdigit()
    assert "未初始化" not in infos[0]["status"]
