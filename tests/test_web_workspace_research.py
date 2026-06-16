"""Tests for web/workspace_research.py — research data access layer."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from web.workspace_research import (
    _parse_json_list,
    archive_research,
    get_research_detail,
    list_recent_research,
    publish_brief,
    rename_research,
    search_research,
    sync_published,
    tag_research,
    unarchive_research,
)


@pytest.fixture
def mock_db(tmp_path):
    """Create a temporary SQLite database with research table."""
    db_path = tmp_path / ".workspace" / "data.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE research (
            id INTEGER PRIMARY KEY,
            topic TEXT,
            summary TEXT,
            full_text TEXT,
            created_at TEXT,
            source_count INTEGER DEFAULT 0,
            tags TEXT DEFAULT '[]',
            archived_at TEXT,
            archive_reason TEXT,
            quarantined_at TEXT,
            quarantine_reason TEXT,
            published_path TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE research_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            research_id INTEGER,
            event_type TEXT,
            description TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE research_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER,
            child_id INTEGER,
            relation_type TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE published_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            research_id INTEGER,
            style TEXT,
            output_path TEXT,
            published_at TEXT
        )
    """)
    conn.execute("""
        INSERT INTO research (id, topic, summary, full_text, created_at, source_count, tags)
        VALUES (1, 'Test Topic', 'Test summary', 'Full text content', '2026-01-01', 5, '["ai", "ml"]')
    """)
    conn.execute("""
        INSERT INTO research (id, topic, summary, full_text, created_at, source_count, tags)
        VALUES (2, 'Another Topic', 'Another summary', 'More content', '2026-01-02', 3, '["llm"]')
    """)
    conn.commit()
    conn.close()

    with patch("web.workspace_research.workspace_home", return_value=tmp_path):
        yield db_path


class TestParseJsonList:
    def test_none(self):
        assert _parse_json_list(None) == []

    def test_empty(self):
        assert _parse_json_list("") == []

    def test_valid_json(self):
        assert _parse_json_list('["a", "b", "c"]') == ["a", "b", "c"]

    def test_invalid_json(self):
        assert _parse_json_list("not json") == []

    def test_with_none_items(self):
        result = _parse_json_list('["a", null, "b"]')
        assert result == ["a", "b"]


class TestListRecentResearch:
    def test_no_db(self, tmp_path):
        with patch("web.workspace_research.workspace_home", return_value=tmp_path):
            result = list_recent_research()
        assert result["research"] == []
        assert result["total"] == 0

    def test_with_db(self, mock_db):
        result = list_recent_research()
        assert result["total"] == 2
        assert result["research"][0]["topic"] == "Another Topic"

    def test_with_limit(self, mock_db):
        result = list_recent_research(limit=1)
        assert result["total"] == 1


class TestSearchResearch:
    def test_no_db(self, tmp_path):
        with patch("web.workspace_research.workspace_home", return_value=tmp_path):
            result = search_research()
        assert result["research"] == []

    def test_search_all(self, mock_db):
        result = search_research()
        assert result["total"] == 2

    def test_search_by_query(self, mock_db):
        result = search_research(q="Test")
        assert result["total"] >= 1

    def test_search_by_tag(self, mock_db):
        result = search_research(tag="ai")
        assert result["total"] >= 1

    def test_search_archived(self, mock_db):
        result = search_research(status="archived")
        assert result["total"] == 0


class TestGetResearchDetail:
    def test_no_db(self, tmp_path):
        with patch("web.workspace_research.workspace_home", return_value=tmp_path):
            result = get_research_detail(1)
        assert result is None

    def test_found(self, mock_db):
        result = get_research_detail(1)
        assert result is not None
        assert result["record"]["topic"] == "Test Topic"

    def test_not_found(self, mock_db):
        result = get_research_detail(999)
        assert result is None


class TestArchiveResearch:
    def test_no_db(self, tmp_path):
        with patch("web.workspace_research.workspace_home", return_value=tmp_path):
            result = archive_research(1)
        assert result is False

    def test_archive(self, mock_db):
        result = archive_research(1)
        assert result is True

    def test_not_found(self, mock_db):
        result = archive_research(999)
        assert result is False


class TestUnarchiveResearch:
    def test_no_db(self, tmp_path):
        with patch("web.workspace_research.workspace_home", return_value=tmp_path):
            result = unarchive_research(1)
        assert result is False


class TestTagResearch:
    def test_no_db(self, tmp_path):
        with patch("web.workspace_research.workspace_home", return_value=tmp_path):
            result = tag_research(1, ["new-tag"])
        assert result is False

    def test_tag(self, mock_db):
        result = tag_research(1, ["new-tag"])
        assert result is True


class TestRenameResearch:
    def test_no_db(self, tmp_path):
        with patch("web.workspace_research.workspace_home", return_value=tmp_path):
            result = rename_research(1, "New Title")
        assert result is False

    def test_rename(self, mock_db):
        result = rename_research(1, "New Title")
        assert result is True


class TestPublishBrief:
    def test_no_db(self, tmp_path):
        with patch("web.workspace_research.workspace_home", return_value=tmp_path):
            result = publish_brief(1)
        assert result is None


class TestSyncPublished:
    def test_no_db(self, tmp_path):
        with patch("web.workspace_research.workspace_home", return_value=tmp_path):
            result = sync_published(1)
        assert result is None
