from __future__ import annotations

from pathlib import Path

import cockpit.storage as storage


def test_research_timeline_aggregates_events(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")

    source_id = storage.save_research("source topic", "summary", "body", source_count=1)
    digest_id = storage.save_research("digest topic", "digest summary", "digest body", source_count=2)
    storage.add_research_relations([source_id], digest_id, "digest")
    storage.save_published_report(digest_id, "brief", "/tmp/report.md")
    storage.quarantine_research([digest_id], reason="traceback")
    storage.restore_research([digest_id])

    timeline = storage.get_research_timeline(digest_id)

    event_types = [item["event_type"] for item in timeline]
    assert "created" in event_types
    assert "derived_from" in event_types
    assert "published" in event_types
    assert "quarantined" in event_types
    assert "restored" in event_types
