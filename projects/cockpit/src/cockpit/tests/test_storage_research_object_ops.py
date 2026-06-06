from __future__ import annotations

from pathlib import Path

import cockpit.storage as storage


def test_tag_rename_archive_roundtrip(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")

    research_id = storage.save_research("original topic", "summary", "body", source_count=1)

    updated_tags = storage.set_research_tags(research_id, ["llm", "agents"])
    renamed = storage.rename_research(research_id, "renamed topic")
    archived, missing = storage.archive_research([research_id], reason="manual archive")

    assert updated_tags == ["agents", "llm"]
    assert renamed is True
    assert archived == [research_id]
    assert missing == []

    listed_ids = [row["id"] for row in storage.list_research(limit=10)]
    assert research_id not in listed_ids

    record = storage.get_research(research_id)
    assert record is not None
    assert record["topic"] == "renamed topic"
    assert record["tags"] == ["agents", "llm"]
    assert record["archived_at"] is not None
    assert record["archive_reason"] == "manual archive"

    restored, missing = storage.restore_archived_research([research_id])
    assert restored == [research_id]
    assert missing == []
    listed_ids = [row["id"] for row in storage.list_research(limit=10)]
    assert research_id in listed_ids
