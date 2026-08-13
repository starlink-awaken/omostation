"""Tests for the Task 2 installable package skeleton."""

from __future__ import annotations

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
    assert "3.0.0a1" in result.stdout.strip()


def test_daemon_module_exposes_private_uds_help() -> None:
    """The daemon module exposes its real Task 7 Unix-socket entry point."""
    result = _run_module("omlxc.daemon", "--help")

    assert result.returncode == 0
    assert "Unix Socket" in result.stdout


def test_installed_omlxc_console_script_reports_its_version() -> None:
    """Run the generated script in this interpreter's scripts directory."""
    result = _run_installed_script("omlxc", "--version")

    assert result.returncode == 0
    assert "3.0.0a1" in result.stdout.strip()


def test_installed_omlxcd_console_script_exposes_private_uds_help() -> None:
    """Run the installed Task 7 daemon entry without binding a real socket."""
    result = _run_installed_script("omlxcd", "--help")

    assert result.returncode == 0
    assert "Unix Socket" in result.stdout
