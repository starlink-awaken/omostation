from __future__ import annotations

import argparse
import sys

import pytest
from rich.console import Console
from cockpit import cli
from cockpit.tests.conftest import MockDataAccess


def test_research_help_includes_object_ops(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["workspace", "research", "--help"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "--tag" in captured.out
    assert "--rename" in captured.out
    assert "--archive" in captured.out
    assert "--unarchive" in captured.out


def test_cmd_research_tag_updates_tags(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.set_research_tags = lambda research_id, tags: ["agents", "llm"]
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_tag")(argparse.Namespace(tag=12, labels=["llm", "agents"]))

    output = capture.export_text()
    assert code == 0
    assert "已更新标签" in output
    assert "agents, llm" in output


def test_cmd_research_tag_not_found(monkeypatch):
    """ID 不存在→set_research_tags 返回 []→错误提示 (lines 393-394)"""
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.set_research_tags = lambda research_id, tags: []
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_tag")(argparse.Namespace(tag=999, labels=["test"]))

    output = capture.export_text()
    assert code == 1
    assert "未找到" in output
    assert "999" in output


def test_cmd_research_rename_updates_topic(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.rename_research = lambda research_id, new_topic: True
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_rename")(argparse.Namespace(rename=7, new_title=["better", "title"]))

    output = capture.export_text()
    assert code == 0
    assert "已重命名" in output
    assert "better title" in output


def test_cmd_research_rename_not_found(monkeypatch):
    """ID 不存在→rename_research 返回 False→错误提示 (lines 414-415)"""
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.rename_research = lambda research_id, new_topic: False
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_rename")(argparse.Namespace(rename=999, new_title=["new", "title"]))

    output = capture.export_text()
    assert code == 1
    assert "未找到" in output
    assert "999" in output


def test_cmd_research_archive_reports_result(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.archive_research = lambda ids, reason="manual archive": ([4, 5], [9])
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_archive")(argparse.Namespace(archive=[4, 5, 9]))

    output = capture.export_text()
    assert code == 0
    assert "已归档 2 条研究记录" in output
    assert "4, 5" in output
    assert "未找到这些研究 ID: 9" in output


def test_cmd_research_archive_all_missing(monkeypatch):
    """全部 ID 不存在→archived=[] missing=[1,2]→错误返回码 (lines 434-435)"""
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.archive_research = lambda ids, reason="manual archive": ([], [1, 2])
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_archive")(argparse.Namespace(archive=[1, 2]))

    output = capture.export_text()
    assert code == 1
    assert "未找到这些研究 ID: 1, 2" in output


def test_cmd_research_unarchive_reports_result(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.restore_archived_research = lambda ids: ([4, 5], [9])
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_unarchive")(argparse.Namespace(unarchive=[4, 5, 9]))

    output = capture.export_text()
    assert code == 0
    assert "已恢复归档 2 条研究记录" in output
    assert "4, 5" in output
    assert "未找到这些研究 ID: 9" in output


def test_cmd_research_unarchive_all_missing(monkeypatch):
    """全部 ID 不存在→restored=[] missing=[1,2]→错误返回码 (lines 457-458)"""
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.restore_archived_research = lambda ids: ([], [1, 2])
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_unarchive")(argparse.Namespace(unarchive=[1, 2]))

    output = capture.export_text()
    assert code == 1
    assert "未找到这些研究 ID: 1, 2" in output


def test_cmd_research_archive_rejects_missing_ids(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)

    code = getattr(cli, "cmd_research_archive")(argparse.Namespace(archive=None, all_active=False))

    assert code == 1
    output = capture.export_text()
    assert "请提供研究 ID" in output


def test_cmd_research_unarchive_rejects_missing_ids(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)

    code = getattr(cli, "cmd_research_unarchive")(argparse.Namespace(unarchive=None, all_active=False))

    assert code == 1
    output = capture.export_text()
    assert "请提供研究 ID" in output


def test_cmd_research_archive_all_active(monkeypatch):
    """--all-active 归档全部活跃研究"""
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.list_research = lambda limit=5000, include_archived=False: [
        {"id": 42, "archived_at": None},
        {"id": 43, "archived_at": None},
    ]
    mock.archive_research = lambda ids, reason="manual archive": (ids, [])
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)
    code = getattr(cli, "cmd_research_archive")(argparse.Namespace(archive=None, all_active=True))
    assert code == 0
    output = capture.export_text()
    assert "已归档" in output
    assert "42" in output
    assert "43" in output


def test_cmd_research_archive_all_active_empty(monkeypatch):
    """--all-active 无活跃研究→提示"""
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.list_research = lambda limit=5000, include_archived=False: []
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)
    code = getattr(cli, "cmd_research_archive")(argparse.Namespace(archive=None, all_active=True))
    assert code == 0
    output = capture.export_text()
    assert "没有活跃的研究" in output


def test_cmd_research_tag_no_labels_returns_error(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)

    code = getattr(cli, "cmd_research_tag")(argparse.Namespace(tag=12, labels=[]))

    assert code == 1
    output = capture.export_text()
    assert "请提供标签" in output or "请提供研究 ID" in output


def test_cmd_research_rename_no_title_returns_error(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=160)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)

    code = getattr(cli, "cmd_research_rename")(argparse.Namespace(rename=7, new_title=None))

    assert code == 1
    output = capture.export_text()
    assert "请提供新标题" in output or "请提供研究 ID" in output
