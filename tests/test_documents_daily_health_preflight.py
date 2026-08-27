from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from lib.documents_daily_health_preflight import inspect_daily_health


def test_daily_health_preflight_reads_documents_without_mutating_tree(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    domain = documents / "@工作文档" / "卫健委"
    (domain / "_knowledge").mkdir(parents=True)
    (domain / "_storage" / "01-Inbox").mkdir(parents=True)
    (domain / "_control").mkdir(parents=True)
    old_note = domain / "_knowledge" / "old.md"
    old_note.write_text("old\n", encoding="utf-8")
    old_time = old_note.stat().st_mtime - 31 * 86400
    os.utime(old_note, (old_time, old_time))
    stale_inbox = domain / "_storage" / "01-Inbox" / "stale.md"
    stale_inbox.write_text("inbox\n", encoding="utf-8")
    stale_inbox_time = stale_inbox.stat().st_mtime - 8 * 86400
    os.utime(stale_inbox, (stale_inbox_time, stale_inbox_time))
    (domain / "_storage" / "01-Inbox" / "inbox-manifest.md").write_text(
        "📥 待分类\n", encoding="utf-8"
    )
    (domain / "_control" / "signals.md").write_text("signal-1\nsignal-2\n", encoding="utf-8")
    before = sorted((p.relative_to(documents), p.read_bytes()) for p in documents.rglob("*") if p.is_file())

    result = inspect_daily_health(documents, workspace, today=date.today())

    assert result["schema"] == "documents.daily-health-preflight.v1"
    assert result["status"] == "findings"
    assert result["summary"] == {"stale_knowledge": 1, "stale_inbox": 1, "pending_inbox": 1, "signals": 2}
    after = sorted((p.relative_to(documents), p.read_bytes()) for p in documents.rglob("*") if p.is_file())
    assert before == after


def test_daily_health_preflight_rejects_documents_workspace_overlap(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()

    result = inspect_daily_health(documents, documents)

    assert result["status"] == "unavailable"
    assert "must not overlap" in result["errors"][0]
