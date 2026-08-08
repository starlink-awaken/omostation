"""Integration tests for bin/gac/gac-worktree-cleanup.sh (isolated via WS_PARENT).

每个测试在 tmp_path 下自建 `ws-*` 目录 (真实 git repo 或空目录) 与
`.ws-<session>.claiming` marker, 通过注入 WS_PARENT 让 cleanup 脚本只扫描
tmp 目录, 完全不触碰真实 workspace 的 ws-* worktree.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLAIM_SCRIPT = ROOT / "bin" / "gac" / "gac-worktree.sh"
CLEANUP_SCRIPT = ROOT / "bin" / "gac" / "gac-worktree-cleanup.sh"

# 唯一分支名: 避免命中真实 workspace 的 branch-claims (G5) 或 open PR 检查
_UNIQUE_BRANCH = "ws-it-stale-branch-8fb31988"


def _make_aged_git_repo(path: Path, branch: str = _UNIQUE_BRANCH) -> None:
    """初始化一个带过期 commit 的 git repo (无 remote, 隔离于真实 workspace)."""
    path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", branch, str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "it@test"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "it"], check=True)
    env = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2020-01-01T00:00:00",
        "GIT_COMMITTER_DATE": "2020-01-01T00:00:00",
    }
    subprocess.run(
        ["git", "-C", str(path), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        env=env,
    )


def _run_cleanup(tmp_path: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "WS_ROOT": str(ROOT),  # 真实仓库: origin/gh 检查需要
        "WS_PARENT": str(tmp_path),  # 注入隔离目录
        "PASW_TTL_HOURS": "0",
    }
    return subprocess.run(
        ["bash", str(CLEANUP_SCRIPT), *(extra or ["--dry-run"])],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=120,
    )


def test_claim_marker_blocks_cleanup_dry_run(tmp_path: Path) -> None:
    """claim marker + 对应 ws-* 目录存在时, 即使 TTL=0 也必须跳过回收."""
    (tmp_path / "ws-sweep-test").mkdir()
    marker = tmp_path / ".ws-sweep-test.claiming"
    marker.write_text("")
    result = _run_cleanup(tmp_path)
    assert "claim 初始化进行中" in result.stdout, result.stdout
    assert "回收过期 worktree" not in result.stdout, result.stdout


def test_cleanup_ttl_reclaims_aged_worktree(tmp_path: Path) -> None:
    """无 marker 的过期 worktree (真实 git repo, 旧 commit) 在 TTL=0 时被回收."""
    _make_aged_git_repo(tmp_path / "ws-stale")
    result = _run_cleanup(tmp_path)
    assert "回收过期 worktree: ws-stale" in result.stdout, result.stdout
    # dry-run 模式不允许真删
    assert "已回收 ws-stale" not in result.stdout, result.stdout


def test_cleanup_skips_dir_without_commit_history(tmp_path: Path) -> None:
    """无 commit 历史的 ws-* 目录必须跳过, 避免误删半初始化 worktree."""
    (tmp_path / "ws-half-init").mkdir()
    result = _run_cleanup(tmp_path)
    assert "无 commit 历史, 跳过" in result.stdout, result.stdout
    assert "回收过期 worktree: ws-half-init" not in result.stdout, result.stdout


def test_gac_worktree_script_parses() -> None:
    """gac-worktree.sh 必须通过 bash 语法检查."""
    result = subprocess.run(
        ["bash", "-n", str(CLAIM_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
