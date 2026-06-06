from __future__ import annotations

from pathlib import Path

from cockpit import storage


def test_restored_research_returns_to_list_and_search(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")

    healthy_id = storage.save_research("healthy topic", "good summary", "useful content", source_count=2)
    bad_id = storage.save_research(
        "broken topic", "Traceback content", "Traceback (most recent call last): x", source_count=1
    )

    storage.quarantine_research([bad_id], reason="traceback")
    restored, missing = storage.restore_research([bad_id])

    assert restored == [bad_id]
    assert missing == []

    listed_ids = [row["id"] for row in storage.list_research(limit=10)]
    assert bad_id in listed_ids
    assert healthy_id in listed_ids

    search_ids = [row["id"] for row in storage.search_research("broken", limit=10)]
    assert bad_id in search_ids

    record = storage.get_research(bad_id)
    assert record is not None
    assert record["quarantine_reason"] is None
    assert record["quarantined_at"] is None
