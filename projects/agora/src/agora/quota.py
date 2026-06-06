"""Quota management for model providers.

Probes provider usage (credit balances, usage percentages) and exposes
availability checks. Adapted from agentmesh gateway model-gateway/quota.ts.
"""

from __future__ import annotations

import os
import time
from typing import Any

from agora.agent_providers import QuotaInfo  # type: ignore[import-not-found]

_quota_cache: dict[str, QuotaInfo] = {}
_last_probe_time: float = 0
QUOTA_TTL = 60.0  # seconds


async def probe_quota() -> dict[str, QuotaInfo]:
    """Probe quota for all configured providers.

    Uses cached results within TTL. In production, this would call
    external CLI tools (like `codexbar usage`) or provider APIs.
    """
    global _last_probe_time, _quota_cache

    now = time.time()
    if now - _last_probe_time < QUOTA_TTL and _quota_cache:
        return dict(_quota_cache)

    results: dict[str, QuotaInfo] = {}

    # Simulated probe logic — replace with real provider API calls
    for provider in ("deepseek", "openai", "codex", "openrouter", "gemini", "ollama"):
        info = _parse_quota(provider, _probe_provider(provider))
        results[provider] = info

    _quota_cache = results
    _last_probe_time = now
    return results


def _probe_provider(provider: str) -> dict[str, Any]:
    """Probe a single provider's quota/usage.

    Returns a dict simulating what a real CLI or API would return.
    """
    env_key_map = {
        "deepseek": "DEEPSEEK_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "codex": "CODEX_API_KEY",
        "ollama": "",
    }
    key = os.environ.get(env_key_map.get(provider, ""), "")
    if provider == "ollama":
        return {"available": True, "error": None}
    return {"available": bool(key), "error": None if key else {"message": "no API key configured"}}


def _parse_quota(provider: str, entry: dict[str, Any]) -> QuotaInfo:
    """Parse raw probe data into a QuotaInfo."""

    available = entry.get("available", True)
    error = entry.get("error")

    if error:
        return QuotaInfo(
            provider=provider,
            available=False,
            summary=f"Error: {error.get('message', '')}",
        )

    summary = "Available"
    balance: float | None = None
    used_percent: float | None = None

    if provider == "deepseek":
        # Simulate DeepSeek balance from config
        balance = 100.0
        summary = f"Balance: ¥{balance:.2f}"

    elif provider == "ollama":
        summary = "Local — always available"

    return QuotaInfo(
        provider=provider,
        available=available,
        used_percent=used_percent,
        balance=balance,
        summary=summary,
    )


def is_provider_available(provider: str) -> bool:
    """Check if a provider has available quota."""
    info = _quota_cache.get(provider)
    return info.available if info else True


def get_quota_summary() -> dict[str, QuotaInfo]:
    """Get the current cached quota summary."""
    return dict(_quota_cache)
