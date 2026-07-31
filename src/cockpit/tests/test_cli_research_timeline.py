from __future__ import annotations

import argparse
import sys

import pytest
from rich.console import Console

from cockpit import cli
from cockpit.tests.conftest import MockDataAccess


def test_research_help_includes_timeline_option(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["workspace", "research", "--help"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "--timeline" in captured.out


def test_cmd_research_timeline_renders_events(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.get_research = lambda research_id: {
        "id": 12,
        "topic": "Digest: Transformer Overview + Transformer In Vision",
        "summary": "共同关注: Transformer、Vision",
        "created_at": 1710000000.0,
        "source_count": 8,
    }
    mock.get_research_timeline = lambda research_id: [
        {"event_type": "created", "created_at": 1710000000.0, "description": "研究创建"},
        {"event_type": "derived_from", "created_at": 1710000100.0, "description": "由 1,2 派生 (digest)"},
        {"event_type": "published", "created_at": 1710000200.0, "description": "发布为 brief: /tmp/report.md"},
    ]
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_timeline")(argparse.Namespace(timeline=12))

    output = capture.export_text()
    assert code == 0
    assert "研究 Timeline" in output
    assert "研究创建" in output
    assert "由 1,2 派生 (digest)" in output
    assert "发布为 brief" in output


def test_cmd_research_timeline_not_found(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.get_research = lambda research_id: None
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_timeline")(argparse.Namespace(timeline=99))

    output = capture.export_text()
    assert code == 1
    assert "未找到" in output


def test_cmd_research_timeline_with_agent(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.get_research = lambda research_id: {
        "id": 7,
        "topic": "Agent Topic",
        "summary": "由 Agent 处理",
        "created_at": 1710000000.0,
        "source_count": 2,
        "agent": "Alice",
    }
    mock.get_research_timeline = lambda research_id: [
        {"event_type": "created", "created_at": 1710000000.0, "description": "研究创建"},
        {"event_type": "agent_assigned", "created_at": 1710000100.0, "description": "处理 Agent 标记为: Alice"},
    ]
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_timeline")(argparse.Namespace(timeline=7))

    output = capture.export_text()
    assert code == 0
    assert "Alice" in output


def test_cmd_research_timeline_empty_events(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.get_research = lambda research_id: {
        "id": 8,
        "topic": "Fresh Topic",
        "summary": "刚创建的记录",
        "created_at": 1710000000.0,
        "source_count": 0,
    }
    mock.get_research_timeline = lambda research_id: []
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_timeline")(argparse.Namespace(timeline=8))

    output = capture.export_text()
    assert code == 0
    assert "研究 Timeline" in output
