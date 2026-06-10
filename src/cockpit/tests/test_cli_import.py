from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest import mock
from urllib import error as urlerror

import pytest
from rich.console import Console

from cockpit import cli
from cockpit.commands import importer as importer_mod
from cockpit.tests.conftest import MockDataAccess


class _FakeHTTPResponse:
    def __init__(self, body: bytes, url: str = "https://example.com/post"):
        self._body = body
        self._url = url

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_workspace_help_includes_import_command(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["workspace", "--help"])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "import" in captured.out


def test_cmd_import_reads_file_and_saves_research(monkeypatch, tmp_path: Path):
    sample = tmp_path / "sample.md"
    sample.write_text("# Imported Note\n\nThis is imported content.", encoding="utf-8")

    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)

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
        return 42

    mock = MockDataAccess()
    mock.save_research = fake_save_research
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)
    notified: list[tuple[str, str]] = []
    monkeypatch.setattr(
        importer_mod, "_notify_pipeline_success", lambda stage, detail: notified.append((stage, detail)), raising=False
    )

    code = cli.cmd_import(argparse.Namespace(source=str(sample)))

    output = capture.export_text()
    assert code == 0
    assert saved["topic"] == "Imported Note"
    assert saved["source_count"] == 1
    assert "This is imported content." in str(saved["full_text"])
    assert "导入完成" in output
    assert "ID 42" in output
    assert notified == [("导入", "Imported Note")]


def test_cmd_import_reads_url_and_saves_research(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    monkeypatch.setattr(
        cli.urlrequest,
        "urlopen",
        lambda url, timeout=10: _FakeHTTPResponse(
            b"<html><head><title>Remote Article</title></head><body><h1>Remote Article</h1><p>Hello URL import.</p></body></html>",
            url=url,
        ),
    )

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
        return 7

    mock = MockDataAccess()
    mock.save_research = fake_save_research
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = cli.cmd_import(argparse.Namespace(source="https://example.com/post"))

    output = capture.export_text()
    assert code == 0
    assert saved["topic"] == "Remote Article"
    assert "Hello URL import." in str(saved["full_text"])
    assert "https://example.com/post" in output


def test_cmd_import_rejects_missing_file(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    notified: list[tuple[str, str]] = []
    monkeypatch.setattr(
        importer_mod, "_notify_pipeline_error", lambda stage, detail: notified.append((stage, detail)), raising=False
    )

    code = cli.cmd_import(argparse.Namespace(source="/tmp/does-not-exist-workspace-import.md"))

    output = capture.export_text()
    assert code == 1
    assert "未找到要导入的文件" in output
    assert notified == [("导入", "/tmp/does-not-exist-workspace-import.md")]


def test_cmd_import_empty_source(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)

    code = cli.cmd_import(argparse.Namespace(source=""))

    output = capture.export_text()
    assert code == 1
    assert "请提供要导入的 URL 或文件路径" in output


def test_cmd_import_url_error(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    monkeypatch.setattr(
        cli.urlrequest,
        "urlopen",
        mock.Mock(side_effect=urlerror.URLError("connection refused")),
    )

    code = cli.cmd_import(argparse.Namespace(source="https://example.com/broken"))

    output = capture.export_text()
    assert code == 1
    assert "无法读取 URL" in output


def test_cmd_import_os_error(monkeypatch, tmp_path: Path):
    sample = tmp_path / "unreadable.md"
    sample.write_text("content", encoding="utf-8")

    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    # 模拟文件存在但读取失败
    monkeypatch.setattr(Path, "read_text", mock.Mock(side_effect=OSError("permission denied")))

    code = cli.cmd_import(argparse.Namespace(source=str(sample)))

    output = capture.export_text()
    assert code == 1
    assert "读取内容失败" in output


def test_cmd_import_empty_body(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    monkeypatch.setattr(
        cli.urlrequest,
        "urlopen",
        lambda url, timeout=10: _FakeHTTPResponse(b"", url=url),
    )

    code = cli.cmd_import(argparse.Namespace(source="https://example.com/empty"))

    output = capture.export_text()
    assert code == 1
    assert "导入内容为空" in output
