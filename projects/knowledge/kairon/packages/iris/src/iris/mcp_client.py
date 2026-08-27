"""Synchronous MCP HTTP SSE client.

Connects to any MCP-over-HTTP-SSE server using httpx.
No async needed — we parse SSE events from standard POST responses.

The MCP HTTP SSE transport works as follows:
  1. POST JSON-RPC requests to the server URL
  2. Server responds with SSE events (event: message\ndata: {...})
  3. Each SSE event contains a JSON-RPC response
"""

from __future__ import annotations

import json
import logging
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"
DEFAULT_TIMEOUT = 30.0


class McpError(Exception):
    """Raised when an MCP server returns an error response."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"[{code}] {message}")


class McpClient:
    """Synchronous MCP client over HTTP SSE transport.

    Usage:
        client = McpClient(url="https://example.com/mcp", api_key="...")
        client.initialize()
        result = client.call_tool("list_notes", {"limit": 20})
    """

    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        client_name: str = "iris",
        client_version: str = "0.1.0",
    ) -> None:
        self._url = url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client_name = client_name
        self._client_version = client_version
        self._request_id = 0
        self._initialized = False
        self._server_info: dict[str, Any] = {}

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def initialize(self) -> dict[str, Any]:
        """Send initialize request to the MCP server.

        Must be called once before any tool calls.
        Returns the server's capabilities / server info.
        """
        result = self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": self._client_name,
                    "version": self._client_version,
                },
            },
        )
        self._initialized = True
        self._server_info = result
        return result

    def ping(self) -> bool:
        """Simple ping to check connectivity."""
        try:
            self._request("ping", {})
            return True
        except Exception:
            return False

    def list_tools(self) -> list[dict[str, Any]]:
        """List all available tools from the server."""
        result = self._request("tools/list", {})
        return cast("list[dict[str, Any]]", result.get("tools", []))

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a named tool with the given arguments.

        Returns the tool result dict (the content array is in result["content"]).
        Raises McpError on server-reported errors.
        """
        if not self._initialized:
            self.initialize()
        result = self._request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )
        return result

    def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a resource by URI."""
        result = self._request("resources/read", {"uri": uri})
        return result

    def close(self) -> None:
        """Clean up resources."""
        self._initialized = False

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and parse the SSE response.

        Returns the 'result' portion of the response.
        Raises McpError on error responses.
        """
        request_id = self._next_id()
        body = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id,
        }

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    self._url,
                    headers=headers,
                    json=body,
                )
                resp.raise_for_status()

                sse_data = self._parse_sse(resp.text)
                if sse_data is None:
                    # Try parsing as plain JSON
                    try:
                        sse_data = resp.json()
                    except Exception:
                        raise McpError(
                            -32700,
                            f"Failed to parse response: {resp.text[:500]}",
                        )

        except httpx.HTTPStatusError as e:
            raise McpError(
                e.response.status_code,
                f"HTTP error: {e.response.text[:300]}",
            )
        except httpx.RequestError as e:
            raise McpError(
                -1,
                f"Connection failed: {e}",
            )

        # Check for JSON-RPC error
        if "error" in sse_data:
            err = sse_data["error"]
            raise McpError(
                err.get("code", 0),
                err.get("message", "Unknown error"),
                err.get("data"),
            )

        return cast("dict[str, Any]", sse_data.get("result", {}))

    @staticmethod
    def _parse_sse(text: str) -> dict[str, Any] | None:
        """Parse the first SSE event from a response body.

        SSE format:
            event: message
            data: {...json...}

        Returns the parsed JSON data dict, or None if no SSE event found.
        """
        data_lines: list[str] = []
        in_event = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("data: "):
                data_lines.append(stripped[6:])
                in_event = True
            elif stripped == "" and in_event:
                # Empty line marks end of an SSE event
                if data_lines:
                    break
                in_event = False
            elif stripped.startswith("event:"):
                continue
            elif stripped.startswith("id:"):
                continue

        if data_lines:
            raw = "".join(data_lines)
            try:
                return cast("dict[str, Any] | None", json.loads(raw))
            except json.JSONDecodeError:
                return None

        return None

    @staticmethod
    def extract_text_content(result: dict[str, Any]) -> str:
        """Extract the text content from a tool result.

        MCP tool results have 'content' as a list of content items
        with 'type' and 'text' fields.
        """
        content_items = result.get("content", [])
        texts: list[str] = []
        for item in content_items:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "\n".join(texts)

    @staticmethod
    def extract_json_content(result: dict[str, Any]) -> Any:
        """Extract and parse JSON text content from a tool result."""
        text = McpClient.extract_text_content(result)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        return None
