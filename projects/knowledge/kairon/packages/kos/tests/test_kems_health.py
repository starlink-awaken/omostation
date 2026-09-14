from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest
from kos.kems import (
    KemsPersistenceError,
    backup_sqlite_database,
    inspect_databases,
    inspect_sqlite_database,
    restore_sqlite_database,
)


def create_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE parent (id INTEGER PRIMARY KEY);
            CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id));
            INSERT INTO parent VALUES (1);
            INSERT INTO child VALUES (1, 1);
            """
        )
    path.chmod(0o600)


def test_health_is_read_only_and_redacted(tmp_path: Path) -> None:
    database = tmp_path / "kems.sqlite"
    create_database(database)

    report = inspect_sqlite_database("kems", database, expected_tables=("parent", "child"))

    assert report.status == "healthy"
    assert report.private_mode is True
    assert report.row_counts == {"child": 1, "parent": 1}
    assert "parent_id" not in json.dumps(report.to_dict())
    assert database.exists()


def test_missing_database_is_explicit_and_aggregate_is_degraded(tmp_path: Path) -> None:
    report = inspect_databases({"missing": tmp_path / "missing.sqlite"})

    assert report["status"] == "degraded"
    assert report["databases"][0]["status"] == "missing"  # type: ignore[index]


def test_backup_and_restore_are_atomic_private_and_verified(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite"
    backup = tmp_path / "backup.sqlite"
    restored = tmp_path / "restored.sqlite"
    create_database(source)

    assert backup_sqlite_database(source, backup).status == "healthy"
    assert backup.stat().st_mode & 0o077 == 0
    with pytest.raises(KemsPersistenceError, match="already exists"):
        backup_sqlite_database(source, backup)
    assert restore_sqlite_database(backup, restored).row_counts == {"child": 1, "parent": 1}
    assert restored.stat().st_mode & 0o077 == 0

    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT COUNT(*) FROM child").fetchone()[0] == 1


def test_world_readable_database_is_degraded(tmp_path: Path) -> None:
    database = tmp_path / "world-readable.sqlite"
    create_database(database)
    os.chmod(database, 0o644)

    report = inspect_sqlite_database("kems", database)

    assert report.status == "degraded"
    assert report.private_mode is False
