#!/usr/bin/env python3
"""G-CONV.6 / KOS-Q-GROWTH seed import — index markdown into kos/kos-index.sqlite.

Reusable path: workspace docs + personal vaults. Does not require network.
Safe to re-run (UPSERT by canonical_path).

Usage:
  python3 bin/gac/kos-seed-import.py --limit 50
  python3 bin/gac/kos-seed-import.py --creative-root ~/Documents/@创意创作 --limit 200
  # Q4 growth: only fill with paths not yet in DB
  python3 bin/gac/kos-seed-import.py --prefer-new --limit 2000 \\
    --root ~/Documents/@工作文档 --root ~/Documents/@驾驶舱
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

SKIP_PARTS = {".git", "node_modules", ".venv", "__pycache__", ".tox", "dist", "build"}

# Default personal vaults for quarterly growth (local machine only).
DEFAULT_VAULTS = (
    "~/Documents/@创意创作",
    "~/Documents/@学习进化",
    "~/Documents/@公共",
    # Q4: work notes + cockpit knowledge (精选扩展面)
    "~/Documents/@工作文档",
    "~/Documents/@驾驶舱",
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _doc_id(path: Path) -> str:
    return hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:16]


def _path_keys(path: Path) -> set[str]:
    """All forms that may appear as canonical_path in the DB."""
    keys = {str(path), str(path.resolve())}
    try:
        keys.add(str(path.relative_to(WORKSPACE)))
    except ValueError:
        pass
    return keys


def _load_indexed_paths(db_path: Path) -> set[str]:
    if not db_path.is_file():
        return set()
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT canonical_path FROM documents").fetchall()
    except sqlite3.Error:
        return set()
    finally:
        conn.close()
    return {r[0] for r in rows if r and r[0]}


def _collect_md(
    roots: list[Path],
    limit: int,
    *,
    indexed: set[str] | None = None,
    prefer_new: bool = False,
) -> list[Path]:
    """Collect markdown paths under roots.

    Note: do NOT skip entire trees solely because a parent starts with '.'
    (e.g. `.omo/_knowledge` is a primary SSOT surface). Only skip known junk
    segments (.git, node_modules, .venv, __pycache__).

    When prefer_new=True and indexed is provided, only paths not already in
    the DB count toward the limit (so re-runs actually grow documents).
    """
    out: list[Path] = []
    seen: set[str] = set()
    indexed = indexed or set()

    def _already_indexed(path: Path) -> bool:
        return bool(_path_keys(path) & indexed)

    for root in roots:
        if root.is_file() and root.suffix == ".md":
            key = str(root.resolve())
            if key in seen:
                continue
            if prefer_new and _already_indexed(root):
                continue
            out.append(root)
            seen.add(key)
            if len(out) >= limit:
                return out
            continue
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.md")):
            if any(part in SKIP_PARTS for part in p.parts):
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            if prefer_new and _already_indexed(p):
                continue
            out.append(p)
            seen.add(key)
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
        # Prefer absolute path for vault files outside workspace so UPSERT keys stay stable.
        rel = str(path.resolve())
        try:
            rel = str(path.resolve().relative_to(WORKSPACE.resolve()))
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


def _default_workspace_roots() -> list[Path]:
    return [
        WORKSPACE / "docs",
        WORKSPACE / ".omo" / "_knowledge",
        WORKSPACE / ".omo" / "standards",
        WORKSPACE / "protocols",
        WORKSPACE / "spaces",
        WORKSPACE / "AGENTS.md",
        WORKSPACE / "ARCHITECTURE.md",
        WORKSPACE / "README.md",
        WORKSPACE / "CLAUDE.md",
        WORKSPACE / "BRIEF.md",
        WORKSPACE / "SYSTEM-INDEX.md",
        WORKSPACE / "LAYER-INDEX.md",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument(
        "--creative-root",
        type=Path,
        default=Path(os.path.expanduser("~/Documents/@创意创作")),
        help="legacy single creative vault root (still honored when present)",
    )
    ap.add_argument(
        "--root",
        action="append",
        type=Path,
        default=None,
        help="extra root to scan (repeatable). When set, only these roots + "
        "workspace docs (unless --roots-only)",
    )
    ap.add_argument(
        "--roots-only",
        action="store_true",
        help="with --root: scan only the given roots (skip default workspace/vault set)",
    )
    ap.add_argument(
        "--prefer-new",
        action="store_true",
        help="fill --limit with paths not already present in the DB (Q4 growth mode)",
    )
    ap.add_argument("--workspace-docs-only", action="store_true")
    args = ap.parse_args(argv)

    if args.roots_only and args.root:
        roots = [Path(os.path.expanduser(str(r))) for r in args.root]
    else:
        roots = _default_workspace_roots()
        if not args.workspace_docs_only:
            if args.root:
                for r in args.root:
                    p = Path(os.path.expanduser(str(r)))
                    if p.exists():
                        roots.append(p)
            else:
                # Default vault set (creative flag still works if dir exists)
                vaults = list(DEFAULT_VAULTS)
                cr = str(args.creative_root)
                if cr not in vaults and args.creative_root.is_dir():
                    vaults.insert(0, cr)
                for v in vaults:
                    p = Path(os.path.expanduser(v))
                    if p.is_dir():
                        roots.append(p)

    indexed: set[str] = set()
    if args.prefer_new:
        indexed = _load_indexed_paths(args.db)
        print(f"prefer_new=true already_indexed={len(indexed)}", file=sys.stderr)

    files = _collect_md(
        roots,
        args.limit,
        indexed=indexed,
        prefer_new=bool(args.prefer_new),
    )
    if not files:
        print("no markdown files found (or all already indexed)", file=sys.stderr)
        # still report total if DB exists
        if args.db.is_file():
            conn = sqlite3.connect(str(args.db))
            try:
                total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            finally:
                conn.close()
            print(f"indexed=0 total_documents={total} db={args.db}")
            return 0
        return 1
    total = import_docs(args.db, files)
    return 0 if total > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
