#!/usr/bin/env python3
"""Phase 1 — 性能基线采集 (T19)

采集全系统延迟基线: P50/P95/P99

运行:
  python3 tests/integration/test-perf-baseline.py
"""
import statistics
import time
from urllib.request import urlopen

ENDPOINTS = [
    ("SharedBrain Health", "http://localhost:8088/health"),
    ("Agora Web", "http://localhost:7435/"),
    ("LiteLLM Health", "http://localhost:4000/health"),
]

def measure_latency(url: str, samples: int = 20) -> dict:
    """Measure latency for an endpoint."""
    latencies = []
    errors = 0
    for _ in range(samples):
        start = time.time()
        try:
            resp = urlopen(url, timeout=10)
            resp.read()  # drain
            elapsed = (time.time() - start) * 1000  # ms
            latencies.append(elapsed)
        except Exception:
            errors += 1
    if not latencies:
        return {"error": "all requests failed", "errors": errors, "samples": samples}
    latencies.sort()
    return {
        "min_ms": round(min(latencies), 1),
        "p50_ms": round(statistics.median(latencies), 1),
        "p95_ms": round(latencies[int(len(latencies) * 0.95)], 1),
        "p99_ms": round(latencies[int(len(latencies) * 0.99)], 1),
        "max_ms": round(max(latencies), 1),
        "avg_ms": round(statistics.mean(latencies), 1),
        "errors": errors,
        "samples": samples,
    }

if __name__ == "__main__":
    print("\n═══════════════════════════════════════════")
    print("  Phase 1 — 全系统延迟基线")
    print("═══════════════════════════════════════════\n")

    results = {}
    for name, url in ENDPOINTS:
        print(f"  📡 {name} ({url})")
        result = measure_latency(url, samples=20)
        results[name] = result
        if "error" in result:
            print(f"     ❌ {result['error']}")
        else:
            print(f"     P50: {result['p50_ms']}ms | P95: {result['p95_ms']}ms | P99: {result['p99_ms']}ms")
            print(f"     min: {result['min_ms']}ms | avg: {result['avg_ms']}ms | max: {result['max_ms']}ms")
            print(f"     errors: {result['errors']}/{result['samples']}")

    print("\n  ┌──────────────────────────────────────────────────────────────┐")
    print("  │ 延迟基线 (单位: ms)  P50    P95    P99    min    max  错误率 │")
    print("  ├──────────────────────────────────────────────────────────────┤")
    for name, r in results.items():
        short = name[:20].ljust(20)
        if "error" in r:
            print(f"  │ {short}  ERROR                               │")
        else:
            print(f"  │ {short}  {r['p50_ms']:>5}  {r['p95_ms']:>5}  {r['p99_ms']:>5}  {r['min_ms']:>5}  {r['max_ms']:>5}  {r['errors']}/{r['samples']}  │")
    print("  └──────────────────────────────────────────────────────────────┘")
    print("\n  采样: 20 次请求/端点")
    print("  环境: Docker Desktop (macOS ARM64)")
