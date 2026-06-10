"""Workspace research read models for Agora web dashboard."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def workspace_home() -> Path:
    return Path.home()


def _workspace_db() -> Path:
    return workspace_home() / ".workspace" / "data.db"


def _connect() -> sqlite3.Connection | None:
    db = _workspace_db()
    if not db.exists():
        return None
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


def _parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in data if item]


def list_recent_research(limit: int = 20) -> dict[str, Any]:
    conn = _connect()
    if conn is None:
        return {"research": [], "total": 0}
    try:
        rows = conn.execute(
            """
            SELECT id, topic, summary, created_at, source_count
            FROM research
            WHERE quarantined_at IS NULL AND archived_at IS NULL
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    except sqlite3.Error:
        conn.close()
        return {"research": [], "total": 0}
    conn.close()
    return {
        "research": [
            {
                "id": row["id"],
                "topic": row["topic"],
                "summary": (row["summary"] or "")[:200],
                "date": row["created_at"],
                "sources": row["source_count"],
            }
            for row in rows
        ],
        "total": len(rows),
    }


def search_research(q: str = "", status: str = "active", tag: str = "", limit: int = 20) -> dict[str, Any]:
    conn = _connect()
    if conn is None:
        return {"research": [], "total": 0}
    try:
        research_columns = {row["name"] for row in conn.execute("PRAGMA table_info(research)").fetchall()}
        has_fts = (
            conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'research_fts'").fetchone()
            is not None
        )

        where_conditions: list[str] = []
        params: list[Any] = []

        if status == "active":
            where_conditions.append("r.quarantined_at IS NULL AND r.archived_at IS NULL")
        elif status == "archived":
            where_conditions.append("r.archived_at IS NOT NULL")
        elif status == "quarantined":
            where_conditions.append("r.quarantined_at IS NOT NULL")

        join_sql = ""
        select_snippet = "r.summary AS snippet"
        if q:
            if has_fts:
                join_sql = "JOIN research_fts f ON f.rowid = r.id"
                select_snippet = "snippet(research_fts, 1, '<mark>', '</mark>', '...', 40) AS snippet"
                where_conditions.append("research_fts MATCH ?")
                params.append(q)
            else:
                text_columns = [column for column in ("topic", "summary", "full_text") if column in research_columns]
                if text_columns:
                    like_conditions = [f"r.{column} LIKE ?" for column in text_columns]
                    where_conditions.append("(" + " OR ".join(like_conditions) + ")")
                    params.extend([f"%{q}%"] * len(text_columns))

        if tag:
            where_conditions.append("r.tags LIKE ?")
            params.append(f'%"{tag}"%')

        where_sql = " AND ".join(where_conditions) if where_conditions else "1=1"
        rows = conn.execute(
            f"""
            SELECT r.id, r.topic, r.summary, r.created_at, r.source_count,
                   r.tags, r.archived_at, r.quarantined_at, {select_snippet}
            FROM research r
            {join_sql}
            WHERE {where_sql}
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    except sqlite3.Error:
        conn.close()
        return {"research": [], "total": 0}
    conn.close()
    return {
        "research": [
            {
                "id": row["id"],
                "topic": row["topic"],
                "summary": (row["summary"] or "")[:200],
                "snippet": row["snippet"] or (row["summary"] or ""),
                "date": row["created_at"],
                "sources": row["source_count"],
            }
            for row in rows
        ],
        "total": len(rows),
    }


def get_research_detail(research_id: int) -> dict[str, Any] | None:
    conn = _connect()
    if conn is None:
        return None
    try:
        row = conn.execute(
            """
            SELECT id, topic, summary, source_count, created_at,
                   tags, archived_at, archive_reason,
                   quarantined_at, quarantine_reason
            FROM research
            WHERE id = ?
            """,
            (research_id,),
        ).fetchone()
        if row is None:
            conn.close()
            return None
        record = {
            "id": row["id"],
            "topic": row["topic"],
            "summary": row["summary"] or "",
            "source_count": row["source_count"] or 0,
            "created_at": row["created_at"],
            "tags": _parse_json_list(row["tags"]),
            "archived_at": row["archived_at"],
            "archive_reason": row["archive_reason"],
            "quarantined_at": row["quarantined_at"],
            "quarantine_reason": row["quarantine_reason"],
        }
        parents = conn.execute(
            """
            SELECT r.id, r.topic, r.summary, rel.relation_type, rel.created_at
            FROM research_relations rel
            JOIN research r ON r.id = rel.parent_id
            WHERE rel.child_id = ?
            ORDER BY rel.created_at ASC
            """,
            (research_id,),
        ).fetchall()
        children = conn.execute(
            """
            SELECT r.id, r.topic, r.summary, rel.relation_type, rel.created_at
            FROM research_relations rel
            JOIN research r ON r.id = rel.child_id
            WHERE rel.parent_id = ?
            ORDER BY rel.created_at ASC
            """,
            (research_id,),
        ).fetchall()
        publications = conn.execute(
            """
            SELECT style, output_path, published_at
            FROM published_reports
            WHERE research_id = ?
            ORDER BY published_at DESC
            """,
            (research_id,),
        ).fetchall()
        events = conn.execute(
            """
            SELECT event_type, description, created_at
            FROM research_events
            WHERE research_id = ?
            ORDER BY created_at ASC
            """,
            (research_id,),
        ).fetchall()
    except sqlite3.Error:
        conn.close()
        return None
    conn.close()

    timeline: list[dict[str, Any]] = [
        {
            "event_type": "created",
            "created_at": record["created_at"],
            "description": f"创建研究：{record['topic']}",
        }
    ]
    timeline.extend(
        {
            "event_type": "derived_from",
            "created_at": item["created_at"],
            "description": f"来自 {item['relation_type']}: #{item['id']} {item['topic']}",
        }
        for item in parents
    )
    timeline.extend(
        {
            "event_type": event["event_type"],
            "created_at": event["created_at"],
            "description": event["description"],
        }
        for event in events
    )
    timeline.sort(key=lambda item: item["created_at"] or 0)

    return {
        "record": record,
        "parents": [dict(item) for item in parents],
        "children": [dict(item) for item in children],
        "publications": [dict(item) for item in publications],
        "timeline": timeline,
    }


def archive_research(research_id: int) -> bool:
    """Archive a research record. Returns True on success."""
    conn = _connect()
    if conn is None:
        return False
    try:
        import time

        now = time.time()
        conn.execute(
            "UPDATE research SET archived_at = ?, archive_reason = ? WHERE id = ? AND archived_at IS NULL",
            (now, "dashboard archive", research_id),
        )
        if conn.total_changes == 0:
            conn.close()
            return False
        conn.execute(
            "INSERT INTO research_events (research_id, event_type, description, created_at) VALUES (?, ?, ?, ?)",
            (research_id, "archived", "从 Dashboard 归档", now),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error:
        conn.close()
        return False


def publish_brief(research_id: int) -> str | None:
    """Publish a research record as brief report. Returns output path on success."""
    conn = _connect()
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT id, topic, summary, source_count, created_at FROM research WHERE id = ?", (research_id,)
        ).fetchone()
        if row is None:
            conn.close()
            return None
        publish_dir = Path.home() / "Desktop" / "workspace-published"
        publish_dir.mkdir(parents=True, exist_ok=True)
        slug = row["topic"].replace(" ", "-")[:40]
        output_path = publish_dir / f"brief-{row['id']}-{slug}.md"
        output_path.write_text(
            f"# {row['topic']}\n\n{row['summary'] or ''}\n\n---\n来源数: {row['source_count'] or 0}\nID: {row['id']}\n"
        )
        import time

        now = time.time()
        conn.execute(
            "INSERT INTO published_reports (research_id, style, output_path, published_at) VALUES (?, ?, ?, ?)",
            (research_id, "brief", str(output_path), now),
        )
        conn.execute(
            "INSERT INTO research_events (research_id, event_type, description, created_at) VALUES (?, ?, ?, ?)",
            (research_id, "published", f"从 Dashboard 发布为 brief: {output_path.name}", now),
        )
        conn.commit()
        conn.close()
        return str(output_path)
    except (sqlite3.Error, OSError):
        conn.close()
        return None


def unarchive_research(research_id: int) -> bool:
    conn = _connect()
    if conn is None:
        return False
    try:
        import time

        now = time.time()
        conn.execute(
            "UPDATE research SET archived_at = NULL, archive_reason = NULL WHERE id = ? AND archived_at IS NOT NULL",
            (research_id,),
        )
        if conn.total_changes == 0:
            conn.close()
            return False
        conn.execute(
            "INSERT INTO research_events (research_id, event_type, description, created_at) VALUES (?, ?, ?, ?)",
            (research_id, "unarchived", "从 Dashboard 恢复归档", now),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error:
        conn.close()
        return False


def tag_research(research_id: int, tags: list[str]) -> bool:
    import json

    conn = _connect()
    if conn is None:
        return False
    try:
        conn.execute("UPDATE research SET tags = ? WHERE id = ?", (json.dumps(tags, ensure_ascii=False), research_id))
        if conn.total_changes == 0:
            conn.close()
            return False
        conn.commit()
        conn.close()
        return True
    except (sqlite3.Error, TypeError):
        conn.close()
        return False


def rename_research(research_id: int, new_title: str) -> bool:
    conn = _connect()
    if conn is None:
        return False
    try:
        conn.execute("UPDATE research SET topic = ? WHERE id = ?", (new_title, research_id))
        if conn.total_changes == 0:
            conn.close()
            return False
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error:
        conn.close()
        return False


def sync_published(research_id: int, target_dir: str = "") -> str | None:
    """Copy latest published report to target directory. Returns target path."""
    conn = _connect()
    if conn is None:
        return None
    try:
        pub = conn.execute(
            "SELECT output_path FROM published_reports WHERE research_id = ? ORDER BY published_at DESC LIMIT 1",
            (research_id,),
        ).fetchone()
        if pub is None:
            conn.close()
            return None
        src = Path(pub["output_path"])
        if not src.exists():
            conn.close()
            return None
        base_dir = Path(target_dir) if target_dir else Path.home() / "Desktop" / "workspace-synced"
        base_dir.mkdir(parents=True, exist_ok=True)
        dst = base_dir / src.name
        dst.write_text(src.read_text())
        conn.close()
        return str(dst)
    except (sqlite3.Error, OSError):
        conn.close()
        return None
