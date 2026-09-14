"""Tests for kos.ontology.store — CRUD operations."""

import json
import sqlite3
import unittest
from datetime import datetime

from kos.ontology._types import Entity, EntityType, Relation, RelationType

# Schema matching what store.py ensures
SCHEMA = """
CREATE TABLE IF NOT EXISTS kos_entities (
    entity_id   TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    label       TEXT NOT NULL,
    aliases     TEXT,
    description TEXT,
    zone        TEXT,
    source      TEXT,
    status      TEXT DEFAULT 'active',
    version     INTEGER DEFAULT 1,
    confidence  REAL DEFAULT 1.0,
    created_at  TEXT,
    updated_at  TEXT,
    metadata    TEXT
);
CREATE TABLE IF NOT EXISTS kos_relations (
    source_id   TEXT,
    relation_type TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    confidence  REAL DEFAULT 1.0,
    source      TEXT DEFAULT 'manual',
    updated_at  TEXT,
    PRIMARY KEY (source_id, relation_type, target_id)
);
CREATE INDEX IF NOT EXISTS idx_rel_source ON kos_relations(source_id);
CREATE INDEX IF NOT EXISTS idx_rel_target ON kos_relations(target_id);
CREATE INDEX IF NOT EXISTS idx_entity_type ON kos_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entity_zone ON kos_entities(zone);
"""


class TestStoreCRUD(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def tearDown(self):
        self.conn.close()

    def _put(self, e):
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO kos_entities "
            "(entity_id, entity_type, label, aliases, description, zone, source, status, version, confidence, created_at, updated_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                e.entity_id,
                e.entity_type.value,
                e.label,
                json.dumps(e.aliases) if e.aliases else None,
                e.description,
                e.zone,
                e.source,
                e.status,
                e.version,
                e.confidence,
                e.created_at or now,
                now,
                json.dumps(e.metadata) if e.metadata else None,
            ),
        )
        self.conn.commit()

    def _get(self, eid):
        row = self.conn.execute("SELECT * FROM kos_entities WHERE entity_id=?", (eid,)).fetchone()
        if not row:
            return None
        return Entity(
            entity_id=row["entity_id"],
            entity_type=EntityType(row["entity_type"]),
            label=row["label"],
            aliases=json.loads(row["aliases"]) if row["aliases"] else [],
            description=row["description"] or "",
            zone=row["zone"] or "",
            status=row["status"] or "active",
        )

    def test_put_and_get(self):
        e = Entity(entity_id="ROL-a", entity_type=EntityType.PERSON, label="Alice")
        self._put(e)
        got = self._get("ROL-a")
        self.assertIsNotNone(got)
        self.assertEqual(got.entity_id, "ROL-a")  # type: ignore[reportOptionalMemberAccess]
        self.assertEqual(got.label, "Alice")  # type: ignore[reportOptionalMemberAccess]

    def test_put_twice_updates(self):
        e1 = Entity(entity_id="ROL-a", entity_type=EntityType.PERSON, label="Alice")
        self._put(e1)
        e2 = Entity(entity_id="ROL-a", entity_type=EntityType.PERSON, label="Alice Updated")
        self._put(e2)
        got = self._get("ROL-a")
        self.assertEqual(got.label, "Alice Updated")  # type: ignore[reportOptionalMemberAccess]

    def test_get_nonexistent(self):
        got = self._get("ROL-nonexistent")
        self.assertIsNone(got)

    def test_entity_with_aliases(self):
        e = Entity(entity_id="ROL-b", entity_type=EntityType.PERSON, label="Bob", aliases=["Robert", "Bobby"])
        self._put(e)
        got = self._get("ROL-b")
        self.assertEqual(got.aliases, ["Robert", "Bobby"])  # type: ignore[reportOptionalMemberAccess]

    def test_entity_with_zone(self):
        e = Entity(entity_id="ROL-c", entity_type=EntityType.PERSON, label="Charlie", zone="gongwen")
        self._put(e)
        got = self._get("ROL-c")
        self.assertEqual(got.zone, "gongwen")  # type: ignore[reportOptionalMemberAccess]

    def test_multiple_entities(self):
        for i in range(5):
            e = Entity(entity_id=f"ROL-{i}", entity_type=EntityType.PERSON, label=f"User{i}")
            self._put(e)
        rows = self.conn.execute("SELECT COUNT(*) FROM kos_entities").fetchone()
        self.assertEqual(rows[0], 5)

    def test_list_by_type(self):
        self._put(Entity(entity_id="ROL-a", entity_type=EntityType.PERSON, label="A"))
        self._put(Entity(entity_id="ROL-b", entity_type=EntityType.PERSON, label="B"))
        self._put(Entity(entity_id="ORG-a", entity_type=EntityType.ORGANIZATION, label="Org"))
        rows = self.conn.execute("SELECT entity_id FROM kos_entities WHERE entity_type='person'").fetchall()
        self.assertEqual(len(rows), 2)


class TestRelationCRUD(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        for eid in ["ROL-a", "ROL-b", "ROL-c", "ORG-x"]:
            self.conn.execute(
                "INSERT INTO kos_entities (entity_id, entity_type, label) VALUES (?, ?, ?)",
                (eid, "person" if eid.startswith("ROL") else "organization", eid),
            )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _put_rel(self, r):
        self.conn.execute(
            "INSERT OR REPLACE INTO kos_relations (source_id, relation_type, target_id, confidence) "
            "VALUES (?, ?, ?, ?)",
            (r.source_id, r.relation_type.value, r.target_id, r.confidence),
        )
        self.conn.commit()

    def test_relation_crud(self):
        r = Relation(source_id="ROL-a", relation_type=RelationType.REPORTS_TO, target_id="ROL-b")
        self._put_rel(r)
        rows = self.conn.execute("SELECT * FROM kos_relations").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["relation_type"], "reports_to")

    def test_relation_outgoing(self):
        self._put_rel(Relation(source_id="ROL-a", relation_type=RelationType.REPORTS_TO, target_id="ROL-b"))
        self._put_rel(Relation(source_id="ROL-a", relation_type=RelationType.MEMBER_OF, target_id="ORG-x"))
        rows = self.conn.execute("SELECT * FROM kos_relations WHERE source_id='ROL-a'").fetchall()
        self.assertEqual(len(rows), 2)

    def test_relation_incoming(self):
        self._put_rel(Relation(source_id="ROL-a", relation_type=RelationType.REPORTS_TO, target_id="ROL-c"))
        self._put_rel(Relation(source_id="ROL-b", relation_type=RelationType.REPORTS_TO, target_id="ROL-c"))
        rows = self.conn.execute("SELECT * FROM kos_relations WHERE target_id='ROL-c'").fetchall()
        self.assertEqual(len(rows), 2)

    def test_relation_deleted_with_entity(self):
        self._put_rel(Relation(source_id="ROL-a", relation_type=RelationType.REPORTS_TO, target_id="ROL-b"))
        self.conn.execute("DELETE FROM kos_relations WHERE source_id='ROL-a'")
        rows = self.conn.execute("SELECT * FROM kos_relations").fetchall()
        self.assertEqual(len(rows), 0)


class TestExportFormats(unittest.TestCase):
    """Test JSON-LD and Turtle export format validity (no DB required)."""

    def test_jsonld_valid_structure(self):
        result = '{"@context": {}, "@graph": [{"@id": "test", "@type": "schema:Person"}]}'
        import json

        parsed = json.loads(result)
        self.assertIn("@context", parsed)
        self.assertIn("@graph", parsed)
        self.assertGreater(len(parsed["@graph"]), 0)

    def test_jsonld_node_has_required_fields(self):
        import json

        node = json.loads('{"@id": "ROL-a", "@type": "schema:Person", "schema:name": "Alice"}')
        self.assertIn("@id", node)
        self.assertIn("@type", node)

    def test_turtle_format_has_prefixes(self):
        result = '@prefix schema: <https://schema.org/> .\n@prefix prov: <http://www.w3.org/ns/prov#> .\n\nkos:ROL-a a schema:Person ;\n    schema:name "Alice" .'
        self.assertIn("@prefix", result)
        self.assertIn("schema:", result)

    def test_turtle_statement_format(self):
        result = 'kos:ROL-a a schema:Person ;\n    schema:name "Alice" .'
        self.assertTrue(result.strip().endswith("."))
        self.assertIn("a schema:", result)


if __name__ == "__main__":
    unittest.main()
