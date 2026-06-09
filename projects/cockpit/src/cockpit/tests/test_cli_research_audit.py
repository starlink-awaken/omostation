from __future__ import annotations

import argparse
import sys

import pytest
from rich.console import Console

from cockpit import cli
from cockpit.tests.conftest import MockDataAccess


def test_research_help_includes_audit_option(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["workspace", "research", "--help"])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "--audit" in captured.out


def test_cmd_research_audit_reports_no_issues(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.list_research = lambda limit=200: [
        {"id": 1, "topic": "healthy topic", "summary": "good summary", "created_at": 1710000000.0, "source_count": 2},
    ]
    mock.get_research = lambda research_id: {
        "id": 1,
        "topic": "healthy topic",
        "summary": "good summary",
        "full_text": "useful content",
        "created_at": 1710000000.0,
        "source_count": 2,
        "follow_ups": [],
    }
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research_audit(argparse.Namespace(audit=True, limit=10))

    output = capture.export_text()
    assert code == 0
    assert "未发现可疑研究记录" in output


def test_cmd_research_audit_flags_traceback_records(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.list_research = lambda limit=200: [
        {
            "id": 10,
            "topic": "broken topic",
            "summary": "Traceback (most recent call last): ...",
            "created_at": 1710000000.0,
            "source_count": 3,
        },
        {"id": 11, "topic": "healthy topic", "summary": "good summary", "created_at": 1710000100.0, "source_count": 2},
    ]

    def fake_get(research_id: int):
        if research_id == 10:
            return {
                "id": 10,
                "topic": "broken topic",
                "summary": "Traceback (most recent call last): ...",
                "full_text": "Traceback (most recent call last):\nModuleNotFoundError: x",
                "created_at": 1710000000.0,
                "source_count": 3,
                "follow_ups": [],
            }
        return {
            "id": 11,
            "topic": "healthy topic",
            "summary": "good summary",
            "full_text": "useful content",
            "created_at": 1710000100.0,
            "source_count": 2,
            "follow_ups": [],
        }

    mock.get_research = fake_get
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research_audit(argparse.Namespace(audit=True, limit=10))

    output = capture.export_text()
    assert code == 0
    assert "发现 1 条可疑研究记录" in output
    assert "broken topic" in output
    assert "traceback / import error" in output.lower()
    assert "workspace research --open 10" in output


def test_cmd_research_audit_flags_empty_content_records(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.list_research = lambda limit=200: [
        {"id": 12, "topic": "empty result", "summary": "", "created_at": 1710000200.0, "source_count": 0},
    ]
    mock.get_research = lambda research_id: {
        "id": 12,
        "topic": "empty result",
        "summary": "",
        "full_text": "   ",
        "created_at": 1710000200.0,
        "source_count": 0,
        "follow_ups": [],
    }
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research_audit(argparse.Namespace(audit=True, limit=10))

    output = capture.export_text()
    assert code == 0
    assert "empty result" in output
    assert "empty content" in output.lower()


def test_cmd_research_audit_no_full_text_with_summary(monkeypatch):
    """数据不一致：summary 存在但 full_text 为空 → 标记 'empty content' (line 49)"""
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.list_research = lambda limit=200: [
        {"id": 13, "topic": "summary only", "created_at": 1710000300.0, "source_count": 1},
    ]
    mock.get_research = lambda research_id: {
        "id": 13,
        "topic": "summary only",
        "summary": "only summary exists",
        "full_text": "",
        "created_at": 1710000300.0,
        "source_count": 1,
        "follow_ups": [],
    }
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research_audit(argparse.Namespace(audit=True, limit=10))

    output = capture.export_text()
    assert code == 0
    assert "summary only" in output
    assert "empty content" in output.lower()


def test_cmd_research_audit_skips_none_record(monkeypatch):
    """get_research 返回 None 时跳过 (line 622)"""
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.list_research = lambda limit=200: [
        {"id": 99, "topic": "ghost record", "created_at": 1710000400.0, "source_count": 0},
    ]
    mock.get_research = lambda research_id: None
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research_audit(argparse.Namespace(audit=True, limit=10))

    output = capture.export_text()
    assert code == 0
    assert "未发现可疑研究记录" in output
