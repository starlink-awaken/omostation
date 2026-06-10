from __future__ import annotations

from pathlib import Path

from cockpit import storage


def test_set_research_agent_updates_record(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")

    rid = storage.save_research("topic", "summary", "body", source_count=1)
    result = storage.set_research_agent(rid, "Alice")

    assert result is True
    record = storage.get_research(rid)
    assert record is not None
    assert record["agent"] == "Alice"


def test_set_research_agent_nonexistent_returns_false(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "data.db")

    result = storage.set_research_agent(9999, "Alice")

    assert result is False
