"""Telegram connector — connects to Telegram Bot API for message polling and pushing.

A chat/messaging connector that:
- Uses a Telegram Bot token for authentication
- Polls messages from a configured chat via getUpdates
- Can send messages via sendMessage
- Maps Telegram messages to the unified Note model for downstream processing

Configuration (in order: env var > config file > default):
  - telegram.bot_token / IRIS_TELEGRAM_BOT_TOKEN  — Bot API token
  - telegram.chat_id / IRIS_TELEGRAM_CHAT_ID      — Target chat ID (optional)
  - telegram.polling_interval / IRIS_TELEGRAM_POLLING_INTERVAL — Poll interval seconds (default: 30)

Data model:
  Each Telegram message is mapped to a Note with:
    - id: telegram message ID
    - title: first 80 chars of message text
    - content: full message text
    - tags: ["telegram", f"chat:{chat_id}"]
    - created_at: message date (ISO format)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from iris.base import BaseConnector, SyncResult
from iris.config import IrisConfig
from iris.models import Note

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"
DEFAULT_POLLING_INTERVAL = 30
MAX_MESSAGE_LENGTH = 4096


def _iso_from_unix(ts: int) -> str:
    """Convert unix timestamp to ISO 8601 string."""
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(ts, tz=UTC).isoformat()
    except (OSError, ValueError, OverflowError):
        return ""


def _truncate(text: str, max_len: int = 80) -> str:
    """Truncate text for title use."""
    text = text.strip().replace("\n", " ")
    return text[:max_len] + "..." if len(text) > max_len else text


def _message_to_note(msg: dict[str, Any], chat_id: str) -> Note:
    """Convert a Telegram message dict to a Note model.

    Telegram message structure:
    {
        "message_id": 123,
        "date": 1700000000,
        "text": "Hello world",           # for text messages
        "caption": "...",                 # for media messages
        "from": {"id": ..., "first_name": ...},
        "chat": {"id": ..., "type": ...},
        ...
    }
    """
    msg_id = str(msg.get("message_id", ""))
    text = msg.get("text") or msg.get("caption") or ""
    date_ts = msg.get("date", 0)
    sender = msg.get("from", {})
    sender_name = sender.get("first_name", "") or sender.get("username", "") or "unknown"

    title = _truncate(text) or f"Telegram message #{msg_id}"
    content = text
    if sender_name:
        content = f"[{sender_name}]\n{text}" if text else f"[{sender_name}]"

    return Note(
        id=msg_id,
        title=title,
        platform="telegram",
        content=content,
        tags=["telegram", f"chat:{chat_id}", f"sender:{sender_name}"],
        created_at=_iso_from_unix(date_ts),
        updated_at=_iso_from_unix(date_ts),
    )


class TelegramConnector(BaseConnector):
    """Connector for Telegram Bot API.

    Reads messages from a configured chat and can send replies.
    Uses simple polling (getUpdates) — no webhooks required.
    """

    name = "telegram"
    display_name = "Telegram"

    def __init__(self, config: IrisConfig | None = None) -> None:
        self._config = config or IrisConfig()
        self._available: bool | None = None
        self._last_update_id: int = 0
        self._http_client: httpx.Client | None = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _get_bot_token(self) -> str:
        """Resolve bot token: env var > config file."""
        return os.environ.get(  # type: ignore[no-any-return]
            "IRIS_TELEGRAM_BOT_TOKEN",
            self._config.get("telegram.bot_token", default=""),
        )

    def _get_chat_id(self) -> str:
        """Resolve chat ID: env var > config file."""
        return os.environ.get(  # type: ignore[no-any-return]
            "IRIS_TELEGRAM_CHAT_ID",
            self._config.get("telegram.chat_id", default=""),
        )

    def _get_polling_interval(self) -> int:
        raw = os.environ.get(
            "IRIS_TELEGRAM_POLLING_INTERVAL",
            self._config.get("telegram.polling_interval", default=str(DEFAULT_POLLING_INTERVAL)),
        )
        try:
            return max(5, int(raw))  # type: ignore[reportArgumentType]
        except (ValueError, TypeError):
            return DEFAULT_POLLING_INTERVAL

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> httpx.Client:
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=15.0)
        return self._http_client

    def _api_url(self, method: str) -> str:
        token = self._get_bot_token()
        return f"https://api.telegram.org/bot{token}/{method}"

    def _call_api(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call Telegram Bot API method.

        Returns the 'result' portion of the response.
        Raises RuntimeError on failure.
        """
        url = self._api_url(method)
        try:
            resp = self._get_client().post(url, json=params or {}, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            raise RuntimeError("Telegram API request timed out")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Telegram API HTTP error: {e.response.status_code}")
        except Exception as e:
            raise RuntimeError(f"Telegram API request failed: {e}")

        if not data.get("ok"):
            desc = data.get("description", "unknown error")
            raise RuntimeError(f"Telegram API error: {desc}")

        return cast("dict[str, Any]", data.get("result", {}))

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check if the bot token is configured and the API is reachable.

        Uses getMe to verify the token is valid.
        Result is cached after first check.
        """
        if self._available is not None:
            return self._available
        if not self._get_bot_token():
            self._available = False
            return False
        try:
            result = self._call_api("getMe")
            self._available = bool(result and result.get("ok", result.get("id")))
        except Exception:
            logger.exception("Telegram API unavailable")
            self._available = False
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
        """List recent messages from a Telegram chat.

        Args:
            limit: Max messages to return (default: 20, max: 100).
            cursor: If provided, only return messages with ID > cursor.
            chat_id: Override the configured chat ID.

        Returns:
            List of Note models, newest first.
        """
        target_chat = chat_id or self._get_chat_id()
        if not target_chat:
            logger.warning("No chat_id configured for Telegram connector")
            return []

        params: dict[str, Any] = {
            "chat_id": target_chat,
            "limit": min(limit, 100),
        }

        if cursor:
            try:
                params["offset"] = int(cursor)
            except (ValueError, TypeError):
                pass
        try:
            result: list[dict[str, Any]] | dict[str, Any] = self._call_api("getUpdates", params)
        except RuntimeError:
            logger.exception("Failed to fetch Telegram messages")
            return []

        # getUpdates returns an array of Update objects, each with a 'message' key
        messages: list[Note] = []
        for update in result if isinstance(result, list) else []:
            msg = update.get("message") or update.get("channel_post") or update.get("edited_message")  # type: ignore[reportAttributeAccessIssue]
            if not msg:
                continue

            note = _message_to_note(msg, target_chat)
            messages.append(note)

            # Track the latest update_id for pagination
            upd_id = update.get("update_id", 0)  # type: ignore[reportAttributeAccessIssue]
            if upd_id > self._last_update_id:
                self._last_update_id = upd_id

        # Return newest first
        messages.reverse()
        return messages[:limit]

    def get_item(self, id: str) -> Note | None:
        """Get a single message by its message ID.

        Telegram Bot API doesn't support fetching a single message by ID
        directly. This attempts to find it via getUpdates with a small limit.
        """
        target_chat = self._get_chat_id()
        if not target_chat:
            return None

        # Try to find the message by scanning recent updates
        try:
            result: list[dict[str, Any]] | dict[str, Any] = self._call_api(
                "getUpdates",
                {
                    "chat_id": target_chat,
                    "limit": 1,
                    "offset": int(id),
                },
            )
        except (RuntimeError, ValueError):
            return None

        for update in result if isinstance(result, list) else []:
            msg = update.get("message") or update.get("channel_post")  # type: ignore[reportAttributeAccessIssue]
            if msg and str(msg.get("message_id")) == id:
                return _message_to_note(msg, target_chat)

        return None

    def search(self, query: str, limit: int = 10) -> list[Note]:
        """Search messages by text content.

        Telegram Bot API doesn't support server-side search.
        This polls recent messages and filters client-side.
        """
        messages = self.list_items(limit=100)
        results: list[Note] = []
        query_lower = query.lower()
        for msg in messages:
            if len(results) >= limit:
                break
            if query_lower in msg.content.lower():
                results.append(msg)
        return results

    def sync(self, dry_run: bool = False) -> SyncResult:
        """Fetch new messages since the last sync.

        Uses the last known update_id to only fetch new messages.
        """
        target_chat = self._get_chat_id()
        if not target_chat:
            return SyncResult(
                connector_name=self.name,
                success=False,
                message="No chat_id configured for Telegram connector",
            )

        try:
            params: dict[str, Any] = {
                "chat_id": target_chat,
                "timeout": 10,
            }
            if self._last_update_id > 0:
                params["offset"] = self._last_update_id + 1

            result: list[dict[str, Any]] | dict[str, Any] = self._call_api("getUpdates", params)
        except RuntimeError as e:
            return SyncResult(
                connector_name=self.name,
                success=False,
                errors=[str(e)],
                message=f"Sync failed: {e}",
            )

        updates: list[dict[str, Any]] = result if isinstance(result, list) else []
        new_messages = 0
        for update in updates:
            msg = update.get("message") or update.get("channel_post") or update.get("edited_message")  # type: ignore[reportAttributeAccessIssue]
            if msg:
                new_messages += 1
            upd_id = update.get("update_id", 0)  # type: ignore[reportAttributeAccessIssue]
            if upd_id > self._last_update_id:
                self._last_update_id = upd_id

        status = "dry_run" if dry_run else "success"
        return SyncResult(
            connector_name=self.name,
            items_found=new_messages,
            success=True,
            message=f"Found {new_messages} new message(s) (chat: {target_chat}) [{status}]",
        )

    def status(self) -> dict[str, Any]:
        """Return connector health and configuration status."""
        token_configured = bool(self._get_bot_token())
        chat_configured = bool(self._get_chat_id())
        available = self.is_available()

        info: dict[str, Any] = {
            "available": available,
            "token_configured": token_configured,
            "chat_configured": chat_configured,
            "polling_interval": self._get_polling_interval(),
            "last_update_id": self._last_update_id,
        }

        if available:
            try:
                me = self._call_api("getMe")
                info["bot_name"] = me.get("first_name", "") or me.get("username", "")
                info["bot_id"] = me.get("id", "")
            except Exception:
                pass

        return info

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def send_message(
        self,
        text: str,
        chat_id: str | None = None,
        parse_mode: str = "Markdown",
    ) -> dict[str, Any]:
        """Send a message to a Telegram chat.

        Args:
            text: Message text (max 4096 chars).
            chat_id: Target chat ID (defaults to configured chat_id).
            parse_mode: 'Markdown', 'HTML', or '' (default: 'Markdown').

        Returns:
            Dict with 'message_id', 'chat_id', 'date' on success.

        Raises:
            RuntimeError: If chat_id is not configured or API call fails.
        """
        target = chat_id or self._get_chat_id()
        if not target:
            raise RuntimeError("No chat_id configured for send_message")

        params: dict[str, Any] = {
            "chat_id": target,
            "text": text[:MAX_MESSAGE_LENGTH],
        }
        if parse_mode:
            params["parse_mode"] = parse_mode

        result = self._call_api("sendMessage", params)
        return {
            "message_id": result.get("message_id", 0),
            "chat_id": result.get("chat", {}).get("id", target),
            "date": result.get("date", 0),
        }

    def create_item(self, title: str = "", content: str = "", **kwargs: Any) -> dict[str, Any]:
        """Send a message (alias for send_message).

        Title is prefixed to content if both are provided.
        Returns dict with send result.
        """
        text = content
        if title and content:
            text = f"{title}\n\n{content}"
        elif title and not content:
            text = title
        return self.send_message(text=text)

    def update_item(self, id: str, data: dict[str, Any]) -> dict[str, Any]:  # type: ignore[reportIncompatibleMethodOverride]
        """Edit a sent message (only works for bot's own messages).

        Args:
            id: The message_id to edit.
            data: Dict with optional key 'text' (new message text).

        Returns:
            Dict with edit result.
        """
        target_chat = self._get_chat_id()
        if not target_chat:
            raise RuntimeError("No chat_id configured")

        text = data.get("text", "")
        parse_mode = data.get("parse_mode", "Markdown")

        params: dict[str, Any] = {
            "chat_id": target_chat,
            "message_id": int(id) if str(id).isdigit() else id,
            "text": text[:MAX_MESSAGE_LENGTH],
        }
        if parse_mode:
            params["parse_mode"] = parse_mode

        self._call_api("editMessageText", params)
        return {"message_id": id, "updated": True}

    def delete_item(self, item_id: str, **kwargs: Any) -> bool:
        """Delete a message (only works for bot's own messages)."""
        target_chat = self._get_chat_id()
        if not target_chat:
            return False
        try:
            self._call_api(
                "deleteMessage",
                {
                    "chat_id": target_chat,
                    "message_id": int(item_id) if str(item_id).isdigit() else item_id,
                },
            )
            return True
        except RuntimeError:
            return False

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export(self, fmt: str = "json") -> str:
        """Export recent messages."""
        items = self.list_items(limit=500)
        if fmt == "json":
            return json.dumps(
                [item.to_dict() for item in items],
                ensure_ascii=False,
                indent=2,
            )
        if fmt == "md":
            lines = ["# Telegram Export\n"]
            for item in items:
                lines.append(f"## {item.title}")
                lines.append(f"ID: {item.id} | Chat: {item.platform}")
                if item.created_at:
                    lines.append(f"Date: {item.created_at}")
                lines.append("")
                lines.append(item.content or "")
                lines.append("\n---\n")
            return "\n".join(lines)
        raise ValueError(f"Unsupported format: {fmt}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Clean up HTTP client."""
        if self._http_client is not None:
            self._http_client.close()
            self._http_client = None
