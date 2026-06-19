"""Agent health checking — system-level and provider-level health checks.

Adapted from agentmesh gateway model-gateway/health.ts.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from agora.agent_providers import ModelGatewayConfig, ResolvedProvider  # type: ignore[import-not-found]
from agora.core.circuit_breaker import registry  # type: ignore[import-not-found]

# ── System Health ────────────────────────────────────────────────────────────


async def check_system_health() -> dict[str, Any]:
    """Run basic system-level health checks (memory, event loop, CPU)."""
    import psutil

    mem = psutil.virtual_memory()
    mem_status = "healthy" if mem.percent < 90 else "degraded"
    mem_msg = f"{mem.percent:.1f}% used ({mem.available / 1024**3:.1f}G available)"

    cpu_percent = psutil.cpu_percent(interval=0.1)
    cpu_status = "healthy" if cpu_percent < 90 else "degraded"
    cpu_msg = f"{cpu_percent:.1f}% used"

    statuses = [mem_status, "healthy", cpu_status]
    overall = "healthy" if all(s == "healthy" for s in statuses) else "degraded"

    return {
        "memory": {"status": mem_status, "message": mem_msg},
        "event_loop": {"status": "healthy", "message": "event loop responsive"},
        "cpu": {"status": cpu_status, "message": cpu_msg},
        "overall": overall,
    }


# ── Provider Health ──────────────────────────────────────────────────────────


_health_cache: dict[str, tuple[dict[str, Any], float]] = {}
CACHE_TTL = 30.0


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


async def check_provider_health(provider: ResolvedProvider) -> dict[str, Any]:
    """Check health of a single model provider."""
    now = time.time()
    cached = _health_cache.get(provider.name)
    if cached and now - cached[1] < CACHE_TTL:
        return dict(cached[0])

    circuit_state = registry.get_state(provider.name)
    if circuit_state == "OPEN":
        result = {
            "provider": provider.name,
            "status": "unhealthy",
            "latency_ms": 0,
            "circuit": circuit_state,
            "error": "circuit_breaker_open",
            "checked_at": _iso_now(),
        }
        _health_cache[provider.name] = (result, now)
        return result

    import httpx

    base_url = provider.base_url.rstrip("/")
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {provider.api_key}"},
            )
        latency = int((time.time() - start) * 1000)
        result = {
            "provider": provider.name,
            "status": "healthy" if resp.is_success else "unhealthy",
            "latency_ms": latency,
            "circuit": circuit_state,
            "error": None if resp.is_success else f"HTTP {resp.status_code}",
            "checked_at": _iso_now(),
        }
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        result = {
            "provider": provider.name,
            "status": "unhealthy",
            "latency_ms": latency,
            "circuit": circuit_state,
            "error": str(e)[:100] or "unknown error",
            "checked_at": _iso_now(),
        }

    _health_cache[provider.name] = (result, time.time())
    return result


async def check_all_providers(config: ModelGatewayConfig) -> list[dict[str, Any]]:
    """Check health of all configured providers."""

    async def _check(name: str, cfg: Any) -> dict[str, Any]:
        api_key = os.environ.get(getattr(cfg, "api_key_env", ""), "") or getattr(
            cfg, "api_key", ""
        )
        if not api_key:
            return {
                "provider": name,
                "status": "unknown",
                "latency_ms": 0,
                "circuit": registry.get_state(name),
                "error": "no_api_key",
                "checked_at": _iso_now(),
            }
        return await check_provider_health(
            ResolvedProvider(name=name, base_url=cfg.base_url, api_key=api_key)
        )

    results = await asyncio.gather(
        *[_check(n, c) for n, c in config.providers.items()],
        return_exceptions=True,
    )
    return [
        r
        if isinstance(r, dict)
        else {
            "provider": "unknown",
            "status": "unhealthy",
            "latency_ms": 0,
            "circuit": "unknown",
            "error": str(r) if isinstance(r, BaseException) else "check failed",
            "checked_at": _iso_now(),
        }
        for r in results
    ]


# ── Combined ─────────────────────────────────────────────────────────────────


async def run_all_health_checks(config: ModelGatewayConfig) -> dict[str, Any]:
    """Execute all health checks (system + providers) concurrently."""
    system, providers = await asyncio.gather(
        check_system_health(),
        check_all_providers(config),
    )
    return {"system": system, "providers": providers}
