"""Smoke test for AppendOnlyLog benchmark — Round 8 P1.

验证 benchmark 脚本本身不破, 用 1000 records 跑小规模版, 数字格式正确.
不是性能测试 (100K records 那个在 bench 脚本本身跑).
"""
from __future__ import annotations

import sys
from pathlib import Path

# 把 src + benchmarks 加入 path
ROOT = Path(__file__).resolve().parents[1]
for p in [ROOT / "src", ROOT / "benchmarks"]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def test_bench_small_n_returns_valid_metrics():
    """1000 records 跑 bench, 数字格式与关键约束."""
    from append_only_log_bench import run_bench

    result = run_bench(n=1000)

    # 关键字段必须存在
    assert "n_records" in result
    assert "file_size_mb" in result
    assert "append_records_per_sec" in result
    assert "tail_p50_ms" in result
    assert "read_all_p50_ms" in result
    assert "group_by_p50_ms" in result

    # 数值约束
    assert result["n_records"] == 1000
    assert result["file_size_mb"] > 0
    assert result["append_records_per_sec"] > 0
    assert result["tail_p50_ms"] >= 0
    assert result["read_all_p50_ms"] >= 0
    assert result["group_by_p50_ms"] >= 0

    # tail 应比 read_all 快 (Round 7 reverse-seek 优化)
    # 1000 records 太小, 可能差异不大, 但 tail 不应比 read_all 慢 10x
    assert result["tail_p50_ms"] < result["read_all_p50_ms"] * 10
