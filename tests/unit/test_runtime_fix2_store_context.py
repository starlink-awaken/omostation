from __future__ import annotations

import asyncio
from pathlib import Path

import anyio
import pytest

from omlxc.storage import SQLiteRuntimeStore, StorageDegradedError


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
