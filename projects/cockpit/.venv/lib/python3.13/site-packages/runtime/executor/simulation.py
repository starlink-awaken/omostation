"""Simulation provider for testing — deterministic, zero-cost LLM replacement.

Migrated from agentmesh llm/simulation.ts.

Provides a simulated agent execution environment that returns deterministic
outputs without calling real APIs. Supports configurable latency, error
rates, and mock responses.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass


@dataclass
class SimulationConfig:
    """Configuration for the simulation provider."""

    latency_ms: float = 100.0
    error_rate: float = 0.0
    fixed_output: str = ""


@dataclass
class SimulationResult:
    """Result from a simulated execution."""

    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    duration_ms: float = 0.0
    finish_reason: str = "stop"


class SimulationProvider:
    """Deterministic simulation provider for agent testing.

    Produces output without calling real LLM APIs. Supports preset
    responses, configurable latency, and error injection.
    """

    def __init__(
        self,
        config: SimulationConfig | None = None,
    ) -> None:
        self._config = config or SimulationConfig()
        self._mock_responses: dict[str, str] = {}
        self._call_count = 0

    async def complete(
        self,
        prompt: str,
        model: str | None = None,
    ) -> SimulationResult:
        """Simulate a completion call."""
        start = time.monotonic()
        self._call_count += 1
        await asyncio.sleep(self._config.latency_ms / 1000)
        if random.random() < self._config.error_rate:  # noqa: S311
            raise RuntimeError("Simulated API error")
        output = self._generate_output(prompt)
        input_tokens = self._estimate_tokens(prompt)
        output_tokens = self._estimate_tokens(output)
        elapsed = (time.monotonic() - start) * 1000
        return SimulationResult(
            content=output,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            duration_ms=elapsed,
        )

    def set_mock_response(self, key: str, response: str) -> None:
        self._mock_responses[key] = response

    def clear_mock_responses(self) -> None:
        self._mock_responses.clear()

    @property
    def call_count(self) -> int:
        return self._call_count

    def _generate_output(self, prompt: str) -> str:
        key = prompt[:100]
        if key in self._mock_responses:
            return self._mock_responses[key]
        if self._config.fixed_output:
            return self._config.fixed_output
        return (
            f"[Simulation] Agent executed.\n"
            f"Task: {prompt[:200]}{'...' if len(prompt) > 200 else ''}\n"
            f"Status: Completed (simulation mode)"
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        chinese = sum(1 for c in text if "一" <= c <= "鿿")
        other = len(text) - chinese
        return max(1, chinese // 2 + other // 4)
