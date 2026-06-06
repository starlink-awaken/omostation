"""Benchmark utility functions -- migrated from agentmesh engine/benchmarks/utils.ts."""

from __future__ import annotations

import math
import os
import platform
import time
import uuid as _uuid
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class StatsMetrics:
    min: float = 0.0
    max: float = 0.0
    avg: float = 0.0
    median: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    samples: int = 0
    stdDev: float = 0.0  # noqa: N815


@dataclass
class EnvironmentInfo:
    node_version: str = ""
    platform_str: str = ""
    arch: str = ""
    cpu_cores: int = 4
    total_memory_mb: int = 0
    timestamp: str = ""


@dataclass
class BenchmarkReport:
    report_id: str = ""
    environment: EnvironmentInfo = field(default_factory=EnvironmentInfo)
    agent_execution: list[dict[str, Any]] = field(default_factory=list)
    message_bus: list[dict[str, Any]] = field(default_factory=list)
    checkpoint: list[dict[str, Any]] = field(default_factory=list)
    state_machine: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=lambda: {
        "totalTests": 0,
        "passedTests": 0,
        "failedTests": 0,
        "totalDurationMs": 0.0,
    })


# ---------------------------------------------------------------------------
# Time measurement
# ---------------------------------------------------------------------------

def measure_time(fn) -> dict[str, Any]:
    """Measure synchronous function execution time."""
    start = time.perf_counter()
    result = fn()
    duration_ms = (time.perf_counter() - start) * 1000
    return {"result": result, "duration_ms": duration_ms}


async def measure_time_async(fn) -> dict[str, Any]:
    """Measure async function execution time."""
    start = time.perf_counter()
    result = await fn()
    duration_ms = (time.perf_counter() - start) * 1000
    return {"result": result, "duration_ms": duration_ms}


def collect_samples(fn, samples: int) -> dict[str, Any]:
    """Execute function multiple times and collect duration samples."""
    results: list[Any] = []
    durations: list[float] = []

    # Warmup (5 or 10% of samples, whichever is smaller)
    warmup = min(5, max(1, samples // 10))
    for _ in range(warmup):
        fn()

    for _ in range(samples):
        m = measure_time(fn)
        results.append(m["result"])
        durations.append(m["duration_ms"])

    return {"results": results, "durations_ms": durations}


async def collect_samples_async(fn, samples: int) -> dict[str, Any]:
    """Execute async function multiple times and collect duration samples."""
    results: list[Any] = []
    durations: list[float] = []

    warmup = min(5, max(1, samples // 10))
    for _ in range(warmup):
        await fn()

    for _ in range(samples):
        m = await measure_time_async(fn)
        results.append(m["result"])
        durations.append(m["duration_ms"])

    return {"results": results, "durations_ms": durations}


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def calculate_stats(values: list[float]) -> StatsMetrics:
    if not values:
        return StatsMetrics()

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    min_v = sorted_vals[0]
    max_v = sorted_vals[-1]
    avg = sum(sorted_vals) / n
    median = _percentile(sorted_vals, 50)
    p95 = _percentile(sorted_vals, 95)
    p99 = _percentile(sorted_vals, 99)
    variance = sum((v - avg) ** 2 for v in sorted_vals) / n
    std_dev = math.sqrt(variance)

    return StatsMetrics(
        min=min_v,
        max=max_v,
        avg=avg,
        median=median,
        p95=p95,
        p99=p99,
        samples=n,
        stdDev=std_dev,
    )


def _percentile(sorted_vals: list[float], p: float) -> float:
    idx = (p / 100.0) * (len(sorted_vals) - 1)
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    weight = idx - lower
    if upper >= len(sorted_vals):
        return sorted_vals[-1]
    return sorted_vals[lower] * (1 - weight) + sorted_vals[upper] * weight


# ---------------------------------------------------------------------------
# Environment info
# ---------------------------------------------------------------------------

def get_environment_info() -> EnvironmentInfo:
    try:
        import psutil
        mem = psutil.virtual_memory()
        total_mb = mem.total // (1024 * 1024)
        cpu_cores = psutil.cpu_count(logical=True) or 4
    except ImportError:
        total_mb = 0
        cpu_cores = _guess_cpu_cores()

    return EnvironmentInfo(
        node_version="N/A",
        platform_str=platform.system().lower(),
        arch=platform.machine(),
        cpu_cores=cpu_cores,
        total_memory_mb=total_mb,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


def _guess_cpu_cores() -> int:
    try:
        return len(os.sched_getaffinity(0))  # type: ignore[attr-defined]
    except AttributeError:
        try:
            import multiprocessing
            return multiprocessing.cpu_count()
        except Exception:
            return 4


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_markdown_report(report: BenchmarkReport) -> str:
    """Generate a Markdown-format benchmark report."""
    lines: list[str] = []
    lines.append("# Performance Benchmark Report")
    lines.append("")
    lines.append(f"**Report ID**: {report.report_id}")
    lines.append(f"**Time**: {report.environment.timestamp}")
    lines.append("")
    lines.append("## Environment")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|------|-------|")
    lines.append(f"| Platform | {report.environment.platform_str} ({report.environment.arch}) |")
    lines.append(f"| CPU Cores | {report.environment.cpu_cores} |")
    lines.append(f"| Memory | {report.environment.total_memory_mb} MB |")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    s = report.summary
    lines.append(f"- **Total tests**: {s['totalTests']}")
    lines.append(f"- **Passed**: {s['passedTests']}")
    lines.append(f"- **Failed**: {s['failedTests']}")
    lines.append(f"- **Total duration**: {s['totalDurationMs']:.2f} ms")
    lines.append("")

    def _render_table(title: str, rows: list[dict], headers: list[str], cols: list[str]) -> None:
        if not rows:
            return
        lines.append(f"## {title}")
        lines.append("")
        sep = "| " + " | ".join(headers) + " |"
        lines.append(sep)
        lines.append("|" + "|".join("---" for _ in headers) + "|")
        for r in rows:
            vals = []
            for c in cols:
                v = r.get(c, "")
                if isinstance(v, float):
                    vals.append(f"{v:.3f}")
                else:
                    vals.append(str(v))
            lines.append("| " + " | ".join(vals) + " |")
        lines.append("")

    _render_table("Agent Execution", report.agent_execution,
                  ["Test", "Avg", "Median", "P95", "P99", "Samples", "Status"],
                  ["name", "avg", "median", "p95", "p99", "samples", "status"])
    _render_table("Message Bus", report.message_bus,
                  ["Test", "Avg", "Throughput", "Messages", "Status"],
                  ["name", "avg", "throughput", "messageCount", "status"])
    _render_table("Checkpoint", report.checkpoint,
                  ["Test", "Avg", "P95", "P99", "Checkpoints", "Status"],
                  ["name", "avg", "p95", "p99", "checkpointCount", "status"])
    _render_table("State Machine", report.state_machine,
                  ["Test", "Avg", "P95", "Transitions", "Status"],
                  ["name", "avg", "p95", "transitionCount", "status"])

    return "\n".join(lines)


def generate_report_filename(extension: str) -> str:
    now = time.strftime("%Y-%m-%d")
    ts = time.strftime("%H-%M-%S")
    return f"benchmark-{now}-{ts}.{extension}"


def generate_report_id() -> str:
    return f"bench-{int(time.time() * 1000)}-{_uuid.uuid4().hex[:8]}"
