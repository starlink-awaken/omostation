"""C2G delegates use the OMO-vendored console authority."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from cockpit.commands import compass

_CANONICAL_WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
_CANONICAL_OMO_PROJECT = _CANONICAL_WORKSPACE_ROOT / "projects" / "omo"


def test_compass_delegates_to_omo_console_and_preserves_argument_and_exit_code(monkeypatch):
    seen: dict[str, object] = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        return SimpleNamespace(returncode=11)

    monkeypatch.setattr(compass.sys, "argv", ["cockpit-compass", "bet", "pitch.md"])
    monkeypatch.setenv("VIRTUAL_ENV", "/unsafe/parent-env")
    monkeypatch.setenv("PYTHONHOME", "/unsafe/python-home")
    monkeypatch.setattr(compass.subprocess, "run", fake_run)

    assert compass.main() == 11
    assert seen["command"] == [
        "uv",
        "run",
        "--project",
        str(_CANONICAL_OMO_PROJECT),
        "c2g",
        "--adapter",
        "ecos",
        "bet",
        "pitch.md",
    ]
    assert Path(seen["command"][3]).resolve() == _CANONICAL_OMO_PROJECT
    assert Path(seen["kwargs"]["cwd"]).resolve() == _CANONICAL_WORKSPACE_ROOT
    assert "VIRTUAL_ENV" not in seen["kwargs"]["env"]
    assert "PYTHONHOME" not in seen["kwargs"]["env"]


def test_cli_compass_delegates_to_omo_console_and_preserves_arguments(monkeypatch):
    from cockpit import cli

    seen: dict[str, object] = {}

    def fake_call(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        return 13

    monkeypatch.setattr(cli.sys, "argv", ["cockpit", "compass", "radar", "--machine-readable"])
    monkeypatch.setenv("VIRTUAL_ENV", "/unsafe/parent-env")
    monkeypatch.setenv("PYTHONHOME", "/unsafe/python-home")
    monkeypatch.setattr("subprocess.call", fake_call)

    assert cli.main() == 13
    assert seen["command"] == [
        "uv",
        "run",
        "--project",
        str(_CANONICAL_OMO_PROJECT),
        "c2g",
        "--adapter",
        "ecos",
        "radar",
        "--machine-readable",
    ]
    assert Path(seen["command"][3]).resolve() == _CANONICAL_OMO_PROJECT
    assert Path(seen["kwargs"]["cwd"]).resolve() == _CANONICAL_WORKSPACE_ROOT
    assert "VIRTUAL_ENV" not in seen["kwargs"]["env"]
    assert "PYTHONHOME" not in seen["kwargs"]["env"]
