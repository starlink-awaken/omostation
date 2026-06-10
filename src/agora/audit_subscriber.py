"""Audit Subscriber — pipes all EventBus events to durable audit storage.

Design:
- Subscribes to "*" (all events) on the EventBus
- Writes every event to SSB with structured audit fields
- Enables queries by actor, resource, action, time range
- OTel-compatible span attributes for external SIEM export

Persistence: Writes to SSB (State-Signal-Broadcast) via agora SSB module,
with fallback to SQLite audit log.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from agora.auth.identity import normalize_identity  # type: ignore[import-not-found]

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from agora.core.event_bus import EventBus  # type: ignore[import-not-found]
    from agora.core.registry import ServiceRegistry  # type: ignore[import-not-found]

# Default audit DB path (relative to agora project root)
from agora.mcp.mcp_bootstrap import get_data_dir  # type: ignore[import-not-found]  # noqa: E402

AUDIT_DB = Path(os.environ.get("AGORA_AUDIT_DB", get_data_dir() / "agora-audit.db"))


class AuditSubscriber:
    """Subscribes to all EventBus events and persists them for audit.

    Usage:
        bus = EventBus(registry=registry)
        auditor = AuditSubscriber(bus)
        auditor.start()  # begins listening
    """

    def __init__(
        self,
        event_bus: EventBus,
        registry: ServiceRegistry | None = None,
        db_path: str | Path | None = None,
    ):
        self._bus = event_bus
        self._registry = registry
        self._db_path = Path(db_path or AUDIT_DB)
        self._init_db()

    def _init_db(self):
        """Ensure audit database exists with correct schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id          TEXT PRIMARY KEY,
                timestamp   TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                source      TEXT NOT NULL DEFAULT '',
                actor       TEXT NOT NULL DEFAULT '',
                resource    TEXT NOT NULL DEFAULT '',
                action      TEXT NOT NULL DEFAULT '',
                trace_id    TEXT NOT NULL DEFAULT '',
                payload     TEXT NOT NULL DEFAULT '{}',
                risk_level  TEXT NOT NULL DEFAULT 'INFO',
                duration_ms REAL NOT NULL DEFAULT 0.0
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_log(event_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor)
        """)
        conn.commit()
        conn.close()

    def _classify(self, event_type: str) -> dict:
        """Classify event into actor/resource/action/risk for audit.

        Mapping rules:
          registry:*     → actor=registry,   resource=service,   action=register/unregister
          route:*        → actor=route,      resource=route,     action=add/remove
          event:*        → actor=event,      resource=event_bus, action=publish/subscribe
          pipeline:*     → actor=pipeline,   resource=pipeline,  action=start/stop/step
          proxy:*        → actor=proxy,      resource=proxy,     action=connect/disconnect/call
          index:*        → actor=indexer,    resource=index,     action=start/done/fail
          error:*        → actor=system,     resource=system,    action=error, risk=ERROR
          security:*     → actor=security,   resource=system,    action=alert, risk=CRITICAL
          *              → actor=unknown,    resource=event_bus, action=published, risk=INFO
        """
        parts = event_type.split(":", 1)
        category = parts[0] if len(parts) > 1 else parts[0]
        verb = parts[1] if len(parts) > 1 else "published"

        mapping = {
            "registry": {"actor": "registry", "resource": "service", "risk": "INFO"},
            "route": {"actor": "route", "resource": "route", "risk": "INFO"},
            "event": {"actor": "event", "resource": "event_bus", "risk": "INFO"},
            "pipeline": {"actor": "pipeline", "resource": "pipeline", "risk": "INFO"},
            "proxy": {"actor": "proxy", "resource": "proxy", "risk": "INFO"},
            "index": {"actor": "indexer", "resource": "index", "risk": "INFO"},
            "error": {"actor": "system", "resource": "system", "risk": "ERROR"},
            "security": {"actor": "security", "resource": "system", "risk": "CRITICAL"},
            "PERCEPTION": {"actor": "perception", "resource": "signal", "risk": "INFO"},
            "INTEGRATE": {
                "actor": "integrator",
                "resource": "knowledge",
                "risk": "INFO",
            },
            "SIGNAL": {"actor": "signal", "resource": "signal", "risk": "MEDIUM"},
            "STATE_CHANGE": {"actor": "system", "resource": "state", "risk": "INFO"},
            "ALERT": {"actor": "system", "resource": "system", "risk": "HIGH"},
            "SYSTEM": {"actor": "system", "resource": "system", "risk": "INFO"},
        }

        info = mapping.get(
            category, {"actor": "unknown", "resource": "event_bus", "risk": "INFO"}
        )
        return {
            "actor": info["actor"],
            "resource": info["resource"],
            "action": verb,
            "risk_level": info["risk"],
        }

    def on_event(self, event: dict):
        """Callback: persist an event to the audit database.

        Designed to be registered as a subscriber callback.
        """
        event_type = event.get("type", "unknown")
        event_id = event.get("id", f"audit_{uuid.uuid4().hex[:8]}")
        source = event.get("source", "")
        trace_id = event.get("trace_id", "")
        payload = event.get("payload", {})
        ts = event.get("time", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

        # Classify for structured audit
        classified = self._classify(event_type)
        identity = payload.get("identity") if isinstance(payload, dict) else None
        if identity:
            classified["actor"] = normalize_identity(identity).actor

        # Serialize payload
        payload_str = json.dumps(payload, ensure_ascii=False, default=str)

        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute(
                """INSERT OR IGNORE INTO audit_log
                   (id, timestamp, event_type, source, actor, resource, action,
                    trace_id, payload, risk_level, duration_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"{event_id}",
                    ts,
                    event_type,
                    source,
                    classified["actor"],
                    classified["resource"],
                    classified["action"],
                    trace_id,
                    payload_str,
                    classified["risk_level"],
                    payload.get("_duration_ms", 0.0),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("audit_write_failed", event_id=event_id, error=str(e))

    def query(
        self,
        actor: str = "",
        resource: str = "",
        event_type: str = "",
        since: str = "",
        limit: int = 50,
    ) -> list[dict]:
        """Query the audit log with optional filters.

        Args:
            actor: Filter by actor name (e.g., 'registry', 'pipeline')
            resource: Filter by resource type (e.g., 'service', 'route')
            event_type: Filter by event type (e.g., 'registry:register')
            since: ISO timestamp (e.g., '2026-05-01T00:00:00Z')
            limit: Max results (default 50)

        Returns:
            List of audit log entries as dicts.
        """
        conditions = []
        params = []

        if actor:
            conditions.append("actor = ?")
            params.append(actor)
        if resource:
            conditions.append("resource = ?")
            params.append(resource)
        if event_type:
            conditions.append("event_type LIKE ?")
            params.append(event_type.replace("*", "%"))
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM audit_log WHERE {where} ORDER BY timestamp DESC LIMIT ?"

        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, [*params, limit]).fetchall()
            conn.close()
            result = []
            for row in rows:
                entry = dict(row)
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    entry["payload"] = json.loads(entry["payload"])
                result.append(entry)
            return result
        except Exception as e:
            logger.error("audit_query_failed", error=str(e))
            return []

    def stats(self, since: str = "") -> dict:
        """Get audit log statistics.

        Args:
            since: ISO timestamp to filter from

        Returns:
            Dict with counts grouped by risk_level and event_type.
        """
        stats: dict = {
            "total": 0,
            "by_risk": {},
            "by_event_type": {},
        }

        try:
            conn = sqlite3.connect(str(self._db_path))
            if since:
                rows = conn.execute(
                    "SELECT risk_level, COUNT(*) as cnt FROM audit_log WHERE timestamp >= ? GROUP BY risk_level",
                    (since,),
                ).fetchall()
                stats["total"] = sum(r[1] for r in rows)
            else:
                rows = conn.execute(
                    "SELECT risk_level, COUNT(*) as cnt FROM audit_log GROUP BY risk_level"
                ).fetchall()
                total_row = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()
                stats["total"] = total_row[0] if total_row else 0

            stats["by_risk"] = {r[0]: r[1] for r in rows}

            if since:
                type_rows = conn.execute(
                    "SELECT event_type, COUNT(*) as cnt FROM audit_log WHERE timestamp >= ? GROUP BY event_type ORDER BY cnt DESC LIMIT 20",
                    (since,),
                ).fetchall()
            else:
                type_rows = conn.execute(
                    "SELECT event_type, COUNT(*) as cnt FROM audit_log GROUP BY event_type ORDER BY cnt DESC LIMIT 20"
                ).fetchall()
            stats["by_event_type"] = {r[0]: r[1] for r in type_rows}

            conn.close()
        except Exception as e:
            logger.error("audit_stats_failed", error=str(e))

        return stats

    def to_otel_json(self, since: str = "") -> list[dict]:
        """Export audit entries as OpenTelemetry-compatible spans.

        Each audit entry becomes an OTel span with:
          - name: event_type
          - attributes: actor, resource, action, risk_level
          - trace_id: derived from audit trace_id or event id
          - timestamp: event time

        Args:
            since: ISO timestamp to filter from

        Returns:
            List of OTel-compatible span dicts.
        """
        entries = self.query(since=since, limit=1000)
        spans = []

        for entry in entries:
            trace_id = entry.get("trace_id", "") or entry.get("id", "")
            # Hash string trace_id into a 16-byte hex for OTel spec
            import hashlib

            trace_hex = hashlib.md5(trace_id.encode()).hexdigest()[:32]  # noqa: S324
            span_id_hex = hashlib.md5((trace_id + ":span").encode()).hexdigest()[:16]  # noqa: S324

            span = {
                "name": entry.get("event_type", "unknown"),
                "traceId": trace_hex,
                "spanId": span_id_hex,
                "startTime": entry.get("timestamp", ""),
                "attributes": {
                    "audit.actor": entry.get("actor", ""),
                    "audit.resource": entry.get("resource", ""),
                    "audit.action": entry.get("action", ""),
                    "audit.risk_level": entry.get("risk_level", "INFO"),
                    "audit.source": entry.get("source", ""),
                    "audit.event_type": entry.get("event_type", ""),
                },
            }
            spans.append(span)

        return spans
