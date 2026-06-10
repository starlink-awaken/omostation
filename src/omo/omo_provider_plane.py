from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .omo_redaction import redact_sensitive_text


@dataclass(frozen=True)
class ProviderRuntime:
    provider_id: str
    app_type: str
    name: str
    base_url: str
    api_key: str
    model: str
    is_healthy: bool
    last_success_at: str | None
    source: str = "cc-switch"


def select_cc_switch_provider(
    db_path: Path | None = None,
    app_type: str = "claude",
    preferred_names: list[str] | None = None,
    m1_dir: Path | None = None,
) -> ProviderRuntime:
    import asyncio
    import os
    from llm_gateway_kernel.llm_gateway.scheduler import ModelScheduler
    from llm_gateway_kernel.llm_gateway.types import ModelRequest, ModelRoutePolicy
    
    if m1_dir is None:
        m1_dir = Path(__file__).resolve().parents[3] / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "compute_engine"
        
    async def _do_select() -> ProviderRuntime:
        scheduler = ModelScheduler.from_m1_dir(str(m1_dir))
        await scheduler._registry.refresh()
        
        req = ModelRequest(required_capabilities=["chat"])
        policy = ModelRoutePolicy(priority=preferred_names or [])
        sel = await scheduler.select_model(req, policy=policy)
        
        if not sel:
            raise ValueError(f"No healthy provider found in M1 registry for app_type={app_type}")
            
        provider_name = sel.provider_name
        adapter = scheduler._registry._providers.get(provider_name)
        
        base_url = ""
        if adapter and hasattr(adapter, "base_url"):
            base_url = adapter.base_url or ""
            
        if app_type == "claude":
            api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY", "dummy-key")
        elif app_type in {"codex", "openai"}:
            api_key = os.environ.get("OPENAI_API_KEY", "dummy-key")
        else:
            api_key = os.environ.get("API_KEY", "dummy-key")
            
        if app_type == "claude" and not base_url:
            base_url = os.environ.get("ANTHROPIC_BASE_URL", base_url)
        if app_type in {"codex", "openai"} and not base_url:
            base_url = os.environ.get("OPENAI_BASE_URL", base_url)
            
        real_model = sel.model.id.split("/")[-1] if "/" in sel.model.id else sel.model.id
            
        return ProviderRuntime(
            provider_id=sel.model.provider,
            app_type=app_type,
            name=sel.provider_name,
            base_url=base_url,
            api_key=api_key,
            model=real_model,
            is_healthy=True,
            last_success_at=None,
            source="llm-gateway",
        )
        
    return asyncio.run(_do_select())


def _litellm_model_name(provider: ProviderRuntime) -> str:
    if "/" in provider.model:
        return provider.model
    if provider.app_type == "claude":
        return f"anthropic/{provider.model}"
    if provider.app_type in {"codex", "openai"}:
        return f"openai/{provider.model}"
    return provider.model


def apply_provider_to_litellm_config(
    config_path: Path, target_model_name: str, provider: ProviderRuntime
) -> None:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    model_list = data.get("model_list", [])
    for entry in model_list:
        if entry.get("model_name") != target_model_name:
            continue
        params = dict(entry.get("litellm_params", {}))
        params["model"] = _litellm_model_name(provider)
        params["api_key"] = provider.api_key
        params["api_base"] = provider.base_url
        entry["litellm_params"] = params
        break
    else:
        raise ValueError(
            f"Target model not found in LiteLLM config: {target_model_name}"
        )

    config_path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def summarize_codexbar_usage(raw_json: str) -> dict[str, Any]:
    entries = json.loads(raw_json or "[]")
    providers: dict[str, dict[str, Any]] = {}

    for entry in entries:
        provider = entry.get("provider")
        if not provider:
            continue
        summary: dict[str, Any] = {
            "available": True,
            "summary": "",
        }
        if provider == "codex":
            remaining = ((entry.get("credits") or {}).get("remaining")) or 0
            used = (
                ((entry.get("usage") or {}).get("secondary") or {}).get("usedPercent")
            ) or 0
            summary["available"] = remaining > 0 or used < 100
            summary["remaining"] = remaining
            summary["used_percent"] = used
            summary["summary"] = f"credits={remaining}, secondary_used={used}%"
        elif provider == "openrouter":
            usage = (entry.get("usage") or {}).get("openRouterUsage") or {}
            balance = usage.get("balance") or 0
            used = usage.get("usedPercent") or 0
            summary["available"] = balance > 0
            summary["balance"] = balance
            summary["used_percent"] = used
            summary["summary"] = f"balance=${balance:.2f}, used={used}%"
        else:
            error = entry.get("error")
            summary["available"] = not bool(error)
            summary["summary"] = (
                error.get("message", "ok") if isinstance(error, dict) else "ok"
            )
        providers[str(provider)] = summary

    return {
        "provider_count": len(providers),
        "providers": providers,
    }


def write_provider_plane_snapshot(
    snapshot_path: Path,
    selected_provider: dict[str, Any],
    quota_summary: dict[str, Any],
    litellm_health: dict[str, Any],
) -> None:
    summarized_health = {
        "healthy_count": litellm_health.get("healthy_count", 0),
        "unhealthy_count": litellm_health.get("unhealthy_count", 0),
    }
    if "healthy_endpoints" in litellm_health:
        summarized_health["healthy_models"] = [
            endpoint.get("model")
            for endpoint in litellm_health.get("healthy_endpoints", [])
            if isinstance(endpoint, dict) and endpoint.get("model")
        ]
    if "unhealthy_endpoints" in litellm_health:
        summarized_health["unhealthy_models"] = [
            endpoint.get("model")
            for endpoint in litellm_health.get("unhealthy_endpoints", [])
            if isinstance(endpoint, dict) and endpoint.get("model")
        ]

    sanitized_provider = {
        k: redact_sensitive_text(str(v)) if isinstance(v, str) else v
        for k, v in selected_provider.items()
        if k not in {"api_key", "token", "auth_token"}
    }

    payload = {
        "updated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "selected_provider": sanitized_provider,
        "quota_summary": quota_summary,
        "litellm_health": summarized_health,
    }
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def safe_provider_summary(provider: ProviderRuntime) -> dict[str, Any]:
    summary = asdict(provider)
    summary.pop("api_key", None)
    return summary
