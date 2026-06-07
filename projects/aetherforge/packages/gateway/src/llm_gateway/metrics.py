"""MetricsCollector — Prometheus-compatible metrics for AetherForge.

Collects and exposes key observability metrics:
  - **Latency**: per-model and per-provider request latency
  - **Cost**: per-model cost tracking
  - **Errors**: error counts by provider and error type
  - **Rate limits**: throttle events
  - **Requests**: throughput by model and provider

Usage::

    from llm_gateway.metrics import MetricsCollector

    metrics = MetricsCollector()
    metrics.record_latency("gpt-4", 1234.5)
    metrics.record_cost("gpt-4", 0.015)
    metrics.record_error("openai", "timeout")
    metrics.record_rate_limit("gpt-4")

    report = metrics.report()
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# JSON export path
DEFAULT_METRICS_PATH = Path.home() / ".aetherforge" / "metrics.jsonl"


@dataclass
class ModelMetrics:
    """Per-model aggregated metrics."""

    requests: int = 0
    errors: int = 0
    rate_limits: int = 0
    total_latency_ms: float = 0.0
    total_cost: float = 0.0
    total_tokens: int = 0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / max(1, self.requests)

    @property
    def error_rate(self) -> float:
        return self.errors / max(1, self.requests)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "errors": self.errors,
            "error_rate": round(self.error_rate, 4),
            "rate_limits": self.rate_limits,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "min_latency_ms": round(self.min_latency_ms if self.min_latency_ms != float("inf") else 0, 1),
            "max_latency_ms": round(self.max_latency_ms, 1),
            "total_cost": round(self.total_cost, 6),
            "total_tokens": self.total_tokens,
        }


class MetricsCollector:
    """Thread-safe Prometheus-compatible metrics collector.

    Collects per-model metrics that can be exported to Prometheus,
    JSONL, or inspected via the CLI.
    """

    def __init__(self, export_path: str | Path = DEFAULT_METRICS_PATH) -> None:
        self._models: dict[str, ModelMetrics] = defaultdict(ModelMetrics)
        self._providers: dict[str, ModelMetrics] = defaultdict(ModelMetrics)
        self._lock = threading.RLock()
        self._export_path = Path(export_path)
        self._start_time = time.time()

    # ── Recording ────────────────────────────────────────────────────────────

    def record_latency(self, model: str, latency_ms: float, provider: str = "") -> None:
        """Record a request latency."""
        with self._lock:
            m = self._models[model]
            m.requests += 1
            m.total_latency_ms += latency_ms
            m.min_latency_ms = min(m.min_latency_ms, latency_ms)
            m.max_latency_ms = max(m.max_latency_ms, latency_ms)

            if provider:
                p = self._providers[provider]
                p.requests += 1
                p.total_latency_ms += latency_ms

    def record_cost(self, model: str, cost: float, tokens: int = 0, provider: str = "") -> None:
        """Record cost and token usage."""
        with self._lock:
            self._models[model].total_cost += cost
            self._models[model].total_tokens += tokens
            if provider:
                self._providers[provider].total_cost += cost

    def record_error(self, model: str, error_type: str = "unknown", provider: str = "") -> None:
        """Record an error event."""
        with self._lock:
            self._models[model].errors += 1
            if provider:
                self._providers[provider].errors += 1

    def record_rate_limit(self, model: str, provider: str = "") -> None:
        """Record a rate-limit throttle event."""
        with self._lock:
            self._models[model].rate_limits += 1
            if provider:
                self._providers[provider].rate_limits += 1

    def record_generation(
        self,
        model: str,
        latency_ms: float,
        cost: float = 0.0,
        tokens: int = 0,
        provider: str = "",
        error: str = "",
    ) -> None:
        """Convenience: record a full generation cycle."""
        if error:
            self.record_error(model, error, provider)
        else:
            self.record_latency(model, latency_ms, provider)
            if cost or tokens:
                self.record_cost(model, cost, tokens, provider)

    # ── Export ───────────────────────────────────────────────────────────────

    def report(self) -> dict[str, Any]:
        """Return a snapshot of all metrics."""
        with self._lock:
            uptime = time.time() - self._start_time
            return {
                "uptime_seconds": round(uptime, 1),
                "total_models": len(self._models),
                "total_requests": sum(m.requests for m in self._models.values()),
                "total_errors": sum(m.errors for m in self._models.values()),
                "total_rate_limits": sum(m.rate_limits for m in self._models.values()),
                "total_cost": round(sum(m.total_cost for m in self._models.values()), 6),
                "total_tokens": sum(m.total_tokens for m in self._models.values()),
                "models": {k: v.to_dict() for k, v in sorted(self._models.items())},
                "providers": {k: v.to_dict() for k, v in sorted(self._providers.items())},
            }

    def export_jsonl(self) -> Path:
        """Append current snapshot to the JSONL export file."""
        snapshot = self.report()
        snapshot["ts"] = time.time()
        try:
            self._export_path.parent.mkdir(parents=True, exist_ok=True)
            line = (json.dumps(snapshot, ensure_ascii=False) + "\n").encode("utf-8")
            fd = os.open(str(self._export_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(fd, line)
            finally:
                os.close(fd)
        except Exception:
            _log.exception("Failed to export metrics")
        return self._export_path

    # ── Reset ────────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._models.clear()
            self._providers.clear()
            self._start_time = time.time()

    def get_model(self, model: str) -> ModelMetrics | None:
        """Get metrics for a specific model."""
        with self._lock:
            return self._models.get(model)

    @property
    def error_rate(self) -> float:
        """Overall error rate across all models."""
        with self._lock:
            total_req = sum(m.requests for m in self._models.values())
            total_err = sum(m.errors for m in self._models.values())
            return total_err / max(1, total_req)


# Import os for file writing
import os  # noqa: E402
