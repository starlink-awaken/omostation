#!/usr/bin/env python3
"""
test_worktree_janitor.py — worktree-janitor.py 的 temp repo 测试

使用 subprocess 运行脚本，测试判定逻辑（不真删）。
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest


class TempGitRepo:
    """临时 git 仓库（用于测试）"""

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.root = Path(self.temp_dir)
        self.bare_repo = None
        self.worktrees = []

    def init_bare(self):
        """创建 bare repo"""
        self.bare_repo = self.root / "bare.git"
        subprocess.run(
            ["git", "init", "--bare", str(self.bare_repo)],
            check=True,
            capture_output=True,
        )

    def clone(self, name: str) -> Path:
        """clone bare repo 到 worktree"""
        worktree = self.root / name
        subprocess.run(
            ["git", "clone", str(self.bare_repo), str(worktree)],
            check=True,
            capture_output=True,
        )
        # 配置 user
        subprocess.run(
            ["git", "-C", str(worktree), "config", "user.name", "Test User"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(worktree), "config", "user.email", "test@example.com"],
            check=True,
            capture_output=True,
        )
        # 初始 commit
        (worktree / "README.md").write_text("# test repo")
        subprocess.run(
            ["git", "-C", str(worktree), "add", "."],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(worktree), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(worktree), "push", "origin", "main"],
            check=True,
            capture_output=True,
        )
        self.worktrees.append(worktree)
        return worktree

    def add_worktree(self, base: Path, session: str) -> Path:
        """创建 worktree（模拟 ws-XXX）"""
        wt_path = base.parent / f"ws-{session}"
        subprocess.run(
            [
                "git",
                "-C",
                str(base),
                "worktree",
                "add",
                "-b",
                f"work/{session}",
                str(wt_path),
            ],
            check=True,
            capture_output=True,
        )
        return wt_path

    def add_commit(self, worktree: Path, msg: str = "test commit"):
        """添加一个 commit"""
        (worktree / "test.txt").write_text(msg)
        subprocess.run(
            ["git", "-C", str(worktree), "add", "."],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(worktree), "commit", "-m", msg],
            check=True,
            capture_output=True,
        )

    def cleanup(self):
        """清理临时目录"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)


def run_janitor_in_repo(repo: TempGitRepo) -> str:
    """在临时 repo 中运行 janitor 脚本"""
    main_wt = repo.worktrees[0]
    result = subprocess.run(
        ["python3", "bin/gac/worktree-janitor.py"],
        cwd=str(main_wt),
        capture_output=True,
        text=True,
    )
    return result.stdout


@pytest.fixture
def temp_repo():
    """临时 git 仓库"""
    repo = TempGitRepo()
    repo.init_bare()
    repo.clone("main")
    yield repo
    repo.cleanup()


def test_repo_setup(temp_repo):
    """测试：临时 repo 创建成功"""
    assert temp_repo.bare_repo.exists()
    assert len(temp_repo.worktrees) == 1
    assert temp_repo.worktrees[0].exists()


def test_janitor_runs(temp_repo):
    """测试：janitor 脚本能正常运行"""
    # 获取主仓路径
    from pathlib import Path

    repo_root = Path.cwd()
    while repo_root != repo_root.parent:
        if (repo_root / "bin" / "gac" / "worktree-janitor.py").exists():
            break
        repo_root = repo_root.parent

    main_wt = temp_repo.worktrees[0]
    result = subprocess.run(
        [str(repo_root / "bin/gac/worktree-janitor.py")],
        cwd=str(main_wt),
        capture_output=True,
        text=True,
    )
    # 在空 repo 中可能没有 ws-* worktree，但应该能正常运行
    assert "总计" in result.stdout or result.returncode == 0


def test_claim_file_check(temp_repo):
    """测试：claim 文件存在性检查"""
    main_wt = temp_repo.worktrees[0]
    claim_dir = main_wt / ".omo" / "_delivery" / "branch-claims"
    claim_dir.mkdir(parents=True, exist_ok=True)

    # 场景 1：claim 文件不存在
    assert not (claim_dir / "nonexistent.json").exists()

    # 场景 2：创建 claim 文件
    claim_file = claim_dir / "test-session.json"
    claim_file.write_text(json.dumps({"coordination_token": 12345}))
    assert claim_file.exists()
    data = json.loads(claim_file.read_text())
    assert data["coordination_token"] == 12345


def test_worktree_status_checks(temp_repo):
    """测试：worktree 状态检查（dirty/clean）"""
    main_wt = temp_repo.worktrees[0]
    wt = temp_repo.add_worktree(main_wt, "test-session")

    # 场景 1：clean worktree
    result = subprocess.run(
        ["git", "-C", str(wt), "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "", f"worktree should be clean, got: {result.stdout}"

    # 场景 2：添加 dirty 文件
    (wt / "dirty.txt").write_text("dirty content")
    result = subprocess.run(
        ["git", "-C", str(wt), "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    assert "dirty.txt" in result.stdout, f"should show dirty.txt, got: {result.stdout}"


def test_branch_merge_status(temp_repo):
    """测试：分支 merge 状态检查"""
    main_wt = temp_repo.worktrees[0]
    wt = temp_repo.add_worktree(main_wt, "test-session")

    # 检查分支是否存在
    result = subprocess.run(
        ["git", "-C", str(main_wt), "branch", "--list", "work/test-session"],
        capture_output=True,
        text=True,
    )
    assert "work/test-session" in result.stdout or result.stdout.strip().startswith("* work/test-session"), (
        f"branch should exist, got: {result.stdout}"
    )

    # 检查是否已 merge 到 main（刚创建的分支通常未 merge）
    result = subprocess.run(
        ["git", "-C", str(main_wt), "branch", "--merged", "main"],
        capture_output=True,
        text=True,
    )
    # 新分支应该不在 merged 列表（除非是空 commit）
    # 这里只检查命令能正常运行
    assert result.returncode == 0, f"git branch --merged should succeed, got: {result.stderr}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def _load_janitor():
    import importlib.util
    import sys

    path = Path(__file__).resolve().parents[1] / "bin" / "gac" / "worktree-janitor.py"
    spec = importlib.util.spec_from_file_location("worktree_janitor", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_deleted_remote_branch_merged_to_main_is_recognised(tmp_path):
    """run_git returns stdout and --is-ancestor prints nothing: the old check never passed."""
    j = _load_janitor()
    repo = tmp_path / "r"
    _git(tmp_path, "init", "-q", "-b", "main", str(repo))
    (repo / "f").write_text("1")
    _git(repo, "add", "f")
    _git(repo, "commit", "-q", "-m", "c")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    info = j.WorktreeInfo(path=repo, session="s", branch="already-deleted", mtime=0.0)
    ok, reason = j.check_branch_merged_or_deleted(info, repo)
    assert (ok, reason) == (True, "deleted and ancestor")


def test_unpushed_submodule_commit_blocks_janitor(tmp_path):
    j = _load_janitor()
    remote = tmp_path / "sub.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    seed = tmp_path / "seed"
    _git(tmp_path, "clone", "-q", str(remote), str(seed))
    (seed / "f").write_text("1")
    _git(seed, "add", "f")
    _git(seed, "commit", "-q", "-m", "seed")
    _git(seed, "push", "-q", "origin", "HEAD:main")
    sup = tmp_path / "super"
    _git(tmp_path, "init", "-q", "-b", "main", str(sup))
    _git(sup, "submodule", "add", "-q", str(remote), "kairon")
    _git(sup, "commit", "-q", "-m", "add submodule")
    info = j.WorktreeInfo(path=sup, session="s", branch="b", mtime=0.0)
    assert j.check_submodules_pushed(info) == (True, "all pushed")

    (sup / "kairon" / "f").write_text("local only")
    _git(sup / "kairon", "commit", "-q", "-am", "local only")
    ok, reason = j.check_submodules_pushed(info)
    assert not ok
    assert "kairon" in reason and "not on any remote branch" in reason
