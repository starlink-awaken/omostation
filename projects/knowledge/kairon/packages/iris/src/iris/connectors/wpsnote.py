"""WPS Note connector — connects directly to WPS Note Cloud MCP server.

Replaces the old subprocess-based stub that had ID-mapping bugs.
Uses MCP over HTTP SSE to communicate with the WPS Note Cloud server directly.

Configuration (required — at least one must be set):
  - Config key: wpsnote.api_key
  - Environment variable: IRIS_WPSNOTE_API_KEY
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC
from typing import Any, cast

from iris.base import BaseConnector
from iris.config import IrisConfig
from iris.mcp_client import McpClient, McpError
from iris.models import Note

logger = logging.getLogger(__name__)

# WPS Note Cloud MCP server
WPSNOTE_MCP_URL = "https://ainote.kdocs.cn/mcp-svc/mcp"
DEFAULT_API_KEY = ""


def _xml_wrap(text: str) -> str:
    """Wrap plain text in WPS XML paragraph tags, splitting by double newlines."""
    paragraphs = text.strip().split("\n\n")
    wrapped = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Escape XML special chars
        para = para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        wrapped.append(f"<p>{para}</p>")
    return "\n".join(wrapped) if wrapped else "<p></p>"


def _timestamp_to_iso(ts: int) -> str:
    """Convert a unix timestamp (seconds) to ISO 8601 string."""
    from datetime import datetime

    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(ts, tz=UTC).isoformat()
    except (OSError, ValueError, OverflowError):
        return ""


def _extract_notes_from_list(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the notes array from a list_notes response."""
    content = raw.get("content", [])
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            try:
                data = json.loads(item["text"])
                return cast("list[dict[str, Any]]", data.get("notes", []))
            except (json.JSONDecodeError, KeyError):
                continue
    return []


def _extract_single_result(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Extract the result metadata from a tool response that returns a single note.

    Cloud MCP may return either:
      - flat: ``{"note_id": "...", "title": "..."}``
      - wrapped: ``{"note": {"note_id": "...", ...}, "tags": [...]}``
      - structuredContent: ``{"structuredContent": {"note": {...}}}``
    """
    data: Any = None

    # Prefer structuredContent when present (typed payload)
    sc = raw.get("structuredContent")
    if isinstance(sc, dict) and sc:
        data = sc
    else:
        text = ""
        if "content" in raw:
            for item in raw.get("content", []):
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    break
        if text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = None
        if data is None:
            data = raw

    if not isinstance(data, dict):
        return None

    # Unwrap {"note": {...}, "tags": [...]}
    note = data.get("note")
    if isinstance(note, dict) and (note.get("note_id") or note.get("id")):
        out = dict(note)
        tags = data.get("tags")
        if tags is not None and "tags" not in out:
            out["tags"] = tags
        return cast("dict[str, Any]", out)

    return cast("dict[str, Any]", data)


def _note_from_list_entry(entry: dict[str, Any]) -> Note:
    """Convert a WPS note dict from list_notes into a Note."""
    return Note(
        id=entry.get("note_id", ""),
        title=entry.get("title", "") or entry.get("file_name", "").replace(".ainote", ""),
        platform="wpsnote",
        created_at=_timestamp_to_iso(entry.get("create_time", 0)),
        updated_at=_timestamp_to_iso(entry.get("update_time", 0)),
        content=entry.get("intro", ""),
        tags=[],
    )


def _note_from_info(info: dict[str, Any], content_text: str = "") -> Note:
    """Convert a WPS note info dict (from get_note_info) into a Note."""
    return Note(
        id=info.get("note_id", ""),
        title=info.get("title", "") or info.get("file_name", "").replace(".ainote", ""),
        platform="wpsnote",
        created_at=_timestamp_to_iso(info.get("create_time", 0)),
        updated_at=_timestamp_to_iso(info.get("update_time", 0)),
        content=content_text or info.get("intro", ""),
        tags=[t.get("name", "") for t in info.get("tags", []) if isinstance(t, dict)],
    )


def _extract_text_from_content(raw: dict[str, Any]) -> str:
    """Extract text content from a read_note_content response.

    Cloud MCP returns body as ``content`` (HTML/XML) and/or ``content_xml`` / ``text``.
    """
    # structuredContent first
    sc = raw.get("structuredContent")
    if isinstance(sc, dict):
        body = sc.get("content_xml") or sc.get("content") or sc.get("text") or ""
        if body:
            return str(body)

    content = raw.get("content", [])
    texts = []
    for item in content:
        if isinstance(item, dict):
            t = item.get("text", "")
            try:
                parsed = json.loads(t)
                if isinstance(parsed, dict):
                    # Take the full content text from the response
                    texts.append(parsed.get("content_xml", "") or parsed.get("content", "") or parsed.get("text", ""))
                else:
                    texts.append(t)
            except (json.JSONDecodeError, TypeError):
                texts.append(t)
    return "\n".join(texts)


class WPSNoteConnector(BaseConnector):
    """Connector for WPS Note Cloud via MCP HTTP SSE.

    Reads and writes WPS Notes through the WPS Note Cloud MCP server.
    """

    name = "wpsnote"
    display_name = "WPS Note"

    def __init__(self, config: IrisConfig | None = None) -> None:
        self._config = config or IrisConfig()
        self._client: McpClient | None = None
        self._available: bool | None = None

    @property
    def config(self) -> IrisConfig:
        return self._config

    def _get_api_key(self) -> str:
        """Resolve API key: config file > env var."""
        key = self._config.get("wpsnote.api_key") or os.environ.get("IRIS_WPSNOTE_API_KEY", DEFAULT_API_KEY)
        if not key:
            logger.warning(
                "WPS Note API key not configured — set IRIS_WPSNOTE_API_KEY env var or config wpsnote.api_key"
            )
        return key

    def _get_client(self) -> McpClient:
        """Get or create the MCP client."""
        if self._client is None:
            self._client = McpClient(
                url=WPSNOTE_MCP_URL,
                api_key=self._get_api_key(),
            )
        return self._client

    def is_available(self) -> bool:
        """Check if the WPS Note Cloud MCP server is reachable."""
        if self._available is not None:
            return self._available
        try:
            client = self._get_client()
            # Try listing tools as a health check
            tools = client.list_tools()
            self._available = len(tools) > 0
        except Exception as exc:
            self._available = False
            # Expected when API key missing/invalid; avoid full traceback on `iris list`
            logger.warning("WPS Note MCP server unavailable: %s", exc)
        return self._available

    def list_items(
        self,
        limit: int = 20,
        cursor: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        subdir: str | None = None,
        chat_id: str | None = None,
        **kwargs: Any,
    ) -> list[Note]:
        """List notes from WPS Note Cloud."""
        params: dict[str, Any] = {"limit": min(limit, 100)}
        if cursor:
            params["cursor"] = cursor

        raw = self._get_client().call_tool("list_notes", params)
        entries = _extract_notes_from_list(raw)
        return [_note_from_list_entry(e) for e in entries[:limit]]

    def get_item(self, id: str) -> Note | None:
        """Get a single note by its note_id, including full content."""
        client = self._get_client()

        # Step 1: Get note info
        try:
            info_raw = client.call_tool("get_note_info", {"note_id": id})
        except McpError as e:
            if e.code == -32602 or "not found" in e.message.lower():
                return None
            raise

        info = _extract_single_result(info_raw)
        if not info or not info.get("note_id"):
            return None

        # Step 2: Get content
        content_text = ""
        try:
            content_raw = client.call_tool("read_note_content", {"note_id": id, "max_length": 50000})
            content_text = _extract_text_from_content(content_raw)
        except McpError:
            # content reading may fail for empty notes
            pass

        return _note_from_info(info, content_text)

    def search(self, query: str, limit: int = 10) -> list[Note]:
        """Search notes by keyword (full-text search)."""
        raw = self._get_client().call_tool(
            "search_notes",
            {
                "keyword": query,
                "limit": min(limit, 20),
            },
        )
        entries = _extract_notes_from_list(raw)
        return [_note_from_list_entry(e) for e in entries[:limit]]

    def create_item(
        self,
        title: str = "",
        content: str = "",
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a new WPS note with title, content, and optional tags.

        Returns a dict with 'note_id', 'title', 'link_url' on success.
        """
        client = self._get_client()

        # Step 1: Create note
        create_raw = client.call_tool("create_note", {"title": title})
        create_data = _extract_single_result(create_raw)
        note_id = create_data.get("note_id", "") if isinstance(create_data, dict) else ""
        if not note_id:
            raise McpError(-1, "create_note returned no note_id", create_raw)

        result: dict[str, Any] = {
            "note_id": note_id,
            "title": title,
            "link_url": create_data.get("link_url", "") if isinstance(create_data, dict) else "",
        }

        # Step 2: Add tags
        if tags:
            try:
                client.call_tool(
                    "add_note_tags",
                    {
                        "note_id": note_id,
                        "tag_names": tags,
                    },
                )
                result["tags"] = tags
            except McpError as e:
                logger.warning("Failed to add tags to note %s: %s", note_id, e)

        # Step 3: Write content
        if content:
            try:
                self._write_content(client, note_id, content)
                result["content_written"] = True
            except McpError as e:
                logger.warning("Failed to write content to note %s: %s", note_id, e)
                result["content_written"] = False

        return result

    def update_item(self, id: str, data: dict[str, Any]) -> dict[str, Any]:  # type: ignore[reportIncompatibleMethodOverride]
        """Update a note's title, content, and/or starred status.

        Args:
            id: The note_id to update.
            data: Dict with optional keys: 'title', 'content', 'starred'.

        Returns: dict with update result.
        """
        client = self._get_client()

        result: dict[str, Any] = {"note_id": id, "updated": []}

        # Update metadata
        update_info: dict[str, Any] = {"note_id": id}
        if "title" in data:
            update_info["title"] = data["title"]
        if "starred" in data:
            update_info["starred"] = bool(data["starred"])

        if len(update_info) > 1:  # has fields beyond note_id
            client.call_tool("update_note_info", update_info)
            result["updated"].append("metadata")

        # Update content
        if "content" in data and data["content"]:
            self._write_content(client, id, data["content"])
            result["updated"].append("content")

        return result

    def delete_item(self, item_id: str, **kwargs: Any) -> bool:
        """Move a note to the trash."""
        try:
            self._get_client().call_tool("trash_note", {"note_id": item_id})
            return True
        except McpError:
            return False

    def status(self) -> dict[str, Any]:
        """Return connector health/configuration status."""
        available = self.is_available()
        info: dict[str, Any] = {
            "available": available,
            "server_url": WPSNOTE_MCP_URL,
            "api_key_configured": bool(self._get_api_key()),
        }
        if available:
            try:
                tools = self._get_client().list_tools()
                info["tools_available"] = len(tools)
            except Exception:
                info["tools_available"] = 0
        return info

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    def _write_content(self, client: McpClient, note_id: str, content: str) -> None:
        """Write content to a note by replacing the first block."""
        # Get the note outline to find the first block
        outline_raw = client.call_tool("get_note_outline", {"note_id": note_id, "include_preview": False})
        outline = _extract_single_result(outline_raw)
        blocks = outline.get("blocks", []) if isinstance(outline, dict) else []

        if blocks:
            first_block_id = blocks[0].get("block_id", "")
            if first_block_id:
                xml_content = _xml_wrap(content)
                client.call_tool(
                    "edit_block",
                    {
                        "note_id": note_id,
                        "op": "replace",
                        "block_id": first_block_id,
                        "content": xml_content,
                    },
                )
                return

        # If no blocks found, insert a new block
        xml_content = _xml_wrap(content)
        # Try inserting at the beginning using a known anchor (or just replace)
        # First try to use get_note_outline again with preview
        outline_raw2 = client.call_tool("get_note_outline", {"note_id": note_id, "include_preview": True})
        outline2 = _extract_single_result(outline_raw2)
        blocks2 = outline2.get("blocks", []) if isinstance(outline2, dict) else []

        if blocks2:
            anchor_id = blocks2[0].get("block_id", "")
            if anchor_id:
                client.call_tool(
                    "edit_block",
                    {
                        "note_id": note_id,
                        "op": "insert",
                        "anchor_id": anchor_id,
                        "position": "after",
                        "content": xml_content,
                    },
                )
                # Delete the empty default block
                try:
                    client.call_tool(
                        "edit_block",
                        {
                            "note_id": note_id,
                            "op": "delete",
                            "block_ids": [anchor_id],
                        },
                    )
                except McpError:
                    pass
                return

        # Last resort: just call edit_block with replace on a guessed block
        client.call_tool(
            "edit_block",
            {
                "note_id": note_id,
                "op": "insert",
                "anchor_id": "",
                "position": "after",
                "content": xml_content,
            },
        )

    # ----------------------------------------------------------------
    # Backward compatibility
    # ----------------------------------------------------------------

    def create_note(self, title: str, content: str = "", tags: list[str] | None = None) -> dict[str, Any]:
        """Backward-compatible alias for create_item."""
        return self.create_item(title=title, content=content, tags=tags)

    def sync_research(self, result_id: str) -> dict[str, Any]:
        """Sync a minerva research result to WPS Note.

        Reads from ~/.minerva/research/{result_id}/ and creates a note.
        """
        from pathlib import Path

        research_dir = Path.home() / ".minerva" / "research" / result_id
        if not research_dir.exists():
            return {"status": "error", "message": f"Research {result_id} not found"}

        meta_path = research_dir / "meta.json"
        report_path = research_dir / "report.md"

        meta: dict[str, Any] = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        title = meta.get("query", f"Research {result_id}")
        content = ""
        if report_path.exists():
            content = report_path.read_text(encoding="utf-8")

        tags = ["research", meta.get("level", "L0")]
        result = self.create_item(title=title, content=content, tags=tags)
        return {"status": "ok" if result.get("note_id") else "error", "detail": result}
