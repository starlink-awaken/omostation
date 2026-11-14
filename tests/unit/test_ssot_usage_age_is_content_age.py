"""`ssot-usage.py` 的文件年龄必须来自**内容**（最后一次提交），不是 checkout 的 mtime。

契约来源：2026-11-14 —— 原实现用 `os.path.getmtime`，实测同一个仓：
**干净 worktree 全部 age=0（stale=0）**，而 60 天没动的检出 **56/68 stale**。
两个读数都不描述内容：前者是空绿，后者是环境性假红。改用 `git log -1 --format=%ct`。

本文件两条互补判据：
- **mtime 变、年龄不变**（checkout / touch 不该改变「内容多久没更新」）；
- **提交变、年龄才变**（真的改了内容，年龄必须跟上）。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "ssot" / "ssot-usage.py"


def _load():
    spec = importlib.util.spec_from_file_location("ssot_usage_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ssot_usage_under_test"] = module
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _make_repo(tmp_path: Path) -> tuple:
    module = _load()
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    return module, repo


def _commit(repo: Path, message: str, *, days_ago: float = 0) -> None:
    """提交, 并显式钉住 committer/author 日期。

    注意 `%ct` 是 **committer** 日期, 而 `git commit --date` 只设 **author** 日期
    —— 想用 `--date` 控制 `%ct` 是无效的(实测)。
    """
    import os

    stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - days_ago * 86400))
    env = dict(os.environ)
    env["GIT_COMMITTER_DATE"] = stamp
    env["GIT_AUTHOR_DATE"] = stamp
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", message],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def test_mtime_change_does_not_change_age(tmp_path: Path) -> None:
    """checkout / touch 改变 mtime —— 年龄必须不变。"""
    module, repo = _make_repo(tmp_path)
    f = repo / "reg.yaml"
    f.write_text("a: 1\n", encoding="utf-8")
    _git(repo, "add", "reg.yaml")
    _git(repo, "commit", "-q", "-m", "one")

    before = module.file_age_days(f)
    # 只动 mtime：内容不动、提交不动。
    future = time.time() + 3 * 86400
    f.touch()
    import os

    os.utime(f, (future, future))
    after = module.file_age_days(f)

    assert abs(after - before) < 0.01, (before, after)


def test_new_commit_changes_age(tmp_path: Path) -> None:
    """真的改了内容 —— 年龄必须跟着变。"""
    module, repo = _make_repo(tmp_path)
    f = repo / "reg.yaml"
    f.write_text("a: 1\n", encoding="utf-8")
    _git(repo, "add", "reg.yaml")
    _commit(repo, "one", days_ago=10)
    first = module.file_age_days(f)

    f.write_text("a: 2\n", encoding="utf-8")
    _git(repo, "add", "reg.yaml")
    _commit(repo, "two")
    second = module.file_age_days(f)

    assert first >= 9.0, first
    assert second < 1.0, second


def test_untracked_file_falls_back_to_mtime(tmp_path: Path) -> None:
    """未跟踪/无历史 ⇒ 退回 mtime（有读数总比没有好，且不冒充提交时间）。"""
    module, repo = _make_repo(tmp_path)
    f = repo / "untracked.yaml"
    f.write_text("x: 1\n", encoding="utf-8")
    age = module.file_age_days(f)
    assert age < 0.01, age


def test_fresh_checkout_does_not_make_everything_fresh(tmp_path: Path) -> None:
    """反证：新检出（mtime 全新）不该把所有文件变成 age=0。

    这是原实现最容易骗人的一条 —— 干净 worktree 实测 stale=0。
    """
    module, repo = _make_repo(tmp_path)
    f = repo / "reg.yaml"
    f.write_text("a: 1\n", encoding="utf-8")
    _git(repo, "add", "reg.yaml")
    _commit(repo, "one", days_ago=10)

    # 模拟「刚 checkout」：把 mtime 刷成现在
    import os

    now = time.time()
    os.utime(f, (now, now))
    age = module.file_age_days(f)
    assert age >= 9.0, f"新检出把 10 天前的提交读成了 {age} 天"
