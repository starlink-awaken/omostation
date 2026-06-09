from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest
from rich.console import Console

from cockpit import cli
from cockpit.tests.conftest import MockDataAccess


def test_research_help_includes_publish_option(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["workspace", "research", "--help"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "--publish" in captured.out
    assert "--style" in captured.out


def test_cmd_research_publish_requires_existing_record(monkeypatch):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    mock = MockDataAccess()
    mock.get_research = lambda research_id: None
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_publish")(argparse.Namespace(publish=99, style="report"))

    output = capture.export_text()
    assert code == 1
    assert "未找到 ID=99 的研究记录" in output


def test_cmd_research_publish_writes_brief_report_and_tracks_publication(monkeypatch, tmp_path: Path):
    capture = Console(record=True, force_terminal=True, width=140)
    monkeypatch.setattr(cli, "console", capture)
    monkeypatch.setattr(cli, "err", capture)
    mock = MockDataAccess()
    mock.get_research = lambda research_id: {
        "id": 12,
        "topic": "Digest: Transformer Overview + Transformer In Vision",
        "summary": "共同关注: Transformer、Vision",
        "full_text": "# Digest\n\n## 核心主题\n- Transformer\n\n## 下一步\n- do something",
        "created_at": 1710000000.0,
        "source_count": 8,
        "follow_ups": [],
        "quarantined_at": None,
        "quarantine_reason": None,
    }
    monkeypatch.setattr(cli.Path, "home", lambda: tmp_path)
    published: dict[str, object] = {}
    mock.save_published_report = lambda research_id, style, output_path: (
        published.update({"research_id": research_id, "style": style, "output_path": output_path}) or 1
    )
    monkeypatch.setattr(cli, "get_data_access", lambda: mock)

    code = getattr(cli, "cmd_research_publish")(argparse.Namespace(publish=12, style="brief"))

    output = capture.export_text()
    publish_dir = tmp_path / "Desktop" / "workspace-published"
    files = list(publish_dir.glob("*.md"))
    assert code == 0
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "# Digest: Transformer Overview + Transformer In Vision" in content
    assert "## One-Page Brief" in content
    assert "Source Count: 8" in content
    assert published["research_id"] == 12
    assert published["style"] == "brief"
    assert str(files[0]) == published["output_path"]
    assert "workspace research --open 12" in output
    assert "已发布到" in output
