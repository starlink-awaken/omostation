"""L0 性能精确测量工具 — 独立运行，记录历史数据。

用法:
    uv run python tools/benchmark_l0.py          # 运行全部 benchmark
    uv run python tools/benchmark_l0.py --json   # JSON 输出
    uv run python tools/benchmark_l0.py --compare # 对比历史数据
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def bench_state_sync(iterations: int = 1000) -> dict:
    """状态同步性能"""
    from ecos.l0.governance import StateSyncService, SyncStrategy

    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        a = StateSyncService("a", SyncStrategy.EVENTUAL)
        a.set("k", "v")
        snap = a.generate_snapshot()
        b = StateSyncService("b", SyncStrategy.EVENTUAL)
        b.sync_from_snapshot(snap)
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    return {
        "name": "state_sync",
        "iterations": iterations,
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "p95_ms": sorted(times)[int(0.95 * len(times))],
        "p99_ms": sorted(times)[int(0.99 * len(times))],
        "min_ms": min(times),
        "max_ms": max(times),
        "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
    }


def bench_pagerank(iterations: int = 100) -> dict:
    """PageRank 性能"""
    from ecos.l0.governance import KnowledgeGraphBuilder

    kg = KnowledgeGraphBuilder()
    for i in range(100):
        kg.add_node(f"n{i}")
    for i in range(99):
        kg.add_edge(f"n{i}", f"n{i + 1}", "link")

    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        kg.pagerank(iterations=10)
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    return {
        "name": "pagerank",
        "iterations": iterations,
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "p95_ms": sorted(times)[int(0.95 * len(times))],
        "p99_ms": sorted(times)[int(0.99 * len(times))],
        "min_ms": min(times),
        "max_ms": max(times),
        "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
    }


def bench_decision(iterations: int = 1000) -> dict:
    """决策性能"""
    from ecos.l0.governance import CollectiveDecision, DecisionMethod

    times = []
    for _ in range(iterations):
        cd = CollectiveDecision()
        cd.create_proposal("p1", "test", ["A", "B", "C"], DecisionMethod.MAJORITY_VOTE)
        for i in range(50):
            cd.vote("p1", f"a{i}", "A" if i < 30 else "B")

        start = time.perf_counter()
        cd.decide("p1")
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    return {
        "name": "decision",
        "iterations": iterations,
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "p95_ms": sorted(times)[int(0.95 * len(times))],
        "p99_ms": sorted(times)[int(0.99 * len(times))],
        "min_ms": min(times),
        "max_ms": max(times),
        "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
    }


BENCHMARKS = [bench_state_sync, bench_pagerank, bench_decision]


def main():
    import argparse

    parser = argparse.ArgumentParser(description="L0 性能基准测量")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--compare", action="store_true", help="对比历史数据")
    parser.add_argument("--save", action="store_true", help="保存到历史记录")
    args = parser.parse_args()

    results = [bench() for bench in BENCHMARKS]

    if args.json:
        print(json.dumps(results, indent=2,ensure_ascii=False))
    else:
        for r in results:
            print(f"\n{'=' * 50}")
            print(f"  {r['name']} ({r['iterations']} iterations)")
            print(f"{'=' * 50}")
            print(f"  mean:   {r['mean_ms']:.3f} ms")
            print(f"  median: {r['median_ms']:.3f} ms")
            print(f"  p95:    {r['p95_ms']:.3f} ms")
            print(f"  p99:    {r['p99_ms']:.3f} ms")
            print(f"  min:    {r['min_ms']:.3f} ms")
            print(f"  max:    {r['max_ms']:.3f} ms")
            print(f"  stdev:  {r['stdev_ms']:.3f} ms")

    if args.save:
        history_file = Path(__file__).parent / "benchmark_history.jsonl"
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "results": results,
        }
        with open(history_file, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"\nSaved to {history_file}")

    if args.compare:
        history_file = Path(__file__).parent / "benchmark_history.jsonl"
        if history_file.exists():
            with open(history_file) as f:
                lines = f.readlines()
            if len(lines) >= 2:
                prev = json.loads(lines[-2])["results"]
                curr = results
                print(f"\n{'=' * 50}")
                print(" comparison with previous run")
                print(f"{'=' * 50}")
                for p, c in zip(prev, curr):
                    delta = c["mean_ms"] - p["mean_ms"]
                    sign = "+" if delta > 0 else ""
                    print(f"  {c['name']}: {sign}{delta:.3f} ms ({p['mean_ms']:.3f} → {c['mean_ms']:.3f})")
            else:
                print("\nNo previous data to compare")
        else:
            print("\nNo history file found")


if __name__ == "__main__":
    main()
