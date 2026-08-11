"""Tests for the Task 2 installable package skeleton."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[2]


def _run_module(module: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ | {"PYTHONPATH": str(REPOSITORY_ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", module, *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        check=False,
        text=True,
        env=environment,
    )


def test_project_metadata_declares_the_v3_package_and_console_scripts() -> None:
    """The build metadata installs both public v3 command names."""
    pyproject = REPOSITORY_ROOT / "pyproject.toml"
    assert pyproject.is_file()

    metadata = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert metadata["project"]["version"] == "3.0.0a1"
    assert metadata["project"]["requires-python"] == ">=3.13,<3.14"
    assert metadata["project"]["scripts"] == {
        "omlxc": "omlxc.cli:main",
        "omlxcd": "omlxc.daemon:main",
    }


def test_package_exposes_the_v3_alpha_version() -> None:
    """The importable package is the single source for the release version."""
    result = _run_module("omlxc", "--version")

    assert result.returncode == 0
    assert result.stdout.strip() == "3.0.0a1"


def test_daemon_placeholder_reports_its_unimplemented_state() -> None:
    """The daemon entry point does not imply that a daemon API exists yet."""
    result = _run_module("omlxc.daemon")

    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "component": "omlxcd",
        "status": "placeholder",
        "version": "3.0.0a1",
    }
