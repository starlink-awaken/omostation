"""Gateway runtime metrics collection.

Tracks request counts, success/failure rates, and latency per provider.
Adapted from agentmesh gateway model-gateway/metrics.ts.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any


class ProviderMetrics:
    """Per-provider metric counters."""

    def __init__(self) -> None:
        self.requests = 0
        self.success = 0
        self.failures = 0
        self.total_latency_ms: float = 0
        self.last_error: str | None = None
        self.last_error_time: float | None = None
        self.last_success_time: float | None = None


_provider_metrics: dict[str, ProviderMetrics] = {}
_recent_requests: deque[dict[str, Any]] = deque(maxlen=200)


def _get_or_init(name: str) -> ProviderMetrics:
    if name not in _provider_metrics:
        _provider_metrics[name] = ProviderMetrics()
    return _provider_metrics[name]


def record_request(log: dict[str, Any]) -> None:
    """Record a single request metric."""
    m = _get_or_init(log.get("provider", "unknown"))
    m.requests += 1
    m.total_latency_ms += log.get("latency_ms", 0)

    status = log.get("status", 500)
    if 200 <= status < 400:
        m.success += 1
        m.last_success_time = log.get("timestamp", time.time())
    else:
        m.failures += 1
        m.last_error = log.get("error")
        m.last_error_time = log.get("timestamp", time.time())

    _recent_requests.append(log)


def get_metrics() -> dict[str, Any]:
    """Get aggregated metrics snapshot."""
    providers: dict[str, Any] = {}
    total_requests = 0
    total_failures = 0

    for name, m in _provider_metrics.items():
        total_requests += m.requests
        total_failures += m.failures
        providers[name] = {
            "requests": m.requests,
            "success_rate": (
                f"{(m.success / m.requests * 100):.1f}%" if m.requests > 0 else "N/A"
            ),
            "avg_latency_ms": (
                round(m.total_latency_ms / m.requests) if m.requests > 0 else 0
            ),
            "last_success": (
                __import__("datetime")
                .datetime.fromtimestamp(m.last_success_time)
                .isoformat()
                if m.last_success_time
                else None
            ),
            "last_error": m.last_error,
            "last_error_time": (
                __import__("datetime")
                .datetime.fromtimestamp(m.last_error_time)
                .isoformat()
                if m.last_error_time
                else None
            ),
        }

    return {
        "uptime_seconds": round(time.time() - _process_start),
        "total_requests": total_requests,
        "total_failures": total_failures,
        "providers": providers,
        "recent": [
            {
                "time": __import__("datetime")
                .datetime.fromtimestamp(r.get("timestamp", 0))
                .isoformat(),
                "model": r.get("model", ""),
                "provider": r.get("provider", ""),
                "actual": r.get("actual_model", ""),
                "latency_ms": r.get("latency_ms", 0),
                "status": r.get("status", 0),
                "streaming": r.get("streaming", False),
                "error": r.get("error"),
            }
            for r in list(_recent_requests)[-20:]
        ],
    }


_process_start = time.time()
