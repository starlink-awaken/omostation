"""Tests for Shell completion generator (BET-Y1Q4-T8-16)."""

import json

from cockpit.cli import main
from cockpit.domain.exit_codes import ExitCode


def test_completion_bash(capsys):
    rc = main(["completion", "bash"])
    assert rc == ExitCode.SUCCESS
    captured = capsys.readouterr()
    assert "_cockpit_completions()" in captured.out
    assert "complete -F _cockpit_completions cockpit" in captured.out
    assert "governance" in captured.out
    assert "system" in captured.out


def test_completion_zsh(capsys):
    rc = main(["completion", "zsh"])
    assert rc == ExitCode.SUCCESS
    captured = capsys.readouterr()
    assert "#compdef cockpit" in captured.out
    assert "_arguments" in captured.out
    assert "_describe" in captured.out


def test_completion_fish(capsys):
    rc = main(["completion", "fish"])
    assert rc == ExitCode.SUCCESS
    captured = capsys.readouterr()
    assert "complete -c cockpit" in captured.out
    assert "__fish_seen_subcommand_from" in captured.out


def test_completion_invalid_shell(capsys):
    import pytest

    with pytest.raises(SystemExit) as excinfo:
        main(["completion", "powershell", "--json"])
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is False
    assert "invalid choice" in data["error"] or "powershell" in data["error"]
    assert data["exit_code"] == 2


def test_completion_dry_run_json(capsys):
    rc = main(["completion", "zsh", "--dry-run", "--json"])
    assert rc == ExitCode.SUCCESS
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["dry_run"] is True
    assert data["shell"] == "zsh"
    assert data["ready"] is True
