"""cockpit wave2 command unit tests (no c2g subprocess required)."""

from __future__ import annotations

import argparse
from unittest.mock import patch

from cockpit.commands import wave2
from cockpit.commands.wave2 import cmd_wave2


def test_wave2_dashboard_dispatches_module():
    with patch("cockpit.commands.wave2._run_c2g_module", return_value=0) as m:
        code = cmd_wave2(argparse.Namespace(wave2_command="dashboard", pretty=True, wave2_args=[]))
        assert code == 0
        m.assert_called_once()
        assert m.call_args[0][0] == "omo._vendored.c2g.dashboard_export"
        assert "--pretty" in m.call_args[0][1]


def test_wave2_proposals_dispatch():
    with patch("cockpit.commands.wave2._run_c2g_module", return_value=0) as m:
        code = cmd_wave2(argparse.Namespace(wave2_command="proposals", pretty=False, wave2_args=["--show-apply-plan"]))
        assert code == 0
        assert m.call_args[0][0] == "omo._vendored.c2g.governance_feedback"


def test_wave2_unknown():
    code = cmd_wave2(argparse.Namespace(wave2_command="nope", pretty=False, wave2_args=[]))
    assert code == 2


def test_wave2_delegates_to_omo_vendored_module_and_preserves_exit_code(monkeypatch, tmp_path):
    seen: dict[str, object] = {}

    def fake_call(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        return 9

    monkeypatch.setattr(wave2, "_WORKSPACE", tmp_path)
    monkeypatch.setattr(wave2, "_OMO_PROJECT", "/authority/projects/omo")
    monkeypatch.setattr(wave2.subprocess, "call", fake_call)

    assert cmd_wave2(argparse.Namespace(wave2_command="dashboard", pretty=False, wave2_args=["--limit", "3"])) == 9
    assert seen["command"] == [
        "uv",
        "run",
        "--project",
        "/authority/projects/omo",
        "python",
        "-m",
        "omo._vendored.c2g.dashboard_export",
        "--limit",
        "3",
    ]
    assert seen["kwargs"]["cwd"] == str(tmp_path)


def test_wave2_rejects_non_authority_module_without_subprocess(monkeypatch):
    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("unregistered module must not be executed")

    monkeypatch.setattr(wave2.subprocess, "call", unexpected_call)
    assert wave2._run_c2g_module("os") == 2
