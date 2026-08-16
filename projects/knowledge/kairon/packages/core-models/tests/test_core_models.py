"""Core tests for core-models package."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

from core_models.entity import Entity
from core_models.relation import Relation


def test_entity_creation():
    e = Entity(id="test-1", name="Test Entity", type="concept", source="test")
    assert e.id == "test-1"
    assert e.name == "Test Entity"


def test_relation_creation():
    r = Relation(source_id="a", target_id="b", type="depends_on")
    assert r.source_id == "a"
    assert r.target_id == "b"
