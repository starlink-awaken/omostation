"""Model provider types, calling logic, and routing.

Combines agentmesh gateway model-gateway types.ts, providers.ts, and router.ts
into a single module providing provider resolution and API calling.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from agora.core.circuit_breaker import registry  # type: ignore[import-not-found]
from agora.retry import is_retryable  # type: ignore[import-not-found]
from agora.retry import with_retry as retry_with_retry

# ── Types ────────────────────────────────────────────────────────────────────


@dataclass
class ModelProviderConfig:
    """Configuration for a single model provider."""
    base_url: str
    api_key_env: str = ""
    api_key: str = ""
    models: list[str] = field(default_factory=list)


@dataclass
class ModelGatewayConfig:
    """Top-level model gateway configuration."""
    default_model: str = ""
    providers: dict[str, ModelProviderConfig] = field(default_factory=dict)
    fallback_chain: list[str] = field(default_factory=list)
    model_routing: dict[str, list[str]] = field(default_factory=dict)
    model_aliases: dict[str, str] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolvedProvider:
    """A resolved provider with an API key."""
    name: str
    base_url: str
    api_key: str


@dataclass
class QuotaInfo:
    """Provider quota information."""
    provider: str
    available: bool
    used_percent: float | None = None
    balance: float | None = None
    summary: str = ""


# ── Global State ─────────────────────────────────────────────────────────────

_model_aliases: dict[str, dict[str, str]] = {
    "deepseek": {
        "gpt-5.3-codex": "deepseek-v4-pro",
        "gpt-5.4": "deepseek-v4-pro",
        "gpt-5.5": "deepseek-v4-pro",
        "o4-mini": "deepseek-v4-flash",
        "claude-sonnet-4-6": "deepseek-v4-pro",
    },
}

_gateway_config: ModelGatewayConfig | None = None


# ── Router Initialization ────────────────────────────────────────────────────


def init_model_router(cfg: ModelGatewayConfig) -> None:
    """Initialize the model router with configuration."""
    global _gateway_config, _model_aliases
    _gateway_config = cfg

    if cfg.model_aliases:
        for alias_key, real_model in cfg.model_aliases.items():
            matched = False
            for provider_name, provider_cfg in cfg.providers.items():
                if real_model in (provider_cfg.models or []):
                    _model_aliases.setdefault(provider_name, {})[alias_key] = real_model
                    matched = True
                    break
            if not matched:
                _model_aliases.setdefault("deepseek", {})[alias_key] = real_model


def get_config() -> ModelGatewayConfig | None:
    return _gateway_config


# ── API Key Resolution ───────────────────────────────────────────────────────


def _resolve_api_key(name: str, provider_cfg: ModelProviderConfig) -> str | None:
    if provider_cfg.api_key:
        return provider_cfg.api_key
    if provider_cfg.api_key_env:
        return os.environ.get(provider_cfg.api_key_env) or None
    return None


# ── Provider Resolution ──────────────────────────────────────────────────────


def resolve_provider(model: str) -> ResolvedProvider | None:
    """Resolve the best provider for a given model name."""
    cfg = _gateway_config
    if not cfg:
        return None

    # 1. Check model_routing patterns
    for pattern, providers in (cfg.model_routing or {}).items():
        if model.startswith(pattern):
            for provider_name in providers:
                provider_cfg = cfg.providers.get(provider_name)
                if not provider_cfg:
                    continue
                api_key = _resolve_api_key(provider_name, provider_cfg)
                if not api_key:
                    continue
                if registry.is_open(provider_name):
                    continue
                return ResolvedProvider(
                    name=provider_name,
                    base_url=provider_cfg.base_url,
                    api_key=api_key,
                )
            break

    # 2. Fallback chain
    for provider_name in cfg.fallback_chain or []:
        provider_cfg = cfg.providers.get(provider_name)
        if not provider_cfg:
            continue
        api_key = _resolve_api_key(provider_name, provider_cfg)
        if not api_key:
            continue
        if registry.is_open(provider_name):
            continue
        return ResolvedProvider(
            name=provider_name,
            base_url=provider_cfg.base_url,
            api_key=api_key,
        )

    # 3. Ultimate fallback: first provider with API key
    for name, provider_cfg in cfg.providers.items():
        if registry.is_open(name):
            continue
        key = _resolve_api_key(name, provider_cfg)
        if key:
            return ResolvedProvider(name=name, base_url=provider_cfg.base_url, api_key=key)

    return None


def remap_model(model: str, provider_name: str) -> str:
    """Remap an external model name to the provider's internal name."""
    return _model_aliases.get(provider_name, {}).get(model, model)


# ── Provider Calling ─────────────────────────────────────────────────────────


async def call_chat_completions(
    provider: ResolvedProvider,
    request: dict[str, Any],
) -> dict[str, Any]:
    """Call a provider's /chat/completions endpoint with circuit breaker & retry."""
    base_url = provider.base_url.rstrip("/")
    url = f"{base_url}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {provider.api_key}",
    }
    if provider.name == "openrouter":
        headers["HTTP-Referer"] = "http://127.0.0.1:3000"
        headers["X-Title"] = "Agent Mesh Gateway"

    if not registry.can_request(provider.name):
        raise RuntimeError(f"Circuit breaker open for {provider.name}")

    import httpx

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            resp = await retry_with_retry(
                provider.name,
                lambda: client.post(url, json=request, headers=headers),
                on_retry=lambda a, s, d: print(
                    f"[Retry] {provider.name} attempt {a} after {s} — retrying in {d}ms"
                ),
            )

            if not resp.is_error and is_retryable(resp.status_code):
                registry.record_failure(provider.name)
            elif resp.is_success:
                registry.record_success(provider.name)
            else:
                registry.record_failure(provider.name)

            resp.raise_for_status()
            return resp.json()
        except Exception:
            registry.record_failure(provider.name)
            raise
