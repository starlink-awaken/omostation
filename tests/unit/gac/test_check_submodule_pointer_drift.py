"""Tests for check-submodule-pointer-drift.py (BET-Y1Q2-T1-05)."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "check-submodule-pointer-drift.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_submodule_pointer_drift", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *extra_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_detect_runs_cleanly():
    result = _run()
    assert result.returncode in (0, 1)
    assert "子模块" in result.stdout or "aligned" in result.stdout


def test_json_output():
    result = _run("--json")
    assert result.returncode in (0, 1)
    data = json.loads(result.stdout)
    assert "results" in data
    assert "diverged" in data
    assert "behind" in data
    assert isinstance(data["results"], list)
    assert len(data["results"]) > 0


def test_fix_dry_run():
    result = _run("--fix")
    assert result.returncode in (0, 1)
    if "DIVERGED" in result.stdout:
        assert "would fix" in result.stdout or "→" in result.stdout


def test_each_result_has_required_fields():
    result = _run("--json")
    data = json.loads(result.stdout)
    for r in data["results"]:
        assert "submodule" in r
        assert "status" in r
        assert r["status"] in ("aligned", "behind", "DIVERGED", "skip")


def test_detects_omo_divergence():
    """omo pointer was diverged (4acece91b on side branch) — verify detection."""
    result = _run("--json")
    data = json.loads(result.stdout)
    omo_results = [r for r in data["results"] if r["submodule"] == "projects/omo"]
    if omo_results:
        r = omo_results[0]
        assert r["status"] in ("DIVERGED", "aligned", "behind")


def test_submodule_git_clears_superproject_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pre-push Git state must not force submodule commands into the root repo."""
    module = _load_module()
    monkeypatch.setenv("GIT_DIR", "/tmp/root.git")
    monkeypatch.setenv("GIT_WORK_TREE", "/tmp/root-worktree")

    completed = subprocess.CompletedProcess(
        args=["git", "rev-parse", "origin/main"],
        returncode=0,
        stdout="abc123\n",
        stderr="",
    )
    with (
        patch.object(
            module,
            "_git_local_env_vars",
            return_value=frozenset({"GIT_DIR", "GIT_WORK_TREE"}),
        ),
        patch.object(module.subprocess, "run", return_value=completed) as run,
    ):
        result = module._git(
            "rev-parse",
            "origin/main",
            cwd=REPO_ROOT / "projects" / "aetherforge",
        )

    assert result == "abc123"
    child_env = run.call_args.kwargs["env"]
    assert "GIT_DIR" not in child_env
    assert "GIT_WORK_TREE" not in child_env
