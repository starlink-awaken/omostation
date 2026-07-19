"""G-DEL.4 file-backed shared context store (cross-process agent handoff).

Default root: ``.omo/_delivery/shared-context/`` (gitignored delivery plane).
Caliber: single-repo / process-local multi-agent — not multi-host.

Contract mirrors gbrain AgentSharedContextStore visibility rules:
- empty readers list ⇒ shared to all agents in scope
- non-empty readers ⇒ only writer + listed readers
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SAFE_SEG = re.compile(r"^[A-Za-z0-9._@+=\-]+$")


@dataclass
class SharedContextRecord:
    key: str
    value: str
    writer: str
    written_at: str
    readers: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def visible_to(self, reader: str) -> bool:
        if reader == self.writer:
            return True
        if not self.readers:
            return True
        return reader in self.readers


def default_store_root(workspace: Path | None = None) -> Path:
    root = workspace or Path(__file__).resolve().parents[2]
    return root / ".omo" / "_delivery" / "shared-context"


class FileSharedContextStore:
    """Atomic JSON-file store under ``{root}/{scope}/{key}.json``."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else default_store_root()

    def _scope_dir(self, scope: str) -> Path:
        if not SAFE_SEG.match(scope):
            raise ValueError(f"invalid scope: {scope!r}")
        d = self.root / scope
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _key_path(self, scope: str, key: str) -> Path:
        if not SAFE_SEG.match(key):
            raise ValueError(f"invalid key: {key!r}")
        return self._scope_dir(scope) / f"{key}.json"

    def write(
        self,
        writer: str,
        key: str,
        value: str,
        *,
        scope: str = "default",
        readers: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> SharedContextRecord:
        if not writer or not writer.strip():
            raise ValueError("writer required")
        if not key or not key.strip():
            raise ValueError("key required")
        rec = SharedContextRecord(
            key=key,
            value=value,
            writer=writer,
            written_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            readers=list(readers or []),
            tags=list(tags or []),
        )
        path = self._key_path(scope, key)
        tmp = path.with_suffix(".json.tmp")
        payload = asdict(rec)
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        return rec

    def _load(self, path: Path) -> SharedContextRecord | None:
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return SharedContextRecord(
            key=str(data.get("key") or path.stem),
            value=str(data.get("value") or ""),
            writer=str(data.get("writer") or ""),
            written_at=str(data.get("written_at") or ""),
            readers=list(data.get("readers") or []),
            tags=list(data.get("tags") or []),
        )

    def read(
        self, reader: str, key: str, *, scope: str = "default"
    ) -> SharedContextRecord | None:
        if not reader or not reader.strip():
            raise ValueError("reader required")
        rec = self._load(self._key_path(scope, key))
        if rec is None:
            return None
        if not rec.visible_to(reader):
            return None
        return rec

    def list_visible(self, reader: str, *, scope: str = "default") -> list[SharedContextRecord]:
        d = self.root / scope
        if not d.is_dir():
            return []
        out: list[SharedContextRecord] = []
        for p in sorted(d.glob("*.json")):
            if p.name.endswith(".tmp"):
                continue
            rec = self._load(p)
            if rec and rec.visible_to(reader):
                out.append(rec)
        return out

    def export_scope(self, scope: str = "default") -> list[SharedContextRecord]:
        d = self.root / scope
        if not d.is_dir():
            return []
        out: list[SharedContextRecord] = []
        for p in sorted(d.glob("*.json")):
            if p.name.endswith(".tmp"):
                continue
            rec = self._load(p)
            if rec:
                out.append(rec)
        return out


def format_for_kos(rec: SharedContextRecord, scope: str) -> str:
    tags = ", ".join(rec.tags) if rec.tags else ""
    lines = [
        f"# shared-context/{scope}/{rec.key}",
        f"writer: {rec.writer}",
        f"writtenAt: {rec.written_at}",
    ]
    if tags:
        lines.append(f"tags: {tags}")
    lines.extend(["", rec.value])
    return "\n".join(lines)


def seed_into_kos(
    records: list[SharedContextRecord],
    *,
    scope: str,
    db_path: Path,
) -> dict[str, Any]:
    """UPSERT shared-context records into KOS documents table."""
    import hashlib
    import sqlite3

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
              doc_id TEXT PRIMARY KEY,
              title TEXT,
              canonical_path TEXT UNIQUE,
              body_preview TEXT,
              indexed_at TEXT
            );
            """
        )
        n = 0
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for rec in records:
            path = f"gbrain://shared-context/{scope}/{rec.key}"
            doc_id = hashlib.sha1(path.encode()).hexdigest()[:16]
            body = format_for_kos(rec, scope)
            title = f"shared-context {scope}/{rec.key}"
            preview = body[:500]
            conn.execute(
                """
                INSERT INTO documents (doc_id, title, canonical_path, body_preview, indexed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(canonical_path) DO UPDATE SET
                  title=excluded.title,
                  body_preview=excluded.body_preview,
                  indexed_at=excluded.indexed_at,
                  doc_id=excluded.doc_id
                """,
                (doc_id, title, path, preview, now),
            )
            n += 1
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        return {"ok": True, "upserted": n, "total_documents": total, "db": str(db_path)}
    finally:
        conn.close()


def kos_retrieve(db_path: Path, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Simple LIKE search over body_preview / title / path."""
    import sqlite3

    if not Path(db_path).is_file():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        q = f"%{query}%"
        rows = conn.execute(
            """
            SELECT canonical_path, title, body_preview FROM documents
            WHERE canonical_path LIKE ? OR title LIKE ? OR body_preview LIKE ?
            LIMIT ?
            """,
            (q, q, q, limit),
        ).fetchall()
        return [
            {"path": r[0], "title": r[1], "preview": (r[2] or "")[:200]} for r in rows
        ]
    finally:
        conn.close()
