#!/usr/bin/env python3
"""BET-Y1Q1-T1-08 bump-fast timing and functional checks."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "gac-worktree.sh"


def _git_env() -> dict[str, str]:
    return {
        **os.environ,
        "GIT_ALLOW_PROTOCOL": "file",
        "GIT_AUTHOR_NAME": "gac test",
        "GIT_AUTHOR_EMAIL": "gac-test@example.invalid",
        "GIT_COMMITTER_NAME": "gac test",
        "GIT_COMMITTER_EMAIL": "gac-test@example.invalid",
    }


def _run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=check,
        env=_git_env(),
    )


def _make_repo_with_submodule(tmp: Path) -> tuple[Path, str]:
    """Create a local repository with a submodule and return its initial SHA."""
    sub_repo = tmp / "sub_remote.git"
    sub_repo.mkdir()
    _run(["git", "init", "--bare", str(sub_repo)], cwd=tmp)

    sub_work = tmp / "sub_work"
    sub_work.mkdir()
    _run(["git", "init", "-b", "main", str(sub_work)], cwd=tmp)
    (sub_work / "README.md").write_text("# sub\n", encoding="utf-8")
    _run(["git", "add", "."], cwd=sub_work)
    _run(["git", "commit", "-m", "init"], cwd=sub_work)
    _run(["git", "push", str(sub_repo), "main"], cwd=sub_work)
    initial_sha = _run(["git", "rev-parse", "HEAD"], cwd=sub_work).stdout.strip()

    root = tmp / "root"
    root.mkdir()
    _run(["git", "init", "-b", "main", str(root)], cwd=tmp)
    (root / "README.md").write_text("# root\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "project-registry.yaml").write_text("projects: {}\n", encoding="utf-8")
    _run(["git", "add", "."], cwd=root)
    _run(["git", "commit", "-m", "init"], cwd=root)
    _run(["git", "submodule", "add", str(sub_repo), "projects/sub"], cwd=root)
    _run(["git", "commit", "-am", "add sub"], cwd=root)
    return root, initial_sha


def test_bump_fast_timing() -> None:
    """The local ls-remote plus cacheinfo path should remain below two seconds."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        root, _ = _make_repo_with_submodule(tmp)

        start = time.monotonic()
        result = _run(
            ["bash", str(SCRIPT), "bump-fast", "projects/sub", "--latest-main"],
            cwd=root,
        )
        elapsed = time.monotonic() - start

        assert result.returncode == 0, f"bump-fast failed: {result.stderr}"
        assert elapsed < 2.0, f"bump-fast took {elapsed:.2f}s; expected < 2s"


def test_bump_fast_fail_closed() -> None:
    """An unreachable SHA must be rejected."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        root, initial_sha = _make_repo_with_submodule(tmp)

        fake_sha = "deadbeef" * 5
        result = _run(
            ["bash", str(SCRIPT), "bump-fast", "projects/sub", "--sha", fake_sha],
            cwd=root,
            check=False,
        )
        assert result.returncode != 0
        index_sha = _run(["git", "ls-files", "-s", "--", "projects/sub"], cwd=root).stdout.split()[1]
        assert index_sha == initial_sha


def test_bump_fast_interface() -> None:
    """The command should reject a missing submodule argument with usage guidance."""
    result = _run(["bash", str(SCRIPT), "bump-fast"], cwd=ROOT, check=False)
    assert result.returncode != 0
    assert "用法" in result.stdout or "用法" in result.stderr
