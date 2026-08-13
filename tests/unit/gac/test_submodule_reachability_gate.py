from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "ssot" / "submodule-reachability-gate.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("submodule_reachability_gate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worktree_source_falls_back_to_index_for_uninitialized_submodule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    module.WORKSPACE = tmp_path
    (tmp_path / "projects" / "runtime").mkdir(parents=True)
    expected = "1206c68abb7a1904808750cee42aa6136fb686cf"

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        assert cmd[:3] == ["git", "ls-files", "-s"]
        return subprocess.CompletedProcess(cmd, 0, f"160000 {expected} 0\tprojects/runtime\n", "")

    monkeypatch.setattr(module, "run", fake_run)

    assert module.gitlink_sha("projects/runtime", "worktree") == expected


def test_remote_contains_accepts_uninitialized_submodule_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    module.WORKSPACE = tmp_path
    (tmp_path / "projects" / "runtime").mkdir(parents=True)
    monkeypatch.setattr(
        module,
        "run",
        lambda *_args, **_kwargs: pytest.fail("must not run git inside an uninitialized submodule"),
    )

    ok, detail = module.remote_contains("projects/runtime", "deadbeef", fetch=False)

    assert ok is True
    assert "not initialized" in detail


def test_remote_contains_rejects_feature_only_commit_when_main_is_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    module.WORKSPACE = tmp_path
    submodule = tmp_path / "projects" / "runtime"
    (submodule / ".git").mkdir(parents=True)
    sha = "a" * 40

    def fake_run(
        cmd: list[str], *, cwd: Path = tmp_path, check: bool = False
    ) -> subprocess.CompletedProcess[str]:
        del check
        if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        if cmd == ["git", "branch", "-r", "--contains", sha]:
            return subprocess.CompletedProcess(cmd, 0, "  origin/agent/personal-feature\n", "")
        if cmd == ["git", "merge-base", "--is-ancestor", sha, "refs/remotes/origin/main"]:
            return subprocess.CompletedProcess(cmd, 1, "", "")
        pytest.fail(f"unexpected command in {cwd}: {cmd}")

    monkeypatch.setattr(module, "run", fake_run)

    ok, detail = module.remote_contains(
        "projects/runtime", sha, fetch=False, require_main=True
    )

    assert ok is False
    assert detail == "not contained in refs/remotes/origin/main"


def test_remote_contains_accepts_main_ancestor_when_main_is_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    module.WORKSPACE = tmp_path
    submodule = tmp_path / "projects" / "runtime"
    (submodule / ".git").mkdir(parents=True)
    sha = "b" * 40

    def fake_run(
        cmd: list[str], *, cwd: Path = tmp_path, check: bool = False
    ) -> subprocess.CompletedProcess[str]:
        del check
        if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        if cmd == ["git", "merge-base", "--is-ancestor", sha, "refs/remotes/origin/main"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        pytest.fail(f"unexpected command in {cwd}: {cmd}")

    monkeypatch.setattr(module, "run", fake_run)

    ok, detail = module.remote_contains(
        "projects/runtime", sha, fetch=False, require_main=True
    )

    assert ok is True
    assert detail == "refs/remotes/origin/main"
