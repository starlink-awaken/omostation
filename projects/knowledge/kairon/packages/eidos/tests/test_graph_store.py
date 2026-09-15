"""GraphStore 真存储 MVP 验证 (TASK-1E562797 stub 后端接真).

GraphStore 复用 SQLiteRelationalProvider (entities/relations 表) 真实现 CRUD.
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import pytest
from eidos.graph_store import Entity, GraphStore, Relation


@pytest.fixture
def store() -> GraphStore:
    return GraphStore(":memory:")


def test_entity_crud_roundtrip(store: GraphStore) -> None:
    """add_entity → get_entity 往返一致 (含扩展字段)."""
    e = Entity(
        id="e1",
        name="函数A",
        entity_type="function",
        properties={"line": 42},
        source_files=["a.py"],
        entity_id="e1",
        is_canonical=True,
    )
    store.add_entity(e)
    got = store.get_entity("e1")
    assert got is not None
    assert got.id == "e1"
    assert got.name == "函数A"
    assert got.entity_type == "function"
    assert got.properties == {"line": 42}
    assert got.source_files == ["a.py"]
    assert got.is_canonical is True


def test_entity_not_found(store: GraphStore) -> None:
    assert store.get_entity("nope") is None


def test_search_entities_by_pattern(store: GraphStore) -> None:
    store.add_entity(Entity(id="e1", name="foo"))
    store.add_entity(Entity(id="e2", name="bar_foo"))
    store.add_entity(Entity(id="e3", name="baz"))
    results = store.search_entities(name_pattern="foo")
    assert len(results) == 2
    names = {r.name for r in results}
    assert names == {"foo", "bar_foo"}


def test_relation_crud_roundtrip(store: GraphStore) -> None:
    store.add_entity(Entity(id="src", name="s"))
    store.add_entity(Entity(id="tgt", name="t"))
    r = Relation(id="r1", source_id="src", target_id="tgt", relation_type="calls", weight=2.5)
    store.add_relation(r)
    got = store.get_relation("r1")
    assert got is not None
    assert got.source_id == "src"
    assert got.target_id == "tgt"
    assert got.relation_type == "calls"
    assert got.weight == 2.5


def test_get_relations_for_entity_direction(store: GraphStore) -> None:
    store.add_entity(Entity(id="a", name="a"))
    store.add_entity(Entity(id="b", name="b"))
    store.add_entity(Entity(id="c", name="c"))
    store.add_relation(Relation(id="r1", source_id="a", target_id="b", relation_type="x"))
    store.add_relation(Relation(id="r2", source_id="c", target_id="a", relation_type="y"))

    out = store.get_relations_for_entity("a", direction="out")
    assert len(out) == 1 and out[0].id == "r1"

    incoming = store.get_relations_for_entity("a", direction="in")
    assert len(incoming) == 1 and incoming[0].id == "r2"

    both = store.get_relations_for_entity("a")
    assert len(both) == 2


def test_query_returns_entities(store: GraphStore) -> None:
    store.add_entity(Entity(id="e1", name="foo"))
    rows = store.query()
    assert len(rows) == 1
    assert rows[0]["name"] == "foo"


def test_ping(store: GraphStore) -> None:
    assert store.ping() is True
