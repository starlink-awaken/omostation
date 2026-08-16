"""Tests for memory schema — extracted from SharedBrain D_Memory."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from eidos.memory_schema import MemoryRecord, MemorySession


def test_memory_record_defaults():
    r = MemoryRecord(record_id="r1", content="test content")
    assert r.memory_type == "fact"
    assert r.confidence == 1.0


def test_memory_record_to_dict():
    r = MemoryRecord(record_id="r1", content="test", memory_type="fact", confidence=0.8, source="minerva")
    d = r.to_dict()
    assert d["source"] == "minerva"


def test_memory_session_add_record():
    s = MemorySession(session_id="s1")
    s.add_record(MemoryRecord(record_id="r1", content="hello"))
    s.add_record(MemoryRecord(record_id="r2", content="world"))
    assert s.record_count == 2


def test_memory_session_valid_records():
    s = MemorySession(
        session_id="s1",
        records=[
            MemoryRecord("r1", "a", confidence=0.9),
            MemoryRecord("r2", "b", confidence=0.3),
        ],
    )
    valid = s.valid_records(min_confidence=0.5)
    assert len(valid) == 1
