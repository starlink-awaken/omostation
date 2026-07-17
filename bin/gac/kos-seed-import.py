#!/usr/bin/env python3
"""G-CONV.6 KOS seed import — create kos/kos-index.sqlite and index markdown docs.

Reusable first-batch path: indexes workspace docs + optional creative vault md files.
Does not require network. Safe to re-run (UPSERT by path).

Usage:
  python3 bin/gac/kos-seed-import.py --limit 50
  python3 bin/gac/kos-seed-import.py --creative-root ~/Documents/@创意创作 --limit 200
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_DB = WORKSPACE / "kos" / "kos-index.sqlite"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _doc_id(path: Path) -> str:
    return hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:16]


def _collect_md(roots: list[Path], limit: int) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.md")):
            if any(part.startswith(".") for part in p.parts):
                continue
            if "node_modules" in p.parts or ".venv" in p.parts:
                continue
            out.append(p)
            if len(out) >= limit:
                return out
    return out


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
          doc_id TEXT PRIMARY KEY,
          title TEXT,
          canonical_path TEXT UNIQUE,
          body_preview TEXT,
          indexed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS kos_entities (
          entity_id TEXT PRIMARY KEY,
          kind TEXT,
          title TEXT,
          path TEXT
        );
        CREATE TABLE IF NOT EXISTS kos_relations (
          source_id TEXT,
          predicate TEXT,
          target_id TEXT
        );
        """
    )


def import_docs(db_path: Path, files: list[Path]) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    _ensure_schema(conn)
    n = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        title = path.stem
        for line in text.splitlines()[:20]:
            if line.startswith("# "):
                title = line[2:].strip() or title
                break
        doc_id = _doc_id(path)
        rel = str(path)
        try:
            rel = str(path.relative_to(WORKSPACE))
        except ValueError:
            pass
        conn.execute(
            """
            INSERT INTO documents(doc_id, title, canonical_path, body_preview, indexed_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(canonical_path) DO UPDATE SET
              title=excluded.title,
              body_preview=excluded.body_preview,
              indexed_at=excluded.indexed_at
            """,
            (doc_id, title, rel, text[:500], _utc()),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO kos_entities(entity_id, kind, title, path)
            VALUES(?,?,?,?)
            """,
            (doc_id, "document", title, rel),
        )
        n += 1
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()
    print(f"indexed={n} total_documents={count} db={db_path}")
    return int(count)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument(
        "--creative-root",
        type=Path,
        default=Path(os.path.expanduser("~/Documents/@创意创作")),
        help="optional creative vault root",
    )
    ap.add_argument("--workspace-docs-only", action="store_true")
    args = ap.parse_args(argv)

    roots = [
        WORKSPACE / "docs",
        WORKSPACE / ".omo" / "_knowledge" / "decisions",
    ]
    if not args.workspace_docs_only and args.creative_root.is_dir():
        roots.append(args.creative_root)

    files = _collect_md(roots, args.limit)
    if not files:
        print("no markdown files found", file=sys.stderr)
        return 1
    total = import_docs(args.db, files)
    return 0 if total > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
