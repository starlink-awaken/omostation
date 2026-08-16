"""
Unit tests for BenchmarkRunner and SQLite benchmark persistence.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from omlxc.dataplane.benchmark import BenchmarkRunner
from omlxc.domain.protocols import StreamEvent, StreamEventKind, StreamPhase
from omlxc.storage.database import SQLiteRuntimeStore
from omlxc.storage.models import BenchmarkRunRecord


async def dummy_stream(req) -> AsyncIterator[StreamEvent]:
    await asyncio.sleep(0.01)
    yield StreamEvent(
        kind=StreamEventKind.CONTENT,
        request_id=req.request_id,
        content="Hello",
        emitted_content=True,
        phase=StreamPhase.AFTER_CONTENT,
    )
    await asyncio.sleep(0.01)
    yield StreamEvent(
        kind=StreamEventKind.CONTENT,
        request_id=req.request_id,
        content=" world",
        emitted_content=True,
        phase=StreamPhase.AFTER_CONTENT,
    )
    await asyncio.sleep(0.01)
    yield StreamEvent(
        kind=StreamEventKind.CONTENT,
        request_id=req.request_id,
        content="!",
        emitted_content=True,
        phase=StreamPhase.AFTER_CONTENT,
    )


@pytest.mark.asyncio
async def test_benchmark_runner_metrics() -> None:
    runner = BenchmarkRunner()
    record = await runner.benchmark_chat(
        model_id="qwen-3.8-27b",
        placement_id="p-mbp-qwen",
        node_id="mbp-m5-max-128g",
        adapter_stream_func=dummy_stream,
    )
    assert record.model_id == "qwen-3.8-27b"
    assert record.placement_id == "p-mbp-qwen"
    assert record.ttft_ms > 0
    assert record.tps > 0


@pytest.mark.asyncio
async def test_sqlite_benchmark_persistence(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    store = await SQLiteRuntimeStore.open(db_path)

    rec1 = BenchmarkRunRecord(
        run_id="run-1",
        model_id="qwen-3.8-27b",
        placement_id="p-mbp-qwen",
        node_id="mbp-m5-max-128g",
        cold_load_ms=120.5,
        warm_load_ms=45.2,
        ttft_ms=35.0,
        tps=48.5,
        vram_used_mb=18432,
        tested_at=datetime.now(UTC),
    )
    await store.record_benchmark_run(rec1)

    records = await store.list_benchmark_runs(model_id="qwen-3.8-27b")
    assert len(records) == 1
    assert records[0].run_id == "run-1"
    assert records[0].tps == 48.5
    assert records[0].vram_used_mb == 18432

    await store.close()
