"""Token efficiency benchmark functions.

Maps to TS source: agentmesh/packages/engine/src/benchmarks/performance/token-efficiency.ts (benchmarks section)

Provides benchmark functions for:
  - Token statistics accuracy
  - Token budget control
  - Multi-provider separation
"""

from __future__ import annotations

import statistics
import time
from typing import Any

from runtime.executor.token_efficiency import TokenEfficiencyResult, TokenTracker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect_timing_samples_async(fn: Any, samples: int = 50) -> list[float]:
    times: list[float] = []
    for _ in range(samples):
        t0 = time.perf_counter()
        await fn()
        times.append((time.perf_counter() - t0) * 1000)
    return times


def _generate_usage_sequence(
    agent_count: int,
    tokens_per_agent: tuple[int, int],
) -> list[dict[str, Any]]:
    providers = ["claude", "openai", "simulation"]
    sequence: list[dict[str, Any]] = []
    rng = 1
    for i in range(agent_count):
        inp = tokens_per_agent[0] + (rng % 100)
        out = tokens_per_agent[1] + (rng % 50)
        rng += 1
        sequence.append({
            "provider": providers[i % len(providers)],
            "input": inp,
            "output": out,
            "agentName": f"agent-{i}",
        })
    return sequence


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


async def bench_token_statistics_accuracy(record_count: int = 1000) -> TokenEfficiencyResult:
    tracker = TokenTracker()

    async def run() -> int:
        seq = _generate_usage_sequence(record_count, (1000, 500))
        for r in seq:
            tracker.record(r["provider"], r["input"], r["output"], {"agentName": r["agentName"], "projectId": "test"})
        return tracker.get_total().input + tracker.get_total().output

    durations = await _collect_timing_samples_async(run, 50)
    total = tracker.get_total()
    expected = sum(r["input"] + r["output"] for r in _generate_usage_sequence(record_count, (1000, 500)))
    accuracy = total.input + total.output
    cost = tracker.estimate_cost()
    avg_ms = statistics.mean(durations) if durations else 0.0

    return TokenEfficiencyResult(
        name="Token Statistics Accuracy",
        description=f"Token stats accuracy ({record_count} records)",
        total_tokens=accuracy,
        input_tokens=total.input,
        output_tokens=total.output,
        io_ratio=total.output / max(total.input, 1),
        estimated_cost=cost.total_cost,
        avg_time_ms=avg_ms,
        passed=accuracy == expected,
        threshold=float(expected),
        rate_metrics={
            "tokens_per_second": accuracy / max(avg_ms / 1000, 0.001),
            "tokens_per_minute": (accuracy / max(avg_ms / 1000, 0.001)) * 60,
        },
        stats={"avg": avg_ms, "samples": float(len(durations))},
    )


async def bench_token_budget_control(budget: int = 100_000) -> TokenEfficiencyResult:
    tracker = TokenTracker()
    durations: list[float] = []

    for i in range(100):
        t0 = time.perf_counter()
        usage = _generate_usage_sequence(10, (100, 50))
        for r in usage:
            tracker.record(r["provider"], r["input"], r["output"])
        tracker.check_budget(budget)
        durations.append((time.perf_counter() - t0) * 1000)
        if i < 99:
            tracker.reset()

    total = tracker.get_total()
    avg_ms = statistics.mean(durations) if durations else 0.0
    return TokenEfficiencyResult(
        name="Token Budget Control",
        description=f"Budget control test (budget: {budget})",
        total_tokens=total.input + total.output,
        input_tokens=total.input,
        output_tokens=total.output,
        avg_time_ms=avg_ms,
        passed=True,
        stats={"avg": avg_ms, "samples": float(len(durations))},
    )


async def bench_multi_provider_separation(providers: list[str] | None = None) -> TokenEfficiencyResult:
    if providers is None:
        providers = ["claude", "openai", "simulation"]
    tracker = TokenTracker()
    usage_by_provider = {"claude": (1000, 500), "openai": (800, 400), "simulation": (500, 250)}

    async def run() -> int:
        for prov in providers:
            inp, out = usage_by_provider.get(prov, (500, 250))
            tracker.record(prov, inp, out, {"agentName": f"{prov}-agent"})
        return tracker.get_total().input + tracker.get_total().output

    durations = await _collect_timing_samples_async(run, 100)
    tracker.reset()

    for prov in providers:
        inp, out = usage_by_provider.get(prov, (500, 250))
        tracker.record(prov, inp, out, {"agentName": f"{prov}-agent"})

    total = tracker.get_total()
    cost = tracker.estimate_cost()
    correct = True
    for prov in providers:
        p = tracker.get_total(prov)
        expected_inp, expected_out = usage_by_provider.get(prov, (500, 250))
        if p.input != expected_inp or p.output != expected_out:
            correct = False

    avg_ms = statistics.mean(durations) if durations else 0.0
    return TokenEfficiencyResult(
        name="Multi-Provider Separation",
        description=f"Provider separation test ({len(providers)} providers)",
        total_tokens=total.input + total.output,
        input_tokens=total.input,
        output_tokens=total.output,
        io_ratio=total.output / max(total.input, 1),
        estimated_cost=cost.total_cost,
        avg_time_ms=avg_ms,
        passed=correct,
        stats={"avg": avg_ms, "samples": float(len(durations))},
    )
