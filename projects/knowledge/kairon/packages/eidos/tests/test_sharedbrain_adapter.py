"""Tests for SharedBrain → Eidos ontology adapter — deep integration layer."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from eidos.adapters.sharedbrain import (
    ORGAN_MAP,
    batch_import_organs,
    discover_organs_on_disk,
    find_sharedbrain_root,
    get_organ_path,
    list_available_organs,
    organ_to_facts,
    organ_to_knowledge_cards,
    organ_to_meta_type,
    organ_to_ontology_nodes,
    read_json_file,
    read_organ_data,
    read_sqlite_tables,
)

# ======================================================================
# Fixtures: SharedBrain data on disk
# ======================================================================


@pytest.fixture
def sb_root(tmp_path: Path) -> str:
    """Create a minimal SharedBrain filesystem tree with test data."""
    organs_dir = tmp_path / "organs"
    organs_dir.mkdir()

    # Create AGENTS.md marker
    (tmp_path / "AGENTS.md").write_text("# SharedBrain Test", encoding="utf-8")

    # ── D_Memory organ ──
    mem_dir = organs_dir / "D_Memory"
    mem_dir.mkdir()
    data_dir = mem_dir / "data"
    data_dir.mkdir()
    schema_dir = data_dir / "schema"
    schema_dir.mkdir()

    # SQLite DB with role_profiles and role_memories
    db_path = data_dir / "roles.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS role_profiles (
            role_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            version TEXT DEFAULT '1.0.0',
            status TEXT DEFAULT 'active',
            personality TEXT DEFAULT '{}',
            permissions TEXT DEFAULT '{}',
            state TEXT DEFAULT '{}',
            created_at REAL,
            updated_at REAL,
            last_active REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS role_memories (
            memory_id TEXT PRIMARY KEY,
            role_id TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT,
            created_at REAL,
            updated_at REAL,
            metadata TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS role_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_role TEXT NOT NULL,
            to_role TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            trust_level REAL DEFAULT 0.5,
            interaction_count INTEGER DEFAULT 0,
            created_at REAL,
            updated_at REAL
        )
    """)

    # Insert test data
    conn.execute(
        "INSERT INTO role_profiles VALUES ('r1', 'Architect', 'agent', '1.0', 'active', '{}', '{}', '{}', 100.0, 100.0, 100.0)"
    )
    conn.execute(
        "INSERT INTO role_profiles VALUES ('r2', 'Critic', 'agent', '1.0', 'active', '{}', '{}', '{}', 200.0, 200.0, 200.0)"
    )
    conn.execute(
        "INSERT INTO role_memories VALUES ('m1', 'r1', 'strategic', 'Design system architecture', 100.0, 100.0, '{\"source\": \"conversation\"}')"
    )
    conn.execute(
        "INSERT INTO role_memories VALUES ('m2', 'r2', 'tactical', 'Review and critique designs', 200.0, 200.0, '{}')"
    )
    conn.execute("INSERT INTO role_relationships VALUES (1, 'r1', 'r2', 'collaborates_with', 0.8, 10, 100.0, 200.0)")
    conn.commit()
    conn.close()

    # JSON file: task registry
    task_registry = {
        "active_tasks": {
            "TASK_001": {
                "name": "SYSTEM_AUDIT",
                "intent": "Perform system audit",
                "status": "IN_PROGRESS",
                "assigned_to": "@Prime",
                "created_at": 1000.0,
                "commits": [],
                "reflection": None,
            }
        },
        "archived_tasks": [],
    }
    (data_dir / "task-registry.json").write_text(json.dumps(task_registry, ensure_ascii=False), encoding="utf-8")

    # Schema SQL file
    (schema_dir / "roles_schema.sql").write_text(
        "-- Roles schema\nCREATE TABLE IF NOT EXISTS role_profiles (role_id TEXT PRIMARY KEY);",
        encoding="utf-8",
    )

    # ── D_KnowledgeIntegration organ ──
    ki_dir = organs_dir / "D_KnowledgeIntegration"
    ki_dir.mkdir()
    ki_data = ki_dir / "data"
    ki_data.mkdir()

    # SQLite DB with knowledge_metadata and evolution_patterns
    ki_db = ki_data / "knowledge.db"
    conn2 = sqlite3.connect(str(ki_db))
    conn2.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_metadata (
            knowledge_id TEXT PRIMARY KEY,
            category TEXT,
            tags TEXT,
            harvest_source TEXT,
            harvest_quality REAL DEFAULT 0.0,
            is_stale BOOLEAN DEFAULT 0,
            created_at TEXT
        )
    """)
    conn2.execute("""
        CREATE TABLE IF NOT EXISTS evolution_patterns (
            pattern_id TEXT PRIMARY KEY,
            pattern_type TEXT NOT NULL,
            confidence REAL NOT NULL,
            frequency INTEGER DEFAULT 1,
            source_domain TEXT,
            facts_json TEXT,
            extracted_at TEXT,
            validated BOOLEAN DEFAULT 0
        )
    """)
    conn2.execute(
        "INSERT INTO knowledge_metadata VALUES ('k1', 'architecture', 'system,design', 'manual', 0.9, 0, '2025-01-01')"
    )
    conn2.execute(
        'INSERT INTO evolution_patterns VALUES (\'p1\', \'SUCCESS\', 0.85, 5, \'coding\', \'[["refactor", "improves", "maintainability"], ["tests", "validate", "correctness"]]\', \'2025-01-01\', 1)'
    )
    conn2.commit()
    conn2.close()

    return str(tmp_path)


# ======================================================================
# Test helpers
# ======================================================================


def _insert_test_role_profiles(conn: sqlite3.Connection) -> None:
    """Insert standardized test role_profiles rows."""
    conn.execute(
        "INSERT INTO role_profiles VALUES ('r1', 'Architect', 'agent', '1.0', 'active', '{}', '{}', '{}', 100, 100, 100)"
    )


# ======================================================================
# Core mapping tests (existing + extended)
# ======================================================================


class TestOrganToMetaType:
    def test_known_organs(self):
        assert organ_to_meta_type("D_Memory") == "document"
        assert organ_to_meta_type("D_Intelligence") == "inference"
        assert organ_to_meta_type("D_Monitoring") == "state"
        assert organ_to_meta_type("D_Gateway") == "processor"
        assert organ_to_meta_type("D_Governance") == "constraint"

    def test_hyphen_aliases(self):
        assert organ_to_meta_type("D-Memory") == "document"
        assert organ_to_meta_type("D-KnowledgeIntegration") == "domain"
        assert organ_to_meta_type("D-Intelligence") == "inference"

    def test_unknown_organ_returns_domain(self):
        assert organ_to_meta_type("nonexistent") == "domain"
        assert organ_to_meta_type("") == "domain"

    def test_all_organs_valid(self):
        for organ in ORGAN_MAP:
            mt = organ_to_meta_type(organ)
            assert mt in ("document", "inference", "domain", "state", "relation", "constraint", "processor")


class TestListAvailableOrgans:
    def test_returns_list_of_dicts(self):
        result = list_available_organs()
        assert isinstance(result, list)
        assert all(isinstance(item, dict) for item in result)

    def test_each_entry_has_organ_and_meta_type(self):
        for entry in list_available_organs():
            assert "organ" in entry
            assert "meta_type" in entry

    def test_count_matches_organ_map(self):
        assert len(list_available_organs()) == len(ORGAN_MAP)


# ======================================================================
# File system discovery tests
# ======================================================================


class TestFindSharedBrainRoot:
    def test_returns_none_when_not_found(self):
        result = find_sharedbrain_root()
        # Should find the real one or return None
        assert result is None or Path(result).joinpath("AGENTS.md").exists()

    def test_finds_provided_root(self, sb_root: str):
        # find_sharedbrain_root checks env var SHAREDBRAIN_ROOT
        old = os.environ.get("SHAREDBRAIN_ROOT")
        try:
            os.environ["SHAREDBRAIN_ROOT"] = sb_root
            result = find_sharedbrain_root()
            assert result == sb_root
        finally:
            if old:
                os.environ["SHAREDBRAIN_ROOT"] = old
            else:
                del os.environ["SHAREDBRAIN_ROOT"]


class TestGetOrganPath:
    def test_known_organ(self, sb_root: str):
        path = get_organ_path("D_Memory", sb_root)
        assert path is not None
        assert "D_Memory" in path

    def test_hyphen_alias(self, sb_root: str):
        path = get_organ_path("D-Memory", sb_root)
        assert path is not None
        assert "D_Memory" in path

    def test_unknown_organ(self, sb_root: str):
        assert get_organ_path("nonexistent", sb_root) is None

    def test_nonexistent_root(self):
        assert get_organ_path("D_Memory", "/nonexistent/path") is None


class TestDiscoverOrgansOnDisk:
    def test_finds_organs(self, sb_root: str):
        organs = discover_organs_on_disk(sb_root)
        assert len(organs) >= 2
        names = [o["name"] for o in organs]
        assert "D_Memory" in names
        assert "D_KnowledgeIntegration" in names

    def test_each_has_path_and_meta_type(self, sb_root: str):
        for organ in discover_organs_on_disk(sb_root):
            assert "path" in organ
            assert "meta_type" in organ
            assert Path(organ["path"]).is_dir()

    def test_nonexistent_root(self):
        assert discover_organs_on_disk("/nonexistent") == []


# ======================================================================
# Data reader tests
# ======================================================================


class TestReadSQLiteTables:
    def test_reads_all_tables(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE t1 (id INT, name TEXT)")
            conn.execute("INSERT INTO t1 VALUES (1, 'foo')")
            conn.execute("INSERT INTO t1 VALUES (2, 'bar')")
            conn.execute("CREATE TABLE t2 (k TEXT, v INT)")
            conn.execute("INSERT INTO t2 VALUES ('a', 10)")
            conn.commit()
            conn.close()

            result = read_sqlite_tables(db_path)
            assert "t1" in result
            assert len(result["t1"]) == 2
            assert result["t1"][0]["name"] == "foo"
            assert "t2" in result
            assert result["t2"][0]["v"] == 10
        finally:
            os.unlink(db_path)

    def test_empty_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE t1 (id INT)")
            conn.commit()
            conn.close()
            result = read_sqlite_tables(db_path)
            # Empty tables are excluded from result (no rows to import)
            assert result == {}
        finally:
            os.unlink(db_path)

    def test_nonexistent_file(self):
        assert read_sqlite_tables("/nonexistent/db.sqlite") == {}

    def test_invalid_file(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            f.write(b"not a sqlite database")
            db_path = f.name
        try:
            result = read_sqlite_tables(db_path)
            assert result == {}
        finally:
            os.unlink(db_path)


class TestReadJsonFile:
    def test_read_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value", "num": 42}')
            path = f.name
        try:
            result = read_json_file(path)
            assert result == {"key": "value", "num": 42}
        finally:
            os.unlink(path)

    def test_read_json_array(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('[1, 2, "three"]')
            path = f.name
        try:
            result = read_json_file(path)
            assert result == [1, 2, "three"]
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        assert read_json_file("/nonexistent/file.json") is None

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json")
            path = f.name
        try:
            assert read_json_file(path) is None
        finally:
            os.unlink(path)


class TestReadOrganData:
    def test_reads_memory_organ(self, sb_root: str):
        result = read_organ_data("D_Memory", sb_root)
        assert result["organ_name"] == "D_Memory"
        assert result["meta_type"] == "document"
        assert result["organ_path"] is not None

        # Should find SQLite tables
        sqlite_keys = [k for k in result["found"] if k.startswith("sqlite:")]
        assert len(sqlite_keys) >= 1

        # Should contain role_profiles, role_memories, role_relationships
        tables = {}
        for k in sqlite_keys:
            tables.update(result["found"][k])
        assert "role_profiles" in tables
        assert "role_memories" in tables
        assert "role_relationships" in tables

        # Should have role data
        profiles = tables["role_profiles"]
        assert len(profiles) >= 2
        assert profiles[0]["name"] == "Architect"
        assert profiles[1]["name"] == "Critic"

        # Should find JSON files
        assert "task-registry" in result["json_files"]

        # Should find schema SQL
        schema_found = any(k == "schemas" for k in result["found"])
        assert schema_found

    def test_reads_knowledge_organ(self, sb_root: str):
        result = read_organ_data("D_KnowledgeIntegration", sb_root)
        assert result["organ_name"] == "D_KnowledgeIntegration"
        sqlite_keys = [k for k in result["found"] if k.startswith("sqlite:")]
        assert len(sqlite_keys) >= 1
        tables = {}
        for k in sqlite_keys:
            tables.update(result["found"][k])
        assert "knowledge_metadata" in tables
        assert "evolution_patterns" in tables

    def test_unknown_organ(self, sb_root: str):
        result = read_organ_data("nonexistent", sb_root)
        assert result["organ_name"] == "nonexistent"
        assert result["found"] == {}
        assert result["organ_path"] is None

    def test_no_root(self):
        result = read_organ_data("D_Memory")
        # Should not crash, may find nothing
        assert result["organ_name"] == "D_Memory"


# ======================================================================
# Conversion tests
# ======================================================================


class TestOrganToKnowledgeCards:
    def test_converts_sqlite_rows(self, sb_root: str):
        data = read_organ_data("D_Memory", sb_root)
        cards = organ_to_knowledge_cards("D_Memory", data)
        assert len(cards) >= 4  # 2 role profiles + 2 role memories + 1 relationship + 1 JSON

        # Find role_memories cards
        [c for c in cards if "memory_id" in c.get("source", "")]
        # From role_memories table
        role_mem_cards = [c for c in cards if "r1" in c.get("id", "") or "m1" in c.get("id", "")]
        assert len(role_mem_cards) >= 1

    def test_converts_json_files(self, sb_root: str):
        data = read_organ_data("D_Memory", sb_root)
        cards = organ_to_knowledge_cards("D_Memory", data)
        json_card = next((c for c in cards if "task-registry" in c.get("id", "")), None)
        assert json_card is not None
        assert json_card["source_type"] == "sharedbrain-D_Memory"

    def test_adds_tags_from_row_fields(self, sb_root: str):
        data = read_organ_data("D_KnowledgeIntegration", sb_root)
        cards = organ_to_knowledge_cards("D_KnowledgeIntegration", data)
        # Find the knowledge_metadata card
        k1_cards = [c for c in cards if "k1" in c.get("id", "")]
        assert len(k1_cards) >= 1
        card = k1_cards[0]
        assert "system" in card["tags"]
        assert "design" in card["tags"]

    def test_empty_data(self):
        data = {
            "organ_name": "test",
            "organ_path": None,
            "meta_type": "domain",
            "found": {},
            "json_files": {},
        }
        cards = organ_to_knowledge_cards("test", data)
        assert cards == []


class TestOrganToFacts:
    def test_extracts_role_relationships(self, sb_root: str):
        data = read_organ_data("D_Memory", sb_root)
        facts = organ_to_facts("D_Memory", data)
        rel_facts = [f for f in facts if f["predicate"] == "collaborates_with"]
        assert len(rel_facts) >= 1
        assert "role:r1" in rel_facts[0]["subject"]
        assert "role:r2" in rel_facts[0]["object"]

    def test_extracts_pattern_facts(self, sb_root: str):
        data = read_organ_data("D_KnowledgeIntegration", sb_root)
        facts = organ_to_facts("D_KnowledgeIntegration", data)
        pattern_facts = [f for f in facts if f["id"].startswith("pf_")]
        assert len(pattern_facts) >= 2
        assert pattern_facts[0]["subject"] == "refactor"
        assert pattern_facts[0]["predicate"] == "improves"

    def test_extracts_task_status_facts(self, sb_root: str):
        data = read_organ_data("D_Memory", sb_root)
        facts = organ_to_facts("D_Memory", data)
        status_facts = [f for f in facts if "has_status" in f.get("predicate", "")]
        assert len(status_facts) >= 1
        assignment_facts = [f for f in facts if "assigned_to" in f.get("predicate", "")]
        assert len(assignment_facts) >= 1

    def test_empty_data(self):
        data = {
            "organ_name": "test",
            "organ_path": None,
            "meta_type": "domain",
            "found": {},
            "json_files": {},
        }
        assert organ_to_facts("test", data) == []


class TestOrganToOntologyNodes:
    def test_generates_root_node(self, sb_root: str):
        data = read_organ_data("D_Memory", sb_root)
        nodes = organ_to_ontology_nodes("D_Memory", data)
        root_node = next((n for n in nodes if n["id"] == "organ_D_Memory"), None)
        assert root_node is not None
        assert root_node["name"] == "D_Memory"
        assert root_node["parent"] == "sharedbrain"
        assert root_node["node_type"] == "document"

    def test_generates_child_nodes(self, sb_root: str):
        data = read_organ_data("D_Memory", sb_root)
        nodes = organ_to_ontology_nodes("D_Memory", data)
        # Should have child nodes for each table
        table_nodes = [n for n in nodes if n["id"].startswith("table_")]
        assert len(table_nodes) >= 3  # role_profiles, role_memories, role_relationships
        # Should have a json file node
        json_nodes = [n for n in nodes if n["id"].startswith("json_")]
        assert len(json_nodes) >= 1

    def test_hyphen_organ_name(self, sb_root: str):
        data = read_organ_data("D-Memory", sb_root)
        nodes = organ_to_ontology_nodes("D-Memory", data)
        root_node = next((n for n in nodes if n["id"] == "organ_D_Memory"), None)
        assert root_node is not None

    def test_empty_data(self):
        data = {
            "organ_name": "test",
            "organ_path": None,
            "meta_type": "domain",
            "found": {},
            "json_files": {},
        }
        nodes = organ_to_ontology_nodes("test", data)
        # Should still produce a root node
        assert len(nodes) == 1
        assert nodes[0]["id"] == "organ_test"


# ======================================================================
# Batch import tests
# ======================================================================


class TestBatchImportOrgans:
    def test_imports_all_organs(self, sb_root: str):
        result = batch_import_organs(sharedbrain_root=sb_root)
        assert "cards" in result
        assert "facts" in result
        assert "nodes" in result
        assert "organs" in result
        assert "summary" in result

        # Should have data from both organs
        assert len(result["summary"]) >= 2
        assert "D_Memory" in result["summary"]
        assert "D_KnowledgeIntegration" in result["summary"]

    def test_imports_selected_organs(self, sb_root: str):
        result = batch_import_organs(["D_Memory"], sb_root)
        assert len(result["summary"]) == 1
        assert "D_Memory" in result["summary"]

    def test_summary_has_stats(self, sb_root: str):
        result = batch_import_organs(["D_Memory"], sb_root)
        summary = result["summary"]["D_Memory"]
        assert "cards" in summary
        assert "facts" in summary
        assert "nodes" in summary
        assert summary["meta_type"] == "document"
        assert summary["cards"] >= 4
        assert summary["facts"] >= 1
        assert summary["nodes"] >= 4

    def test_deduplicates_hyphen_and_underscore(self, sb_root: str):
        # Both names should resolve to the same organ
        result_a = batch_import_organs(["D_Memory"], sb_root)
        result_b = batch_import_organs(["D-Memory"], sb_root)
        assert result_a["summary"]["D_Memory"]["cards"] == result_b["summary"]["D_Memory"]["cards"]

    def test_non_existent_root(self):
        result = batch_import_organs(sharedbrain_root="/nonexistent")
        assert result["cards"] == []
        assert result["facts"] == []
        assert result["organs"] == []
