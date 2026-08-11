"""Tests for the Task 2 installable package skeleton."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
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


def _installed_script(name: str) -> Path:
    scripts_directory = sysconfig.get_path("scripts")
    assert scripts_directory is not None
    script = Path(scripts_directory) / name
    assert script.is_file()
    return script


def _run_installed_script(name: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(_installed_script(name)), *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        check=False,
        text=True,
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


def test_default_pytest_configuration_excludes_hardware() -> None:
    """Ordinary test runs must never invoke real-hardware smoke coverage."""
    pyproject = REPOSITORY_ROOT / "pyproject.toml"
    metadata = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert '-m "not hardware"' in metadata["tool"]["pytest"]["ini_options"]["addopts"]


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


def test_installed_omlxc_console_script_reports_its_version() -> None:
    """Run the generated script in this interpreter's scripts directory."""
    result = _run_installed_script("omlxc", "--version")

    assert result.returncode == 0
    assert result.stdout.strip() == "3.0.0a1"


def test_installed_omlxcd_console_script_reports_placeholder_json() -> None:
    """Run the generated daemon script instead of importing its module directly."""
    result = _run_installed_script("omlxcd")

    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "component": "omlxcd",
        "status": "placeholder",
        "version": "3.0.0a1",
    }
