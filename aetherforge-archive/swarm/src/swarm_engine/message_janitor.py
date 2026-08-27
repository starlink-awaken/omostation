from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time

from ._compat import ProjectPaths

"""
---
Type: Daemon
Status: ACTIVE
Version: 1.0.0
Owner: '@SecurityLead'
Layer: Z-Microkernel
Summary: "Message Janitor for TTL enforcement and dead letter cleanup"
Authority: organs/D-Execution/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Message Janitor ≡ Module
# 内涵 ≝ {Message, Janitor}
# 外延 ≝ {e | e ∈ D-Execution ∧ implements(e, MessageJanitor)}
# 功能 ⊢ {Message_Janitor, Init_Message, Validate_Janitor}
# =============================================================================


_log = logging.getLogger(__name__)
DB_PATH = os.environ.get("BOS_ROUTER_DB", str(ProjectPaths.get_core_db_path("messages.db")))


class MessageJanitor:
    def __init__(self, interval_seconds: int = 60) -> None:
        self.status = "active"  # was super().__init__(metadata_path=...)
        self.interval = interval_seconds
        self.running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        _log.info(f"🧹 [MessageJanitor] Started. Cleaning every {self.interval}s.")

    def stop(self) -> None:
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
        _log.info("🧹 [MessageJanitor] Stopped.")

    def _run_loop(self) -> None:
        while self.running:
            try:
                self.cleanup()
            except Exception as exc:
                _log.info(f"❌ [MessageJanitor] Error during cleanup: {exc}")
            time.sleep(self.interval)

    def cleanup(self) -> None:
        """Perform TTL enforcement and dead letter cleanup."""
        now = time.time()
        try:
            conn = sqlite3.connect(DB_PATH)
            with conn:
                # Enable WAL mode for concurrency
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                cursor = conn.cursor()

                # 1. TTL Enforcement (delete messages where created_at + ttl < now AND ttl > 0 AND status != 'processed')
                # For safety, we only delete pending or read messages that have expired.
                cursor.execute(
                    """
                    DELETE FROM messages
                    WHERE ttl > 0
                    AND (created_at + ttl) < ?
                    AND status IN ('pending', 'read')
                    """,
                    (now,),
                )
                ttl_deleted = cursor.rowcount

                # 2. Dead Letter Cleanup (delete any message older than 24 hours, regardless of status)
                twenty_four_hours_ago = now - (24 * 3600)
                cursor.execute(
                    """
                    DELETE FROM messages
                    WHERE created_at < ?
                    """,
                    (twenty_four_hours_ago,),
                )
                dead_deleted = cursor.rowcount

            total_deleted = ttl_deleted + dead_deleted
            if total_deleted > 0:
                _log.info(
                    f"🧹 [MessageJanitor] Cleaned up {total_deleted} messages (TTL: {ttl_deleted}, Dead: {dead_deleted})."
                )

        except sqlite3.OperationalError as exc:
            _log.info(f"⚠️ [MessageJanitor] Database locked or unavailable: {exc}")
        except sqlite3.Error as exc:
            _log.info(f"❌ [MessageJanitor] Unexpected error: {exc}")


if __name__ == "__main__":
    janitor = MessageJanitor(interval_seconds=10)  # Faster interval for testing
    janitor.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        janitor.stop()
