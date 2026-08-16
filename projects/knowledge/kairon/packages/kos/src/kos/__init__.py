"""KOS — Knowledge Ontology Storage (library entry point)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _db() -> sqlite3.Connection:
    p = Path.home() / ".kos" / "index.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(p))
    c.row_factory = sqlite3.Row
    return c


def search(query: str, meta_type: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    c = _db()
    try:
        sql = "SELECT * FROM documents WHERE title LIKE ? OR body LIKE ?"
        p = [f"%{query}%", f"%{query}%"]
        if meta_type:
            sql += " AND json_extract(metadata_json, '$.meta_type') = ?"
            p.append(meta_type)
        sql += f" LIMIT {int(limit)}"
        return [dict(r) for r in c.execute(sql, p).fetchall()]
    except Exception:
        return []
    finally:
        c.close()


def stats() -> dict[str, Any]:
    c = _db()
    try:
        return {"total": c.execute("SELECT COUNT(*) as c FROM documents").fetchone()["c"]}
    except Exception:
        return {"total": 0}
    finally:
        c.close()


def list_documents(limit: int = 10) -> list[dict[str, Any]]:
    """List documents in the knowledge base."""
    c = _db()
    try:
        sql = "SELECT * FROM documents LIMIT ?"
        return [dict(r) for r in c.execute(sql, (int(limit),)).fetchall()]
    except Exception:
        return []
    finally:
        c.close()


__all__ = (
    "list_documents",
    "search",
    "stats",
)
