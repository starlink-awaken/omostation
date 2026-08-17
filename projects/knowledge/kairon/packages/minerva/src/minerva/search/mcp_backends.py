"""MCP-based search backends — call external MCP servers as data sources."""

from __future__ import annotations

from typing import Any

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client


async def _call_mcp_tool(
    url: str,
    tool_name: str,
    arguments: dict,
    headers: dict | None = None,
    timeout: int = 20,
) -> Any:
    """Call an MCP tool via HTTP/SSE transport.

    Args:
        url: MCP server URL (SSE endpoint)
        tool_name: Name of the tool to call
        arguments: Tool arguments dict
        headers: Optional HTTP headers (e.g., Authorization)
        timeout: Request timeout in seconds

    Returns:
        Tool result content, or None on failure
    """
    try:
        async with (
            sse_client(url=url, headers=headers, timeout=timeout) as streams,
            ClientSession(*streams) as session,
        ):
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            if result.content:
                # Extract text from content blocks
                texts = []
                for block in result.content:
                    if hasattr(block, "text"):
                        texts.append(block.text)  # type: ignore[reportAttributeAccessIssue]
                return "\n".join(texts)
            return None
    except Exception:
        return None


async def search_web_search_prime(
    query: str,
    api_key: str,
    max_results: int = 10,
) -> list[Any]:
    """Search via Zhipu web-search-prime MCP server.

    Uses the MCP protocol to call web_search_prime tool.
    API: https://open.bigmodel.cn/api/mcp/web_search_prime/mcp
    """
    url = "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"
    headers = {"Authorization": f"Bearer {api_key}"}
    text = await _call_mcp_tool(
        url=url,
        tool_name="web_search_prime",
        arguments={
            "search_query": query,
            "content_size": "medium",
            "location": "cn",
        },
        headers=headers,
    )
    if not text:
        return []

    # Parse results from MCP response
    results = []
    try:
        import json

        data = json.loads(text) if isinstance(text, str) else text
        # MCP returns results in various formats; handle list of dicts
        items = data if isinstance(data, list) else data.get("results", data.get("data", []))
        if isinstance(items, list):
            from minerva.search.engine import SearchResult

            for item in items:
                if isinstance(item, dict):
                    results.append(
                        SearchResult(
                            title=item.get("title", "") or "",
                            url=item.get("url") or item.get("link") or "",
                            snippet=(item.get("snippet") or item.get("content") or "")[:500],
                            source="zhipu-search",
                        )
                    )
    except (json.JSONDecodeError, TypeError):  # type: ignore[reportPossiblyUnboundVariable]
        pass
    return results


async def extract_zread(url: str, api_key: str) -> str:
    """Extract and convert URL content via Zhipu zread MCP server.

    Uses MCP protocol to call zread tool for content extraction.
    API: https://open.bigmodel.cn/api/mcp/zread/mcp
    """
    mcp_url = "https://open.bigmodel.cn/api/mcp/zread/mcp"
    headers = {"Authorization": f"Bearer {api_key}"}
    text = await _call_mcp_tool(
        url=mcp_url,
        tool_name="zread",
        arguments={"url": url},
        headers=headers,
    )
    return text or ""
