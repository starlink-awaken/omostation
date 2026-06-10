from __future__ import annotations

import argparse
import sys

import pytest
from rich.console import Console

from cockpit import cli
from cockpit.tests.conftest import MockDataAccess


def test_research_help_includes_quarantine_option(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["workspace", "research", "--help"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "--quarantine" in captured.out


def test_cmd_research_quarantine_requires_ids(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)

    code = cli.cmd_research_quarantine(argparse.Namespace(quarantine=[]))

    output = capture.export_text()
    assert code == 1
    assert "至少提供一个研究 ID" in output


def test_cmd_research_quarantine_reports_result(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.quarantine_research = lambda ids, reason="manual quarantine": ([4, 5], [9])
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research_quarantine(argparse.Namespace(quarantine=[4, 5, 9]))

    output = capture.export_text()
    assert code == 0
    assert "已隔离 2 条研究记录" in output
    assert "4, 5" in output
    assert "未找到这些研究 ID: 9" in output
    assert "workspace research --audit" in output


def test_cmd_research_quarantine_all_missing(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.quarantine_research = lambda ids, reason="manual quarantine": ([], [1, 2])
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research_quarantine(argparse.Namespace(quarantine=[1, 2]))

    output = capture.export_text()
    assert code == 1
    assert "未找到这些研究 ID: 1, 2" in output


def test_cmd_research_quarantine_all_success(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.quarantine_research = lambda ids, reason="manual quarantine": ([1, 2], [])
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research_quarantine(argparse.Namespace(quarantine=[1, 2]))

    output = capture.export_text()
    assert code == 0
    assert "已隔离 2 条研究记录" in output
    assert "未找到这些研究 ID" not in output
