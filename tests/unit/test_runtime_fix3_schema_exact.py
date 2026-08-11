from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from omlxc.storage import SQLiteRuntimeStore


def _damage_schema(database: Path, damage: str) -> None:
    connection = sqlite3.connect(database)
    if damage == "additive-check":
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'health_snapshots'"
        ).fetchone()
        assert row is not None
        original = str(row[0])
        changed = original.replace(
            "stale INTEGER NOT NULL CHECK(stale IN (0, 1))",
            "stale INTEGER NOT NULL CHECK(stale IN (0, 1)) CHECK(stale >= 0)",
        )
        version = int(connection.execute("PRAGMA schema_version").fetchone()[0])
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute(
            "UPDATE sqlite_master SET sql = ? WHERE type = 'table' AND name = ?",
            (changed, "health_snapshots"),
        )
        connection.execute(f"PRAGMA schema_version = {version + 1}")
        connection.execute("PRAGMA writable_schema = OFF")
    elif damage == "extra-trigger":
        connection.execute(
            """
            CREATE TRIGGER unexpected_health_trigger AFTER INSERT ON health_snapshots
            BEGIN SELECT 1; END
            """
        )
    elif damage == "extra-index":
        connection.execute("CREATE INDEX unexpected_route_idx ON route_audits(request_id)")
    elif damage == "extra-unique-index":
        connection.execute(
            "CREATE UNIQUE INDEX unexpected_route_unique ON route_audits(config_revision)"
        )
    elif damage == "extra-view":
        connection.execute(
            "CREATE VIEW unexpected_health_view AS SELECT resource_id FROM health_snapshots"
        )
    else:
        raise AssertionError(f"unknown test damage: {damage}")
    connection.commit()
    connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "damage",
    [
        "additive-check",
        "extra-trigger",
        "extra-index",
        "extra-unique-index",
        "extra-view",
    ],
)
async def test_v1_schema_requires_exact_definitions_and_registered_objects_only(
    tmp_path: Path, damage: str
) -> None:
    database = tmp_path / f"{damage}.db"
    created = await SQLiteRuntimeStore.open(database)
    await created.close()
    _damage_schema(database, damage)

    store = await SQLiteRuntimeStore.open(
        database, quarantine_suffix_factory=lambda: "exact-schema"
    )
    try:
        assert store.degraded
        assert not database.exists()
        assert (tmp_path / f"{damage}.db.corrupt-exact-schema").exists()
    finally:
        await store.close()
