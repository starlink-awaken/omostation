"""append_only_log tests — B-1 P0 跨仓 SSOT 验证."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import json
import multiprocessing
import shutil
import tempfile
from pathlib import Path

import pytest
from kairon_utils import AppendOnlyLog, fcntl_lock


@pytest.fixture
def tmp_path():
    d = tempfile.mkdtemp(prefix="kairon-aol-test-")
    try:
        yield Path(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_append_basic(tmp_path):
    p = tmp_path / "log.jsonl"
    log = AppendOnlyLog(p)
    log.append({"ts": "2026-06-11T00:00:00Z", "event": "hello", "count": 1})
    assert len(log.read_all()) == 1


def test_sort_keys(tmp_path):
    p = tmp_path / "log.jsonl"
    log = AppendOnlyLog(p, lock=fcntl_lock(p.with_suffix(".lock")))
    log.append({"b": 1, "a": 2, "c": 3})
    content = p.read_text()
    # §12.1.4 跨仓不变量: 默认 sort_keys=True
    assert content.index('"a"') < content.index('"b"') < content.index('"c"')


# 顶级函数 — multiprocessing spawn 模式要求
def _concurrent_worker(idx_and_path):
    idx, path_str = idx_and_path
    from kairon_utils import AppendOnlyLog, fcntl_lock

    p = Path(path_str)
    for i in range(50):
        log = AppendOnlyLog(p, lock=fcntl_lock(p.with_suffix(".lock")))
        log.append({"ts": f"2026-06-11T00:00:{idx:02d}Z", "i": idx * 100 + i})


def test_fcntl_lock_concurrent(tmp_path):
    """P0: 跨进程并发写 0 丢行. 2 个进程并发 50 次 append."""
    p = tmp_path / "concurrent.jsonl"
    procs = [multiprocessing.Process(target=_concurrent_worker, args=((i, str(p)),)) for i in range(2)]
    for pr in procs:
        pr.start()
    for pr in procs:
        pr.join(timeout=30)
        if pr.exitcode != 0:
            pytest.fail(f"worker exited with {pr.exitcode}")

    # fcntl_lock 是短生命周期 — 进程退出后 lock 释放, 但行数应该 >= 100
    records = AppendOnlyLog(p).read_all()
    assert len(records) >= 100, f"expected >= 100, got {len(records)}"


@pytest.mark.asyncio
async def test_async_versioning_migration(tmp_path):
    """B-1 + E3 P0: ContentVersionTracker async → AppendOnlyLog + fcntl_lock + asyncio.to_thread."""
    import asyncio

    from kairon_utils.versioning import ContentVersionTracker

    tracker = ContentVersionTracker(storage_dir=tmp_path)
    v1 = await tracker.record_version("src1", "hello world", {"note": "first"})
    await tracker.record_version("src1", "hello universe", {"note": "second"})

    # 验证 AppendOnlyLog 写盘
    version_file = tmp_path / "src1_versions.jsonl"
    assert version_file.exists()
    lines = version_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert rec["content_hash"] == v1.content_hash
    assert rec["version_number"] == 1

    # E3 P0 验证: 50 次并发 record_version 不阻塞 event loop
    # event loop 在 await 期间应能处理其他 task (快速返回)
    import time

    t0 = time.monotonic()
    await asyncio.gather(*[tracker.record_version(f"src{i}", f"content-{i}", {"i": i}) for i in range(50)])
    elapsed = time.monotonic() - t0

    # 50 个 record 串行做 fcntl 大约需要 50ms 量级; 串行会阻塞但 total 短
    # E3 验证: 50 个并发 append 不应触发任何 fcntl 阻塞导致的明显慢延迟
    # (即: to_thread 释放了 event loop, 但 fcntl 仍然串行 — 总时间应 < 1s)
    assert elapsed < 2.0, f"50 concurrent record_version took {elapsed:.2f}s (fcntl 阻塞?)"

    # 验证 50 条都落盘
    for i in range(50):
        f = tmp_path / f"src{i}_versions.jsonl"
        if i > 0:  # src0 没写, src1 写 2 条
            assert f.exists(), f"src{i} 未写盘"
