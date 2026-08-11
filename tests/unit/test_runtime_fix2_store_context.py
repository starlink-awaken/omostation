from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import anyio
import pytest

from omlxc.storage import MetricRecord, SQLiteRuntimeStore, StorageDegradedError


@pytest.mark.asyncio
async def test_store_context_body_exception_closes_actor_and_connections(tmp_path: Path) -> None:
    store = await SQLiteRuntimeStore.open(tmp_path / "exception.db")
    try:
        with pytest.raises(RuntimeError, match="body failed"):
            async with store:
                raise RuntimeError("body failed")
        assert store.writer_task_settled
        with pytest.raises(StorageDegradedError):
            await store.latest_health("node", "node-a")
        assert await store.close() == 0
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_store_context_task_cancellation_closes_actor_without_pending_task(
    tmp_path: Path,
) -> None:
    store = await SQLiteRuntimeStore.open(tmp_path / "cancel.db")
    started = anyio.Event()

    async def owner() -> None:
        started.set()
        async with store:
            await anyio.sleep_forever()

    task = asyncio.create_task(owner(), name="store-context-owner")
    try:
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.done()
        assert store.writer_task_settled
        assert await store.close() == 0
    finally:
        if not task.done():
            task.cancel()
        await store.close()


@pytest.mark.asyncio
async def test_anyio_cancel_scope_waits_for_blocked_writer_before_context_exits(
    tmp_path: Path,
) -> None:
    commit_entered = anyio.Event()
    allow_commit = anyio.Event()

    async def before_writer_commit() -> None:
        commit_entered.set()
        await allow_commit.wait()

    store = await SQLiteRuntimeStore.open(
        tmp_path / "cancel-scope.db", before_writer_commit=before_writer_commit
    )

    async def owner() -> None:
        with anyio.CancelScope() as scope:
            async with store:
                assert store.accept_metric(
                    MetricRecord(
                        "request-cancelled",
                        datetime(2026, 8, 11, tzinfo=UTC),
                        1.0,
                        True,
                    )
                )
                scope.cancel()
                await anyio.lowlevel.checkpoint()

    async def release_writer() -> None:
        await commit_entered.wait()
        await allow_release.wait()
        allow_commit.set()

    allow_release = anyio.Event()
    owner_task = asyncio.create_task(owner(), name="store-cancel-scope-owner")
    release_task = asyncio.create_task(release_writer(), name="store-cancel-scope-release")
    try:
        await commit_entered.wait()
        await anyio.lowlevel.checkpoint()
        assert not owner_task.done(), "context exited before its writer and close task settled"
        allow_release.set()
        await release_task
        await owner_task
        assert store.writer_task_settled
        assert await store.close() == 1
        pending_storage_tasks = {
            task.get_name()
            for task in asyncio.all_tasks()
            if not task.done() and task.get_name().startswith("omlxc-")
        }
        assert pending_storage_tasks == set()
    finally:
        allow_release.set()
        allow_commit.set()
        await asyncio.gather(owner_task, release_task, return_exceptions=True)
        await asyncio.shield(store.close())


@pytest.mark.asyncio
async def test_asyncio_cancel_during_blocked_close_settles_before_propagating(
    tmp_path: Path,
) -> None:
    commit_entered = anyio.Event()
    allow_commit = anyio.Event()

    async def before_writer_commit() -> None:
        commit_entered.set()
        await allow_commit.wait()

    store = await SQLiteRuntimeStore.open(
        tmp_path / "task-cancel-during-close.db", before_writer_commit=before_writer_commit
    )

    async def owner() -> None:
        async with store:
            assert store.accept_metric(
                MetricRecord("request-task-cancel", datetime(2026, 8, 11, tzinfo=UTC), 2.0, True)
            )

    owner_task = asyncio.create_task(owner(), name="store-task-cancel-owner")
    try:
        await commit_entered.wait()
        owner_task.cancel()
        await anyio.lowlevel.checkpoint()
        assert not owner_task.done(), "task cancellation escaped before close settled"
        allow_commit.set()
        with pytest.raises(asyncio.CancelledError):
            await owner_task
        assert store.writer_task_settled
        assert await store.close() == 1
    finally:
        allow_commit.set()
        await asyncio.gather(owner_task, return_exceptions=True)
        await asyncio.shield(store.close())
