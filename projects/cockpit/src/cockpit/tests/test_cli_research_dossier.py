from __future__ import annotations

import argparse
import sys

import pytest
from rich.console import Console
from cockpit import cli
from cockpit.tests.conftest import MockDataAccess


def test_research_help_includes_dossier_option(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["workspace", "research", "--help"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "--dossier" in captured.out


def test_cmd_research_dossier_renders_relations(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.get_research_dossier = lambda research_id: {
        "record": {
            "id": 12,
            "topic": "Digest: Transformer Overview + Transformer In Vision",
            "summary": "共同关注: Transformer、Vision",
            "created_at": 1710000000.0,
            "source_count": 8,
        },
        "parents": [
            {"id": 1, "topic": "Transformer Overview", "relation_type": "digest"},
            {"id": 2, "topic": "Transformer In Vision", "relation_type": "digest"},
        ],
        "children": [],
        "publications": [
            {"style": "brief", "output_path": "/tmp/report.md", "published_at": 1710000100.0},
        ],
    }
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_dossier")(argparse.Namespace(dossier=12))

    output = capture.export_text()
    assert code == 0
    assert "研究 Dossier" in output
    assert "Transformer Overview" in output
    assert "Transformer In Vision" in output
    assert "/tmp/report.md" in output


def test_cmd_research_dossier_not_found(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.get_research_dossier = lambda research_id: None
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_dossier")(argparse.Namespace(dossier=99))

    output = capture.export_text()
    assert code == 1
    assert "未找到" in output


def test_cmd_research_dossier_no_relations(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.get_research_dossier = lambda research_id: {
        "record": {
            "id": 5,
            "topic": "Standalone",
            "summary": "孤立记录",
            "created_at": 1710000000.0,
            "source_count": 1,
        },
        "parents": [],
        "children": [],
        "publications": [],
    }
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_dossier")(argparse.Namespace(dossier=5))

    output = capture.export_text()
    assert code == 0
    assert "暂无关系记录" in output
    assert "暂无发布产物" in output


def test_cmd_research_dossier_no_publications(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.get_research_dossier = lambda research_id: {
        "record": {
            "id": 6,
            "topic": "With Parents",
            "summary": "有来源无发布",
            "created_at": 1710000000.0,
            "source_count": 2,
        },
        "parents": [{"id": 1, "topic": "Source A", "relation_type": "source"}],
        "children": [],
        "publications": [],
    }
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_dossier")(argparse.Namespace(dossier=6))

    output = capture.export_text()
    assert code == 0
    assert "Source A" in output
    assert "暂无发布产物" in output


def test_cmd_research_dossier_only_children(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.get_research_dossier = lambda research_id: {
        "record": {"id": 7, "topic": "Child Focus", "summary": "有派生", "created_at": 1710000000.0, "source_count": 1},
        "parents": [],
        "children": [{"id": 8, "topic": "Derived Work", "relation_type": "digest"}],
        "publications": [],
    }
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_dossier")(argparse.Namespace(dossier=7))

    output = capture.export_text()
    assert code == 0
    assert "Derived Work" in output
