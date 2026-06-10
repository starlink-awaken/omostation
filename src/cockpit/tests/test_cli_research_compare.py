from __future__ import annotations

import argparse
import sys

import pytest
from rich.console import Console

from cockpit import cli
from cockpit.tests.conftest import MockDataAccess


def test_research_help_includes_compare_option(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["workspace", "research", "--help"])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "--compare" in captured.out


def test_cmd_research_compare_requires_at_least_two_ids(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)

    code = cli.cmd_research_compare(argparse.Namespace(compare=[1]))

    output = capture.export_text()
    assert code == 1
    assert "至少提供两个研究 ID" in output


def test_cmd_research_compare_renders_comparison_table(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)

    records = {
        1: {
            "id": 1,
            "topic": "transformer overview",
            "summary": "关注整体架构与核心机制。",
            "full_text": "A",
            "created_at": 1710000000.0,
            "source_count": 3,
            "follow_ups": [{"question": "q1", "answer": "a1", "timestamp": 1710001000.0}],
        },
        2: {
            "id": 2,
            "topic": "transformer in vision",
            "summary": "关注视觉任务中的 transformer 变体。",
            "full_text": "B",
            "created_at": 1710086400.0,
            "source_count": 5,
            "follow_ups": [],
        },
    }
    mock = MockDataAccess()
    mock.get_research = lambda research_id: records.get(research_id)
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research_compare(argparse.Namespace(compare=[1, 2]))

    output = capture.export_text()
    assert code == 0
    assert "研究对比" in output
    assert "transformer overview" in output
    assert "transformer in vision" in output
    assert "共同关注" in output
    assert "workspace research --open 1" in output


def test_cmd_research_compare_reports_missing_ids(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.get_research = lambda research_id: (
        None
        if research_id == 9
        else {
            "id": research_id,
            "topic": f"topic {research_id}",
            "summary": "ok",
            "full_text": "ok",
            "created_at": 1710000000.0,
            "source_count": 1,
            "follow_ups": [],
        }
    )
    mock.list_research = lambda limit=3: [
        {"id": 3, "topic": "topic 3", "summary": "", "created_at": 1710000000.0, "source_count": 1},
        {"id": 4, "topic": "topic 4", "summary": "", "created_at": 1710001000.0, "source_count": 1},
    ]
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_research_compare(argparse.Namespace(compare=[1, 9]))

    output = capture.export_text()
    assert code == 1
    assert "未找到这些研究 ID: 9" in output
    assert "最近的研究" in output
