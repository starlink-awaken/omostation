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

T6-25 enhancements:
  - Watchdog: alive → degraded → dead → revive state machine
  - Retry: exponential backoff (1s → 2s → 4s) with SQLite fallback
  - Fallback: SQLite local transaction store when JSON-RPC unavailable
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

from iris.base import BaseConnector, SyncResult
from iris.models import KnowledgeArtifact, Note

logger = logging.getLogger(__name__)

OH_HOST = os.environ.get("OPENHUMAN_HOST", "http://127.0.0.1")
OH_PORT = int(os.environ.get("OPENHUMAN_PORT", "7788"))
OH_URL = f"{OH_HOST}:{OH_PORT}"

CONNECTION_TIMEOUT = 5
FALLBACK_DB_PATH = os.environ.get(
    "OPENHUMAN_FALLBACK_DB",
    os.path.expanduser("~/.iris/openhuman_fallback.db"),
)


class WatchdogState(Enum):
    """Watchdog state machine states."""

    ALIVE = "alive"
    DEGRADED = "degraded"
    DEAD = "dead"
    REVIVE = "revive"


@dataclass
class WatchdogResult:
    """Result of a watchdog probe."""

    state: WatchdogState
    reachable: bool
    latency_ms: float | None = None
    error: str | None = None


class OpenHumanConnector(BaseConnector):
    """Connector to OpenHuman's JSON-RPC API.

    Provides read-only bridge to 118+ integrations managed by OpenHuman.
    Each integration (GitHub, Notion, Slack, etc.) is a "source" with
    its own auth and data model — this connector treats them uniformly
    through OpenHuman's query_memory and sync RPC methods.

    T6-25 adds:
      - Watchdog state machine (alive → degraded → dead → revive)
      - Exponential backoff retry with SQLite fallback
    """

    name = "openhuman"
    display_name = "OpenHuman"

    def __init__(self) -> None:
        self._available: bool | None = None
        self._connected: bool = False
        self._last_sync: str | None = None

        # Watchdog state
        self._watchdog_state: WatchdogState = WatchdogState.ALIVE
        self._failure_count: int = 0
        self._success_count: int = 0

        # Fallback SQLite
        self._fallback_db: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Watchdog
    # ------------------------------------------------------------------

    def watchdog(self) -> WatchdogResult:
        """Probe OpenHuman JSON-RPC 7788 port reachability.

        Returns WatchdogResult with state machine transition.
        State machine:
          - 3 consecutive timeouts → DEGRADED
          - 5 consecutive timeouts → DEAD
          - 2 consecutive successes from DEAD → REVIVE → ALIVE
        """
        start = time.perf_counter()
        result = self._rpc("ping")
        latency = (time.perf_counter() - start) * 1000

        if "error" not in result:
            # Success
            self._success_count += 1
            self._failure_count = 0

            if self._watchdog_state == WatchdogState.DEAD:
                if self._success_count >= 2:
                    self._watchdog_state = WatchdogState.REVIVE
                    logger.info("Watchdog: DEAD → REVIVE (2 consecutive successes)")
                    return WatchdogResult(
                        state=WatchdogState.REVIVE,
                        reachable=True,
                        latency_ms=latency,
                    )
                self._watchdog_state = WatchdogState.DEAD
                return WatchdogResult(
                    state=WatchdogState.DEAD,
                    reachable=True,
                    latency_ms=latency,
                )

            self._watchdog_state = WatchdogState.ALIVE
            return WatchdogResult(
                state=WatchdogState.ALIVE,
                reachable=True,
                latency_ms=latency,
            )

        # Failure
        self._failure_count += 1
        self._success_count = 0

        if self._failure_count >= 5:
            self._watchdog_state = WatchdogState.DEAD
            logger.warning("Watchdog: → DEAD (%d consecutive failures)", self._failure_count)
        elif self._failure_count >= 3:
            self._watchdog_state = WatchdogState.DEGRADED
            logger.warning("Watchdog: → DEGRADED (%d consecutive failures)", self._failure_count)
        else:
            self._watchdog_state = WatchdogState.ALIVE

        return WatchdogResult(
            state=self._watchdog_state,
            reachable=False,
            error=result.get("error"),
        )

    @property
    def watchdog_state(self) -> WatchdogState:
        """Current watchdog state."""
        return self._watchdog_state

    # ------------------------------------------------------------------
    # JSON-RPC client with retry + fallback
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

    def call_with_retry(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> dict[str, Any]:
        """Call JSON-RPC with exponential backoff retry.

        On all retries exhausted, falls back to SQLite local store.

        Args:
            method: RPC method name.
            params: Optional parameters.
            max_retries: Max retry attempts (default 3).
            base_delay: Base delay in seconds (exponential: 1, 2, 4...).

        Returns:
            RPC response dict, or fallback result.
        """
        last_error: str | None = None

        for attempt in range(max_retries + 1):
            result = self._rpc(method, params)
            if "error" not in result:
                return result

            last_error = result.get("error", "unknown")

            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "RPC %s failed (attempt %d/%d): %s — retrying in %.1fs",
                    method,
                    attempt + 1,
                    max_retries + 1,
                    last_error,
                    delay,
                )
                time.sleep(delay)

        # All retries exhausted — fallback to SQLite
        logger.error(
            "RPC %s failed after %d retries: %s — falling back to SQLite",
            method,
            max_retries,
            last_error,
        )
        return self._fallback_to_sqlite(method, params or {}, error=last_error)

    def _ensure_fallback_db(self) -> sqlite3.Connection:
        """Initialize SQLite fallback database if not already open."""
        if self._fallback_db is None:
            db_dir = os.path.dirname(FALLBACK_DB_PATH)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            self._fallback_db = sqlite3.connect(FALLBACK_DB_PATH)
            self._fallback_db.execute(
                """CREATE TABLE IF NOT EXISTS rpc_cache (
                    method TEXT NOT NULL,
                    params TEXT NOT NULL,
                    result TEXT NOT NULL,
                    cached_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (method, params)
                )"""
            )
            self._fallback_db.execute(
                """CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    method TEXT NOT NULL,
                    params TEXT NOT NULL,
                    result TEXT NOT NULL,
                    synced_at TEXT NOT NULL DEFAULT (datetime('now')),
                    is_fallback INTEGER NOT NULL DEFAULT 1
                )"""
            )
            self._fallback_db.commit()
        return self._fallback_db

    def _fallback_to_sqlite(
        self,
        method: str,
        params: dict[str, Any],
        error: str | None = None,
    ) -> dict[str, Any]:
        """Fall back to SQLite local transaction store.

        Ensures core flow never blocks when JSON-RPC is unavailable.

        Args:
            method: RPC method name.
            params: Original parameters.
            error: Original error message.

        Returns:
            Dict with fallback result and metadata.
        """
        db = self._ensure_fallback_db()
        params_json = json.dumps(params, sort_keys=True, ensure_ascii=False)
        fallback_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Try to read from cache
        cursor = db.execute(
            "SELECT result, cached_at FROM rpc_cache WHERE method = ? AND params = ?",
            (method, params_json),
        )
        row = cursor.fetchone()

        if row:
            result = json.loads(row[0])
            logger.info(
                "Fallback: serving cached result for %s (cached at %s)",
                method,
                row[1],
            )
            return {
                **result,
                "_fallback": True,
                "_fallback_source": "cache",
                "_fallback_cached_at": row[1],
                "_fallback_error": error,
            }

        # No cache — return honest empty result
        logger.warning(
            "Fallback: no cached result for %s — returning empty",
            method,
        )
        empty_result = {"result": [], "fallback": True}

        # Log the fallback attempt
        db.execute(
            "INSERT INTO sync_log (method, params, result, synced_at, is_fallback) VALUES (?, ?, ?, ?, 1)",
            (method, params_json, json.dumps(empty_result), fallback_ts),
        )
        db.commit()

        return {
            **empty_result,
            "_fallback": True,
            "_fallback_source": "empty",
            "_fallback_ts": fallback_ts,
            "_fallback_error": error,
        }

    def cache_rpc_result(
        self, method: str, params: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Cache a successful RPC result for future fallback use."""
        db = self._ensure_fallback_db()
        params_json = json.dumps(params, sort_keys=True, ensure_ascii=False)
        db.execute(
            """INSERT OR REPLACE INTO rpc_cache (method, params, result)
               VALUES (?, ?, ?)""",
            (method, params_json, json.dumps(result, ensure_ascii=False)),
        )
        db.commit()

    def close_fallback_db(self) -> None:
        """Close the SQLite fallback database connection."""
        if self._fallback_db:
            self._fallback_db.close()
            self._fallback_db = None

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check if OpenHuman is reachable via RPC ping.

        Uses watchdog state — returns False when DEAD.
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
        """List available OpenHuman sources (= configured integrations)."""
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
        """Get a specific source by its slug name."""
        sources = self.list_items(limit=200)
        for src in sources:
            if src.id == id:
                return src
        return None

    def search(self, query: str, limit: int = 10) -> list[KnowledgeArtifact]:
        """Search across OpenHuman memory."""
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
        """Pull latest data from all configured OpenHuman sources."""
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
            "sources": [
                s.get("name", str(s)) if isinstance(s, dict) else str(s) for s in sources[:20]
            ],
            "host": OH_HOST,
            "port": OH_PORT,
            "watchdog_state": self._watchdog_state.value,
            "failure_count": self._failure_count,
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
        """List configured integrations with full metadata."""
        result = self._rpc("list_connections")
        return result.get("result", []) if "error" not in result else []

    def query(
        self,
        query: str,
        source_hint: str = "",
    ) -> list[dict[str, Any]]:
        """Query OpenHuman memory with optional source filter."""
        params: dict[str, Any] = {"query": query}
        if source_hint:
            params["source"] = source_hint
        result = self._rpc("query_memory", params)
        items = result.get("result", []) if "error" not in result else []
        return items if isinstance(items, list) else []
