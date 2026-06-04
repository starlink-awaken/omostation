from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from .omo_redaction import redact_sensitive_text
except ModuleNotFoundError:
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


def _load_settings(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def _load_provider_rows(db_path: Path, app_type: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                p.id,
                p.app_type,
                p.name,
                p.settings_config,
                p.is_current,
                p.sort_index,
                pe.url AS endpoint_url,
                ph.is_healthy,
                ph.last_success_at
            FROM providers p
            LEFT JOIN provider_endpoints pe
              ON pe.provider_id = p.id AND pe.app_type = p.app_type
            LEFT JOIN provider_health ph
              ON ph.provider_id = p.id AND ph.app_type = p.app_type
            WHERE p.app_type = ?
            ORDER BY COALESCE(ph.is_healthy, 0) DESC,
                     COALESCE(ph.last_success_at, '') DESC,
                     COALESCE(p.is_current, 0) DESC,
                     COALESCE(p.sort_index, 9999) ASC
            """,
            (app_type,),
        ).fetchall()
    finally:
        conn.close()
    return rows


def _runtime_from_row(row: sqlite3.Row) -> ProviderRuntime | None:
    settings = _load_settings(row["settings_config"])
    env = settings.get("env", {})
    if not isinstance(env, dict):
        env = {}

    if row["app_type"] == "claude":
        api_key = env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY")
        base_url = env.get("ANTHROPIC_BASE_URL") or row["endpoint_url"]
        model = env.get("ANTHROPIC_MODEL") or env.get("ANTHROPIC_DEFAULT_SONNET_MODEL") or "claude-3-5-sonnet-20241022"
    elif row["app_type"] in {"codex", "openai"}:
        api_key = env.get("OPENAI_API_KEY")
        base_url = env.get("OPENAI_BASE_URL") or env.get("OPENAI_API_BASE") or row["endpoint_url"]
        model = env.get("OPENAI_MODEL") or "gpt-4o"
    else:
        api_key = env.get("API_KEY")
        base_url = env.get("BASE_URL") or row["endpoint_url"]
        model = env.get("MODEL") or ""

    if not api_key or not base_url or not model:
        return None

    return ProviderRuntime(
        provider_id=str(row["id"]),
        app_type=str(row["app_type"]),
        name=str(row["name"]),
        base_url=str(base_url).rstrip("/"),
        api_key=str(api_key),
        model=str(model),
        is_healthy=bool(row["is_healthy"]),
        last_success_at=row["last_success_at"],
    )


def select_cc_switch_provider(
    db_path: Path,
    app_type: str,
    preferred_names: list[str] | None = None,
) -> ProviderRuntime:
    preferred = {name.lower() for name in preferred_names or []}
    candidates = []
    preferred_candidates = []

    for row in _load_provider_rows(db_path, app_type=app_type):
        runtime = _runtime_from_row(row)
        if runtime is None or not runtime.is_healthy:
            continue
        candidates.append(runtime)
        if runtime.name.lower() in preferred:
            preferred_candidates.append(runtime)

    pool = preferred_candidates or candidates
    if not pool:
        raise ValueError(f"No healthy {app_type} provider with runtime config found in {db_path}")
    return pool[0]


def _litellm_model_name(provider: ProviderRuntime) -> str:
    if "/" in provider.model:
        return provider.model
    if provider.app_type == "claude":
        return f"anthropic/{provider.model}"
    if provider.app_type in {"codex", "openai"}:
        return f"openai/{provider.model}"
    return provider.model


def apply_provider_to_litellm_config(config_path: Path, target_model_name: str, provider: ProviderRuntime) -> None:
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
        raise ValueError(f"Target model not found in LiteLLM config: {target_model_name}")

    config_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


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
            used = (((entry.get("usage") or {}).get("secondary") or {}).get("usedPercent")) or 0
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
            summary["summary"] = error.get("message", "ok") if isinstance(error, dict) else "ok"
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
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "selected_provider": sanitized_provider,
        "quota_summary": quota_summary,
        "litellm_health": summarized_health,
    }
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def safe_provider_summary(provider: ProviderRuntime) -> dict[str, Any]:
    summary = asdict(provider)
    summary.pop("api_key", None)
    return summary
