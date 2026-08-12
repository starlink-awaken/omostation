"""Tests for gac-worktree.sh submodule-aware worktree removal.

Bug: git worktree remove (without --force) returns 128 on worktrees with
initialized submodules even when clean. Fix: verify clean then use --force.

Tests use real isolated git repos (parent + submodule + linked worktree).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "gac-worktree.sh"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True, text=True, check=True,
    )


def _make_child_repo(path: Path) -> None:
    """Create a minimal git repo suitable as a submodule."""
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")
    (path / "hello.txt").write_text("hello\n")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "init")


def _make_parent_with_submodule(tmp_path: Path) -> tuple[Path, Path]:
    """Create parent repo with one submodule; return (parent_dir, child_dir)."""
    child = tmp_path / "child-repo"
    _make_child_repo(child)

    parent = tmp_path / "parent-repo"
    parent.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(parent)], check=True)
    _git(parent, "config", "user.email", "t@t")
    _git(parent, "config", "user.name", "t")
    (parent / "tracked.txt").write_text("tracked\n")
    _git(parent, "add", "tracked.txt")
    # protocol.file.allow=always: needed for local submodule URLs (CVE-2022-39253 mitigation)
    subprocess.run(
        ["git", "-C", str(parent), "-c", "protocol.file.allow=always",
         "submodule", "add", "-q", str(child), "lib-sub"],
        check=True,
    )
    _git(parent, "commit", "-q", "-m", "add submodule")
    return parent, child


def _make_worktree(parent: Path, wt_path: Path, branch: str = "wt-branch") -> None:
    """Create a linked worktree and initialize submodules inside it."""
    subprocess.run(
        ["git", "-C", str(parent), "worktree", "add", str(wt_path), "-b", branch],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(wt_path), "-c", "protocol.file.allow=always",
         "submodule", "update", "--init"],
        check=True,
    )


def _make_pasw_worktree(wt_path: Path, branch: str) -> Path:
    """Create the same linked child worktree that PASW cleanup will remove."""
    pasw = wt_path / ".subtrees" / "lib-sub"
    pasw.parent.mkdir()
    subprocess.run(
        ["git", "-C", str(wt_path / "lib-sub"), "worktree", "add", "-b", branch, str(pasw)],
        check=True,
    )
    return pasw


def _run_release(
    parent: Path,
    parent_dir: Path,
    session: str,
    *,
    git_wrapper_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the actual release entry point against only the temporary repos."""
    env = {
        **os.environ,
        "WS_ROOT": str(parent),
        "WS_PARENT": str(parent_dir),
    }
    if git_wrapper_dir is not None:
        env["PATH"] = f"{git_wrapper_dir}{os.pathsep}{env['PATH']}"
    return subprocess.run(
        ["bash", str(SCRIPT), "release", session],
        cwd=parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _write_failing_git_wrapper(tmp_path: Path, condition: str, message: str) -> Path:
    """Inject one Git probe failure while delegating every other call to Git."""
    real_git = shutil.which("git")
    assert real_git
    wrapper_dir = tmp_path / "git-wrapper"
    wrapper_dir.mkdir(parents=True)
    (wrapper_dir / "git").write_text(
        "#!/bin/sh\n"
        f"if {condition}; then\n"
        f"  echo '{message}' >&2\n"
        "  exit 73\n"
        "fi\n"
        f'exec "{real_git}" "$@"\n'
    )
    (wrapper_dir / "git").chmod(0o755)
    return wrapper_dir


def _extract_verify_function() -> str:
    """Pull verify_clean_for_force_removal() source from gac-worktree.sh."""
    source = SCRIPT.read_text()
    match = re.search(
        r'(verify_clean_for_force_removal\(\)\s*\{.*?\n\})',
        source, re.DOTALL,
    )
    assert match, "verify_clean_for_force_removal not found in gac-worktree.sh"
    return match.group(1)


def _run_verify(wt_path: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Build a tiny bash script that calls the real verify function."""
    func_src = _extract_verify_function()
    script = (
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        'export PASW_SUBTREE_DIR=".subtrees"\n'
        'export PASW_ISOLATED_SUBS=""\n'
        f"{func_src}\n"
        f'verify_clean_for_force_removal "{wt_path}"\n'
    )
    script_file = tmp_path / "run_verify.sh"
    script_file.write_text(script)
    return subprocess.run(
        ["bash", str(script_file)],
        capture_output=True, text=True, check=False,
    )


# ── Static tests ─────────────────────────────────────────────────────────────

def test_script_has_verify_function() -> None:
    source = SCRIPT.read_text()
    assert "verify_clean_for_force_removal()" in source


def test_release_uses_force_with_verify() -> None:
    source = SCRIPT.read_text()
    release_section = source[source.index("  release)"):source.index("  merge)")]
    assert "verify_clean_for_force_removal" in release_section
    assert "git worktree remove --force" in release_section
    # Must NOT have plain (non-force) remove in release
    assert 'git worktree remove "$wt" 2>&1' not in release_section


def test_merge_uses_force_with_verify() -> None:
    source = SCRIPT.read_text()
    merge_section = source[source.index("  merge)"):]
    assert "verify_clean_for_force_removal" in merge_section
    assert "git worktree remove --force" in merge_section


def test_verified_pasw_removal_has_no_rm_fallback() -> None:
    """The release-only PASW remover must fail rather than delete files itself."""
    source = SCRIPT.read_text()
    helper = source[source.index("remove_verified_pasw()") : source.index('case "$cmd" in')]
    assert "git -C \"$wt/$sub\" worktree remove --force \"$pasw_wt\"" in helper
    assert "rm -rf" not in helper


def test_script_bash_syntax_ok() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr


# ── Dynamic tests: reproduce the bug ─────────────────────────────────────────

def test_plain_remove_fails_on_initialized_submodule(tmp_path: Path) -> None:
    """Reproduce the bug: plain git worktree remove returns non-zero (128)
    for a clean worktree with an initialized submodule."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    wt = tmp_path / "wt-bug"
    _make_worktree(parent, wt)

    result = subprocess.run(
        ["git", "-C", str(parent), "worktree", "remove", str(wt)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0, (
        "Expected plain remove to fail on worktree with initialized submodule; "
        "git may have fixed the underlying issue — update this test."
    )
    # Worktree must still exist (refused)
    assert wt.exists()
    # Clean up with --force
    subprocess.run(
        ["git", "-C", str(parent), "worktree", "remove", "--force", str(wt)],
        check=False,
    )


def test_force_remove_succeeds_on_clean(tmp_path: Path) -> None:
    """--force removal succeeds on clean worktree with initialized submodule."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    wt = tmp_path / "wt-force"
    _make_worktree(parent, wt, branch="wt-force-br")

    result = subprocess.run(
        ["git", "-C", str(parent), "worktree", "remove", "--force", str(wt)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not wt.exists()


# ── Dynamic tests: verify_clean_for_force_removal ────────────────────────────

def test_verify_succeeds_on_clean_worktree(tmp_path: Path) -> None:
    """Verify function returns 0 for clean worktree + initialized submodule."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    wt = tmp_path / "wt-clean"
    _make_worktree(parent, wt, branch="wt-clean-br")

    result = _run_verify(wt, tmp_path)
    assert result.returncode == 0, f"Expected clean, got: {result.stderr}"


def test_verify_fails_on_untracked_root(tmp_path: Path) -> None:
    """Verify function rejects untracked files in root."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    wt = tmp_path / "wt-untracked-root"
    _make_worktree(parent, wt, branch="wt-ut-root-br")
    (wt / "stray.txt").write_text("oops")

    result = _run_verify(wt, tmp_path)
    assert result.returncode == 1
    assert "root has changes" in result.stderr.lower()


def test_verify_fails_on_root_staged_and_unstaged_changes(tmp_path: Path) -> None:
    """The force-removal guard itself rejects both root diff states."""
    parent, _ = _make_parent_with_submodule(tmp_path)

    unstaged = tmp_path / "wt-root-unstaged"
    _make_worktree(parent, unstaged, branch="wt-root-unstaged-br")
    (unstaged / "tracked.txt").write_text("unstaged\n")
    assert _run_verify(unstaged, tmp_path).returncode == 1

    staged = tmp_path / "wt-root-staged"
    _make_worktree(parent, staged, branch="wt-root-staged-br")
    (staged / "tracked.txt").write_text("staged\n")
    _git(staged, "add", "tracked.txt")
    assert _run_verify(staged, tmp_path).returncode == 1


def test_verify_fails_on_untracked_submodule(tmp_path: Path) -> None:
    """Verify function rejects untracked files inside a submodule."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    wt = tmp_path / "wt-untracked-sub"
    _make_worktree(parent, wt, branch="wt-ut-sub-br")
    (wt / "lib-sub" / "stray.txt").write_text("oops")

    result = _run_verify(wt, tmp_path)
    assert result.returncode == 1
    assert "submodule lib-sub has changes" in result.stderr.lower()


def test_verify_fails_on_dirty_submodule(tmp_path: Path) -> None:
    """Verify function rejects tracked (staged) changes in a submodule."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    wt = tmp_path / "wt-dirty-sub"
    _make_worktree(parent, wt, branch="wt-dirty-br")
    (wt / "lib-sub" / "hello.txt").write_text("modified\n")
    _git(wt / "lib-sub", "add", "hello.txt")

    result = _run_verify(wt, tmp_path)
    assert result.returncode == 1
    assert "submodule lib-sub has changes" in result.stderr.lower()


def test_verify_fails_on_modified_submodule_not_staged(tmp_path: Path) -> None:
    """Verify function rejects unstaged modifications in a submodule."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    wt = tmp_path / "wt-mod-sub"
    _make_worktree(parent, wt, branch="wt-mod-br")
    (wt / "lib-sub" / "hello.txt").write_text("modified but not staged\n")

    result = _run_verify(wt, tmp_path)
    assert result.returncode == 1


# ── Dynamic tests: full clean cycle (verify + force) ─────────────────────────

def test_clean_cycle_verify_then_force_remove(tmp_path: Path) -> None:
    """End-to-end: verify passes, then --force remove succeeds and worktree is gone."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    wt = tmp_path / "wt-cycle"
    _make_worktree(parent, wt, branch="wt-cycle-br")

    # Step 1: verify clean
    verify_result = _run_verify(wt, tmp_path)
    assert verify_result.returncode == 0, verify_result.stderr

    # Step 2: --force remove (should succeed because verified clean)
    remove_result = subprocess.run(
        ["git", "-C", str(parent), "worktree", "remove", "--force", str(wt)],
        capture_output=True, text=True, check=False,
    )
    assert remove_result.returncode == 0, remove_result.stderr
    assert not wt.exists()


def test_dirty_submodule_refuses_and_remains(tmp_path: Path) -> None:
    """Dirty submodule: verify refuses, worktree is NOT removed (remains intact)."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    wt = tmp_path / "wt-refuse"
    _make_worktree(parent, wt, branch="wt-refuse-br")
    (wt / "lib-sub" / "extra.txt").write_text("untracked junk")

    # Verify fails
    verify_result = _run_verify(wt, tmp_path)
    assert verify_result.returncode == 1

    # Worktree still exists (not removed)
    assert wt.exists()
    assert (wt / "lib-sub" / "extra.txt").exists()


# ── Dynamic tests: actual release entry point ───────────────────────────────

def test_release_removes_clean_initialized_submodule_and_pasw(tmp_path: Path) -> None:
    """release accepts clean ordinary/PASW child worktrees and removes the root."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    session = "clean-release"
    wt = tmp_path / f"ws-{session}"
    _make_worktree(parent, wt, branch="wt-clean-release")
    pasw = _make_pasw_worktree(wt, branch="pasw-clean-release")

    result = _run_release(parent, tmp_path, session)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "worktree 释放" in result.stdout
    assert not wt.exists()
    assert not pasw.exists()


def test_release_refuses_dirty_or_untracked_submodule_and_keeps_worktree(tmp_path: Path) -> None:
    """release must not reach --force when ordinary and PASW children are dirty."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    session = "refuse-release"
    wt = tmp_path / f"ws-{session}"
    _make_worktree(parent, wt, branch="wt-refuse-release")
    pasw = _make_pasw_worktree(wt, branch="pasw-refuse-release")
    (wt / "lib-sub" / "ordinary-untracked.txt").write_text("ordinary untracked\n")
    (pasw / "untracked.txt").write_text("PASW untracked\n")

    result = _run_release(parent, tmp_path, session)

    assert result.returncode != 0
    assert "拒绝释放" in result.stderr
    assert wt.exists(), "release must preserve a dirty root worktree"
    assert (wt / "lib-sub" / "ordinary-untracked.txt").exists()
    assert (pasw / "untracked.txt").exists()


def test_release_aborts_when_verified_pasw_removal_fails(tmp_path: Path) -> None:
    """A Git removal failure must retain both PASW and root worktree; no rm fallback."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    session = "pasw-remove-failure"
    wt = tmp_path / f"ws-{session}"
    _make_worktree(parent, wt, branch="wt-pasw-remove-failure")
    pasw = _make_pasw_worktree(wt, branch="pasw-remove-failure")
    wrapper_dir = _write_failing_git_wrapper(
        tmp_path,
        f'[ "$1" = "-C" ] && [ "$2" = "{wt / "lib-sub"}" ] && '
        f'[ "$3" = "worktree" ] && [ "$4" = "remove" ] && '
        f'[ "$5" = "--force" ] && [ "$6" = "{pasw}" ]',
        "simulated PASW removal failure",
    )
    (wrapper_dir / "git").chmod(0o755)

    result = _run_release(parent, tmp_path, session, git_wrapper_dir=wrapper_dir)

    assert result.returncode != 0
    assert "PASW worktree 清理失败" in result.stderr
    assert wt.exists(), "root worktree must remain after PASW cleanup failure"
    assert pasw.exists(), "PASW worktree must remain after Git refuses removal"


def test_release_refuses_when_root_status_probe_fails(tmp_path: Path) -> None:
    """An unreadable root status is unsafe, not evidence of a clean worktree."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    session = "root-status-failure"
    wt = tmp_path / f"ws-{session}"
    _make_worktree(parent, wt, branch="wt-root-status-failure")
    wrapper_dir = _write_failing_git_wrapper(
        tmp_path,
        f'[ "$1" = "-C" ] && [ "$2" = "{wt}" ] && '
        '[ "$3" = "status" ] && [ "$4" = "--porcelain" ]',
        "simulated root status failure",
    )

    result = _run_release(parent, tmp_path, session, git_wrapper_dir=wrapper_dir)

    assert result.returncode != 0
    assert "无法检查 root worktree 状态" in result.stderr
    assert wt.exists()


def test_release_refuses_when_submodule_enumeration_or_status_probe_fails(tmp_path: Path) -> None:
    """Failed submodule enumeration/status probes must preserve the root worktree."""
    parent, _ = _make_parent_with_submodule(tmp_path)
    for suffix, condition, expected in (
        (
            "enumeration",
            (
                f'[ "$1" = "-C" ] && [ "$2" = "{tmp_path / "ws-sub-enumeration"}" ] && '
                '[ "$3" = "submodule" ] && [ "$4" = "foreach" ]'
            ),
            "无法枚举已初始化子模块",
        ),
        (
            "status",
            (
                f'[ "$1" = "-C" ] && [ "$2" = "{tmp_path / "ws-sub-status" / "lib-sub"}" ] && '
                '[ "$3" = "status" ] && [ "$4" = "--porcelain" ]'
            ),
            "无法检查子模块状态",
        ),
    ):
        session = f"sub-{suffix}"
        wt = tmp_path / f"ws-sub-{suffix}"
        _make_worktree(parent, wt, branch=f"wt-sub-{suffix}")
        wrapper_dir = _write_failing_git_wrapper(tmp_path / suffix, condition, f"simulated {suffix} failure")

        result = _run_release(parent, tmp_path, session, git_wrapper_dir=wrapper_dir)

        assert result.returncode != 0
        assert expected in result.stderr
        assert wt.exists()
