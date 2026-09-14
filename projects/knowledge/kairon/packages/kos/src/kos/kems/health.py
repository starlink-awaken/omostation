"""Read-only KEMS SQLite health checks and verified backup/restore helpers."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from stat import S_IMODE
from urllib.parse import quote


class KemsPersistenceError(RuntimeError):
    """A KEMS database cannot be safely inspected or copied."""


@dataclass(frozen=True)
class SQLiteHealth:
    """Safe operational metadata; it never contains table rows or source content."""

    name: str
    path: str
    status: str
    integrity: str
    foreign_key_violations: int
    tables: tuple[str, ...]
    row_counts: Mapping[str, int]
    missing_tables: tuple[str, ...]
    file_mode: int | None
    private_mode: bool
    size_bytes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "path": self.path,
            "status": self.status,
            "integrity": self.integrity,
            "foreign_key_violations": self.foreign_key_violations,
            "tables": list(self.tables),
            "row_counts": dict(self.row_counts),
            "missing_tables": list(self.missing_tables),
            "file_mode": None if self.file_mode is None else oct(self.file_mode),
            "private_mode": self.private_mode,
            "size_bytes": self.size_bytes,
        }


def _read_only_uri(path: Path) -> str:
    return f"file:{quote(path.as_posix(), safe='/')}?mode=ro"


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def inspect_sqlite_database(name: str, path: str | Path, *, expected_tables: tuple[str, ...] = ()) -> SQLiteHealth:
    """Inspect a SQLite file without creating it or reading user rows."""
    if not name.strip():
        raise ValueError("database name is required")
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        return SQLiteHealth(
            name=name,
            path=str(resolved),
            status="missing",
            integrity="unavailable",
            foreign_key_violations=0,
            tables=(),
            row_counts={},
            missing_tables=tuple(expected_tables),
            file_mode=None,
            private_mode=False,
            size_bytes=0,
        )
    if not resolved.is_file():
        raise KemsPersistenceError(f"database path is not a file: {resolved}")

    stat = resolved.stat()
    file_mode = S_IMODE(stat.st_mode)
    private_mode = (file_mode & 0o077) == 0
    try:
        with sqlite3.connect(_read_only_uri(resolved), uri=True) as connection:
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            tables = tuple(
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            )
            row_counts = {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table)}").fetchone()[0])
                for table in tables
            }
    except (OSError, sqlite3.DatabaseError) as exc:
        raise KemsPersistenceError(f"unable to inspect SQLite database: {resolved}") from exc

    missing_tables = tuple(table for table in expected_tables if table not in tables)
    status = "healthy"
    if integrity != "ok" or foreign_keys or missing_tables or not private_mode:
        status = "degraded"
    return SQLiteHealth(
        name=name,
        path=str(resolved),
        status=status,
        integrity=integrity,
        foreign_key_violations=len(foreign_keys),
        tables=tables,
        row_counts=row_counts,
        missing_tables=missing_tables,
        file_mode=file_mode,
        private_mode=private_mode,
        size_bytes=stat.st_size,
    )


def inspect_databases(databases: Mapping[str, str | Path]) -> dict[str, object]:
    """Return an aggregate health document suitable for an operator endpoint."""
    if not databases:
        raise ValueError("at least one database is required")
    reports = [inspect_sqlite_database(name, path) for name, path in sorted(databases.items())]
    return {
        "status": "healthy" if all(report.status == "healthy" for report in reports) else "degraded",
        "databases": [report.to_dict() for report in reports],
    }


def backup_sqlite_database(source: str | Path, destination: str | Path, *, force: bool = False) -> SQLiteHealth:
    """Create and verify a private atomic SQLite backup."""
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    source_health = inspect_sqlite_database("source", source_path)
    if source_health.status != "healthy":
        raise KemsPersistenceError(f"source database is not healthy: {source_path}")
    if destination_path.exists() and not force:
        raise KemsPersistenceError(f"backup already exists; pass force=True to replace: {destination_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination_path.with_name(f".{destination_path.name}.tmp")
    try:
        with sqlite3.connect(_read_only_uri(source_path), uri=True) as source_connection:
            with sqlite3.connect(temporary) as destination_connection:
                source_connection.backup(destination_connection)
                destination_connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        temporary.chmod(0o600)
        os.replace(temporary, destination_path)
        destination_path.chmod(0o600)
        backup_health = inspect_sqlite_database("backup", destination_path)
        if backup_health.status != "healthy":
            raise KemsPersistenceError(f"backup verification failed: {destination_path}")
        return backup_health
    except (OSError, sqlite3.DatabaseError) as exc:
        raise KemsPersistenceError(f"unable to create SQLite backup: {destination_path}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()


def restore_sqlite_database(backup: str | Path, destination: str | Path, *, force: bool = False) -> SQLiteHealth:
    """Restore a backup through the same verified atomic path used for backups."""
    return backup_sqlite_database(backup, destination, force=force)
