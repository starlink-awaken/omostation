"""Token counting, usage tracking, cost estimation.

Maps to TS source: agentmesh/packages/engine/src/benchmarks/performance/token-efficiency.ts (core logic)

Provides:
  - TokenTracker: records token usage per provider/agent with cost estimation
  - TokenUsage, TokenUsageRate, CostEstimate, TokenSummary dataclasses
  - Budget checking and usage rate tracking
  - Benchmark functions in token_efficiency_benchmarks.py
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants & Types
# ---------------------------------------------------------------------------

TOKEN_COST_PER_MILLION: dict[str, dict[str, float]] = {
    "claude": {"input": 3.0, "output": 15.0},
    "openai": {"input": 2.5, "output": 10.0},
    "simulation": {"input": 1.0, "output": 5.0},
}


@dataclass
class TokenUsage:
    """Token usage totals."""
    input: int = 0
    output: int = 0


@dataclass
class TokenUsageRate:
    """Token usage rate within a time window."""
    tokens_per_minute: float = 0.0
    input_tokens_per_minute: float = 0.0
    output_tokens_per_minute: float = 0.0
    window_duration_s: float = 0.0


@dataclass
class CostEstimate:
    """Estimated cost breakdown."""
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    per_provider: dict[str, float] = field(default_factory=dict)


@dataclass
class TokenSummary:
    """Aggregate token summary."""
    total_tokens: int = 0
    total_input: int = 0
    total_output: int = 0
    avg_input_per_call: float = 0.0
    avg_output_per_call: float = 0.0
    total_calls: int = 0


@dataclass
class TokenEfficiencyResult:
    """Result of a token efficiency benchmark."""
    name: str
    description: str = ""
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    io_ratio: float = 0.0
    estimated_cost: float = 0.0
    avg_time_ms: float = 0.0
    passed: bool = True
    threshold: float = 0.0
    rate_metrics: dict[str, float] = field(default_factory=dict)
    stats: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# TokenTracker
# ---------------------------------------------------------------------------


class TokenTracker:
    """Tracks token usage across providers and agents with cost estimation.

    Maps to TS TokenTracker from agentmesh/packages/engine/src/llm/tracker.ts.
    """

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []
        self._totals: dict[str, TokenUsage] = {}
        self._agent_usage: dict[str, TokenUsage] = {}

    def record(
        self,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = time.time()
        self._records.append({
            "provider": provider,
            "input": input_tokens,
            "output": output_tokens,
            "metadata": metadata or {},
            "timestamp": now,
        })

        p_total = self._totals.setdefault(provider, TokenUsage())
        p_total.input += input_tokens
        p_total.output += output_tokens

        agent = (metadata or {}).get("agentName")
        if agent:
            a_total = self._agent_usage.setdefault(agent, TokenUsage())
            a_total.input += input_tokens
            a_total.output += output_tokens

    def get_total(self, provider: str | None = None) -> TokenUsage:
        if provider:
            return self._totals.get(provider, TokenUsage())
        total = TokenUsage()
        for usage in self._totals.values():
            total.input += usage.input
            total.output += usage.output
        return total

    def get_usage_by_agent(self) -> dict[str, TokenUsage]:
        return dict(self._agent_usage)

    def get_usage_rate(self, window_s: float = 60.0) -> TokenUsageRate:
        now = time.time()
        cutoff = now - window_s
        recent = [r for r in self._records if r["timestamp"] >= cutoff]

        input_t = sum(r["input"] for r in recent)
        output_t = sum(r["output"] for r in recent)
        total_t = input_t + output_t
        window_duration = (now - min((r["timestamp"] for r in recent), default=now)) if recent else 0.0
        rate = (total_t / window_duration * 60) if window_duration > 0 else 0.0

        return TokenUsageRate(
            tokens_per_minute=rate,
            input_tokens_per_minute=(input_t / window_duration * 60) if window_duration > 0 else 0.0,
            output_tokens_per_minute=(output_t / window_duration * 60) if window_duration > 0 else 0.0,
            window_duration_s=window_duration,
        )

    def estimate_cost(self, provider: str | None = None) -> CostEstimate:
        pricing = TOKEN_COST_PER_MILLION
        total_input = 0.0
        total_output = 0.0
        per_provider: dict[str, float] = {}
        providers_to_check = [provider] if provider else list(self._totals.keys())

        for prov in providers_to_check:
            usage = self._totals.get(prov)
            if usage is None:
                continue
            price = pricing.get(prov, pricing["simulation"])
            inp = (usage.input / 1_000_000) * price["input"]
            out = (usage.output / 1_000_000) * price["output"]
            total_input += inp
            total_output += out
            per_provider[prov] = inp + out

        return CostEstimate(
            input_cost=total_input,
            output_cost=total_output,
            total_cost=total_input + total_output,
            per_provider=per_provider,
        )

    def check_budget(self, budget: int) -> bool:
        total = self.get_total()
        return (total.input + total.output) <= budget

    def get_summary(self) -> TokenSummary:
        total = self.get_total()
        call_count = len(self._records) if self._records else 1
        return TokenSummary(
            total_tokens=total.input + total.output,
            total_input=total.input,
            total_output=total.output,
            avg_input_per_call=total.input / call_count,
            avg_output_per_call=total.output / call_count,
            total_calls=len(self._records),
        )

    def get_report(self) -> dict[str, Any]:
        return {
            "totals": {
                "input": self.get_total().input,
                "output": self.get_total().output,
            },
            "by_provider": {k: {"input": v.input, "output": v.output} for k, v in self._totals.items()},
            "by_agent": {k: {"input": v.input, "output": v.output} for k, v in self._agent_usage.items()},
            "cost": {"total_cost": self.estimate_cost().total_cost},
        }

    def reset(self) -> None:
        self._records.clear()
        self._totals.clear()
        self._agent_usage.clear()
