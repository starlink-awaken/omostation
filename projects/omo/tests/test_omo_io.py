"""Tests for omo.omo_io — AppendOnlyLog + read_jsonl.

Covers:
- AppendOnlyLog: append / read_all / clear
- read_jsonl: 容错读 (JSON 错行保留为 raw)
- 锁: 注入自定义锁 (用于跨进程 fcntl 升级)
- 并发: 4 线程各 10 次 append, 全数到达
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from threading import Thread

# 把 src 加入 path (与 omo 现有 tests 同)
OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))

from omo.omo_io import (  # noqa: E402
    AppendOnlyLog,
    read_jsonl,
    write_text_atomic,
    write_yaml_atomic,
)


# ── read_jsonl ────────────────────────────────────────────


class TestReadJsonl:
    def test_nonexistent_returns_empty(self, tmp_path):
        assert read_jsonl(tmp_path / "nope.jsonl") == []

    def test_empty_file_returns_empty(self, tmp_path):
        p = tmp_path / "empty.jsonl"
        p.write_text("", encoding="utf-8")
        assert read_jsonl(p) == []

    def test_reads_valid_records(self, tmp_path):
        p = tmp_path / "test.jsonl"
        p.write_text('{"a": 1}\n{"b": 2}\n', encoding="utf-8")
        assert read_jsonl(p) == [{"a": 1}, {"b": 2}]

    def test_tolerates_malformed_lines_as_raw(self, tmp_path):
        p = tmp_path / "test.jsonl"
        p.write_text(
            '{"a": 1}\n'
            'INVALID JSON LINE\n'
            '{"b": 2}\n'
            '{broken json too\n',
            encoding="utf-8",
        )
        records = read_jsonl(p)
        assert records[0] == {"a": 1}
        assert "raw" in records[1] and "INVALID" in records[1]["raw"]
        assert records[2] == {"b": 2}
        assert "raw" in records[3]

    def test_skips_empty_lines(self, tmp_path):
        p = tmp_path / "test.jsonl"
        p.write_text('\n{"a": 1}\n\n{"b": 2}\n\n', encoding="utf-8")
        assert read_jsonl(p) == [{"a": 1}, {"b": 2}]


# ── AppendOnlyLog.append ──────────────────────────────────


class TestAppendOnlyLogAppend:
    def test_creates_file_and_parent_dir(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "subdir" / "test.jsonl")
        log.append({"k": "v"})
        records = read_jsonl(tmp_path / "subdir" / "test.jsonl")
        assert records == [{"k": "v"}]

    def test_append_multiple_lines(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        for i in range(5):
            log.append({"i": i})
        records = log.read_all()
        assert len(records) == 5
        assert [r["i"] for r in records] == [0, 1, 2, 3, 4]

    def test_append_returns_record(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        rec = log.append({"x": 1})
        assert rec == {"x": 1}

    def test_append_unicode(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        log.append({"name": "中文", "emoji": "🎉"})
        assert log.read_all() == [{"name": "中文", "emoji": "🎉"}]

    def test_uses_custom_lock(self, tmp_path):
        """验证: AppendOnlyLog 接受并使用注入的锁 (为未来 fcntl 升级留口子)."""
        custom_lock = threading.Lock()
        log = AppendOnlyLog(tmp_path / "test.jsonl", lock=custom_lock)
        assert log._lock is custom_lock
        log.append({"a": 1})
        assert log.read_all() == [{"a": 1}]


# ── AppendOnlyLog.read_all ────────────────────────────────


class TestAppendOnlyLogRead:
    def test_empty_log(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        assert log.read_all() == []

    def test_roundtrip(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        for i in range(3):
            log.append({"i": i, "name": f"item-{i}"})
        records = log.read_all()
        assert len(records) == 3
        assert records[2] == {"i": 2, "name": "item-2"}


# ── AppendOnlyLog.clear ───────────────────────────────────


class TestAppendOnlyLogClear:
    def test_clear_returns_count(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        for i in range(3):
            log.append({"i": i})
        n = log.clear()
        assert n == 3

    def test_clear_empties_file_but_keeps_it(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        log.append({"a": 1})
        log.clear()
        assert log.path.exists()
        assert log.read_all() == []

    def test_clear_nonexistent_returns_zero(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "nope.jsonl")
        assert log.clear() == 0

    def test_can_append_after_clear(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        log.append({"a": 1})
        log.clear()
        log.append({"b": 2})
        assert log.read_all() == [{"b": 2}]


# ── 并发安全 ─────────────────────────────────────────────


class TestConcurrency:
    def test_concurrent_appends_no_loss(self, tmp_path):
        """4 线程各 10 次 append → 40 条全数到达 (默认 lock thread-safe)."""
        log = AppendOnlyLog(tmp_path / "test.jsonl")

        def worker(worker_id: int) -> None:
            for j in range(10):
                log.append({"worker": worker_id, "j": j})

        threads = [Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        records = log.read_all()
        assert len(records) == 40
        # 验证每行 JSON 完整 (无半行)
        for r in records:
            assert "worker" in r and "j" in r


# ── 与现有 helpers 共存 (regression) ──────────────────────


class TestExistingHelpers:
    def test_write_text_atomic_still_works(self, tmp_path):
        p = tmp_path / "atomic.txt"
        write_text_atomic(p, "hello\n")
        assert p.read_text(encoding="utf-8") == "hello\n"

    def test_write_yaml_atomic_still_works(self, tmp_path):
        p = tmp_path / "atomic.yaml"
        write_yaml_atomic(p, {"key": "value", "中文": "测试"})
        assert p.read_text(encoding="utf-8").startswith("key:")
