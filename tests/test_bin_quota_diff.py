"""check-bin-quota-diff.py 自测: 配额"变更侧问责"语义.

三场景:
  1. 净增 (added > deleted) → fail (ok=False)
  2. 增删平衡 (added == deleted) → pass (ok=True)
  3. 无 bin 变更 → pass (ok=True)
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path


def load_module():
    path = Path(__file__).parents[1] / "bin/gac/check-bin-quota-diff.py"
    spec = importlib.util.spec_from_file_location("check_bin_quota_diff", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _make_repo(tmp_path: Path) -> tuple[Path, str]:
    """建临时 git 仓库, 初始 commit 含 bin/a.py, bin/b.sh. 返回 (repo, base_sha)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "bin").mkdir()
    (repo / "bin/a.py").write_text("print('a')\n", encoding="utf-8")
    (repo / "bin/b.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base_sha = _git(repo, "rev-parse", "HEAD").strip()
    return repo, base_sha


def _commit(repo: Path, msg: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)


def test_net_add_fails(tmp_path: Path) -> None:
    """场景1: 净增 (新增 2, 删除 0) → fail."""
    module = load_module()
    repo, base = _make_repo(tmp_path)
    (repo / "bin/c.py").write_text("print('c')\n", encoding="utf-8")
    (repo / "bin/d.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    _commit(repo, "add two")
    result = module.evaluate(base, repo)
    assert result["ok"] is False
    assert len(result["added"]) == 2
    assert len(result["deleted"]) == 0


def test_balanced_pass(tmp_path: Path) -> None:
    """场景2: 增删平衡 (新增 1, 删除 1) → pass."""
    module = load_module()
    repo, base = _make_repo(tmp_path)
    (repo / "bin/c.py").write_text("print('c')\n", encoding="utf-8")
    (repo / "bin/a.py").unlink()
    _commit(repo, "add one delete one")
    result = module.evaluate(base, repo)
    assert result["ok"] is True
    assert len(result["added"]) == 1
    assert len(result["deleted"]) == 1


def test_no_bin_change_pass(tmp_path: Path) -> None:
    """场景3: 无 bin 变更 → pass."""
    module = load_module()
    repo, base = _make_repo(tmp_path)
    (repo / "README.md").write_text("hi\n", encoding="utf-8")
    _commit(repo, "doc only")
    result = module.evaluate(base, repo)
    assert result["ok"] is True
    assert result["added"] == []
    assert result["deleted"] == []


def test_archive_counts_as_deletion_pass(tmp_path: Path) -> None:
    """场景4: 归档 (git mv 到 _archive/) 计入 deleted, 新增 1 归档 1 → pass."""
    module = load_module()
    repo, base = _make_repo(tmp_path)
    (repo / "bin/_archive").mkdir()
    _git(repo, "mv", "bin/a.py", "bin/_archive/a.py")
    (repo / "bin/c.py").write_text("print('c')\n", encoding="utf-8")
    _commit(repo, "add one archive one")
    result = module.evaluate(base, repo)
    assert result["ok"] is True
    assert len(result["added"]) == 1  # 仅 c.py, _archive/a.py 不计新增
    assert len(result["deleted"]) == 1  # a.py 归档计入删除
