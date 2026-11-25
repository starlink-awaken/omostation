"""``sync-submodules-push``：``.invalid`` 在途 init 瞬态不得判成 blocking 失败。

``.git`` 存在不等于检出可读：worktree 守卫的在途 ``submodule update --init``
会留下 gitdir 指针指向 ``refs/heads/.invalid`` 的瞬态（无 refs，pin 对象可能
还不在本地对象库里）。改动前该形态穿不过「``.git`` 不存在」这一支，落到
``rev-parse --abbrev-ref HEAD`` 失败 ⇒ 计 ``failed`` ⇒ ``git push`` 被自己的
pre-push 钩子拦下（2026-11-25 ws-ssotfix 实测，本 PR 的 gitlink 一个都没动）。

三条用例两两不共享失效模式：
- 正例：``.invalid` 瞬态 ⇒ 跳过（``失败=0``, rc=0）；
- 反例：真的有未推 commit ⇒ 仍 ``pending=1``, rc=1（防「一律放行」的放宽）；
- 变异：把守卫从脚本副本里摘掉 ⇒ 正例当场转红。
"""

from __future__ import annotations


import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "ssot" / "sync-submodules-push.sh"

GUARD_MARKER = "检出不可读 (.invalid 在途 init / 无有效 HEAD)"


def _git(repo: Path, *args: str, check: bool = True) -> str:
    done = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and done.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} rc={done.returncode}: {done.stderr}")
    return done.stdout.strip()


def _init_parent(tmp_path: Path) -> Path:
    parent = tmp_path / "parent"
    parent.mkdir(parents=True)
    _git(parent, "init", "-q")
    _git(parent, "config", "user.email", "test@example.com")
    _git(parent, "config", "user.name", "Test")
    return parent


def _write_gitmodules(parent: Path, entries: list[tuple[str, str]]) -> None:
    lines = []
    for name, url in entries:
        lines.append(f'[submodule "{name}"]')
        lines.append(f"\tpath = {name}")
        lines.append(f"\turl = {url}")
    (parent / ".gitmodules").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_invalid_transient(sm: Path) -> None:
    """构造 ``.git`` 在位但 HEAD 不可读的 ``.invalid`` 瞬态。"""
    (sm / ".git" / "refs").mkdir(parents=True)
    (sm / ".git" / "objects").mkdir()
    (sm / ".git" / "HEAD").write_text("ref: refs/heads/.invalid\n", encoding="utf-8")
    (sm / ".git" / "config").write_text(
        "[core]\n\trepositoryformatversion = 0\n\tbare = false\n", encoding="utf-8"
    )


def _run(script: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _remote_with_main(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "-q", "--bare", "-b", "main")
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-q")
    _git(seed, "config", "user.email", "test@example.com")
    _git(seed, "config", "user.name", "Test")
    (seed / "tracked.txt").write_text("baseline\n", encoding="utf-8")
    _git(seed, "add", "tracked.txt")
    _git(seed, "commit", "-qm", "baseline")
    _git(seed, "branch", "-M", "main")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-qu", "origin", "main")
    return remote


def test_invalid_init_transient_is_skipped_not_failed(tmp_path: Path) -> None:
    parent = _init_parent(tmp_path)
    _write_gitmodules(parent, [("sm", "https://example.invalid/sm.git")])
    _make_invalid_transient(parent / "sm")

    done = _run(SCRIPT, parent)

    assert done.returncode == 0, done.stdout + done.stderr
    assert GUARD_MARKER in done.stdout, done.stdout
    assert "失败=0" in done.stdout, done.stdout
    assert "缺失=1" in done.stdout, done.stdout
    assert "❌" not in done.stdout, done.stdout


def test_unpushed_submodule_still_blocks(tmp_path: Path) -> None:
    parent = _init_parent(tmp_path)
    remote = _remote_with_main(tmp_path)
    _write_gitmodules(
        parent, [("sm", "https://example.invalid/sm.git"), ("sm2", str(remote))]
    )
    _make_invalid_transient(parent / "sm")

    sm2 = parent / "sm2"
    _git(parent, "clone", "-q", str(remote), "sm2")
    _git(sm2, "config", "user.email", "test@example.com")
    _git(sm2, "config", "user.name", "Test")
    (sm2 / "unpushed.txt").write_text("local only\n", encoding="utf-8")
    _git(sm2, "add", "unpushed.txt")
    _git(sm2, "commit", "-qm", "unpushed")

    done = _run(SCRIPT, parent)

    assert done.returncode == 1, done.stdout + done.stderr
    assert "sm2: 1 个未推" in done.stdout, done.stdout
    assert "待push=1" in done.stdout, done.stdout
    assert "失败=0" in done.stdout, done.stdout


def test_guard_is_load_bearing(tmp_path: Path) -> None:
    """摘掉守卫 ⇒ 同一条瞬态回到 ``failed`` 且 rc=1（否则上面那条断言可能是空转）。"""
    parent = _init_parent(tmp_path)
    _write_gitmodules(parent, [("sm", "https://example.invalid/sm.git")])
    _make_invalid_transient(parent / "sm")

    guard_line = '  if ! git -C "$sm" rev-parse --verify HEAD >/dev/null 2>&1; then'
    text = SCRIPT.read_text(encoding="utf-8")
    assert guard_line in text, "守卫条件行不在脚本里 —— 变异装置失效"
    mutated = tmp_path / "sync-mutated.sh"
    mutated.write_text(text.replace(guard_line, "  if false; then"), encoding="utf-8")

    done = _run(mutated, parent)

    assert done.returncode == 1, done.stdout + done.stderr
    assert "无法读取当前分支" in done.stdout, done.stdout
    assert "失败=1" in done.stdout, done.stdout
