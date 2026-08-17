"""KOS Consensus API — X3价值堆栈：三级共识模型。

L1 (Agent自检): 30天有效期, 可自动续签
L2 (User确认): 90天有效期, 需用户参与续签
L3 (RedTeam验证): 365天有效期, 需红队参与续签

数据存储: KOS retrieval DB 中的 kos_consensus 表。
"""

import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from kos.config import get_artifact_path  # type: ignore[import-untyped, import-not-found]

EXPIRY_DAYS = {1: 30, 2: 90, 3: 365}


def _get_db() -> sqlite3.Connection:
    db_path = get_artifact_path("retrievalDatabase")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS kos_consensus (
            consensus_id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL,
            level INTEGER NOT NULL,
            agreed_by TEXT NOT NULL DEFAULT '[]',
            agreement TEXT NOT NULL DEFAULT '',
            source_session TEXT DEFAULT '',
            confirmed_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            renewed_from TEXT,
            provenance_chain TEXT DEFAULT '[]',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_kos_cons_entity ON kos_consensus(entity_id);
        CREATE INDEX IF NOT EXISTS idx_kos_cons_status ON kos_consensus(status);
    """)
    conn.commit()


def _detect_level(agreed_by: list[str], explicit_level: int = 1) -> int:
    # 明确指定了level 3就保持
    if explicit_level >= 3:
        return 3
    for a in agreed_by:
        if a.startswith("redteam:") or a.lower().startswith("redteam"):
            return 3
    # 含user:且level<2 → 自动升为2
    has_user = any(a.startswith("user:") or a.lower().startswith("user") for a in agreed_by)
    if has_user and explicit_level < 2:
        return 2
    if explicit_level > 1:
        return explicit_level
    return 1


def create_consensus(
    entity_id: str,
    agreed_by: list[str],
    agreement: str,
    source_session: str = "",
    level: int = 1,
    provenance_chain: list[dict] | None = None,
) -> dict[str, Any] | None:
    conn = _get_db()
    _ensure_table(conn)
    now = datetime.now(UTC)
    level = _detect_level(agreed_by, level)
    expires_at = now + timedelta(days=EXPIRY_DAYS[level])
    consensus_id = f"consensus:{entity_id}:{uuid.uuid4().hex[:8]}"
    provenance_chain_json = json.dumps(provenance_chain or [], ensure_ascii=False)
    conn.execute(
        """INSERT INTO kos_consensus
           (consensus_id, entity_id, level, agreed_by, agreement, source_session,
            confirmed_at, expires_at, status, provenance_chain, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
        (
            consensus_id,
            entity_id,
            level,
            json.dumps(agreed_by, ensure_ascii=False),
            agreement,
            source_session,
            now.isoformat(),
            expires_at.isoformat(),
            provenance_chain_json,
            now.isoformat(),
            now.isoformat(),
        ),
    )
    # 将旧的活跃共识标记为superseded (同一entity同一level)
    conn.execute(
        """UPDATE kos_consensus SET status='superseded', updated_at=?
           WHERE entity_id=? AND level=? AND status='active' AND consensus_id!=?""",
        (now.isoformat(), entity_id, level, consensus_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM kos_consensus WHERE consensus_id=?", (consensus_id,)).fetchone()
    conn.close()
    # 发射 KOS 共识创建事件 (hermes-ops)
    import os  # type: ignore[import-untyped]
    import urllib.request

    try:
        ops_url = os.environ.get("HERMES_OPS_URL", "http://localhost:9800")
        req = urllib.request.Request(
            f"{ops_url}/event",
            data=json.dumps({"type": "CONSENSUS_CREATED", "payload": {"entity_id": entity_id}}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass
    return _row_to_dict(row)


def get_consensus(consensus_id: str) -> dict[str, Any] | None:
    conn = _get_db()
    _ensure_table(conn)
    row = conn.execute("SELECT * FROM kos_consensus WHERE consensus_id=?", (consensus_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(row)


def get_entity_consensus(entity_id: str) -> list[dict[str, Any]]:
    conn = _get_db()
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM kos_consensus WHERE entity_id=? AND status='active' ORDER BY level ASC",
        (entity_id,),
    ).fetchall()
    conn.close()
    return [r for r in (_row_to_dict(r) for r in rows) if r is not None]


def mark_expired() -> int:
    """标记所有过期共识为expired。返回标记数。"""
    conn = _get_db()
    _ensure_table(conn)
    now = datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE kos_consensus SET status='expired', updated_at=? WHERE status='active' AND expires_at < ?",
        (now, now),
    )
    marked = conn.total_changes
    conn.commit()
    conn.close()
    return marked


def list_expired_consensus() -> list[dict[str, Any]]:
    conn = _get_db()
    _ensure_table(conn)
    rows = conn.execute(
        "SELECT * FROM kos_consensus WHERE status='expired' ORDER BY expires_at ASC LIMIT 50"
    ).fetchall()
    conn.close()
    return [r for r in (_row_to_dict(r) for r in rows) if r is not None]


def trace_consensus(entity_id: str) -> dict[str, Any]:
    """追踪共识的完整引用链。

    查询实体的活跃共识，提取每条共识的 provenance_chain 形成执行链追踪。
    """
    entries = get_entity_consensus(entity_id)
    if not entries:
        return {"error": f"No active consensus found for entity: {entity_id}", "code": "NOT_FOUND"}

    results = []
    for entry in entries:
        chain = entry.get("provenance_chain", [])
        # 如果 provenance_chain 为空，fallback 到 basic 信息
        if not chain:
            chain = [{"tool": entry.get("agreed_by", []), "status": entry.get("status", "active")}]
        results.append(
            {
                "entry": {
                    "consensus_id": entry.get("consensus_id"),
                    "entity_id": entry.get("entity_id"),
                    "level": entry.get("level"),
                    "status": entry.get("status"),
                },
                "chain": chain,
            }
        )

    return {"status": "ok", "traces": results, "count": len(results)}


def renew_consensus(
    consensus_id: str,
    agreed_by: list[str] | None = None,
) -> dict[str, Any]:
    """续签共识。L1自动续签，L2/L3需提供新的agreed_by。"""
    conn = _get_db()
    _ensure_table(conn)
    row = conn.execute("SELECT * FROM kos_consensus WHERE consensus_id=?", (consensus_id,)).fetchone()
    if row is None:
        conn.close()
        return {"error": f"Consensus not found: {consensus_id}", "code": "NOT_FOUND"}

    level = row["level"]
    if level >= 2 and not agreed_by:
        conn.close()
        return {
            "error": f"L{level} consensus requires agreed_by for renewal",
            "code": "AGREED_BY_REQUIRED",
        }

    now = datetime.now(UTC)
    new_agreed_by = agreed_by or json.loads(row["agreed_by"] or "[]")
    expires_at = now + timedelta(days=EXPIRY_DAYS[level])
    new_id = f"consensus:{row['entity_id']}:{uuid.uuid4().hex[:8]}"

    # Mark old as renewed
    conn.execute(
        "UPDATE kos_consensus SET status='renewed', updated_at=? WHERE consensus_id=?",
        (now.isoformat(), consensus_id),
    )
    # Carry forward provenance_chain from old entry
    old_chain_raw = row["provenance_chain"] if "provenance_chain" in row.keys() else "[]"
    try:
        old_chain = json.loads(old_chain_raw or "[]")
    except (json.JSONDecodeError, TypeError):
        old_chain = []
    renewed_chain = old_chain + [
        {"source": f"renewed_from:{consensus_id}", "timestamp": now.isoformat(), "action": "renew"}
    ]

    # Create new
    conn.execute(
        """INSERT INTO kos_consensus
           (consensus_id, entity_id, level, agreed_by, agreement, source_session,
            confirmed_at, expires_at, status, renewed_from, provenance_chain, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)""",
        (
            new_id,
            row["entity_id"],
            level,
            json.dumps(new_agreed_by, ensure_ascii=False),
            row["agreement"],
            row["source_session"] or "",
            now.isoformat(),
            expires_at.isoformat(),
            consensus_id,
            json.dumps(renewed_chain, ensure_ascii=False),
            now.isoformat(),
            now.isoformat(),
        ),
    )
    conn.commit()
    new_row = conn.execute("SELECT * FROM kos_consensus WHERE consensus_id=?", (new_id,)).fetchone()
    conn.close()
    return {"status": "renewed", "old_consensus_id": consensus_id, "consensus": _row_to_dict(new_row)}


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    try:
        d["agreed_by"] = json.loads(d.get("agreed_by", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["agreed_by"] = []
    try:
        d["provenance_chain"] = json.loads(d.get("provenance_chain", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["provenance_chain"] = []
    return d
