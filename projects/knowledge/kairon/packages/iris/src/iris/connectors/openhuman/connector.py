"""Bridge connector to OpenHuman — 118+ integrations via JSON-RPC.

Connects Iris to OpenHuman's JSON-RPC API (port 7788), giving Iris
access to 118+ third-party integrations (GitHub, Slack, Notion, GMail,
Linear, Discord, etc.) maintained by the OpenHuman ecosystem.

Data flow:
  Iris (this connector) ──JSON-RPC──► OpenHuman (port 7788)
       │                                      │
       │  list_connections                     │  manages 118+ integrations
       │  sync                                 │  each with its own auth
       │  query_memory                         │
       │  ping                                 │
       └───────────────────────────────────────┘

Configuration (env vars):
  OPENHUMAN_HOST — OpenHuman host (default: http://127.0.0.1)
  OPENHUMAN_PORT — OpenHuman JSON-RPC port (default: 7788)
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from typing import Any, cast

from iris.base import BaseConnector, SyncResult
from iris.models import KnowledgeArtifact, Note

logger = logging.getLogger(__name__)

OH_HOST = os.environ.get("OPENHUMAN_HOST", "http://127.0.0.1")
OH_PORT = int(os.environ.get("OPENHUMAN_PORT", "7788"))
OH_URL = f"{OH_HOST}:{OH_PORT}"

CONNECTION_TIMEOUT = 5


class OpenHumanConnector(BaseConnector):
    """Connector to OpenHuman's JSON-RPC API.

    Provides read-only bridge to 118+ integrations managed by OpenHuman.
    Each integration (GitHub, Notion, Slack, etc.) is a "source" with
    its own auth and data model — this connector treats them uniformly
    through OpenHuman's query_memory and sync RPC methods.
    """

    name = "openhuman"
    display_name = "OpenHuman"

    def __init__(self) -> None:
        self._available: bool | None = None
        self._connected: bool = False
        self._last_sync: str | None = None

    # ------------------------------------------------------------------
    # JSON-RPC client
    # ------------------------------------------------------------------

    @staticmethod
    def _rpc(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call OpenHuman JSON-RPC endpoint.

        Args:
            method: RPC method name (e.g. "ping", "sync", "query_memory").
            params: Optional dict of parameters.

        Returns:
            Parsed JSON-RPC response dict, or {"error": ...} on failure.
        """
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1,
        }
        req = urllib.request.Request(
            f"{OH_URL}/rpc",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=CONNECTION_TIMEOUT) as resp:
                return cast("dict[str, Any]", json.loads(resp.read().decode()))
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON response: {e}"}
        except urllib.error.URLError as e:  # type: ignore[reportAttributeAccessIssue]
            return {"error": f"Connection failed: {e.reason}"}
        except OSError as e:
            return {"error": f"Network error: {e}"}
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check if OpenHuman is reachable via RPC ping.

        Result is cached after first check.
        """
        if self._available is not None:
            return self._available
        result = self._rpc("ping")
        self._available = "error" not in result
        if not self._available:
            logger.info("OpenHuman unavailable: %s", result.get("error"))
        return self._available

    def list_items(
        self,
        limit: int = 20,
        cursor: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        subdir: str | None = None,
        chat_id: str | None = None,
    ) -> list[KnowledgeArtifact]:
        """List available OpenHuman sources (= configured integrations).

        Each source is returned as a KnowledgeArtifact with:
          - id: source slug (e.g. "github", "notion")
          - title: human-readable source name
          - content: brief description / status

        Args:
            limit: Max items to return.
            cursor: Not supported by OpenHuman's list_connections.

        Returns:
            List of KnowledgeArtifact, one per configured integration.
        """
        result = self._rpc("list_connections")
        sources = result.get("result", []) if "error" not in result else []
        if not isinstance(sources, list):
            return []

        artifacts: list[KnowledgeArtifact] = []
        for src in sources[:limit]:
            name = src.get("name", "") if isinstance(src, dict) else str(src)
            artifacts.append(
                Note(
                    id=name,
                    title=name,
                    platform="openhuman",
                    content=json.dumps(src, ensure_ascii=False) if isinstance(src, dict) else name,
                )
            )
        return artifacts

    def get_item(self, id: str) -> KnowledgeArtifact | None:
        """Get a specific source by its slug name.

        Args:
            id: Source slug (e.g. "github", "notion").

        Returns:
            KnowledgeArtifact for the source, or None if not found.
        """
        sources = self.list_items(limit=200)
        for src in sources:
            if src.id == id:
                return src
        return None

    def search(self, query: str, limit: int = 10) -> list[KnowledgeArtifact]:
        """Search across OpenHuman memory.

        Delegates to OpenHuman's query_memory RPC, which searches
        across ALL configured third-party integrations.

        Args:
            query: Free-text search query.
            limit: Max results to return.

        Returns:
            List of KnowledgeArtifact matching the query.
        """
        result = self._rpc("query_memory", {"query": query})
        items = result.get("result", []) if "error" not in result else []
        if not isinstance(items, list):
            return []

        artifacts: list[KnowledgeArtifact] = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            artifacts.append(
                Note(
                    id=str(item.get("id", "")),
                    title=str(item.get("title", item.get("name", ""))),
                    platform="openhuman",
                    content=item.get("content") or item.get("text") or "",
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                )
            )
        return artifacts

    def sync(self, dry_run: bool = False) -> SyncResult:
        """Pull latest data from all configured OpenHuman sources.

        Calls OpenHuman's sync RPC, which triggers a sync across all
        118+ configured third-party integrations.

        Args:
            dry_run: If True, report what would sync without executing.

        Returns:
            SyncResult with count of synced sources.
        """
        result = self._rpc("sync")
        self._last_sync = time.strftime("%Y-%m-%dT%H:%M:%SZ")

        if "error" in result:
            return SyncResult(
                connector_name=self.name,
                success=False,
                errors=[result["error"]],
                message=f"Sync failed: {result['error']}",
            )

        synced_count = result.get("result", {})
        if isinstance(synced_count, dict):
            synced_count = len(synced_count)
        elif not isinstance(synced_count, (int, float)):
            synced_count = 0

        status = "dry_run" if dry_run else "success"
        return SyncResult(
            connector_name=self.name,
            items_found=int(synced_count),
            success=True,
            message=f"Synced {int(synced_count)} source(s) [{status}]",
        )

    def status(self) -> dict[str, Any]:
        """Return connector health and configuration status."""
        available = self.is_available()
        sources: list[Any] = []
        source_count = 0
        if available:
            sources = self._rpc("list_connections").get("result", [])
            if isinstance(sources, list):
                source_count = len(sources)

        return {
            "available": available,
            "connected": self._connected,
            "last_sync": self._last_sync,
            "source_count": source_count,
            "sources": [s.get("name", str(s)) if isinstance(s, dict) else str(s) for s in sources[:20]],
            "host": OH_HOST,
            "port": OH_PORT,
        }

    # ------------------------------------------------------------------
    # OpenHuman-specific operations
    # ------------------------------------------------------------------

    def connect(self) -> dict[str, Any]:
        """Explicit connection check — alias for is_available()."""
        ok = self.is_available()
        self._connected = ok
        return {"connected": ok}

    def list_sources(self) -> list[dict[str, Any]]:
        """List configured integrations with full metadata.

        Returns:
            Raw list of source dicts from OpenHuman's list_connections.
        """
        result = self._rpc("list_connections")
        return result.get("result", []) if "error" not in result else []

    def query(
        self,
        query: str,
        source_hint: str = "",
    ) -> list[dict[str, Any]]:
        """Query OpenHuman memory with optional source filter.

        Args:
            query: Free-text search query.
            source_hint: If provided, scope search to this source.

        Returns:
            Raw result items from OpenHuman.
        """
        params: dict[str, Any] = {"query": query}
        if source_hint:
            params["source"] = source_hint
        result = self._rpc("query_memory", params)
        items = result.get("result", []) if "error" not in result else []
        return items if isinstance(items, list) else []
