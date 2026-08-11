from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import anyio
import pytest

from omlxc.storage import HealthRecord, MetricRecord, SQLiteRuntimeStore, StorageDegradedError


def _metric(request_id: str) -> MetricRecord:
    return MetricRecord(request_id, datetime(2026, 8, 11, tzinfo=UTC), 1.0, True)


@pytest.mark.asyncio
async def test_flush_cancel_accept_and_close_share_one_drain_without_loss_or_duplicates(
    tmp_path: Path,
) -> None:
    commit_entered = anyio.Event()
    release_commit = anyio.Event()

    async def before_commit() -> None:
        commit_entered.set()
        await release_commit.wait()

    database = tmp_path / "state.db"
    store = await SQLiteRuntimeStore.open(database, before_writer_commit=before_commit)
    assert store.accept_metric(_metric("req-1"))
    assert store.accept_metric(_metric("req-2"))

    cancelled_waiter = asyncio.create_task(store.flush_metrics())
    await commit_entered.wait()
    assert store.accept_metric(_metric("req-3"))
    concurrent_flush = asyncio.create_task(store.flush_metrics())
    cancelled_waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled_waiter

    close_one = asyncio.create_task(store.close())
    close_two = asyncio.create_task(store.close())
    await anyio.lowlevel.checkpoint()
    with pytest.raises(StorageDegradedError):
        store.accept_metric(_metric("too-late"))
    release_commit.set()

    assert await concurrent_flush == 3
    assert await close_one == 3
    assert await close_two == 3
    assert store.writer_task_settled

    connection = sqlite3.connect(database)
    rows = connection.execute(
        "SELECT request_id, COUNT(*) FROM request_metrics GROUP BY request_id ORDER BY request_id"
    ).fetchall()
    connection.close()
    assert rows == [("req-1", 1), ("req-2", 1), ("req-3", 1)]


@pytest.mark.asyncio
async def test_cancelled_inflight_writer_settles_before_competing_close(tmp_path: Path) -> None:
    commit_entered = anyio.Event()
    release_commit = anyio.Event()

    async def before_commit() -> None:
        commit_entered.set()
        await release_commit.wait()

    database = tmp_path / "state.db"
    store = await SQLiteRuntimeStore.open(database, before_writer_commit=before_commit)
    write = asyncio.create_task(
        store.save_health(
            HealthRecord(
                resource_kind="node",
                resource_id="node-a",
                state="healthy",
                observed_at=datetime(2026, 8, 11, tzinfo=UTC),
                observed_monotonic=10.0,
                stale=False,
            )
        )
    )
    await commit_entered.wait()
    write.cancel()
    with pytest.raises(asyncio.CancelledError):
        await write
    closing = asyncio.create_task(store.close())
    release_commit.set()
    assert await closing == 0
    assert store.writer_task_settled

    reopened = await SQLiteRuntimeStore.open(database)
    recovered = await reopened.latest_health("node", "node-a")
    assert recovered is not None
    assert recovered.state == "healthy"
    await reopened.close()
