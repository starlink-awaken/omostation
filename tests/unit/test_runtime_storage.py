from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest


def _storage() -> Any:
    import omlxc.storage as storage

    return storage


@pytest.mark.asyncio
async def test_schema_migrates_once_and_enforces_private_wal_pragmas(tmp_path: Path) -> None:
    database = tmp_path / "private" / "state.db"
    SQLiteRuntimeStore = _storage().SQLiteRuntimeStore
    store = await SQLiteRuntimeStore.open(database)
    assert await store.schema_version() == 1
    assert await store.pragma_state() == {
        "busy_timeout": 5000,
        "foreign_keys": 1,
        "journal_mode": "wal",
    }
    await store.close()

    reopened = await SQLiteRuntimeStore.open(database)
    assert await reopened.schema_version() == 1
    await reopened.close()
    assert os.stat(database.parent).st_mode & 0o077 == 0
    assert os.stat(database).st_mode & 0o077 == 0


@pytest.mark.asyncio
async def test_unknown_newer_schema_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    storage = _storage()
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA user_version = 99")
    connection.close()

    with pytest.raises(storage.UnsupportedSchemaError):
        await storage.SQLiteRuntimeStore.open(database)


@pytest.mark.asyncio
async def test_health_sql_is_parameterized_and_latest_snapshot_round_trips(tmp_path: Path) -> None:
    storage = _storage()
    store = await storage.SQLiteRuntimeStore.open(tmp_path / "state.db")
    suspicious_id = "node-a'; DROP TABLE health_snapshots; --"
    observed = datetime(2026, 8, 11, 9, tzinfo=UTC)
    record = storage.HealthRecord("node", suspicious_id, "healthy", observed, 12.0, False)
    await store.save_health(record)

    assert await store.latest_health("node", suspicious_id) == record
    await store.close()


@pytest.mark.asyncio
async def test_metric_batch_flush_and_idempotent_daily_retention(tmp_path: Path) -> None:
    storage = _storage()
    store = await storage.SQLiteRuntimeStore.open(tmp_path / "state.db", metric_buffer_capacity=4)
    now = datetime(2026, 8, 11, 12, tzinfo=UTC)
    old = now - timedelta(days=31)
    assert store.accept_metric(storage.MetricRecord("req-1", old, 10.0, True))
    assert store.accept_metric(storage.MetricRecord("req-2", old, 30.0, False))
    assert await store.flush_metrics() == 2

    assert await store.apply_retention(now=now, retention_days=30) == 2
    assert await store.apply_retention(now=now, retention_days=30) == 0
    aggregate = await store.daily_metric_aggregate(old.date())
    assert aggregate is not None
    assert aggregate.request_count == 2
    assert aggregate.error_count == 1
    assert aggregate.latency_sum_ms == 40.0

    assert store.accept_metric(storage.MetricRecord("req-late", old, 50.0, True))
    assert await store.flush_metrics() == 1
    assert await store.apply_retention(now=now, retention_days=30) == 1
    updated = await store.daily_metric_aggregate(old.date())
    assert updated is not None
    assert (updated.request_count, updated.error_count, updated.latency_sum_ms) == (3, 1, 90.0)
    await store.close()


@pytest.mark.asyncio
async def test_close_flushes_all_accepted_metrics_and_rejects_writes_after_close(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state.db"
    storage = _storage()
    store = await storage.SQLiteRuntimeStore.open(database, metric_buffer_capacity=1)
    assert store.accept_metric(
        storage.MetricRecord("req-1", datetime(2026, 8, 11, 12, tzinfo=UTC), 4.0, True)
    )
    assert not store.accept_metric(
        storage.MetricRecord("req-2", datetime(2026, 8, 11, 12, tzinfo=UTC), 5.0, True)
    )
    assert await store.close() == 1

    reopened = await storage.SQLiteRuntimeStore.open(database)
    assert await reopened.metric_count() == 1
    await reopened.close()
    with pytest.raises(storage.StorageDegradedError):
        store.accept_metric(
            storage.MetricRecord("req-3", datetime(2026, 8, 11, 12, tzinfo=UTC), 6.0, True)
        )
