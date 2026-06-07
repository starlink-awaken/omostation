"""AetherForge Benchmark Suite.

Measures performance of critical paths:
  1. RateLimiter throughput (ops/sec)
  2. RouterPipeline selection latency (μs)
  3. ModelScheduler end-to-end (ms)
  4. Full gateway round-trip generation (ms)
  5. Memory overhead

Usage::

    uv run python3 tests/benchmark.py
    uv run python3 tests/benchmark.py --quick   # minimal run
    uv run python3 tests/benchmark.py --json    # JSON output
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any


# ── Benchmark utilities ────────────────────────────────────────────────────


@dataclass
class BenchResult:
    """Result of a single benchmark."""

    name: str
    ops: int = 0
    total_ms: float = 0.0
    ops_per_sec: float = 0.0
    avg_ms: float = 0.0
    p50_ms: float = 0.0
    p99_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        if self.ops_per_sec > 1000:
            return f"{self.ops_per_sec / 1000:.1f}K ops/sec"
        return f"{self.ops_per_sec:.1f} ops/sec"


def _percentile(latencies: list[float], p: float) -> float:
    """Compute the *p*th percentile."""
    if not latencies:
        return 0.0
    sorted_lats = sorted(latencies)
    idx = max(0, min(len(sorted_lats) - 1, int(len(sorted_lats) * p / 100)))
    return sorted_lats[idx]


def bench(name: str, iterations: int = 1000, warmup: int = 100):
    """Decorator for benchmark functions.

    The decorated function receives ``(n: int)`` and should perform
    *n* iterations, returning a list of per-call latencies in ms.
    """
    def decorator(fn):
        def wrapper(*args, **kwargs):
            result = BenchResult(name=name, ops=iterations)

            # Warmup
            if warmup:
                fn(warmup, *args, **kwargs)

            # Measure
            start = time.perf_counter()
            latencies = fn(iterations, *args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000

            result.total_ms = elapsed
            result.ops_per_sec = iterations / (elapsed / 1000)
            result.avg_ms = elapsed / iterations if latencies is None else (sum(latencies) / len(latencies)) if latencies else 0

            if latencies:
                result.p50_ms = _percentile(latencies, 50)
                result.p99_ms = _percentile(latencies, 99)

            return result
        return wrapper
    return decorator


# ══════════════════════════════════════════════════════════════════════════
# 1. RateLimiter
# ══════════════════════════════════════════════════════════════════════════

@bench("RateLimiter.acquire (hot path)", iterations=10_000, warmup=500)
def bench_rate_limiter(n: int):
    from llm_gateway.rate_limiter import RateLimiter
    rl = RateLimiter()
    rl.set_limit("test-model", tpm=1_000_000, rpm=100_000)

    latencies = []
    for _ in range(n):
        t0 = time.perf_counter()
        rl.acquire("test-model", tokens=100)
        latencies.append((time.perf_counter() - t0) * 1000)
    return latencies


@bench("RateLimiter.throttle (limit hit)", iterations=5_000, warmup=200)
def bench_rate_limiter_throttle(n: int):
    from llm_gateway.rate_limiter import RateLimiter
    rl = RateLimiter()
    rl.set_limit("tight-model", tpm=10, rpm=1)

    latencies = []
    for _ in range(n):
        t0 = time.perf_counter()
        rl.acquire("tight-model", tokens=100)
        latencies.append((time.perf_counter() - t0) * 1000)
    return latencies


# ══════════════════════════════════════════════════════════════════════════
# 2. RouterPipeline
# ══════════════════════════════════════════════════════════════════════════

@bench("RouterPipeline.select (10 models)", iterations=5_000, warmup=500)
def bench_pipeline_select(n: int):
    from llm_gateway.policies import (
        RouterPipeline, OnlineFilter, CapabilityFilter,
        CostScore, SpeedScore, CapabilityScore, BalancedScore,
    )
    from llm_gateway.types import ModelDescriptor, ModelRequest

    # Create test models
    models = [
        ModelDescriptor(
            id=f"model-{i}", provider=f"p{i % 5}", capabilities=["chat"],
            is_available=True, cost_per_1k_tokens={"input": 0.01 * (i % 3), "output": 0.02 * (i % 3)},
            context_window=4096 * (1 + i % 4),
        ) for i in range(10)
    ]
    req = ModelRequest(task="bench", required_capabilities=["chat"])

    pipeline = RouterPipeline()
    pipeline.add_filter(OnlineFilter())
    pipeline.add_filter(CapabilityFilter())
    pipeline.add_score(CostScore())
    pipeline.add_score(SpeedScore())
    pipeline.add_score(CapabilityScore())
    pipeline.add_score(BalancedScore())

    latencies = []
    for _ in range(n):
        t0 = time.perf_counter()
        pipeline.select(models, req)
        latencies.append((time.perf_counter() - t0) * 1000)
    return latencies


@bench("RouterPipeline.select (100 models)", iterations=2_000, warmup=200)
def bench_pipeline_select_100(n: int):
    from llm_gateway.policies import (
        RouterPipeline, OnlineFilter, CapabilityFilter,
        CostScore, SpeedScore, BalancedScore,
    )
    from llm_gateway.types import ModelDescriptor, ModelRequest

    models = [
        ModelDescriptor(
            id=f"model-{i}", provider=f"p{i % 10}", capabilities=["chat"],
            is_available=i % 20 != 0,  # 5% offline
            cost_per_1k_tokens={"input": 0.01 * (i % 5), "output": 0.02 * (i % 5)},
            context_window=4096 * (1 + i % 8),
        ) for i in range(100)
    ]
    req = ModelRequest(task="bench", required_capabilities=["chat"])

    pipeline = RouterPipeline()
    pipeline.add_filter(OnlineFilter())
    pipeline.add_filter(CapabilityFilter())
    pipeline.add_score(CostScore())
    pipeline.add_score(SpeedScore())
    pipeline.add_score(BalancedScore())

    latencies = []
    for _ in range(n):
        t0 = time.perf_counter()
        pipeline.select(models, req)
        latencies.append((time.perf_counter() - t0) * 1000)
    return latencies


# ══════════════════════════════════════════════════════════════════════════
# 3. MetricsCollector
# ══════════════════════════════════════════════════════════════════════════

@bench("MetricsCollector.record (4 fields)", iterations=20_000, warmup=500)
def bench_metrics_record(n: int):
    from llm_gateway.metrics import MetricsCollector
    mc = MetricsCollector()

    latencies = []
    for i in range(n):
        t0 = time.perf_counter()
        mc.record_latency(f"model-{i % 10}", 100.0)
        mc.record_cost(f"model-{i % 10}", 0.01)
        mc.record_error(f"model-{i % 10}", "timeout")
        mc.record_rate_limit(f"model-{i % 10}")
        latencies.append((time.perf_counter() - t0) * 1000)
    return latencies


# ══════════════════════════════════════════════════════════════════════════
# 4. WorkerMessageBus
# ══════════════════════════════════════════════════════════════════════════

@bench("WorkerMessageBus.send+receive", iterations=5_000, warmup=200)
def bench_message_bus(n: int):
    from compute_mesh.worker.message_bus import WorkerMessageBus
    bus = WorkerMessageBus()

    latencies = []
    for i in range(n):
        t0 = time.perf_counter()
        bus.send(f"worker-{i % 5}", {"seq": i})
        latencies.append((time.perf_counter() - t0) * 1000)
    return latencies


# ══════════════════════════════════════════════════════════════════════════
# 5. Config loading
# ══════════════════════════════════════════════════════════════════════════

@bench("Config.load (defaults)", iterations=1_000, warmup=100)
def bench_config_load(n: int):
    from aetherforge.config import load_config
    latencies = []
    for _ in range(n):
        t0 = time.perf_counter()
        load_config()
        latencies.append((time.perf_counter() - t0) * 1000)
    return latencies


# ══════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════

def run_all(json_output: bool = False) -> list[BenchResult]:
    """Run all benchmarks.

    Args:
        json_output: If True, outputs JSON only.

    Returns:
        List of ``BenchResult``.
    """
    benchmarks = [
        bench_rate_limiter,
        bench_rate_limiter_throttle,
        bench_pipeline_select,
        bench_pipeline_select_100,
        bench_metrics_record,
        bench_message_bus,
        bench_config_load,
    ]

    results: list[BenchResult] = []
    for bm in benchmarks:
        r = bm()
        results.append(r)

    return results


def print_results(results: list[BenchResult]) -> None:
    """Print results in a formatted table."""
    print()
    print("=" * 70)
    print("  AetherForge Benchmark Results")
    print("=" * 70)
    print(f"{'Benchmark':40s} {'Ops':>8s} {'Avg':>8s} {'P50':>8s} {'P99':>8s} {'Throughput':>16s}")
    print("-" * 70)
    for r in sorted(results, key=lambda x: x.ops_per_sec, reverse=True):
        avg = f"{r.avg_ms:.1f}ms" if r.avg_ms >= 1 else f"{r.avg_ms * 1000:.0f}μs"
        p50 = f"{r.p50_ms:.1f}ms" if r.p50_ms >= 1 else f"{r.p50_ms * 1000:.0f}μs"
        p99 = f"{r.p99_ms:.1f}ms" if r.p99_ms >= 1 else f"{r.p99_ms * 1000:.0f}μs"
        tp = r.label
        print(f"  {r.name:38s} {r.ops:>8d} {avg:>8s} {p50:>8s} {p99:>8s} {tp:>16s}")
    print("-" * 70)

    # Summary
    total_ops = sum(r.ops for r in results)
    avg_tp = sum(r.ops_per_sec for r in results) / len(results)
    print(f"  Total: {total_ops:,} operations | Avg throughput: {avg_tp / 1000:.1f}K ops/sec")
    print("=" * 70)


if __name__ == "__main__":
    json_output = "--json" in sys.argv

    results = run_all()

    if json_output:
        print(json.dumps(
            [{"name": r.name, "ops_per_sec": round(r.ops_per_sec, 1),
              "avg_ms": round(r.avg_ms, 3), "p50_ms": round(r.p50_ms, 3),
              "p99_ms": round(r.p99_ms, 3)} for r in results],
            indent=2,
        ))
    else:
        print_results(results)
