"""N1 治本测试: _prune_orphan_worktrees 清 orphan record (防 concurrent_conflicts 累积).

治本机制 (PR #553): run_radar 生成 health 前自动 git worktree prune,
清 orphan record (目录已不存在的 worktree 登记项), 防 wt_pressure 累积.

测试 (integration, 真造 orphan + prune + 验证):
- test_prune_clears_orphan_record: 造 orphan → prune → orphan 0
- test_prune_safe_no_orphan: 无 orphan 时 prune 安全 (返回 0)
- test_prune_safe_no_git: 非 git 目录 prune 不崩 (返回 1, 容错)
"""
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "bin"))

from compass_radar import _count_orphan_worktrees, _prune_orphan_worktrees


def _init_git_repo(d: Path) -> None:
    """init 一个最小 git repo (含 1 commit) 供 worktree 测试."""
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=d, check=True)
    (d / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=d, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=d, check=True)


def test_prune_clears_orphan_record(tmp_path: Path) -> None:
    """造 orphan worktree (add + 删目录) → prune → orphan 0."""
    _init_git_repo(tmp_path)
    wt = tmp_path / "wt-orphan"
    subprocess.run(["git", "worktree", "add", "-q", str(wt)], cwd=tmp_path, check=True)
    shutil.rmtree(wt)  # 删目录造 orphan record
    assert _count_orphan_worktrees(tmp_path) == 1, "orphan 应为 1 (目录删 record 残留)"
    rc = _prune_orphan_worktrees(tmp_path)
    assert rc == 0, "prune 应返回 0"
    assert _count_orphan_worktrees(tmp_path) == 0, "prune 后 orphan 应 0"


def test_prune_safe_no_orphan(tmp_path: Path) -> None:
    """无 orphan 时 prune 安全 (返回 0, 不破坏)."""
    _init_git_repo(tmp_path)
    rc = _prune_orphan_worktrees(tmp_path)
    assert rc == 0
    assert _count_orphan_worktrees(tmp_path) == 0


def test_prune_safe_no_git(tmp_path: Path) -> None:
    """非 git 目录 prune 容错 (返回 1, 不抛异常)."""
    rc = _prune_orphan_worktrees(tmp_path)
    assert rc != 0, "非 git 目录 prune 应返回非 0 (git error 128, 容错不崩)"
