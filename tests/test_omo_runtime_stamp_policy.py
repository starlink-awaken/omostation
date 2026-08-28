"""Regression tests for immutable runtime final-tree policy checks."""

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "omo-runtime-stamp-policy.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_treeish_reports_tracked_runtime_outputs() -> None:
    result = _run("--treeish", "HEAD", "--json")

    assert result.returncode == 1, result.stderr + result.stdout
    report = json.loads(result.stdout)
    orphan_paths = {item["path"] for item in report["orphan_paths"]}
    assert "runtime/README.md" not in orphan_paths
    assert "runtime/bos-neural-mesh-owner-live-smoke.json" in orphan_paths


def test_invalid_treeish_fails_closed() -> None:
    result = _run("--treeish", "does-not-exist", "--json")

    assert result.returncode == 2
    assert "treeish" in (result.stderr + result.stdout).lower()
