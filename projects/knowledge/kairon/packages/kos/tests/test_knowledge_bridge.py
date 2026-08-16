"""Tests for knowledge_bridge."""

from kos.knowledge_bridge import KnowledgeRecord


def test_record_below_threshold_fails():
    record = KnowledgeRecord(source="test", content={"a": 1}, quality_score=0.3)
    assert not record.meets_threshold()
    assert not record.validate()


def test_record_above_threshold_passes():
    record = KnowledgeRecord(source="test", content={"a": 1}, quality_score=0.8)
    assert record.meets_threshold()
    assert record.validate()
    assert record.validated


def test_record_empty_content_fails():
    record = KnowledgeRecord(source="test", content={}, quality_score=0.9)
    assert not record.validate()


def test_record_to_triple():
    record = KnowledgeRecord(
        source="minerva",
        content={"entity": "Python", "relation": "requires", "value": "CPython 3.13+"},
        quality_score=0.8,
        validated=True,
    )
    triple = record.to_triple()
    assert triple == ("Python", "requires", "CPython 3.13+")


def test_record_to_triple_unvalidated_returns_none():
    record = KnowledgeRecord(source="test", content={"a": 1}, quality_score=0.8)
    assert record.to_triple() is None


def test_triple_count_starts_at_zero():
    record = KnowledgeRecord(
        source="test",
        content={"entity": "X", "relation": "Y", "value": "Z"},
        quality_score=0.9,
    )
    assert record.triple_count == 0
