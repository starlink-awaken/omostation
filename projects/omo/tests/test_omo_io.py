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
    fcntl_lock,
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


# ── AppendOnlyLog.group_by (Round 7 P0) ──────────────────────


class TestGroupBy:
    def test_group_by_counts_occurrences(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        for action in ["a", "b", "a", "c", "b", "a"]:
            log.append({"action": action})
        result = log.group_by("action")
        assert result == {"a": 3, "b": 2, "c": 1}

    def test_group_by_missing_field_groups_as_missing(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        log.append({"a": 1})
        log.append({"b": 2})
        result = log.group_by("nope")
        assert result == {"<missing>": 2}

    def test_group_by_normalizes_non_str_values(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        log.append({"n": 1})
        log.append({"n": 2})
        log.append({"n": True})
        result = log.group_by("n")
        # str(1)="1", str(2)="2", str(True)="True"
        assert result == {"1": 1, "2": 1, "True": 1}

    def test_group_by_empty_log(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        assert log.group_by("anything") == {}

    def test_group_by_with_explicit_path(self, tmp_path):
        """Round 7 P0: group_by 接受 path 参数, 适配测试场景."""
        log = AppendOnlyLog(tmp_path / "default.jsonl")
        log.append({"x": 1})
        # 显式传 path, 应该读该 path 而非 self.path
        result = log.group_by("x", path=tmp_path / "default.jsonl")
        assert result == {"1": 1}


# ── AppendOnlyLog.rotate (Round 8 P0) ──────────────────────────


class TestRotate:
    def test_rotate_below_threshold_does_nothing(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        log.append({"a": 1})
        result = log.rotate(max_bytes=10_000)
        assert result is False
        # 文件不变
        assert log.path.exists()
        assert len(log.read_all()) == 1

    def test_rotate_above_threshold_creates_backup(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        for i in range(100):
            log.append({"i": i})
        result = log.rotate(max_bytes=100)  # 当前文件 > 100B
        assert result is True
        # 当前文件不存在 (被 rename)
        assert not log.path.exists()
        # backup 存在
        backup = tmp_path / "test.jsonl.1"
        assert backup.exists()
        # backup 含全部 100 records (从 .1 读, 不是从原 path 读)
        backup_records = AppendOnlyLog(backup).read_all()
        assert len(backup_records) == 100
        assert backup_records[0] == {"i": 0}
        assert backup_records[99] == {"i": 99}

    def test_rotate_overwrites_previous_backup(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        # 第 1 次 rotate
        for i in range(50):
            log.append({"first": i})
        log.rotate(max_bytes=100)
        # 第 2 次 rotate — 新数据写新位置, 旧 backup 被覆盖
        log2 = AppendOnlyLog(tmp_path / "test.jsonl")
        for i in range(50):
            log2.append({"second": i})
        result = log2.rotate(max_bytes=100)
        assert result is True
        # backup 现在含 "second" records
        backup_records = AppendOnlyLog(tmp_path / "test.jsonl.1").read_all()
        assert all("second" in r for r in backup_records)

    def test_rotate_nonexistent_returns_false(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "nope.jsonl")
        result = log.rotate(max_bytes=1)
        assert result is False

    def test_rotate_zero_max_bytes_does_nothing(self, tmp_path):
        """Round 8 P0 锁: max_bytes=0 应永远不 rotate (防 0 字节 = 0 触发 = 死循环)."""
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        for i in range(100):
            log.append({"i": i})
        result = log.rotate(max_bytes=0)
        assert result is False
        assert log.path.exists()
        assert len(log.read_all()) == 100

    def test_rotate_negative_max_bytes_does_nothing(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        log.append({"a": 1})
        result = log.rotate(max_bytes=-1)
        assert result is False
        assert log.path.exists()


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


# ── AppendOnlyLog.tail ──────────────────────────────────────


class TestTail:
    def test_tail_n_returns_last_n(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        for i in range(10):
            log.append({"i": i})
        assert log.tail(3) == [{"i": 7}, {"i": 8}, {"i": 9}]

    def test_tail_zero_returns_empty(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        log.append({"a": 1})
        assert log.tail(0) == []

    def test_tail_negative_returns_empty(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        log.append({"a": 1})
        assert log.tail(-1) == []

    def test_tail_more_than_total_returns_all(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        for i in range(3):
            log.append({"i": i})
        assert log.tail(10) == [{"i": 0}, {"i": 1}, {"i": 2}]

    def test_tail_empty_log(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        assert log.tail(5) == []

    # ── Round 7 P1: reverse-seek 性能优化 ──

    def test_tail_reverse_seek_correctness_large_file(self, tmp_path):
        """10000 records, tail(10) 应返回 9990-9999, 与 read_all()[-10:] 一致."""
        log = AppendOnlyLog(tmp_path / "big.jsonl")
        for i in range(10000):
            log.append({"i": i})
        # 与 read_all 对比
        expected = log.read_all()[-10:]
        result = log.tail(10)
        assert result == expected
        assert [r["i"] for r in result] == list(range(9990, 10000))

    def test_tail_reverse_seek_chunk_size_1(self, tmp_path):
        """chunk_size=1 (极端): 应仍能正确解析, 走多次小读."""
        log = AppendOnlyLog(tmp_path / "tiny.jsonl")
        for i in range(100):
            log.append({"i": i})
        result = log.tail(5, chunk_size=1)
        assert [r["i"] for r in result] == [95, 96, 97, 98, 99]

    def test_tail_reverse_seek_unicode(self, tmp_path):
        """Unicode 内容跨 chunk 边界应不丢."""
        log = AppendOnlyLog(tmp_path / "unicode.jsonl")
        for i in range(100):
            log.append({"i": i, "name": f"中文_{i}_emoji_{'🎉' * (i % 5)}"})
        result = log.tail(3, chunk_size=128)  # 故意小 chunk
        assert len(result) == 3
        assert all("name" in r for r in result)
        # 验证 unicode 完整
        assert result[0]["name"].startswith("中文_97")
        assert "🎉" in result[0]["name"]


# ── AppendOnlyLog.since ────────────────────────────────────


class TestSince:
    def test_since_filters_by_default_ts_field(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        for ts in ["2026-06-09T00:00:00Z", "2026-06-09T01:00:00Z", "2026-06-09T02:00:00Z"]:
            log.append({"ts": ts, "value": "x"})
        result = log.since("2026-06-09T01:00:00Z")
        assert len(result) == 2
        assert result[0]["ts"] == "2026-06-09T01:00:00Z"
        assert result[1]["ts"] == "2026-06-09T02:00:00Z"

    def test_since_with_explicit_field(self, tmp_path):
        """omo_bos_metrics 用 'recorded_at' 字段, 显式传 field 即可."""
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        for ts in ["2026-06-09T00:00:00Z", "2026-06-09T01:00:00Z"]:
            log.append({"recorded_at": ts, "uri": "x"})
        result = log.since("2026-06-09T01:00:00Z", field="recorded_at")
        assert len(result) == 1
        assert result[0]["recorded_at"] == "2026-06-09T01:00:00Z"

    def test_since_inclusive_equal(self, tmp_path):
        """since(ts) 应包含 ts 自身 (>= 不是 >)."""
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        log.append({"ts": "2026-06-09T01:00:00Z"})
        log.append({"ts": "2026-06-09T00:59:59Z"})
        result = log.since("2026-06-09T01:00:00Z")
        assert len(result) == 1
        assert result[0]["ts"] == "2026-06-09T01:00:00Z"

    def test_since_no_matches_returns_empty(self, tmp_path):
        log = AppendOnlyLog(tmp_path / "test.jsonl")
        log.append({"ts": "2026-06-09T00:00:00Z"})
        assert log.since("2030-01-01T00:00:00Z") == []


# ── fcntl_lock (跨进程) ─────────────────────────────────────


class TestFcntlLock:
    def test_lock_creates_sidecar_file(self, tmp_path):
        """fcntl_lock 应创建 .lock sidecar 文件."""
        lock_path = tmp_path / "test.lock"
        with fcntl_lock(lock_path):
            assert lock_path.exists()

    def test_lock_creates_parent_dir(self, tmp_path):
        """fcntl_lock 应创建父目录 (AppendOnlyLog 不会自动创 .lock 父目录)."""
        lock_path = tmp_path / "subdir" / "nested" / "test.lock"
        with fcntl_lock(lock_path):
            assert lock_path.exists()

    def test_lock_is_reentrant_after_release(self, tmp_path):
        """同一线程 2 次获取 (嵌套) 应该不卡死."""
        lock_path = tmp_path / "test.lock"
        with fcntl_lock(lock_path):
            with fcntl_lock(lock_path):
                pass  # 嵌套 OK, 内层 flock 是 advisory lock 同一线程会立即返回

    def test_fcntl_lock_with_append_only_log_across_threads(self, tmp_path):
        """验证 fcntl_lock 注入 AppendOnlyLog 后, 4 线程 100 次无丢失."""
        log_path = tmp_path / "test.jsonl"
        lock_path = tmp_path / "test.lock"
        log = AppendOnlyLog(log_path, lock=fcntl_lock(lock_path))

        def worker(wid: int) -> None:
            for j in range(100):
                log.append({"worker": wid, "j": j})

        threads = [Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        records = log.read_all()
        assert len(records) == 400, f"expected 400 records, got {len(records)}"
        # 验证每行 JSON 完整
        for r in records:
            assert "worker" in r and "j" in r
