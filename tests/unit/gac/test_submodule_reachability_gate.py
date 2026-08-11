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
