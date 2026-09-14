"""Integration tests for the canonical zombie-worktree pruner.

Every test binds the Python pruner to a temporary workspace parent and never
touches the real Workspace worktree set.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLAIM_SCRIPT = ROOT / "bin" / "gac" / "gac-worktree.sh"
PRUNER_SCRIPT = ROOT / "bin" / "gac" / "prune-zombie-worktrees.py"


def _load_pruner():
    spec = importlib.util.spec_from_file_location("test_prune_zombie_worktrees_integration", PRUNER_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PRUNER = _load_pruner()

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


def test_claim_marker_blocks_pruner_enforce(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """An initialization marker prevents every destructive enforce effect."""
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    (tmp_path / "ws-sweep-test").mkdir()
    marker = tmp_path / ".ws-sweep-test.claiming"
    marker.write_text("")
    effects: list[object] = []
    monkeypatch.setattr(PRUNER, "WS_ROOT", workspace)
    monkeypatch.setattr(PRUNER, "_git", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(PRUNER, "_registered_worktrees", lambda: (True, {str(workspace)}))
    monkeypatch.setattr(PRUNER, "_claim_release", lambda session: effects.append(("release", session)))
    monkeypatch.setattr(PRUNER.subprocess, "run", lambda command, **_kwargs: effects.append(list(command)))

    assert PRUNER.main(["--enforce", "--ttl-days", "0"]) == 0

    output = capsys.readouterr().out
    assert "claim 初始化进行中" in output
    assert "实删 0" in output
    assert marker.exists()
    assert (tmp_path / "ws-sweep-test").exists()
    assert effects == []


def test_pruner_dry_run_reports_unregistered_orphan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """Dry-run reports an unregistered no-git orphan without deleting it."""
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    orphan = tmp_path / "ws-stale"
    orphan.mkdir()
    monkeypatch.setattr(PRUNER, "WS_ROOT", workspace)
    monkeypatch.setattr(PRUNER, "_git", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(PRUNER, "_registered_worktrees", lambda: (True, {str(workspace)}))

    assert PRUNER.main(["--ttl-days", "0"]) == 0

    output = capsys.readouterr().out
    assert f"僵尸: {orphan} [no-gitfile]" in output
    assert "实删 0" in output
    assert orphan.exists()


def test_pruner_scan_marks_dirty_repo_as_protected(tmp_path: Path) -> None:
    """Dirty repositories remain protected independently of age."""
    worktree = tmp_path / "ws-dirty"
    _make_aged_git_repo(worktree)
    (worktree / "dirty.txt").write_text("preserve", encoding="utf-8")

    zombies = PRUNER.scan_zombies(tmp_path, ttl_days=0)

    assert zombies == [{"path": str(worktree), "reasons": ["dirty-skip"], "skip": True}]


def test_gac_worktree_script_parses() -> None:
    """gac-worktree.sh 必须通过 bash 语法检查."""
    result = subprocess.run(
        ["bash", "-n", str(CLAIM_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_claim_stops_before_worktree_add_when_lifecycle_guard_is_held(tmp_path: Path) -> None:
    """The shell claimant and Python pruner share one atomic session guard."""
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(workspace)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(workspace),
            "remote",
            "add",
            "origin",
            "https://github.com/starlink-awaken/omostation.git",
        ],
        check=True,
    )
    guard = tmp_path / ".ws-guarded.lifecycle-lock"
    guard.mkdir()
    env = {
        **os.environ,
        "WS_ROOT": str(workspace),
        "WS_PARENT": str(tmp_path),
        "OMOSTATION_ROOT_REMOTE": "origin",
        "GIT_TERMINAL_PROMPT": "0",
        "SKIP_SUBMODULE_INIT": "1",
    }

    result = subprocess.run(
        ["bash", str(CLAIM_SCRIPT), "claim", "guarded", "codex-agent"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=30,
    )

    assert result.returncode != 0
    assert "lifecycle guard held" in result.stderr
    assert guard.is_dir()
    assert not (tmp_path / "ws-guarded").exists()
    assert (
        subprocess.run(
            ["git", "-C", str(workspace), "branch", "--list", "agent/codex-agent/guarded"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        == ""
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
