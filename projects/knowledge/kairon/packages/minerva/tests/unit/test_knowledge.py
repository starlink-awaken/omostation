"""Tests for SQLiteKnowledgeStore — CRUD + FTS5 + timeline + contradictions."""

import os
import tempfile

import pytest


@pytest.fixture
def store():
    """Create an in-memory knowledge store for testing."""
    from minerva.knowledge.store import SQLiteKnowledgeStore

    # Use temp file for test isolation
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = SQLiteKnowledgeStore(db_path=path)
    yield store
    store.conn.close()
    os.unlink(path)


class TestKnowledgeStore:
    """Tests for the knowledge store."""

    @pytest.mark.asyncio
    async def test_upsert_get_entity(self, store):
        """Test entity CRUD — insert and retrieve."""
        from minerva.knowledge.store import Entity

        entity = Entity(
            id="test-1",
            type="Concept",
            name="Self-Attention",
            aliases=["attention"],
            properties={"domain": "AI/ML"},
            confidence="HIGH",
            source_ids=["src-001"],
        )
        eid = await store.upsert_entity(entity)
        assert eid == "test-1"

        retrieved = await store.get_entity("test-1")
        assert retrieved is not None
        assert retrieved.name == "Self-Attention"
        assert retrieved.type == "concept"
        assert "attention" in retrieved.aliases
        assert retrieved.properties["domain"] == "AI/ML"
        assert retrieved.confidence == "HIGH"

    @pytest.mark.asyncio
    async def test_upsert_relation(self, store):
        """Test relation CRUD."""
        from minerva.knowledge.store import Relation

        rel = Relation(
            id="rel-1",
            subject_id="entity-a",
            predicate="ENABLES",
            object_id="entity-b",
            meta_relation="SUPPORTS",
            confidence="HIGH",
            source_ids=["src-001"],
        )
        assert rel.meta_relation == "supports"
        rid = await store.upsert_relation(rel)
        assert rid == "rel-1"

    @pytest.mark.asyncio
    async def test_fts5_search(self, store):
        """Test FTS5 full-text search."""
        from minerva.knowledge.store import Entity

        await store.upsert_entity(Entity(id="e1", type="Concept", name="Transformer Architecture"))
        await store.upsert_entity(Entity(id="e2", type="Concept", name="RNN"))

        results = await store.search("transformer")
        assert len(results) >= 1
        # FTS5 search should find the transformer entity
        names = [r["name"] for r in results]
        assert any("Transformer" in n for n in names)

    @pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="requires LLM API key")
    @pytest.mark.asyncio
    async def test_timeline(self, store):
        """Test timeline query."""
        from minerva.knowledge.store import Entity, Relation

        # Create entities and a temporal relationship
        await store.upsert_entity(
            Entity(
                id="event-1",
                type="Event",
                name="Transformer published",
                properties={"date": "2017-06-12"},
                valid_from="2017-06-12",
            )
        )
        await store.upsert_entity(
            Entity(
                id="event-2",
                type="Event",
                name="GPT-3 released",
                properties={"date": "2020-06-11"},
                valid_from="2020-06-11",
            )
        )
        await store.upsert_relation(Relation(id="r1", subject_id="event-1", predicate="PRECEDES", object_id="event-2"))

        timeline = await store.get_timeline("event-1")
        assert len(timeline) >= 1

    @pytest.mark.asyncio
    async def test_contradictions(self, store):
        """Test contradiction detection."""
        from minerva.knowledge.store import Relation

        await store.upsert_relation(
            Relation(id="cr1", subject_id="claim-a", predicate="CONTRADICTS", object_id="claim-b")
        )

        contradictions = await store.get_contradictions()
        assert len(contradictions) >= 1
        assert contradictions[0]["predicate"] == "contradicts"

    @pytest.mark.asyncio
    async def test_ingest_url(self, store):
        """Test ingest pipeline (basic — full implementation in Phase 1)."""
        # ingest() currently returns stub — verify it doesn't crash
        result = await store.ingest("https://example.com", source_type="url")
        assert "entity_count" in result
        assert "relation_count" in result
        assert "source_path" in result
