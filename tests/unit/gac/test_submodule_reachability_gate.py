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


@pytest.mark.parametrize(
    ("source", "current_sha", "expected"),
    [
        ("head", "a" * 40, set()),
        ("index", "b" * 40, {"projects/runtime"}),
        ("worktree", "c" * 40, {"projects/runtime"}),
    ],
)
def test_changed_submodules_compares_the_selected_source(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    current_sha: str,
    expected: set[str],
) -> None:
    module = _load_module()
    base_sha = "a" * 40
    monkeypatch.setattr(module, "submodule_paths", lambda: ["projects/runtime"])
    monkeypatch.setattr(
        module,
        "gitlink_sha",
        lambda path, selected_source: (
            current_sha
            if (path, selected_source) == ("projects/runtime", source)
            else pytest.fail("unexpected gitlink lookup")
        ),
    )

    def fake_run(cmd: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        if cmd[:4] == ["git", "rev-parse", "--verify", "--quiet"]:
            return subprocess.CompletedProcess(cmd, 0, base_sha + "\n", "")
        if cmd == ["git", "ls-tree", "origin/main", "--", "projects/runtime"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                f"160000 commit {base_sha}\tprojects/runtime\n",
                "",
            )
        pytest.fail(f"unexpected command: {cmd}")

    monkeypatch.setattr(module, "run", fake_run)

    assert module.changed_submodules("origin/main", source) == expected


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


def test_remote_contains_reports_main_ancestry_query_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    module.WORKSPACE = tmp_path
    submodule = tmp_path / "projects" / "runtime"
    (submodule / ".git").mkdir(parents=True)
    sha = "c" * 40

    def fake_run(
        cmd: list[str], *, cwd: Path = tmp_path, check: bool = False
    ) -> subprocess.CompletedProcess[str]:
        del check
        if cmd == ["git", "rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        if cmd == ["git", "merge-base", "--is-ancestor", sha, "refs/remotes/origin/main"]:
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: bad revision")
        pytest.fail(f"unexpected command in {cwd}: {cmd}")

    monkeypatch.setattr(module, "run", fake_run)

    ok, detail = module.remote_contains(
        "projects/runtime", sha, fetch=False, require_main=True
    )

    assert ok is False
    assert detail == "main ancestry query failed: fatal: bad revision"
