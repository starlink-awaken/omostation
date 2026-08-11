"""Policy Enforcement Port / PEP (BET-Y1Q2-T1-06).

Shared injectable policy enforcement for Agora gateway routes.

Design mirrors ``admission/port.py`` — a Protocol-based SPI with provider
loading via env / entry_points / soft import.  **Never hard-imports OMO.**

Core types:
    - CapabilityDescriptor  (effectful / read_only / unknown + risk)
    - PolicyRequest          (what the caller wants to do)
    - PolicyDecision         (allow / deny from the provider)
    - ActionReceipt          (terminal outcome record)

Enforcement rules (trusted local single-user boundary):
    1. Unknown effect metadata → deny
    2. Real read-only discovery/status → auto-allow (no regression)
    3. Caller can only tighten (most restrictive wins)
    4. Decision + started not persisted → provider.calls stays 0
    5. Terminal not confirmed → cannot return succeeded
    6. Re-match decision context hash adjacent to provider dispatch
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import time
from dataclasses import dataclass, field
from importlib import metadata as _ilmd
from typing import Any, Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)

# ── Enums (string literals — no enum import needed for KISS) ─────────────

EffectClass = str  # "read_only" | "effectful" | "unknown"
RiskLevel = str  # "low" | "medium" | "high"
Effect = str  # "allow" | "deny"

READ_ONLY = "read_only"
EFFECTFUL = "effectful"
UNKNOWN = "unknown"

# ── Data classes ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CapabilityDescriptor:
    """Server-side capability classification.

    ``effect_class`` drives the baseline policy:
      - read_only → auto-allow baseline
      - effectful → requires explicit PolicyDecision allow
      - unknown   → deny (fail-closed)

    ``risk_level`` is advisory metadata the provider may consult.
    """

    effect_class: EffectClass = UNKNOWN
    risk_level: RiskLevel = "low"


@dataclass(frozen=True)
class PolicyRequest:
    """What the caller wants to do — input to ``evaluate``."""

    uri: str = ""
    tool_name: str = ""
    operation: str = "read"  # "read" | "write" | "discover"
    caller_id: str = "anonymous"
    arguments: dict[str, Any] = field(default_factory=dict)
    capability_descriptor: CapabilityDescriptor | None = None


@dataclass(frozen=True)
class PolicyDecision:
    """Decision returned by the provider (or default policy).

    ``decision_hash`` binds the decision to the exact request context
    so the PEP can re-match before provider dispatch.
    """

    effect: Effect = "deny"
    reason: str = ""
    provider: str = ""
    decision_hash: str = ""
    capability_descriptor: CapabilityDescriptor | None = None


@dataclass
class ActionReceipt:
    """Terminal outcome record — persisted to the event log."""

    decision_hash: str = ""
    status: str = "started"  # "started" | "succeeded" | "failed"
    provider_calls: int = 0
    uri: str = ""
    tool_name: str = ""
    duration_ms: int = 0
    error: str = ""


# ── Event log entry ──────────────────────────────────────────────────────


@dataclass
class PolicyEvent:
    """Ordered event in the enforcement audit trail."""

    timestamp: float
    kind: str  # "evaluated" | "started" | "succeeded" | "failed"
    decision_hash: str
    detail: str = ""


# ── Built-in read-only tool set (discovery / status — no regression) ─────

_BUILTIN_READ_ONLY: frozenset[str] = frozenset(
    {
        "list_bos_resources",
        "list_bos_domains",
        "list_bos_tools",
        "get_bos_schema",
        "bos_middleware_status",
        "bos_metrics_status",
        "bos_health",
        "bos_reload_m1",
        "bos_reload_discovery",
        "read_resource",
        "resolve_bos_uri",
        "watch_resource",
        "bos_inbox_status",
        "bos_inbox_search",
        "bos_inbox_pending",
        "bos_inbox_watch",
        "bos_inbox_triage",
        "bos_inbox_draft",
        "unwatch_resource",
    }
)


def _lookup_capability_descriptor(
    uri: str = "", tool_name: str = ""
) -> CapabilityDescriptor:
    """Determine the capability descriptor from server-side metadata.

    Rules:
      - Built-in read-only tools → read_only
      - mutate_resource → effectful
      - Unknown → unknown (will deny)
    """
    if tool_name in _BUILTIN_READ_ONLY:
        return CapabilityDescriptor(effect_class=READ_ONLY, risk_level="low")
    if tool_name == "mutate_resource":
        return CapabilityDescriptor(effect_class=EFFECTFUL, risk_level="medium")
    # URI-based heuristics for BOS routes
    if uri:
        # discovery / status patterns
        lower_uri = uri.lower()
        if any(
            kw in lower_uri
            for kw in ("list", "discover", "status", "health", "schema", "metrics")
        ):
            return CapabilityDescriptor(effect_class=READ_ONLY, risk_level="low")
        if any(
            kw in lower_uri
            for kw in ("mutate", "create", "update", "delete", "write", "archive")
        ):
            return CapabilityDescriptor(effect_class=EFFECTFUL, risk_level="medium")
    return CapabilityDescriptor(effect_class=UNKNOWN)


# ── Request hash ─────────────────────────────────────────────────────────


def compute_request_hash(request: PolicyRequest) -> str:
    """Deterministic hash of the request context for decision re-matching."""
    payload = json.dumps(
        {
            "uri": request.uri,
            "tool_name": request.tool_name,
            "operation": request.operation,
            "caller_id": request.caller_id,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ── Protocol (SPI) ───────────────────────────────────────────────────────


@runtime_checkable
class PolicyEnforcementPort(Protocol):
    """SPI: evaluate policy and record outcomes.

    ECOS / OMO / external providers implement this interface.
    Agora never hard-imports OMO — providers are resolved via the same
    binding chain as AdmissionPort (env → entry_points → soft import).
    """

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        """Evaluate whether the request is permitted."""
        ...

    def record_outcome(self, receipt: ActionReceipt) -> None:
        """Record the terminal outcome of an evaluated request."""
        ...


# ── Provider resolution (mirrors admission/port.py) ──────────────────────

_SOFT_PROVIDERS: tuple[str, ...] = (
    "ecos.ssot.tools.policy_provider:PROVIDER",
)

_UNSET: object = object()
_provider_cache: PolicyEnforcementPort | None | object = _UNSET


def _missing_mode() -> str:
    mode = os.environ.get("AGORA_PEP_MODE", "required").strip().lower()
    return mode if mode in {"required", "degraded"} else "required"


def reset_pep_provider_cache() -> None:
    """Test helper: clear cached provider."""
    global _provider_cache
    _provider_cache = _UNSET


def _load_from_spec(spec: str) -> PolicyEnforcementPort | None:
    """Load provider from 'module.path:attr' spec."""
    if ":" not in spec:
        return None
    mod_name, attr = spec.split(":", 1)
    try:
        mod = importlib.import_module(mod_name)
        obj = getattr(mod, attr)
        if callable(obj) and not isinstance(obj, type):
            obj = obj()
        if isinstance(obj, type):
            obj = obj()
        if hasattr(obj, "evaluate") and hasattr(obj, "record_outcome"):
            return obj  # type: ignore[return-value]
    except Exception as e:
        logger.debug("pep_provider_load_failed", spec=spec, error=str(e))
    return None


def get_pep_provider() -> PolicyEnforcementPort | None:
    """Resolve and cache the PEP provider (or None if unavailable).

    Binding order (first match wins):
    1. env AGORA_PEP_PROVIDER = "module:attr"
    2. entry_points group "agora.pep"
    3. soft import of known providers
    """
    global _provider_cache
    if _provider_cache is not _UNSET:
        return _provider_cache  # type: ignore[return-value]

    provider: PolicyEnforcementPort | None = None

    # 1. Explicit env override
    env_spec = os.environ.get("AGORA_PEP_PROVIDER", "").strip()
    if env_spec:
        provider = _load_from_spec(env_spec)

    # 2. entry_points
    if provider is None:
        try:
            eps = _ilmd.entry_points()
            selected = (
                eps.select(group="agora.pep")
                if hasattr(eps, "select")
                else eps.get("agora.pep", [])  # type: ignore[arg-type]
            )
            for ep in selected:
                try:
                    obj = ep.load()
                    if isinstance(obj, type):
                        obj = obj()
                    if hasattr(obj, "evaluate") and hasattr(obj, "record_outcome"):
                        provider = obj  # type: ignore[reportAssignmentType]
                        break
                except Exception as e:
                    logger.debug("pep_entry_point_failed", name=ep.name, error=str(e))
        except Exception as e:
            logger.debug("pep_entry_points_unavailable", error=str(e))

    # 3. Soft import known providers
    if provider is None:
        for spec in _SOFT_PROVIDERS:
            provider = _load_from_spec(spec)
            if provider is not None:
                break

    _provider_cache = provider
    if provider is None:
        logger.info("pep_provider_unavailable", mode=_missing_mode())
    else:
        logger.info("pep_provider_bound", provider=type(provider).__name__)
    return provider


# ── PolicyEnforcementPoint (singleton wrapper) ───────────────────────────


class PolicyEnforcementPoint:
    """Singleton PEP — wraps provider + maintains ordered event log.

    Enforces:
      1. Unknown effect → deny
      2. read_only → allow baseline
      3. Caller can only tighten (provider deny overrides default allow)
      4. decision + started persisted → provider_calls tracked
      5. Terminal not confirmed → cannot return succeeded
      6. Re-match decision hash before provider dispatch
    """

    def __init__(self) -> None:
        self._events: list[PolicyEvent] = []
        # decision_hash → (decision, started_bool)
        self._decisions: dict[str, PolicyDecision] = {}
        self._started: dict[str, bool] = {}
        # decision_hash → provider_call_count
        self._provider_calls: dict[str, int] = {}

    def clear(self) -> None:
        """Test helper: reset all state."""
        self._events.clear()
        self._decisions.clear()
        self._started.clear()
        self._provider_calls.clear()

    @property
    def events(self) -> list[PolicyEvent]:
        """Ordered audit trail."""
        return list(self._events)

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        """Evaluate request, persist decision, return PolicyDecision.

        Merges baseline (capability descriptor) with provider SPI.
        Most restrictive wins (caller can only tighten).
        """
        desc = request.capability_descriptor or _lookup_capability_descriptor(
            request.uri, request.tool_name
        )
        request_with_desc = PolicyRequest(
            uri=request.uri,
            tool_name=request.tool_name,
            operation=request.operation,
            caller_id=request.caller_id,
            arguments=request.arguments,
            capability_descriptor=desc,
        )
        h = compute_request_hash(request_with_desc)

        # Rule 1: unknown → deny immediately
        if desc.effect_class == UNKNOWN:
            decision = PolicyDecision(
                effect="deny",
                reason="unknown_effect_metadata",
                provider="baseline",
                decision_hash=h,
                capability_descriptor=desc,
            )
            self._persist_decision(decision)
            return decision

        # Baseline from capability descriptor
        if desc.effect_class == READ_ONLY:
            baseline = "allow"
            baseline_reason = "read_only_baseline"
        else:
            baseline = "allow"  # effectful: local trust by default
            baseline_reason = "effectful_local_trust"

        # Provider SPI (may tighten)
        provider = get_pep_provider()
        provider_effect: Effect | None = None
        provider_reason = ""
        provider_name = "default"
        if provider is not None:
            try:
                pd = provider.evaluate(request_with_desc)
                provider_effect = pd.effect
                provider_reason = pd.reason
                provider_name = type(provider).__name__
            except Exception as e:
                logger.warning("pep_provider_error", error=str(e))
                provider_effect = "deny"  # fail-closed on provider error
                provider_reason = f"provider_error: {e}"
                provider_name = "error"

        # Rule 3: most restrictive wins
        if provider_effect == "deny":
            final_effect = "deny"
            final_reason = provider_reason or "provider_deny"
        else:
            final_effect = baseline
            final_reason = baseline_reason

        decision = PolicyDecision(
            effect=final_effect,
            reason=final_reason,
            provider=provider_name,
            decision_hash=h,
            capability_descriptor=desc,
        )
        self._persist_decision(decision)
        return decision

    def _persist_decision(self, decision: PolicyDecision) -> None:
        self._decisions[decision.decision_hash] = decision
        self._events.append(
            PolicyEvent(
                timestamp=time.time(),
                kind="evaluated",
                decision_hash=decision.decision_hash,
                detail=f"effect={decision.effect} reason={decision.reason}",
            )
        )

    def record_started(self, decision_hash: str, uri: str = "") -> None:
        """Record that the provider has started executing."""
        self._started[decision_hash] = True
        self._events.append(
            PolicyEvent(
                timestamp=time.time(),
                kind="started",
                decision_hash=decision_hash,
                detail=uri,
            )
        )

    def record_provider_call(self, decision_hash: str) -> int:
        """Increment provider call count — only if decision + started persisted.

        Returns the new call count.
        Rule 4: if decision or started missing, returns 0 (no-op).
        """
        if decision_hash not in self._decisions:
            return 0
        if not self._started.get(decision_hash):
            return 0
        self._provider_calls[decision_hash] = (
            self._provider_calls.get(decision_hash, 0) + 1
        )
        return self._provider_calls[decision_hash]

    def get_provider_calls(self, decision_hash: str) -> int:
        """Return the provider call count for a decision.

        Returns 0 if decision + started not persisted.
        """
        if decision_hash not in self._decisions:
            return 0
        if not self._started.get(decision_hash):
            return 0
        return self._provider_calls.get(decision_hash, 0)

    def confirm_terminal(
        self,
        decision_hash: str,
        status: str,
        uri: str = "",
        tool_name: str = "",
        duration_ms: int = 0,
        error: str = "",
    ) -> ActionReceipt:
        """Record terminal outcome and persist to provider.

        Rule 5: terminal not confirmed → caller cannot return succeeded.
        """
        receipt = ActionReceipt(
            decision_hash=decision_hash,
            status=status,
            provider_calls=self.get_provider_calls(decision_hash),
            uri=uri,
            tool_name=tool_name,
            duration_ms=duration_ms,
            error=error,
        )
        # Persist to provider
        provider = get_pep_provider()
        if provider is not None:
            try:
                provider.record_outcome(receipt)
            except Exception as e:
                logger.warning("pep_record_outcome_error", error=str(e))

        self._events.append(
            PolicyEvent(
                timestamp=time.time(),
                kind=status,
                decision_hash=decision_hash,
                detail=f"uri={uri} calls={receipt.provider_calls}",
            )
        )
        return receipt

    def can_return_succeeded(self, decision_hash: str) -> bool:
        """Rule 5: terminal not confirmed → cannot return succeeded."""
        # Must have a terminal event (succeeded or failed)
        for evt in reversed(self._events):
            if evt.decision_hash == decision_hash and evt.kind in (
                "succeeded",
                "failed",
            ):
                return evt.kind == "succeeded"
        return False

    def rematch_decision(
        self, decision_hash: str, request: PolicyRequest
    ) -> bool:
        """Rule 6: re-match decision context hash before provider dispatch.

        Returns True if the hash matches the current request context.
        """
        current_hash = compute_request_hash(request)
        return current_hash == decision_hash

    def get_decision(self, decision_hash: str) -> PolicyDecision | None:
        return self._decisions.get(decision_hash)


# ── Module-level singleton ───────────────────────────────────────────────

_pep: PolicyEnforcementPoint | None = None


def get_pep() -> PolicyEnforcementPoint:
    """Get the singleton PEP instance."""
    global _pep
    if _pep is None:
        _pep = PolicyEnforcementPoint()
    return _pep


def reset_pep() -> None:
    """Test helper: reset the singleton."""
    global _pep
    _pep = None


# ── Convenience module-level API ─────────────────────────────────────────


def evaluate_policy(
    uri: str = "",
    tool_name: str = "",
    operation: str = "read",
    caller_id: str = "anonymous",
    arguments: dict[str, Any] | None = None,
) -> PolicyDecision:
    """Evaluate a policy request and return the decision.

    Convenience wrapper around ``get_pep().evaluate()``.
    """
    request = PolicyRequest(
        uri=uri,
        tool_name=tool_name,
        operation=operation,
        caller_id=caller_id,
        arguments=arguments or {},
    )
    return get_pep().evaluate(request)


def is_read_only(uri: str = "", tool_name: str = "") -> bool:
    """Quick check: is this capability read-only?"""
    desc = _lookup_capability_descriptor(uri, tool_name)
    return desc.effect_class == READ_ONLY
