"""AppendOnlyLog 压测 (Round 8 P1).

用法:
    cd projects/omo && .venv/bin/python -m benchmarks.append_only_log_bench
    # 或:
    .venv/bin/python -m pytest benchmarks/test_append_only_log_bench.py -v -s

度量:
  - append 吞吐量 (records/sec)
  - tail 延迟 (ms for 100K records)
  - group_by 延迟 (ms for 100K records)
  - read_all 延迟 (ms for 100K records)
  - 文件大小 (MB after 100K records)
"""
from __future__ import annotations

import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

# 把 src 加入 path
OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))

from omo.omo_io import AppendOnlyLog  # noqa: E402

N = 100_000  # 默认 100K records


def _bench_append(log: AppendOnlyLog, n: int) -> tuple[float, float]:
    """测 append 吞吐量 (records/sec, MB/sec)."""
    t0 = time.monotonic()
    for i in range(n):
        log.append({"i": i, "kind": "bench", "name": f"item_{i}"})
    elapsed = time.monotonic() - t0
    size_mb = log.path.stat().st_size / 1024 / 1024
    return n / elapsed, size_mb / elapsed


def _bench_tail(log: AppendOnlyLog, n: int = 10) -> float:
    """测 tail(n) 延迟 (ms)."""
    t0 = time.monotonic()
    records = log.tail(n)
    elapsed_ms = (time.monotonic() - t0) * 1000
    assert len(records) == n
    return elapsed_ms


def _bench_read_all(log: AppendOnlyLog, expected_n: int) -> float:
    """测 read_all 延迟 (ms). expected_n 是 append 时的 n (local), 非模块级 N."""
    t0 = time.monotonic()
    records = log.read_all()
    elapsed_ms = (time.monotonic() - t0) * 1000
    assert len(records) == expected_n
    return elapsed_ms


def _bench_group_by(log: AppendOnlyLog) -> float:
    """测 group_by(field) 延迟 (ms)."""
    t0 = time.monotonic()
    counter = log.group_by("kind")
    elapsed_ms = (time.monotonic() - t0) * 1000
    assert counter == {"bench": counter.get("bench", 0)}  # 接受任意 bench 数
    return elapsed_ms


def run_bench(n: int = N) -> dict[str, float]:
    """运行 1 轮 bench, 返回度量 dict."""
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "bench.jsonl"
        log = AppendOnlyLog(log_path)

        # 1. append n records
        append_tps, append_mbps = _bench_append(log, n)

        # 2. tail(10) — Round 7 P1 reverse-seek 优化效果
        # warm cache first
        _ = log.tail(10)
        tail_latencies = [_bench_tail(log) for _ in range(5)]
        tail_p50 = statistics.median(tail_latencies)

        # 3. read_all
        # Round 8 P1 修: 用 n (local) 而非 N (module default) 校验,
        # 否则 n=1000 时, N=100_000 会让 assert 失败.
        read_all_latencies = [_bench_read_all(log, n) for _ in range(3)]
        read_all_p50 = statistics.median(read_all_latencies)

        # 4. group_by
        group_by_latencies = [_bench_group_by(log) for _ in range(3)]
        group_by_p50 = statistics.median(group_by_latencies)

        file_size_mb = log_path.stat().st_size / 1024 / 1024

    return {
        "n_records": n,
        "file_size_mb": round(file_size_mb, 2),
        "append_records_per_sec": round(append_tps, 1),
        "append_mb_per_sec": round(append_mbps, 2),
        "tail_p50_ms": round(tail_p50, 2),
        "read_all_p50_ms": round(read_all_p50, 1),
        "group_by_p50_ms": round(group_by_p50, 1),
    }


def print_report(result: dict[str, float]) -> None:
    print("=" * 60)
    print(f"AppendOnlyLog Benchmark (Round 8 P1) — {result['n_records']:,} records")
    print("=" * 60)
    print(f"  File size:           {result['file_size_mb']:>8.2f} MB")
    print(f"  Append throughput:   {result['append_records_per_sec']:>8,.0f} records/sec")
    print(f"                       {result['append_mb_per_sec']:>8.2f} MB/sec")
    print()
    print(f"  tail(10) p50:        {result['tail_p50_ms']:>8.2f} ms  (Round 7 reverse-seek)")
    print(f"  read_all() p50:      {result['read_all_p50_ms']:>8.1f} ms")
    print(f"  group_by() p50:      {result['group_by_p50_ms']:>8.1f} ms")
    print("=" * 60)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N
    result = run_bench(n)
    print_report(result)
