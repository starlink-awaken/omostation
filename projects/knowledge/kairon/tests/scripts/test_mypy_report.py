"""Behavioral tests for the deterministic mypy regression report."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "mypy_report.py"
MODULE_SPEC = importlib.util.spec_from_file_location("mypy_report", MODULE_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
report = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = report
MODULE_SPEC.loader.exec_module(report)


def test_count_mypy_errors_disables_incremental_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Every per-package invocation must be cold-cache deterministic."""

    observed: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["cwd"] = kwargs["cwd"]
        observed["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 1, stdout="Found 7 errors in 1 file", stderr="")

    monkeypatch.setattr(report.subprocess, "run", fake_run)

    assert report.count_mypy_errors(tmp_path / "eidos") == 7
    assert "--no-incremental" in observed["command"]
    assert observed["cwd"] == str(tmp_path / "eidos")
    assert observed["env"]["MYPYPATH"] == "src"  # type: ignore[index]


def test_count_mypy_errors_fails_closed_for_unavailable_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A missing runner must not be interpreted as zero mypy errors."""

    def missing_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    monkeypatch.setattr(report.subprocess, "run", missing_runner)

    with pytest.raises(FileNotFoundError):
        report.count_mypy_errors(tmp_path / "missing")


def test_count_mypy_errors_fails_closed_for_unparseable_command_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A failed command without a mypy count cannot become a synthetic zero."""

    def unavailable_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 2, stdout="", stderr="mypy command unavailable")

    monkeypatch.setattr(report.subprocess, "run", unavailable_runner)

    with pytest.raises(RuntimeError, match="mypy command unavailable"):
        report.count_mypy_errors(tmp_path / "unavailable")
