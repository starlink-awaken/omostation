from __future__ import annotations

import argparse
import sys

import pytest
from rich.console import Console

from cockpit import cli
from cockpit.tests.conftest import MockDataAccess


def test_research_help_includes_merge_option(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["workspace", "research", "--help"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "--merge" in captured.out


def test_cmd_research_merge_requires_at_least_two_ids(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=120)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)

    code = getattr(cli, "cmd_research_merge")(argparse.Namespace(merge=[1]))

    output = capture.export_text()
    assert code == 1
    assert "至少提供两个研究 ID" in output


def test_cmd_research_merge_saves_new_research(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)

    records = {
        1: {
            "id": 1,
            "topic": "Transformer Overview",
            "summary": "关注模型结构与训练要点。",
            "full_text": "Section A",
            "created_at": 1710000000.0,
            "source_count": 3,
            "follow_ups": [{"question": "q1", "answer": "a1", "timestamp": 1710001000.0}],
        },
        2: {
            "id": 2,
            "topic": "Transformer In Vision",
            "summary": "关注视觉领域里的变体。",
            "full_text": "Section B",
            "created_at": 1710086400.0,
            "source_count": 5,
            "follow_ups": [],
        },
    }
    mock = MockDataAccess()
    mock.get_research = lambda research_id: records.get(research_id)

    saved: dict[str, object] = {}

    def fake_save_research(topic: str, summary: str, full_text: str = "", source_count: int = 0) -> int:
        saved.update(
            {
                "topic": topic,
                "summary": summary,
                "full_text": full_text,
                "source_count": source_count,
            }
        )
        return 11

    mock.save_research = fake_save_research
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_merge")(argparse.Namespace(merge=[1, 2]))

    output = capture.export_text()
    assert code == 0
    assert saved["topic"] == "Merged: Transformer Overview + Transformer In Vision"
    assert saved["source_count"] == 8
    assert "## Transformer Overview" in str(saved["full_text"])
    assert "## Transformer In Vision" in str(saved["full_text"])
    assert "共同关注" in str(saved["summary"])
    assert "合并完成" in output
    assert "ID 11" in output
    assert "workspace research --open 11" in output


def test_cmd_research_merge_reports_missing_ids(monkeypatch):
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

    code = getattr(cli, "cmd_research_merge")(argparse.Namespace(merge=[1, 9]))

    output = capture.export_text()
    assert code == 1
    assert "未找到这些研究 ID: 9" in output
    assert "最近的研究" in output
