#!/usr/bin/env python3
"""test_bump_fast.py — BET-Y1Q1-T1-08 bump-fast 计时 + 功能验证.

用法: python3 bin/gac/test_bump_fast.py
"""
from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "gac-worktree.sh"


def _run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=check)


def _init_git():
    """配置最小 git 环境 + 允许 file:// 传输（Git 2.38+ 安全策略默认禁止）."""
    subprocess.run(["git", "config", "--global", "user.email", "test@test"], capture_output=True, check=False)
    subprocess.run(["git", "config", "--global", "user.name", "test"], capture_output=True, check=False)
    subprocess.run(["git", "config", "--global", "protocol.file.allow", "always"], capture_output=True, check=False)


def _make_repo_with_submodule(tmp: Path) -> tuple[Path, str]:
    """创建含子模块的本地仓库, 返回 (root, initial_sha)."""
    sub_repo = tmp / "sub_remote.git"
    sub_repo.mkdir()
    _run(["git", "init", "--bare", str(sub_repo)], cwd=tmp)

    sub_work = tmp / "sub_work"
    sub_work.mkdir()
    _run(["git", "init", str(sub_work)], cwd=tmp)
    (sub_work / "README.md").write_text("# sub\n")
    _run(["git", "add", "."], cwd=sub_work)
    _run(["git", "commit", "-m", "init"], cwd=sub_work)
    _run(["git", "push", str(sub_repo), "main"], cwd=sub_work)
    initial_sha = _run(["git", "rev-parse", "HEAD"], cwd=sub_work).stdout.strip()

    root = tmp / "root"
    root.mkdir()
    _run(["git", "init", str(root)], cwd=tmp)
    (root / "README.md").write_text("# root\n")
    _run(["git", "add", "."], cwd=root)
    _run(["git", "commit", "-m", "init"], cwd=root)
    _run(["git", "submodule", "add", str(sub_repo), "projects/sub"], cwd=root)
    _run(["git", "commit", "-m", "add sub"], cwd=root)
    return root, initial_sha


def test_bump_fast_timing():
    """核心操作（ls-remote + cacheinfo）< 2s（本地 bare repo 消除网络变量）."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        root, _ = _make_repo_with_submodule(tmp)

        start = time.monotonic()
        result = _run(["bash", str(SCRIPT), "bump-fast", "projects/sub", "--latest-main"], cwd=root)
        elapsed = time.monotonic() - start

        assert result.returncode == 0, f"bump-fast 失败: {result.stderr}"
        assert elapsed < 2.0, f"核心操作 {elapsed:.2f}s > 2s 目标"
        print(f"bump-fast 核心操作: {elapsed:.2f}s (< 2s ✅)")


def test_bump_fast_fail_closed():
    """不可达 SHA → fail-closed 非 0 退出."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        root, _ = _make_repo_with_submodule(tmp)

        fake_sha = "deadbeef" * 5 + "0" * 4  # 40 位不存在 SHA
        result = _run(["bash", str(SCRIPT), "bump-fast", "projects/sub", "--sha", fake_sha],
                      cwd=root, check=False)
        assert result.returncode != 0, "不可达 SHA 应 fail-closed"
        print("fail-closed 拒绝不可达 SHA ✅")


def test_bump_fast_interface():
    """bump-fast 接口可用."""
    result = _run(["bash", str(SCRIPT), "bump-fast"], cwd=Path.cwd(), check=False)
    assert result.returncode != 0  # 缺参数应非 0 退出
    assert "用法" in result.stdout or "用法" in result.stderr
    print("bump-fast 接口可用 ✅")


if __name__ == "__main__":
    _init_git()
    test_bump_fast_timing()
    test_bump_fast_fail_closed()
    test_bump_fast_interface()
    print("\n=== ALL BUMP-FAST TESTS PASSED ===")
