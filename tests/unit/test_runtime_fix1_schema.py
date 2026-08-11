from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from omlxc.storage import SQLiteRuntimeStore, UnsupportedSchemaError


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["missing_table", "missing_index", "foreign_key"])
async def test_v1_schema_or_logical_damage_is_quarantined_degraded(
    tmp_path: Path,
    damage: str,
) -> None:
    database = tmp_path / f"{damage}.db"
    if damage == "missing_table":
        connection = sqlite3.connect(database)
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
        connection.close()
    else:
        valid = await SQLiteRuntimeStore.open(database)
        await valid.close()
        connection = sqlite3.connect(database)
        if damage == "missing_index":
            connection.execute("DROP INDEX health_latest_idx")
        else:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute(
                """
                INSERT INTO job_transitions
                    (job_id, from_state, to_state, progress, observed_at)
                VALUES ('missing-job', NULL, 'pending', 0, '2026-08-11T00:00:00+00:00')
                """
            )
        connection.commit()
        connection.close()

    store = await SQLiteRuntimeStore.open(
        database, quarantine_suffix_factory=lambda: "schema-damage"
    )
    assert store.degraded
    assert not database.exists()
    assert (tmp_path / f"{damage}.db.corrupt-schema-damage").exists()
    await store.close()


@pytest.mark.asyncio
async def test_higher_user_version_fails_closed_without_quarantine(tmp_path: Path) -> None:
    database = tmp_path / "future.db"
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA user_version = 99")
    connection.commit()
    connection.close()

    with pytest.raises(UnsupportedSchemaError):
        await SQLiteRuntimeStore.open(
            database, quarantine_suffix_factory=lambda: "must-not-quarantine"
        )
    assert database.exists()
    assert not (tmp_path / "future.db.corrupt-must-not-quarantine").exists()
