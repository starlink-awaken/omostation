"""CLI behavior contract: ExitCode 0..5, ANSI purity, trace_id (BET-Y1Q4-T8-12)."""

from __future__ import annotations

import json
import os
from io import StringIO

import pytest

from cockpit.domain.exit_codes import ExitCode
from cockpit.logger import _TRACE_ID_VAR, configure_logging, get_or_create_trace_id
from cockpit.output import ansi_free_print, get_console, json_print


ANSI_ESC = "\x1b"


def test_exit_code_contract_values():
    assert ExitCode.SUCCESS == 0
    assert ExitCode.GENERAL_FAILURE == 1
    assert ExitCode.USAGE_ERROR == 2
    assert ExitCode.PERMISSION_DENIED == 3
    assert ExitCode.RESOURCE_NOT_FOUND == 4
    assert ExitCode.UPSTREAM_ERROR == 5
    # Compatibility aliases stay on the same integers.
    assert ExitCode.GENERAL_ERROR == ExitCode.GENERAL_FAILURE
    assert ExitCode.INVALID_ARGS == ExitCode.USAGE_ERROR
    assert ExitCode.SERVICE_UNAVAILABLE == ExitCode.UPSTREAM_ERROR
    assert {int(code) for code in (
        ExitCode.SUCCESS,
        ExitCode.GENERAL_FAILURE,
        ExitCode.USAGE_ERROR,
        ExitCode.PERMISSION_DENIED,
        ExitCode.RESOURCE_NOT_FOUND,
        ExitCode.UPSTREAM_ERROR,
    )} == {0, 1, 2, 3, 4, 5}


def test_get_console_force_json_has_no_ansi():
    buf = StringIO()
    console = get_console(force_json=True, file=buf)
    console.print("[bold red]danger[/] [cyan]info[/]")
    out = buf.getvalue()
    assert ANSI_ESC not in out
    assert "danger" in out
    assert "info" in out


def test_json_print_envelope_includes_trace_id_and_zero_ansi(capsys, monkeypatch):
    monkeypatch.setenv(_TRACE_ID_VAR, "trc-contract-test01")
    json_print({"ok": False, "error": "boom", "exit_code": int(ExitCode.USAGE_ERROR)})
    captured = capsys.readouterr()
    assert ANSI_ESC not in captured.out
    payload = json.loads(captured.out)
    assert payload["ok"] is False
    assert payload["exit_code"] == 2
    assert payload["trace_id"] == "trc-contract-test01"


def test_ansi_free_print_is_plain(capsys):
    ansi_free_print("[red]not-markup[/]")
    assert capsys.readouterr().out.strip() == "[red]not-markup[/]"


def test_configure_logging_injects_trace_id(monkeypatch):
    monkeypatch.delenv(_TRACE_ID_VAR, raising=False)
    configure_logging(verbose=True, as_json=True, trace_id="trc-log-fixed99")
    assert os.environ[_TRACE_ID_VAR] == "trc-log-fixed99"
    assert get_or_create_trace_id() == "trc-log-fixed99"


def test_cli_json_unknown_command_stdout_is_ansi_free_and_traced(monkeypatch, capsys):
    """End-to-end: cockpit main --json unknown → pure JSON + ExitCode.USAGE_ERROR."""
    monkeypatch.setenv(_TRACE_ID_VAR, "trc-cli-e2e0001")
    from cockpit import cli as cli_mod
    from cockpit.output import apply_machine_consoles

    apply_machine_consoles(cli_mod)

    with pytest.raises(SystemExit) as excinfo:
        cli_mod.main(["--json", "definitely-not-a-real-command-xyz"])
    assert excinfo.value.code == int(ExitCode.INVALID_ARGS)

    out = capsys.readouterr().out
    assert ANSI_ESC not in out
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload["ok"] is False
    assert payload["exit_code"] == int(ExitCode.INVALID_ARGS)
    assert payload["trace_id"] == "trc-cli-e2e0001"
