import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[1]


def _run_fix_submodule_drift(*args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        ["uv", "run", "--with", "pyyaml", "python", str(WORKSPACE / "bin/gac/fix-submodule-drift.py"), *args],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_submodule_drift_detection():
    """应检测到 submodule 漂移"""
    result = _run_fix_submodule_drift("--check", "--root", str(WORKSPACE))
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["issue_count"] >= 1
    assert report["modified_count"] >= 1
    paths = [issue["path"] for issue in report["issues"]]
    assert "projects/omlxc" in paths or "projects/omo" in paths
