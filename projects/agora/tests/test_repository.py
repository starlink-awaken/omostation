"""Tests for MCP Registry ToolCatalog — SQLite-backed tool storage."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
from agora.mcp_registry.repository import ToolCatalog

# ── Helpers ────────────────────────────────────────────────────────────


def _make_tool_info(tool_id: str, **overrides) -> dict:
    """Create a minimal tool info dict."""
    info = {
        "id": tool_id,
        "name": tool_id,
        "description": "test tool",
        "repo_url": "",
        "tool_type": "python",
        "entry": "",
        "version": "1.0.0",
        "tags": ["test"],
        "source": "github",
        "quality_score": 0.5,
        "stars": 10,
        "metadata": {"language": "python"},
    }
    info.update(overrides)
    return info


@pytest.fixture
def catalog():
    """Create a ToolCatalog backed by an in-memory SQLite database."""
    c = ToolCatalog(db_path=":memory:")
    yield c
    c.close()


@pytest.fixture
def persistent_catalog():
    """Create a ToolCatalog backed by a temporary file for persistence tests."""
    with NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    c = ToolCatalog(db_path=db_path)
    yield c, db_path
    c.close()
    Path(db_path).unlink(missing_ok=True)


# ── Tests: initialization ──────────────────────────────────────────────


class TestInit:
    def test_default_db_path(self, monkeypatch):
        """Default db_path uses get_data_dir() / repository.db."""
        monkeypatch.delenv("AGORA_DATA_DIR", raising=False)
        c = ToolCatalog()
        assert c._db_path.endswith("repository.db")
        c.close()

    def test_custom_db_path(self):
        c = ToolCatalog(db_path=":memory:")
        assert c._db_path == ":memory:"
        c.close()

    def test_schema_created(self, catalog):
        """Verify the expected tables and indexes exist."""
        conn = catalog._get_conn()
        # Check tools table exists
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tools'").fetchall()
        assert len(rows) == 1

        # Check indexes
        idx_rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tools'").fetchall()
        idx_names = {r["name"] for r in idx_rows}
        assert "idx_tools_status" in idx_names
        assert "idx_tools_name" in idx_names
        assert "idx_tools_quality" in idx_names

    def test_connection_reuse(self, catalog):
        """_get_conn should return the same connection."""
        conn1 = catalog._get_conn()
        conn2 = catalog._get_conn()
        assert conn1 is conn2

    def test_row_factory(self, catalog):
        """Row factory should be set to sqlite3.Row."""
        conn = catalog._get_conn()
        assert conn.row_factory is sqlite3.Row


# ── Tests: add_tool ────────────────────────────────────────────────────


class TestAddTool:
    def test_add_new_tool(self, catalog):
        tool_id = catalog.add_tool(_make_tool_info("my-tool"))
        assert tool_id == "my-tool"

        tool = catalog.get_tool("my-tool")
        assert tool is not None
        assert tool["name"] == "my-tool"
        assert tool["description"] == "test tool"
        assert tool["status"] == "discovered"
        assert tool["quality_score"] == 0.5
        assert tool["stars"] == 10

    def test_add_tool_with_id_from_name(self, catalog):
        """If no 'id' is provided, fall back to 'name'."""
        tool_id = catalog.add_tool({"name": "name-only", "source": "github"})
        assert tool_id == "name-only"

        tool = catalog.get_tool("name-only")
        assert tool is not None
        assert tool["name"] == "name-only"

    def test_add_tool_no_id_no_name(self, catalog):
        with pytest.raises(ValueError, match="must contain"):
            catalog.add_tool({"source": "github"})

    def test_add_duplicate_tool_updates(self, catalog):
        """Adding the same tool_id twice should update fields (UPSERT)."""
        catalog.add_tool(_make_tool_info("dup", description="first"))
        catalog.add_tool(_make_tool_info("dup", description="second", quality_score=0.9))

        tool = catalog.get_tool("dup")
        assert tool["description"] == "second"
        assert tool["quality_score"] == 0.9

    def test_add_tool_with_list_tags(self, catalog):
        """Tags stored as list should be serialized to JSON."""
        catalog.add_tool(_make_tool_info("tagged", tags=["a", "b", "c"]))
        tool = catalog.get_tool("tagged")
        assert tool["tags"] == ["a", "b", "c"]

    def test_add_tool_with_dict_metadata(self, catalog):
        """Metadata stored as dict should be serialized to JSON."""
        catalog.add_tool(_make_tool_info("meta", metadata={"key": "value", "nested": {"x": 1}}))
        tool = catalog.get_tool("meta")
        assert tool["metadata"] == {"key": "value", "nested": {"x": 1}}

    def test_add_tool_preserves_first_discovered(self, catalog):
        """On UPSERT, first_discovered should keep the original value."""
        catalog.add_tool(_make_tool_info("keeps-date"))
        original = catalog.get_tool("keeps-date")["first_discovered"]

        catalog.add_tool(_make_tool_info("keeps-date", description="updated"))
        updated = catalog.get_tool("keeps-date")["first_discovered"]
        assert updated == original

    def test_add_tool_with_defaults(self, catalog):
        """Tool added with minimal fields should get sensible defaults."""
        catalog.add_tool(_make_tool_info("minimal"))
        tool = catalog.get_tool("minimal")
        assert tool["status"] == "discovered"
        assert tool["usage_count"] == 0
        assert tool["last_used"] == ""
        assert tool["install_error"] == ""


# ── Tests: get_tool ────────────────────────────────────────────────────


class TestGetTool:
    def test_get_existing(self, catalog):
        catalog.add_tool(_make_tool_info("exists"))
        tool = catalog.get_tool("exists")
        assert tool is not None
        assert tool["id"] == "exists"

    def test_get_nonexistent(self, catalog):
        tool = catalog.get_tool("nope")
        assert tool is None

    def test_get_returns_dict(self, catalog):
        catalog.add_tool(_make_tool_info("dict-check"))
        tool = catalog.get_tool("dict-check")
        assert isinstance(tool, dict)

    def test_get_parses_json_tags(self, catalog):
        """Tags stored as JSON string should be parsed back to list."""
        # Manually insert a tool with JSON string tags
        conn = catalog._get_conn()
        conn.execute(
            """INSERT INTO tools (id, name, tags) VALUES (?, ?, ?)""",
            ("json-tags", "json-tags", '["a","b"]'),
        )
        conn.commit()

        tool = catalog.get_tool("json-tags")
        assert tool["tags"] == ["a", "b"]

    def test_get_handles_invalid_json_tags(self, catalog):
        """Invalid JSON in tags should produce empty list."""
        conn = catalog._get_conn()
        conn.execute(
            """INSERT INTO tools (id, name, tags) VALUES (?, ?, ?)""",
            ("bad-tags", "bad-tags", "{not json}"),
        )
        conn.commit()

        tool = catalog.get_tool("bad-tags")
        assert tool["tags"] == []


# ── Tests: list_tools ──────────────────────────────────────────────────


class TestListTools:
    def test_list_all(self, catalog):
        catalog.add_tool(_make_tool_info("a"))
        catalog.add_tool(_make_tool_info("b"))
        catalog.add_tool(_make_tool_info("c"))

        tools = catalog.list_tools()
        assert len(tools) == 3

    def test_list_empty(self, catalog):
        tools = catalog.list_tools()
        assert tools == []

    def test_list_by_status(self, catalog):
        catalog.add_tool(_make_tool_info("loaded"))
        catalog.add_tool(_make_tool_info("idle"))
        catalog.add_tool(_make_tool_info("installed"))

        catalog.update_status("loaded", "loaded")
        catalog.update_status("idle", "idle")
        catalog.update_status("installed", "installed")

        loaded = catalog.list_tools(status="loaded")
        assert len(loaded) == 1
        assert loaded[0]["id"] == "loaded"

        idle = catalog.list_tools(status="idle")
        assert len(idle) == 1
        assert idle[0]["id"] == "idle"

    def test_list_by_status_empty(self, catalog):
        tools = catalog.list_tools(status="loaded")
        assert tools == []

    def test_list_sorted_by_quality(self, catalog):
        catalog.add_tool(_make_tool_info("low", quality_score=0.3))
        catalog.add_tool(_make_tool_info("high", quality_score=0.9))
        catalog.add_tool(_make_tool_info("mid", quality_score=0.6))

        tools = catalog.list_tools()
        scores = [t["quality_score"] for t in tools]
        assert scores == sorted(scores, reverse=True)


# ── Tests: search_tools ────────────────────────────────────────────────


class TestSearchTools:
    def test_search_by_name(self, catalog):
        catalog.add_tool(_make_tool_info("sqlite-tool", description="a SQL database tool"))
        catalog.add_tool(_make_tool_info("redis-tool", description="a cache tool"))

        results = catalog.search_tools(query="sqlite")
        assert len(results) == 1
        assert results[0]["id"] == "sqlite-tool"

    def test_search_by_description(self, catalog):
        catalog.add_tool(_make_tool_info("tool1", description="database connector for PostgreSQL"))
        catalog.add_tool(_make_tool_info("tool2", description="file system access"))

        results = catalog.search_tools(query="database")
        assert len(results) == 1
        assert results[0]["id"] == "tool1"

    def test_search_empty_query(self, catalog):
        catalog.add_tool(_make_tool_info("a"))
        catalog.add_tool(_make_tool_info("b"))

        results = catalog.search_tools(query="")
        assert len(results) == 2

    def test_search_with_status_filter(self, catalog):
        catalog.add_tool(_make_tool_info("sqlite-open", description="sqlite"))
        catalog.add_tool(_make_tool_info("sqlite-loaded", description="sqlite"))
        catalog.add_tool(_make_tool_info("redis", description="redis"))

        catalog.update_status("sqlite-open", "discovered")
        catalog.update_status("sqlite-loaded", "loaded")

        results = catalog.search_tools(query="sqlite", status="loaded")
        assert len(results) == 1
        assert results[0]["id"] == "sqlite-loaded"

    def test_search_limit(self, catalog):
        for i in range(25):
            catalog.add_tool(_make_tool_info(f"tool-{i}"))

        results = catalog.search_tools(query="tool", limit=10)
        assert len(results) == 10

    def test_search_no_match(self, catalog):
        catalog.add_tool(_make_tool_info("exists"))
        results = catalog.search_tools(query="zzzzz")
        assert results == []


# ── Tests: count_by_status ─────────────────────────────────────────────


class TestCountByStatus:
    def test_count_by_status(self, catalog):
        catalog.add_tool(_make_tool_info("a"))
        catalog.add_tool(_make_tool_info("b"))
        catalog.add_tool(_make_tool_info("c"))

        catalog.update_status("a", "loaded")
        catalog.update_status("b", "idle")
        # "c" stays "discovered"

        counts = catalog.count_by_status()
        assert counts.get("loaded") == 1
        assert counts.get("idle") == 1
        assert counts.get("discovered") == 1

    def test_count_by_status_empty(self, catalog):
        counts = catalog.count_by_status()
        assert counts == {}


# ── Tests: update_status ───────────────────────────────────────────────


class TestUpdateStatus:
    def test_update_valid_status(self, catalog):
        catalog.add_tool(_make_tool_info("my-tool"))
        result = catalog.update_status("my-tool", "loaded")
        assert result is True

        tool = catalog.get_tool("my-tool")
        assert tool["status"] == "loaded"

    def test_update_invalid_status(self, catalog):
        catalog.add_tool(_make_tool_info("my-tool"))
        with pytest.raises(ValueError, match="Invalid status"):
            catalog.update_status("my-tool", "invalid")

    def test_update_nonexistent_tool(self, catalog):
        result = catalog.update_status("ghost", "loaded")
        assert result is False  # no rows affected

    def test_full_status_transition(self, catalog):
        """Test the full lifecycle status transition."""
        catalog.add_tool(_make_tool_info("lifecycle"))
        assert catalog.get_tool("lifecycle")["status"] == "discovered"

        catalog.update_status("lifecycle", "installed")
        assert catalog.get_tool("lifecycle")["status"] == "installed"

        catalog.update_status("lifecycle", "loaded")
        assert catalog.get_tool("lifecycle")["status"] == "loaded"

        catalog.update_status("lifecycle", "idle")
        assert catalog.get_tool("lifecycle")["status"] == "idle"


# ── Tests: record_usage ────────────────────────────────────────────────


class TestRecordUsage:
    def test_record_increments_count(self, catalog):
        catalog.add_tool(_make_tool_info("used-tool"))
        catalog.record_usage("used-tool")
        catalog.record_usage("used-tool")
        catalog.record_usage("used-tool")

        tool = catalog.get_tool("used-tool")
        assert tool["usage_count"] == 3

    def test_record_updates_last_used(self, catalog):
        catalog.add_tool(_make_tool_info("time-tool"))
        before = datetime.now(UTC).isoformat()
        catalog.record_usage("time-tool")

        tool = catalog.get_tool("time-tool")
        assert tool["last_used"] >= before

    def test_record_nonexistent_tool(self, catalog):
        result = catalog.record_usage("ghost")
        assert result is False  # no rows affected

    def test_record_new_tool_starts_at_one(self, catalog):
        catalog.add_tool(_make_tool_info("fresh"))
        tool = catalog.get_tool("fresh")
        assert tool["usage_count"] == 0

        catalog.record_usage("fresh")
        tool = catalog.get_tool("fresh")
        assert tool["usage_count"] == 1


# ── Tests: update_quality ──────────────────────────────────────────────


class TestUpdateQuality:
    def test_update_quality(self, catalog):
        catalog.add_tool(_make_tool_info("scored"))
        catalog.update_quality("scored", 0.95)

        tool = catalog.get_tool("scored")
        assert tool["quality_score"] == 0.95

    def test_update_quality_nonexistent(self, catalog):
        result = catalog.update_quality("ghost", 0.5)
        assert result is False


# ── Tests: update_install ──────────────────────────────────────────────


class TestUpdateInstall:
    def test_successful_install(self, catalog):
        catalog.add_tool(_make_tool_info("installing"))
        catalog.update_install("installing", install_path="/usr/local/bin/tool")

        tool = catalog.get_tool("installing")
        assert tool["status"] == "installed"
        assert tool["install_path"] == "/usr/local/bin/tool"
        assert tool["install_error"] == ""

    def test_failed_install_with_error(self, catalog):
        catalog.add_tool(_make_tool_info("failing"))
        catalog.update_install("failing", install_path="", install_error="permission denied")

        tool = catalog.get_tool("failing")
        assert tool["status"] == "installed"
        assert tool["install_error"] == "permission denied"

    def test_install_nonexistent(self, catalog):
        result = catalog.update_install("ghost", install_path="/tmp")
        assert result is False


# ── Tests: remove_tool ─────────────────────────────────────────────────


class TestRemoveTool:
    def test_remove_existing(self, catalog):
        catalog.add_tool(_make_tool_info("gone"))
        result = catalog.remove_tool("gone")
        assert result is True

        tool = catalog.get_tool("gone")
        assert tool is None

    def test_remove_nonexistent(self, catalog):
        result = catalog.remove_tool("ghost")
        assert result is False

    def test_remove_then_add_same_id(self, catalog):
        """After removal, a new tool with the same ID can be added."""
        catalog.add_tool(_make_tool_info("recycled", description="old"))
        catalog.remove_tool("recycled")
        catalog.add_tool(_make_tool_info("recycled", description="new"))

        tool = catalog.get_tool("recycled")
        assert tool["description"] == "new"


# ── Tests: persistence ─────────────────────────────────────────────────


class TestPersistence:
    def test_data_survives_reopen(self, persistent_catalog):
        """Data should be written to disk and survive catalog close/reopen."""
        c1, db_path = persistent_catalog
        c1.add_tool(_make_tool_info("persistent"))
        c1.record_usage("persistent")
        c1.close()

        c2 = ToolCatalog(db_path=db_path)
        tool = c2.get_tool("persistent")
        assert tool is not None
        assert tool["name"] == "persistent"
        assert tool["usage_count"] == 1
        c2.close()


# ── Tests: close ───────────────────────────────────────────────────────


class TestClose:
    def test_close_releases_connection(self, catalog):
        catalog._get_conn()
        catalog.close()
        assert catalog._conn is None

    def test_close_idempotent(self, catalog):
        catalog.close()
        catalog.close()  # should not raise

    def test_auto_reconnect_after_close(self, catalog):
        """After close, next operation should create a new connection."""
        catalog.close()
        catalog.list_tools()  # should work, not raise
        assert catalog._conn is not None


# ── Tests: JSON field edge cases ───────────────────────────────────────


class TestJSONEdgeCases:
    def test_tags_stored_as_string(self, catalog):
        """If tags is already stored as JSON string, it should be parsed."""
        conn = catalog._get_conn()
        conn.execute(
            """INSERT INTO tools (id, name, tags) VALUES (?, ?, ?)""",
            ("str-tags", "str-tags", '["x","y"]'),
        )
        conn.commit()

        tool = catalog.get_tool("str-tags")
        assert tool["tags"] == ["x", "y"]

    def test_metadata_stored_as_string(self, catalog):
        """If metadata is already stored as JSON string, it should be parsed."""
        conn = catalog._get_conn()
        conn.execute(
            """INSERT INTO tools (id, name, metadata) VALUES (?, ?, ?)""",
            ("str-meta", "str-meta", '{"key":"value"}'),
        )
        conn.commit()

        tool = catalog.get_tool("str-meta")
        assert tool["metadata"] == {"key": "value"}

    def test_none_tags_becomes_empty_list(self, catalog):
        """Tags field missing or None should result in empty list."""
        conn = catalog._get_conn()
        conn.execute(
            """INSERT INTO tools (id, name) VALUES (?, ?)""",
            ("no-tags", "no-tags"),
        )
        conn.commit()

        tool = catalog.get_tool("no-tags")
        assert tool["tags"] == []

    def test_empty_metadata_no_error(self, catalog):
        """Empty or missing metadata should produce empty dict."""
        catalog.add_tool(_make_tool_info("no-meta", metadata={}))
        tool = catalog.get_tool("no-meta")
        assert tool["metadata"] == {}


# ── Phase 2 Tests: update_entry ───────────────────────────────────────


class TestUpdateEntry:
    def test_update_entry_success(self, catalog):
        catalog.add_tool(_make_tool_info("update-me", entry="old_entry"))
        result = catalog.update_entry("update-me", entry="new_entry")
        assert result is True

        tool = catalog.get_tool("update-me")
        assert tool["entry"] == "new_entry"

    def test_update_entry_with_metadata(self, catalog):
        catalog.add_tool(_make_tool_info("meta-update", entry="old"))
        result = catalog.update_entry(
            "meta-update",
            entry="new",
            metadata={"command": "my-mcp", "args": ["--port", "8080"]},
        )
        assert result is True

        tool = catalog.get_tool("meta-update")
        assert tool["entry"] == "new"
        assert tool["metadata"]["command"] == "my-mcp"
        assert tool["metadata"]["args"] == ["--port", "8080"]

    def test_update_entry_merges_metadata(self, catalog):
        """update_entry should merge new metadata with existing."""
        catalog.add_tool(
            _make_tool_info(
                "merge-test",
                metadata={"existing_key": "value", "command": "old-cmd"},
            )
        )
        result = catalog.update_entry(
            "merge-test",
            metadata={"command": "new-cmd"},
        )
        assert result is True

        tool = catalog.get_tool("merge-test")
        assert tool["metadata"]["existing_key"] == "value"
        assert tool["metadata"]["command"] == "new-cmd"

    def test_update_entry_nonexistent(self, catalog):
        result = catalog.update_entry("ghost", entry="something")
        assert result is False

    def test_update_entry_install_path(self, catalog):
        catalog.add_tool(_make_tool_info("path-test", install_path=""))
        result = catalog.update_entry("path-test", install_path="/usr/local/bin/mcp-tool")
        assert result is True

        tool = catalog.get_tool("path-test")
        assert tool["install_path"] == "/usr/local/bin/mcp-tool"
