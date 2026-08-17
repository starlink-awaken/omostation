"""Tests for MCP-based search backends."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers — build realistic async context manager mocks for sse_client / ClientSession
# ---------------------------------------------------------------------------


def _make_async_cm(return_value):
    """Create an async context manager mock that returns *return_value* on enter."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=return_value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _make_text_content_block(text: str):
    """Create a mock content block with a .text attribute."""
    block = MagicMock()
    block.text = text
    return block


# ---------------------------------------------------------------------------
# Tests: _call_mcp_tool
# ---------------------------------------------------------------------------


class TestCallMcpTool:
    """Tests for _call_mcp_tool()."""

    @pytest.mark.asyncio
    @patch("minerva.search.mcp_backends.ClientSession")
    @patch("minerva.search.mcp_backends.sse_client")
    async def test_call_mcp_tool_success_returns_text(self, mock_sse_client, mock_client_session):
        """_call_mcp_tool returns concatenated text from content blocks on success."""
        from minerva.search.mcp_backends import _call_mcp_tool

        # Mock the tool result
        mock_result = MagicMock()
        mock_result.content = [
            _make_text_content_block("Hello "),
            _make_text_content_block("World"),
        ]

        # Mock ClientSession — async context manager
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=mock_result)
        mock_client_session.return_value = _make_async_cm(mock_session)

        # Mock sse_client — async context manager
        fake_streams = ("read_stream", "write_stream")
        mock_sse_client.return_value = _make_async_cm(fake_streams)

        result = await _call_mcp_tool(
            url="https://example.com/mcp",
            tool_name="test_tool",
            arguments={"key": "value"},
        )

        assert result == "Hello \nWorld"
        mock_session.initialize.assert_awaited_once()
        mock_session.call_tool.assert_awaited_once_with("test_tool", {"key": "value"})

    @pytest.mark.asyncio
    @patch("minerva.search.mcp_backends.ClientSession")
    @patch("minerva.search.mcp_backends.sse_client")
    async def test_call_mcp_tool_none_when_no_content(self, mock_sse_client, mock_client_session):
        """_call_mcp_tool returns None when result.content is falsy."""
        from minerva.search.mcp_backends import _call_mcp_tool

        mock_result = MagicMock()
        mock_result.content = []  # empty — falsy

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=mock_result)
        mock_client_session.return_value = _make_async_cm(mock_session)

        fake_streams = ("read_stream", "write_stream")
        mock_sse_client.return_value = _make_async_cm(fake_streams)

        result = await _call_mcp_tool(
            url="https://example.com/mcp",
            tool_name="test_tool",
            arguments={},
        )

        assert result is None

    @pytest.mark.asyncio
    @patch("minerva.search.mcp_backends.ClientSession")
    @patch("minerva.search.mcp_backends.sse_client")
    async def test_call_mcp_tool_returns_none_on_exception(self, mock_sse_client, mock_client_session):
        """_call_mcp_tool returns None when sse_client raises an exception."""
        from minerva.search.mcp_backends import _call_mcp_tool

        mock_sse_client.return_value = _make_async_cm(None)
        mock_sse_client.return_value.__aenter__ = AsyncMock(side_effect=ConnectionError("Connection refused"))

        result = await _call_mcp_tool(
            url="https://example.com/mcp",
            tool_name="test_tool",
            arguments={},
        )

        assert result is None


# ---------------------------------------------------------------------------
# Tests: search_web_search_prime
# ---------------------------------------------------------------------------


class TestSearchWebSearchPrime:
    """Tests for search_web_search_prime()."""

    @pytest.mark.asyncio
    @patch("minerva.search.mcp_backends._call_mcp_tool")
    async def test_parses_results_from_mcp_json(self, mock_call_mcp):
        """search_web_search_prime parses JSON list response into SearchResult objects."""
        import json

        mock_call_mcp.return_value = json.dumps(
            [
                {
                    "title": "Test Page",
                    "url": "https://example.com",
                    "snippet": "A test snippet",
                },
                {
                    "title": "Another",
                    "link": "https://another.com",
                    "content": "Some content here that is very long...",
                },
            ]
        )

        from minerva.search.mcp_backends import search_web_search_prime

        results = await search_web_search_prime(
            query="test query",
            api_key="fake-key",
        )

        assert len(results) == 2
        assert results[0].title == "Test Page"
        assert results[0].url == "https://example.com"
        assert results[0].snippet == "A test snippet"
        assert results[0].source == "zhipu-search"
        # Second result uses "link" for url and "content" for snippet
        assert results[1].url == "https://another.com"
        assert results[1].snippet.startswith("Some content")

    @pytest.mark.asyncio
    @patch("minerva.search.mcp_backends._call_mcp_tool")
    async def test_returns_empty_list_when_mcp_returns_none(self, mock_call_mcp):
        """search_web_search_prime returns empty list when _call_mcp_tool returns None."""
        mock_call_mcp.return_value = None

        from minerva.search.mcp_backends import search_web_search_prime

        results = await search_web_search_prime(
            query="test query",
            api_key="fake-key",
        )

        assert results == []
        mock_call_mcp.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("minerva.search.mcp_backends._call_mcp_tool")
    async def test_handles_malformed_json_gracefully(self, mock_call_mcp):
        """search_web_search_prime returns empty list on JSON parse error."""
        mock_call_mcp.return_value = "not valid json {{{"

        from minerva.search.mcp_backends import search_web_search_prime

        results = await search_web_search_prime(
            query="test query",
            api_key="fake-key",
        )

        assert results == []


# ---------------------------------------------------------------------------
# Tests: extract_zread
# ---------------------------------------------------------------------------


class TestExtractZread:
    """Tests for extract_zread()."""

    @pytest.mark.asyncio
    @patch("minerva.search.mcp_backends._call_mcp_tool")
    async def test_returns_extracted_text(self, mock_call_mcp):
        """extract_zread returns the text from the MCP zread tool call."""
        mock_call_mcp.return_value = "# Extracted Content\n\nThis is the page content."

        from minerva.search.mcp_backends import extract_zread

        result = await extract_zread(
            url="https://example.com/article",
            api_key="fake-key",
        )

        assert result == "# Extracted Content\n\nThis is the page content."
        mock_call_mcp.assert_awaited_once_with(
            url="https://open.bigmodel.cn/api/mcp/zread/mcp",
            tool_name="zread",
            arguments={"url": "https://example.com/article"},
            headers={"Authorization": "Bearer fake-key"},
        )

    @pytest.mark.asyncio
    @patch("minerva.search.mcp_backends._call_mcp_tool")
    async def test_returns_empty_string_when_mcp_returns_none(self, mock_call_mcp):
        """extract_zread returns empty string when _call_mcp_tool returns None."""
        mock_call_mcp.return_value = None

        from minerva.search.mcp_backends import extract_zread

        result = await extract_zread(
            url="https://example.com/article",
            api_key="fake-key",
        )

        assert result == ""
