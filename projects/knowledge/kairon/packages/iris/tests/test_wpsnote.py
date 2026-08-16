"""Tests for WPS Note Cloud connector (mocked MCP responses)."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from iris.config import IrisConfig
from iris.connectors.wpsnote import (
    WPSNoteConnector,
    _note_from_info,
    _note_from_list_entry,
    _timestamp_to_iso,
    _xml_wrap,
)

# ----------------------------------------------------------------
# Unit tests for helper functions
# ----------------------------------------------------------------


class TestXmlWrap:
    def test_single_paragraph(self):
        assert _xml_wrap("Hello world") == "<p>Hello world</p>"

    def test_multiple_paragraphs(self):
        result = _xml_wrap("Para one\n\nPara two")
        assert "<p>Para one</p>" in result
        assert "<p>Para two</p>" in result

    def test_empty_text(self):
        assert _xml_wrap("") == "<p></p>"

    def test_xml_escaping(self):
        result = _xml_wrap("A & B < C > D")
        assert "<p>A &amp; B &lt; C &gt; D</p>" in result

    def test_blank_lines_stripped(self):
        result = _xml_wrap("First\n\n\n\nSecond")
        assert "<p>First</p>" in result
        assert "<p>Second</p>" in result


class TestTimestampToIso:
    def test_valid_timestamp(self):
        result = _timestamp_to_iso(1779677391)
        assert result.startswith("2026-05-")  # ~May 2026

    def test_zero_timestamp(self):
        assert _timestamp_to_iso(0) == ""

    def test_none_timestamp(self):
        assert _timestamp_to_iso(0) == ""


class TestNoteFromListEntry:
    def test_basic_note(self):
        entry = {
            "note_id": "12345",
            "title": "My Note",
            "create_time": 1779677391,
            "update_time": 1779678000,
            "intro": "Some intro text",
            "file_name": "my_note.ainote",
        }
        note = _note_from_list_entry(entry)
        assert note.id == "12345"
        assert note.title == "My Note"
        assert note.platform == "wpsnote"
        assert note.content == "Some intro text"
        assert note.created_at != ""

    def test_title_from_filename_fallback(self):
        entry = {
            "note_id": "12345",
            "file_name": "test_note.ainote",
        }
        note = _note_from_list_entry(entry)
        assert note.title == "test_note"
        assert note.id == "12345"

    def test_tags_extracted(self):
        entry = {
            "note_id": "12345",
            "tags": [{"name": "tag1"}, {"name": "tag2"}],
        }
        note = _note_from_list_entry(entry)
        assert note.tags == []


class TestNoteFromInfo:
    def test_with_tags(self):
        info = {
            "note_id": "abc",
            "title": "Test",
            "tags": [{"name": "work"}, {"name": "project"}],
        }
        note = _note_from_info(info)
        assert note.id == "abc"
        assert note.tags == ["work", "project"]

    def test_with_content(self):
        info = {"note_id": "abc"}
        note = _note_from_info(info, "Full content here")
        assert note.content == "Full content here"


# ----------------------------------------------------------------
# Connector tests with mocked MCP client
# ----------------------------------------------------------------


@pytest.fixture
def config(tmp_path):
    # Use isolated config path so tests never overwrite ~/.iris/config.json
    cfg_path = tmp_path / "iris-config.json"
    cfg = IrisConfig(config_path=cfg_path)
    cfg.set("wpsnote.api_key", "test-key-123")
    return cfg


@pytest.fixture
def connector(config):
    return WPSNoteConnector(config)


class TestWPSNoteConnector:
    def test_init(self, connector):
        assert connector.name == "wpsnote"
        assert connector.display_name == "WPS Note"
        assert connector.config.get("wpsnote.api_key") == "test-key-123"

    @patch("iris.connectors.wpsnote.McpClient")
    def test_is_available_yes(self, mock_mcp_cls, connector):
        mock_client = MagicMock()
        mock_client.list_tools.return_value = [{"name": "list_notes"}]
        mock_mcp_cls.return_value = mock_client

        assert connector.is_available() is True

    @patch("iris.connectors.wpsnote.McpClient")
    def test_is_available_no(self, mock_mcp_cls, connector):
        mock_client = MagicMock()
        mock_client.list_tools.side_effect = Exception("Connection refused")
        mock_mcp_cls.return_value = mock_client

        assert connector.is_available() is False

    @patch("iris.connectors.wpsnote.McpClient")
    def test_list_items(self, mock_mcp_cls, connector):
        mock_client = MagicMock()
        mock_client.call_tool.return_value = {
            "content": [
                {
                    "type": "text",
                    "text": '{"notes": [{"note_id": "1", "title": "Note 1"}, {"note_id": "2", "title": "Note 2"}], "has_more": false}',
                }
            ]
        }
        mock_mcp_cls.return_value = mock_client

        items = connector.list_items(limit=10)
        assert len(items) == 2
        assert items[0].id == "1"
        assert items[1].title == "Note 2"

    @patch("iris.connectors.wpsnote.McpClient")
    def test_list_items_with_cursor(self, mock_mcp_cls, connector):
        mock_client = MagicMock()
        mock_client.call_tool.return_value = {"content": [{"type": "text", "text": '{"notes": [], "has_more": false}'}]}
        mock_mcp_cls.return_value = mock_client

        items = connector.list_items(limit=20, cursor="abc123")
        mock_client.call_tool.assert_called_once_with("list_notes", {"limit": 20, "cursor": "abc123"})
        assert items == []

    @patch("iris.connectors.wpsnote.McpClient")
    def test_get_item(self, mock_mcp_cls, connector):
        mock_client = MagicMock()
        # Mock get_note_info response
        mock_client.call_tool.side_effect = [
            {
                "content": [
                    {
                        "type": "text",
                        "text": '{"note_id": "abc", "title": "Test Note", "tags": [{"name": "work"}]}',
                    }
                ]
            },
            {
                "content": [
                    {
                        "type": "text",
                        "text": '{"content_xml": "<p>Hello world</p>", "text": "Hello world"}',
                    }
                ]
            },
        ]
        mock_mcp_cls.return_value = mock_client

        note = connector.get_item("abc")
        assert note is not None
        assert note.id == "abc"
        assert note.title == "Test Note"
        assert note.tags == ["work"]
        assert "Hello world" in note.content

    @patch("iris.connectors.wpsnote.McpClient")
    def test_get_item_not_found(self, mock_mcp_cls, connector):
        from iris.mcp_client import McpError

        mock_client = MagicMock()
        mock_client.call_tool.side_effect = McpError(-32602, "not found")
        mock_mcp_cls.return_value = mock_client

        note = connector.get_item("nonexistent")
        assert note is None

    @patch("iris.connectors.wpsnote.McpClient")
    def test_search(self, mock_mcp_cls, connector):
        mock_client = MagicMock()
        mock_client.call_tool.return_value = {
            "content": [
                {
                    "type": "text",
                    "text": '{"notes": [{"note_id": "1", "title": "Result 1", "intro": "matching text"}], "has_more": false}',
                }
            ]
        }
        mock_mcp_cls.return_value = mock_client

        results = connector.search("matching", limit=5)
        assert len(results) == 1
        mock_client.call_tool.assert_called_once_with("search_notes", {"keyword": "matching", "limit": 5})

    @patch("iris.connectors.wpsnote.McpClient")
    def test_create_item(self, mock_mcp_cls, connector):
        mock_client = MagicMock()
        mock_client.call_tool.side_effect = [
            # create_note returns note_id
            {
                "content": [
                    {
                        "type": "text",
                        "text": '{"note_id": "new123", "title": "My New Note", "link_url": "https://kdocs.cn/link"}',
                    }
                ]
            },
            # add_note_tags returns success
            {"content": [{"type": "text", "text": '{"current_tags": [{"name": "tag1"}]}'}]},
            # get_note_outline returns blocks
            {
                "content": [
                    {
                        "type": "text",
                        "text": '{"blocks": [{"block_id": "b1", "type": "p"}]}',
                    }
                ]
            },
            # edit_block returns success
            {"content": [{"type": "text", "text": '{"success": true}'}]},
        ]
        mock_mcp_cls.return_value = mock_client

        result = connector.create_item(
            title="My New Note",
            content="Hello world",
            tags=["tag1", "tag2"],
        )
        assert result["note_id"] == "new123"
        assert result["link_url"] == "https://kdocs.cn/link"
        assert result["content_written"] is True

    @patch("iris.connectors.wpsnote.McpClient")
    def test_update_item_metadata(self, mock_mcp_cls, connector):
        mock_client = MagicMock()
        mock_client.call_tool.return_value = {"content": [{"type": "text", "text": '{"success": true}'}]}
        mock_mcp_cls.return_value = mock_client

        result = connector.update_item("note1", {"title": "Updated Title", "starred": True})
        assert "metadata" in result["updated"]
        mock_client.call_tool.assert_called_once_with(
            "update_note_info", {"note_id": "note1", "title": "Updated Title", "starred": True}
        )

    @patch("iris.connectors.wpsnote.McpClient")
    def test_update_item_content(self, mock_mcp_cls, connector):
        mock_client = MagicMock()
        # First call: update_note_info (no metadata changes, only content)
        # But since data has no title/starred, only content will trigger _write_content
        # _write_content: get_note_outline + edit_block
        mock_client.call_tool.side_effect = [
            # get_note_outline
            {
                "content": [
                    {
                        "type": "text",
                        "text": '{"blocks": [{"block_id": "b1", "type": "p"}]}',
                    }
                ]
            },
            # edit_block
            {"content": [{"type": "text", "text": '{"success": true}'}]},
        ]
        mock_mcp_cls.return_value = mock_client

        result = connector.update_item("note1", {"content": "New body text"})
        assert "content" in result["updated"]

    @patch("iris.connectors.wpsnote.McpClient")
    def test_delete_item(self, mock_mcp_cls, connector):
        mock_client = MagicMock()
        mock_client.call_tool.return_value = {"content": [{"type": "text", "text": '{"success": true}'}]}
        mock_mcp_cls.return_value = mock_client

        result = connector.delete_item("note1")
        assert result is True
        mock_client.call_tool.assert_called_once_with("trash_note", {"note_id": "note1"})

    @patch("iris.connectors.wpsnote.McpClient")
    def test_delete_item_fails(self, mock_mcp_cls, connector):
        from iris.mcp_client import McpError

        mock_client = MagicMock()
        mock_client.call_tool.side_effect = McpError(-1, "trash failed")
        mock_mcp_cls.return_value = mock_client

        result = connector.delete_item("note1")
        assert result is False

    @patch("iris.connectors.wpsnote.McpClient")
    def test_status(self, mock_mcp_cls, connector):
        mock_client = MagicMock()
        mock_client.list_tools.return_value = [{"name": "tool1"}] * 29
        mock_mcp_cls.return_value = mock_client

        status = connector.status()
        assert status["available"] is True
        assert status["server_url"] == "https://ainote.kdocs.cn/mcp-svc/mcp"
        assert status["api_key_configured"] is True

    @patch("iris.connectors.wpsnote.McpClient")
    def test_sync_research_not_found(self, mock_mcp_cls, connector):
        result = connector.sync_research("nonexistent-id-99999")
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_backward_compat_create_note(self, connector):
        """create_note should delegate to create_item."""
        with patch.object(connector, "create_item") as mock_ci:
            mock_ci.return_value = {"note_id": "abc"}
            result = connector.create_note("Title", "Content", ["tag"])
            mock_ci.assert_called_once_with(title="Title", content="Content", tags=["tag"])
            assert result["note_id"] == "abc"
