"""AdmissionPort protocol and resolver.

Binding order (first match wins):
1. env AGORA_ADMISSION_PROVIDER = "module:attr" (e.g. metaos.integrations.admission_provider:PROVIDER)
2. entry_points group "agora.admission" (preferred name "metaos")
3. optional soft import of known provider module (no hard dep on metaos package at import time)

Missing provider policy (env AGORA_ADMISSION_MODE):
- required (default): return rejected with reason provider_unavailable (fail-closed)
- strict: return rejected with reason provider_unavailable
- degraded: return admitted with reason provider_unavailable (explicit local-dev opt-in)
"""

from __future__ import annotations

import importlib
import os
from importlib import metadata
from typing import Any, Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)

# Known soft provider paths — optional, never imported at module load.
_SOFT_PROVIDERS: tuple[str, ...] = ("metaos.integrations.admission_provider:PROVIDER",)

_UNSET: object = object()
_provider_cache: AdmissionPort | None | object = _UNSET


@runtime_checkable
class AdmissionPort(Protocol):
    """SPI: evaluate whether a route/service may register on Agora."""

    def evaluate(self, request: dict[str, Any]) -> dict[str, Any]:
        """Return {status: admitted|rejected, reasons: list[str], ...}."""
        ...


AdmissionRequest = dict[str, Any]
AdmissionResult = dict[str, Any]


def reset_admission_provider_cache() -> None:
    """Test helper: clear cached provider."""
    global _provider_cache
    _provider_cache = _UNSET


def _load_from_spec(spec: str) -> AdmissionPort | None:
    """Load provider from 'module.path:attr' spec."""
    if ":" not in spec:
        return None
    mod_name, attr = spec.split(":", 1)
    try:
        mod = importlib.import_module(mod_name)
        obj = getattr(mod, attr)
        if callable(obj) and not isinstance(obj, type):
            # factory
            obj = obj()
        if isinstance(obj, type):
            obj = obj()
        if hasattr(obj, "evaluate"):
            return obj  # type: ignore[return-value]
        if hasattr(obj, "evaluate_admission"):
            # Adapt legacy gateway-style objects
            return _LegacyGatewayAdapter(obj)
    except Exception as e:
        logger.debug("admission_provider_load_failed", spec=spec, error=str(e))
    return None


class _LegacyGatewayAdapter:
    """Adapt objects with evaluate_admission() to AdmissionPort.evaluate()."""

    def __init__(self, gateway: Any) -> None:
        self._gateway = gateway

    def evaluate(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._gateway.evaluate_admission(request)


def get_admission_provider() -> AdmissionPort | None:
    """Resolve and cache the admission provider (or None if unavailable)."""
    global _provider_cache
    if _provider_cache is not _UNSET:
        return _provider_cache  # type: ignore[return-value]

    provider: AdmissionPort | None = None

    # 1. Explicit env override
    env_spec = os.environ.get("AGORA_ADMISSION_PROVIDER", "").strip()
    if env_spec:
        provider = _load_from_spec(env_spec)

    # 2. entry_points
    if provider is None:
        try:
            eps = metadata.entry_points()
            # Python 3.10+ SelectableGroups; 3.13 uses .select
            selected = (
                eps.select(group="agora.admission")
                if hasattr(eps, "select")
                else eps.get("agora.admission", [])  # type: ignore[arg-type]
            )
            by_name = {ep.name: ep for ep in selected}
            # Prefer name "metaos", else first
            ordered = []
            if "metaos" in by_name:
                ordered.append(by_name["metaos"])
            ordered.extend(ep for name, ep in by_name.items() if name != "metaos")
            for ep in ordered:
                try:
                    obj = ep.load()
                    if isinstance(obj, type):
                        obj = obj()
                    if callable(obj) and not hasattr(obj, "evaluate"):
                        obj = obj()
                    if hasattr(obj, "evaluate"):
                        provider = obj
                        break
                    if hasattr(obj, "evaluate_admission"):
                        provider = _LegacyGatewayAdapter(obj)
                        break
                except Exception as e:
                    logger.debug(
                        "admission_entry_point_failed",
                        name=ep.name,
                        error=str(e),
                    )
        except Exception as e:
            logger.debug("admission_entry_points_unavailable", error=str(e))

    # 3. Soft import known providers
    if provider is None:
        for spec in _SOFT_PROVIDERS:
            provider = _load_from_spec(spec)
            if provider is not None:
                break

    _provider_cache = provider
    if provider is None:
        logger.info("admission_provider_unavailable", mode=_missing_mode())
    else:
        logger.info("admission_provider_bound", provider=type(provider).__name__)
    return provider


def _missing_mode() -> str:
    mode = os.environ.get("AGORA_ADMISSION_MODE", "required").strip().lower()
    return mode if mode in {"required", "strict", "degraded"} else "required"


def evaluate_admission(request: dict[str, Any]) -> dict[str, Any]:
    """Public SPI entry: evaluate admission request.

    Never raises ImportError for missing metaos — returns structured result.
    """
    provider = get_admission_provider()
    if provider is None:
        mode = _missing_mode()
        if mode in {"required", "strict"}:
            return {
                "status": "rejected",
                "reasons": [
                    ("[SPI] Admission provider unavailable "
                    f"(AGORA_ADMISSION_MODE={mode}); fail-closed.")
                ],
                "provider": None,
            }
        return {
            "status": "admitted",
            "reasons": [
                ("[SPI] Admission provider unavailable; degraded admit "
                "(AGORA_ADMISSION_MODE=degraded, explicit local-dev opt-in).")
            ],
            "provider": None,
            "degraded": True,
        }

    result = provider.evaluate(request)
    if not isinstance(result, dict) or "status" not in result:
        return {
            "status": "rejected",
            "reasons": ["[SPI] Provider returned invalid result shape."],
            "provider": type(provider).__name__,
        }
    # Normalize
    out = dict(result)
    out.setdefault("reasons", [])
    out["provider"] = type(provider).__name__
    return out
