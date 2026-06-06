#!/usr/bin/env python3
"""
SSB Client — Shared Semantic Bus for eCOS

Design:
- Dual-write: SQLite (fast query) + File (durable source of truth)
- File is primary; SQLite can be rebuilt from files at any time
- All events follow SSB-SCHEMA-V1.md format

Usage:
    from ssb_client import SSBClient
    ssb = SSBClient()

    # Publish an event
    event_id = ssb.publish({
        "event": {"type": "PROPOSAL"},
        "source": {"agent": "HERMES", "instance": "hermes-main"},
        "payload": {"summary": "...", "detail": "...", "action_required": "DECIDE"}
    })

    # Query events
    events = ssb.query(event_type="PROPOSAL", limit=10)

    # Subscribe to new events
    for ev in ssb.subscribe(event_type="DECISION"):
        print(ev["payload"]["summary"])

    # Get current state
    state = ssb.get_state()
"""

import json
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path

from ecos.core.common import ECOS_HOME, TZ, get_conn, now_iso  # type: ignore[import-not-found]
from ecos.core.common import SSB_DB_PATH as _SSB_DB_PATH

# SSB Auth for event signing
from ecos.core.ssb_auth import compute_signature  # type: ignore[import-not-found]

# ─── Paths ────────────────────────────────────────────────────────────


SSB_DB_PATH = _SSB_DB_PATH
STATE_PATH = ECOS_HOME / "STATE.yaml"
HANDOFF_DIR = ECOS_HOME / "LADS" / "HANDOFF"
HANDOFF_LATEST = HANDOFF_DIR / "LATEST.md"
HANDOFF_HISTORY = HANDOFF_DIR / "HISTORY"
FAILURES_DIR = ECOS_HOME / "LADS" / "FAILURES"


# ─── Helpers ──────────────────────────────────────────────────────────


def _now() -> str:
    """ISO8601 with Asia/Shanghai timezone."""
    return now_iso()


def _new_id() -> str:
    return str(uuid.uuid4())


def _slugify(text: str, max_len: int = 48) -> str:
    """Turn a summary into a filesystem-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug[:max_len]


def _validate_event(event: dict):
    """Basic event schema validation."""
    required = ["event", "source", "payload"]
    for key in required:
        if key not in event:
            raise ValueError(f"Missing required field: {key}")

    if "type" not in event["event"]:
        raise ValueError("Event must have event.type")
    if "agent" not in event["source"]:
        raise ValueError("Event must have source.agent")
    if "summary" not in event["payload"]:
        raise ValueError("Event must have payload.summary")


# ─── Event Type → File Rules ──────────────────────────────────────────

# For each event type, define how it maps to filesystem
_FILE_RULES = {
    "HANDOFF": {
        "file": lambda e: HANDOFF_LATEST,
        "archive": lambda e: HANDOFF_HISTORY / f"{e['timestamp'][:19].replace(':', '-')}.md",
        "content": lambda e: _format_handoff_md(e),
    },
    "STATE_CHANGE": {
        "file": lambda e: STATE_PATH,
        "no_archive": True,  # Overwrite STATE.yaml directly
    },
    "FAILURE": {
        "file": lambda e: FAILURES_DIR / _fail_filename(e),
        "archive": lambda e: FAILURES_DIR / _fail_filename(e),  # same file
        "content": lambda e: _format_failure_md(e),
    },
    # Events below have NO file persistence (SQLite only)
    "SIGNAL": None,
    "PROPOSAL": None,
    "CRITIQUE": None,
    "VOTE": None,
    "DECISION": None,
    "ACTION_START": None,
    "ACTION_RESULT": None,
    "PERCEPTION": None,
}


def _fail_filename(event: dict) -> str:
    date_str = event.get("timestamp", _now())[:10]
    try:
        seq = int(event.get("_seq", 0))
    except (ValueError, TypeError):
        seq = 0
    slug = _slugify(event["payload"].get("summary", "unknown"))
    return f"FAIL-{date_str}-{seq:03d}-{slug}.md"


def _format_handoff_md(event: dict) -> str:
    p = event["payload"]
    return f"""# HANDOFF — {p.get("summary", "")}

**时间**: {event.get("timestamp", _now())}
**来源**: {event["source"].get("agent", "UNKNOWN")}
**会话**: {event.get("session_id", "N/A")}

---

## 当前状态

{p.get("detail", "")}

---

## 待办事项

{p.get("action_required", "NONE")}

---

## 引用

{json.dumps(p.get("references", []), ensure_ascii=False, indent=2)}
"""


def _format_failure_md(event: dict) -> str:
    p = event["payload"]
    timestamp = event.get("timestamp", _now())
    source = event["source"].get("agent", "UNKNOWN")
    event["event"].get("subtype", "BOOLEAN")
    risk = p.get("risk_level", "MED")
    return f"""---
fail_id: FAIL-{timestamp[:10]}-{event.get("_seq", "NNN"):03d}
date: "{timestamp[:10]}"
severity: {risk}
domain: 执行
status: OPEN
reported_by: {source}
---

# {p.get("summary", "Unknown Failure")}

## 失败描述

{p.get("detail", "No detail provided.")}

## 相关文档

- 关联 Event: {event.get("event_id", "N/A")}
"""


# ─── SSB Client ──────────────────────────────────────────────────────


class SSBClient:
    """
    Shared Semantic Bus client.

    Provides publish/subscribe/query semantics over a dual-write
    SQLite + File backend.
    """

    def __init__(self, db_path: str | None = None, auto_init: bool = True):
        self.db_path = Path(db_path or SSB_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        if auto_init:
            self._init_db()
            self._last_seq = self._current_seq()
            self._last_sub_seq = self._last_seq  # subscribe() baseline

    def _get_conn(self):
        """Get a new SQLite connection (thread-safe per-call)."""
        return get_conn(self.db_path)

    def _init_db(self):
        """Create tables if they don't exist."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS ssb_events (
                    id            TEXT PRIMARY KEY,
                    seq           INTEGER NOT NULL,
                    timestamp     TEXT NOT NULL,
                    session_id    TEXT DEFAULT '',
                    source_agent  TEXT NOT NULL,
                    source_instance TEXT DEFAULT '',
                    target_scope  TEXT DEFAULT 'ALL',
                    target_hint   TEXT DEFAULT '',
                    event_type    TEXT NOT NULL,
                    event_subtype TEXT DEFAULT '',
                    summary       TEXT NOT NULL,
                    detail        TEXT DEFAULT '',
                    confidence    REAL DEFAULT 1.0,
                    risk_level    TEXT DEFAULT 'LOW',
                    priority      TEXT DEFAULT 'P3',
                    action_req    TEXT DEFAULT 'NONE',
                    deadline      TEXT DEFAULT '',
                    payload_json  TEXT DEFAULT '{}',
                    semantic_json TEXT DEFAULT '{}',
                    agent_signature TEXT DEFAULT '',
                    created_at    TEXT DEFAULT (datetime('now', 'localtime'))
                );

                CREATE INDEX IF NOT EXISTS idx_ssb_type
                    ON ssb_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_ssb_source
                    ON ssb_events(source_agent);
                CREATE INDEX IF NOT EXISTS idx_ssb_action
                    ON ssb_events(action_req);
                CREATE INDEX IF NOT EXISTS idx_ssb_risk
                    ON ssb_events(risk_level);
                CREATE INDEX IF NOT EXISTS idx_ssb_ts
                    ON ssb_events(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_ssb_seq
                    ON ssb_events(seq);
            """)
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(ssb_events)")}
            if "agent_signature" not in cols:
                conn.execute("ALTER TABLE ssb_events ADD COLUMN agent_signature TEXT DEFAULT ''")
            conn.commit()
        finally:
            conn.close()

    def _current_seq(self) -> int:
        """Get the current max sequence number."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT COALESCE(MAX(seq), 0) AS seq FROM ssb_events").fetchone()
            return row["seq"]
        finally:
            conn.close()

    # ─── Publish ──────────────────────────────────────────────────────

    def publish(self, event: dict, write_file: bool = True) -> str:
        """
        Publish an event to SSB.

        Args:
            event: Dict following SSB-SCHEMA-V1.md format.
                   Required: event.type, source.agent, payload.summary
            write_file: If True, also write to corresponding file (default: True)

        Returns:
            event_id (UUID string)
        """
        _validate_event(event)

        # ── Phase 34 Wave 2: Audit Flood Debounce (Rate Limiting) ──
        if not hasattr(self, "_rate_limit_cache"):
            self._rate_limit_cache = {}
            
        import time
        import hashlib
        import uuid
        
        # We define uniqueness by type, agent, and the exact summary text
        ev_type = event.get("event", {}).get("type", "UNKNOWN")
        source_agent = event.get("source", {}).get("agent", "UNKNOWN")
        payload_summary = event.get("payload", {}).get("summary", "")
        
        sig_str = f"{ev_type}:{source_agent}:{payload_summary}"
        sig = hashlib.md5(sig_str.encode('utf-8')).hexdigest()
        
        now = time.time()
        history = self._rate_limit_cache.setdefault(sig, [])
        # Sliding window: keep events from the last 60 seconds
        history = [ts for ts in history if now - ts < 60]
        self._rate_limit_cache[sig] = history
        
        # Threshold: max 10 identical events per minute
        if len(history) >= 10:
            # We silently drop the DB write, but return a valid UUID structure to not break clients
            return f"debounced-{uuid.uuid4()}"
            
        self._rate_limit_cache[sig].append(now)
        # ──────────────────────────────────────────────────────────

        # Enrich with metadata
        event_id = event.get("event_id", _new_id())
        event["event_id"] = event_id
        if "timestamp" not in event:
            event["timestamp"] = _now()

        ev_type = event["event"].get("type", "SIGNAL")
        ev_subtype = event["event"].get("subtype", "")
        source = event["source"]
        target = event.get("target", {})
        payload = event["payload"]
        semantic = event.get("semantic", {})

        # Compute HMAC signature
        payload_json_str = json.dumps(payload, ensure_ascii=False)

        # Write to SQLite — atomic seq generation inside transaction
        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM ssb_events").fetchone()
            seq = row["next_seq"]
            event["_seq"] = seq
            sig = compute_signature(seq, event_id, source.get("agent", "UNKNOWN"), payload_json_str) or ""

            conn.execute(
                """
                INSERT INTO ssb_events
                (id, seq, timestamp, session_id,
                 source_agent, source_instance,
                 target_scope, target_hint,
                 event_type, event_subtype,
                 summary, detail, confidence, risk_level, priority,
                 action_req, deadline, payload_json, semantic_json, agent_signature)
                VALUES (?, ?, ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?)
            """,
                (
                    event_id,
                    seq,
                    event["timestamp"],
                    event.get("session_id", ""),
                    source.get("agent", "UNKNOWN"),
                    source.get("instance", ""),
                    target.get("scope", "ALL"),
                    target.get("routing_hint", ""),
                    ev_type,
                    ev_subtype,
                    payload.get("summary", ""),
                    json.dumps(payload.get("detail", ""), ensure_ascii=False)
                    if isinstance(payload.get("detail", ""), dict)
                    else payload.get("detail", ""),
                    payload.get("confidence", 1.0),
                    payload.get("risk_level", "LOW"),
                    payload.get("priority", "P3"),
                    payload.get("action_required", "NONE"),
                    payload.get("deadline", ""),
                    json.dumps(payload, ensure_ascii=False),
                    json.dumps(semantic, ensure_ascii=False),
                    sig,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        self._last_seq = seq

        # Write to file (if rule exists)
        if write_file:
            self._write_file_event(event)

        return event_id

    def _write_file_event(self, event: dict):
        """Write event to corresponding file based on type."""
        ev_type = event["event"].get("type", "")
        rule = _FILE_RULES.get(ev_type)

        if rule is None:
            # No file persistence for this type (SIGNAL, PROPOSAL, etc.)
            return

        if "content" in rule:
            # Formatted content available
            content = rule["content"](event)
            filepath = rule["file"](event)

            filepath.parent.mkdir(parents=True, exist_ok=True)

            if rule.get("no_archive"):
                # Overwrite (e.g., STATE.yaml, LATEST.md)
                filepath.write_text(content, encoding="utf-8")
            else:
                # Write new file + archive
                filepath.write_text(content, encoding="utf-8")
                archive = rule.get("archive")
                if archive:
                    ap = archive(event)
                    ap.parent.mkdir(parents=True, exist_ok=True)
                    if not ap.exists():
                        ap.write_text(content, encoding="utf-8")
        elif ev_type == "STATE_CHANGE":
            # Minimal STATE_CHANGE: just update STATE.yaml with event info
            self._write_state_change(event)

    def _write_state_change(self, event: dict):
        """Update STATE.yaml with state change info (non-destructive)."""
        state = self.load_state()
        p = event["payload"]

        state["last_state_change"] = {
            "timestamp": event.get("timestamp", _now()),
            "summary": p.get("summary", ""),
            "event_id": event.get("event_id", ""),
        }

        # Also add/update any state fields from payload
        detail = p.get("detail", "")
        if detail and isinstance(detail, dict):
            for key, value in detail.items():
                state[key] = value

        self._write_state(state)

    # ─── Query ────────────────────────────────────────────────────────

    def query(
        self,
        event_type: str | None = None,
        source_agent: str | None = None,
        action_required: str | None = None,
        risk_level: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list:
        """
        Query events with filters.

        Returns list of event dicts (SSB-SCHEMA-V1.md format).
        """
        conn = self._get_conn()
        try:
            where = []
            params = []

            if event_type:
                where.append("event_type = ?")
                params.append(event_type)
            if source_agent:
                where.append("source_agent = ?")
                params.append(source_agent)
            if action_required:
                where.append("action_req = ?")
                params.append(action_required)
            if risk_level:
                where.append("risk_level = ?")
                params.append(risk_level)
            if since:
                where.append("timestamp >= ?")
                params.append(since)

            where_clause = " AND ".join(where) if where else "1=1"

            rows = conn.execute(
                f"SELECT * FROM ssb_events WHERE {where_clause} ORDER BY seq DESC LIMIT ?",
                params + [limit],
            ).fetchall()

            return [self._row_to_event(r) for r in rows]
        finally:
            conn.close()

    def _row_to_event(self, row: sqlite3.Row) -> dict:
        return {
            "ssb_version": "1.0",
            "event_id": row["id"],
            "timestamp": row["timestamp"],
            "session_id": row["session_id"],
            "source": {
                "agent": row["source_agent"],
                "instance": row["source_instance"],
            },
            "target": {
                "scope": row["target_scope"],
                "routing_hint": row["target_hint"],
            },
            "event": {
                "type": row["event_type"],
                "subtype": row["event_subtype"],
            },
            "payload": json.loads(row["payload_json"]),
            "semantic": json.loads(row["semantic_json"]),
        }

    # ─── Subscribe ────────────────────────────────────────────────────

    def subscribe(self, event_type: str | None = None, block: bool = True, interval: float = 2.0) -> list:
        """轮询新事件 (生产代码请使用 query() 获取精确结果)"""
        deadline = time.time() + 30
        while True:
            new_seq = self._current_seq()
            if new_seq > self._last_sub_seq:
                # Query only new events (since last subscribe checkpoint)
                results = self.query(limit=new_seq - self._last_sub_seq + 5)
                if results:
                    self._last_sub_seq = new_seq
                    return results

            if not block:
                return []

            if time.time() > deadline:
                return []

            time.sleep(interval)

    # ─── State ────────────────────────────────────────────────────────

    def load_state(self) -> dict:
        """Parse current STATE.yaml into a dict (使用 yaml.safe_load)."""
        if not STATE_PATH.exists():
            return {"phase": "2", "sprint": "1", "last_state_change": {}}

        import yaml

        with open(STATE_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _write_state(self, state: dict):
        """Write dict back to STATE.yaml (使用 yaml.dump)."""
        import yaml

        header = "# eCOS System State\n# Auto-generated by SSB Client\n\n"
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            f.write(header)
            yaml.dump(state, f, allow_unicode=True, default_flow_style=False)

    def get_state(self) -> dict:
        """Get current system state (from STATE.yaml)."""
        return self.load_state()

    # ─── Recovery ─────────────────────────────────────────────────────

    def recover_from_files(self) -> dict:
        """
        Rebuild SQLite database from files.

        Reads STATE.yaml, HANDOFF, and FAILURES dir,
        reconstructs SQLite events.

        Returns:
            dict with recovery stats
        """
        stats = {"handoff": 0, "failure": 0, "state_change": 0}

        # Clear and re-init
        if SSB_DB_PATH.exists():
            SSB_DB_PATH.unlink()
        self._init_db()

        # 1. Recover from STATE.yaml
        state = self.load_state()
        if state:
            self.publish(
                {
                    "event": {"type": "STATE_CHANGE", "subtype": "RECOVERED"},
                    "source": {"agent": "SSB_CLIENT", "instance": "recovery"},
                    "payload": {
                        "summary": "System state recovered from STATE.yaml",
                        "detail": "",
                        "risk_level": "LOW",
                        "action_required": "NONE",
                    },
                },
                write_file=False,
            )
            stats["state_change"] = 1

        # 2. Recover from HANDOFF
        if HANDOFF_LATEST.exists():
            content = HANDOFF_LATEST.read_text(encoding="utf-8")
            # Extract summary from first line
            first_line = content.split("\n")[0] if content else "HANDOFF recovery"
            summary = first_line.replace("#", "").strip()
            mtime = os.path.getmtime(HANDOFF_LATEST)
            ts = datetime.fromtimestamp(mtime, TZ).isoformat()

            self.publish(
                {
                    "event_id": f"recovery-handoff-{int(mtime)}",
                    "timestamp": ts,
                    "event": {"type": "HANDOFF", "subtype": "RECOVERED"},
                    "source": {"agent": "SSB_CLIENT", "instance": "recovery"},
                    "payload": {
                        "summary": summary or "HANDOFF recovered",
                        "detail": content[:2000],
                        "risk_level": "LOW",
                        "action_required": "NONE",
                    },
                },
                write_file=False,
            )
            stats["handoff"] = 1

        # 3. Recover from FAILURES
        if FAILURES_DIR.exists():
            for f in sorted(FAILURES_DIR.iterdir()):
                if not f.name.startswith("FAIL-") or not f.name.endswith(".md"):
                    continue
                if f.name == "TEMPLATE.md":
                    continue

                content = f.read_text(encoding="utf-8")
                mtime = os.path.getmtime(f)
                ts = datetime.fromtimestamp(mtime, TZ).isoformat()

                # Extract summary from first content line
                lines = content.split("\n")
                summary = lines[0].replace("#", "").strip() if lines else f.name

                self.publish(
                    {
                        "event_id": f"recovery-fail-{int(mtime)}",
                        "timestamp": ts,
                        "event": {"type": "FAILURE", "subtype": "RECOVERED"},
                        "source": {"agent": "SSB_CLIENT", "instance": "recovery"},
                        "payload": {
                            "summary": summary,
                            "detail": content[:2000],
                            "risk_level": "MED",
                            "action_required": "NONE",
                        },
                    },
                    write_file=False,
                )
                stats["failure"] += 1

        return stats


# ─── CLI Entry Point ─────────────────────────────────────────────────


def main():
    """CLI entry point for ssb-client."""
    import sys

    args = sys.argv[1:]
    if not args or args[0] in ("--help", "-h"):
        print("Usage: ssb-client [publish|query|state|recover|events|stats] [options]")
        sys.exit(1)

    cmd = args[0]
    ssb = SSBClient()

    if cmd == "publish":
        # ssb-client publish '{"event":{"type":"SIGNAL"},"source":{"agent":"HERMES"},"payload":{"summary":"test"}}'
        if len(args) < 2:
            event = json.loads(sys.stdin.read())
        else:
            event = json.loads(args[1])
        eid = ssb.publish(event)
        print(eid)

    elif cmd == "query":
        kwargs = {}
        for arg in args[1:]:
            key, _, val = arg.partition("=")
            kwargs[key] = val
        results = ssb.query(**kwargs)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif cmd == "state":
        state = ssb.get_state()
        print(json.dumps(state, ensure_ascii=False, indent=2))

    elif cmd == "recover":
        stats = ssb.recover_from_files()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif cmd == "events":
        conn = ssb._get_conn()
        try:
            rows = conn.execute(
                "SELECT seq, event_type, summary, timestamp FROM ssb_events ORDER BY seq DESC LIMIT 50"
            ).fetchall()
            for r in rows:
                print(f"{r['seq']:>4} | {r['event_type']:<14} | {r['summary'][:60]:<60} | {r['timestamp'][:19]}")
        finally:
            conn.close()

    elif cmd == "stats":
        conn = ssb._get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) AS c FROM ssb_events").fetchone()["c"]
            by_type = conn.execute(
                "SELECT event_type, COUNT(*) AS c FROM ssb_events GROUP BY event_type ORDER BY c DESC"
            ).fetchall()
            print(f"Total events: {total}")
            for r in by_type:
                print(f"  {r['event_type']:<14} → {r['c']}")
        finally:
            conn.close()

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
