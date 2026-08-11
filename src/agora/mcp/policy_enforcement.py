"""Policy Enforcement Port — narrow SPI to OMO PDP (BET-Y1Q2-T1-06).

Agora does NOT define its own PolicyDecision/ActionReceipt types.
It imports the ECOS-generated contract models and delegates to the OMO
PDP provider via the same SPI binding pattern as admission/port.py.

Rules (trusted local single-user boundary):
    1. Effectful/unknown with no provider → deny (provider.calls=0)
    2. PDP exception or ledger exception → deny (provider.calls=0)
    3. Only server-registered real read-only tools are exempt from mandate
    4. Lifecycle happens ONCE at the entry point; adapters only verify permit
    5. Terminal write-back failure → cannot return succeeded
    6. Request hash covers canonical uri/tool/operation/caller/arguments/payload
    7. No URI keyword guessing for effect classification
"""

from __future__ import annotations

import contextvars
import hashlib
import importlib
import json
import os
from contextvars import Token
from importlib import metadata as _ilmd
from typing import Any, Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)

# ── ECOS contract models (NOT mirrors) ───────────────────────────────────
# These are the SSOT types compiled from m2/*.yaml by the MOF control compiler.
# Agora must never redefine or shadow them.

try:
    from ecos.ssot.mof.generated.control.mof_control_models import (
        ActionReceipt,
        PolicyDecision,
    )
except ImportError:  # pragma: no cover — ecos always available in workspace
    ActionReceipt = None  # type: ignore[assignment,misc]
    PolicyDecision = None  # type: ignore[assignment,misc]


# ── Stable exception ─────────────────────────────────────────────────────


class PEPDenied(Exception):
    """Raised when PEP denies an operation or detects a permit violation.

    Propagates through the routing chain so callers cannot accidentally
    ignore a denial (unlike a dict return).
    """

    def __init__(self, reason: str, decision_id: str = "") -> None:
        self.reason = reason
        self.decision_id = decision_id
        super().__init__(f"PEP denied: {reason}")


# ── Server-side read-only tool registry ──────────────────────────────────
# Explicit declarations by the server code (registration.py). NOT URI keyword
# guessing — these are the server's own tools with known read-only semantics.

SERVER_READ_ONLY_TOOLS: frozenset[str] = frozenset(
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


def is_server_read_only(tool_name: str) -> bool:
    """Check if the tool is server-registered read-only (exempt from mandate)."""
    return tool_name in SERVER_READ_ONLY_TOOLS


# ── Canonical request hash ───────────────────────────────────────────────


def compute_request_hash(
    uri: str = "",
    tool_name: str = "",
    operation: str = "",
    caller_id: str = "",
    arguments: dict[str, Any] | None = None,
    payload: Any = None,
) -> str:
    """Deterministic hash covering all canonical request fields.

    Per W2-03 contract: uri/tool/operation/caller/arguments/payload.
    """
    canonical = json.dumps(
        {
            "uri": uri,
            "tool_name": tool_name,
            "operation": operation,
            "caller_id": caller_id,
            "arguments": arguments or {},
            "payload": _safe_str(payload),
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _safe_str(obj: Any) -> str:
    """Safely stringify arbitrary payload for hashing."""
    try:
        return json.dumps(obj, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(obj)


# ── ContextVar for current permit ────────────────────────────────────────
# The entry point (middleware) sets the permit; downstream adapters read it.
# This avoids changing function signatures throughout the routing chain.

_current_permit: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_pep_permit", default=None
)


def set_current_permit(permit_hash: str | None) -> Token[str | None]:
    """Set the current permit hash (called by entry point after enforce)."""
    return _current_permit.set(permit_hash)


def reset_permit(token: Token[str | None]) -> None:
    """Reset permit to previous value."""
    _current_permit.reset(token)


def get_current_permit() -> str | None:
    """Get the current permit hash (called by downstream adapters)."""
    return _current_permit.get()


# ── Narrow SPI protocol ──────────────────────────────────────────────────


@runtime_checkable
class PolicyEnforcementPort(Protocol):
    """SPI: OMO PDP provider — evaluates, persists, and confirms actions.

    The provider persists decisions and receipts to a durable ledger.
    Agora never mirrors this state; it only calls the provider.
    """

    def evaluate(self, request: dict[str, Any]) -> PolicyDecision | None:
        """Evaluate request → return persisted PolicyDecision (or None on failure)."""
        ...

    def start_receipt(self, decision: PolicyDecision) -> ActionReceipt | None:
        """Persist 'started' state before provider call (or None on failure)."""
        ...

    def confirm_receipt(
        self,
        receipt: ActionReceipt,
        status: str,
        result: dict[str, Any] | None,
        reason: str | None,
    ) -> bool:
        """Persist terminal state (succeeded|failed). Returns True on success."""
        ...


# ── Provider resolution (mirrors admission/port.py) ──────────────────────

_SOFT_PROVIDERS: tuple[str, ...] = (
    "ecos.ssot.tools.policy_provider:PROVIDER",
    "omo.integrations.pep_provider:PROVIDER",
)

_UNSET: object = object()
_provider_cache: PolicyEnforcementPort | None | object = _UNSET


def reset_pep_provider_cache() -> None:
    """Test helper: clear cached provider."""
    global _provider_cache
    _provider_cache = _UNSET


def _load_from_spec(spec: str) -> PolicyEnforcementPort | None:
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
        if hasattr(obj, "evaluate") and hasattr(obj, "start_receipt"):
            return obj  # type: ignore[return-value]
    except Exception as e:
        logger.debug("pep_provider_load_failed", spec=spec, error=str(e))
    return None


def get_pep_provider() -> PolicyEnforcementPort | None:
    """Resolve and cache the PEP provider (or None if unavailable).

    Binding order: env AGORA_PEP_PROVIDER → entry_points → soft import.
    """
    global _provider_cache
    if _provider_cache is not _UNSET:
        return _provider_cache  # type: ignore[return-value]

    provider: PolicyEnforcementPort | None = None

    env_spec = os.environ.get("AGORA_PEP_PROVIDER", "").strip()
    if env_spec:
        provider = _load_from_spec(env_spec)

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
                    if hasattr(obj, "evaluate") and hasattr(obj, "start_receipt"):
                        provider = obj  # type: ignore[reportAssignmentType]
                        break
                except Exception as e:
                    logger.debug("pep_entry_point_failed", name=ep.name, error=str(e))
        except Exception as e:
            logger.debug("pep_entry_points_unavailable", error=str(e))

    if provider is None:
        for spec in _SOFT_PROVIDERS:
            provider = _load_from_spec(spec)
            if provider is not None:
                break

    _provider_cache = provider
    if provider is None:
        logger.info("pep_provider_unavailable")
    else:
        logger.info("pep_provider_bound", provider=type(provider).__name__)
    return provider


# ── Enforcement gate (single lifecycle) ──────────────────────────────────


def enforce(
    uri: str = "",
    tool_name: str = "",
    operation: str = "read",
    caller_id: str = "anonymous",
    arguments: dict[str, Any] | None = None,
    payload: Any = None,
) -> tuple[PolicyDecision | None, ActionReceipt | None]:
    """Single-point PEP enforcement gate.

    Called ONCE at the entry point (middleware). Adapters call verify_permit().

    Returns:
        (None, None) — read-only exemption, no mandate needed.
        (PolicyDecision, ActionReceipt) — permitted by PDP.

    Raises:
        PEPDenied — on denial, provider failure, or ledger failure.
    """
    # Rule 3: server-registered read-only → exempt
    if is_server_read_only(tool_name):
        return None, None

    # Rule 1: effectful/unknown with no provider → deny
    provider = get_pep_provider()
    if provider is None:
        raise PEPDenied("pdp_unavailable")

    # Build request and expected hash
    request_dict: dict[str, Any] = {
        "uri": uri,
        "tool_name": tool_name,
        "operation": operation,
        "caller_id": caller_id,
        "arguments": arguments or {},
        "payload": payload,
    }
    expected_hash = compute_request_hash(
        uri=uri,
        tool_name=tool_name,
        operation=operation,
        caller_id=caller_id,
        arguments=arguments,
        payload=payload,
    )

    # Rule 2: PDP exception → deny
    try:
        decision = provider.evaluate(request_dict)
    except Exception as e:
        logger.warning("pep_evaluate_exception", error=str(e))
        raise PEPDenied(f"provider_failed: {e}") from e

    if decision is None:
        raise PEPDenied("pdp_unavailable")

    if decision.decision == "deny":
        raise PEPDenied(decision.reason, decision.decision_id)

    # Rule 6: verify hash match
    if decision.request_hash != expected_hash:
        raise PEPDenied("request_hash_mismatch", decision.decision_id)

    # Persist 'started' receipt before provider call
    try:
        receipt = provider.start_receipt(decision)
    except Exception as e:
        logger.warning("pep_start_receipt_exception", error=str(e))
        raise PEPDenied(f"ledger_unavailable: {e}", decision.decision_id) from e

    if receipt is None:
        raise PEPDenied("ledger_unavailable", decision.decision_id)

    return decision, receipt


def complete(
    decision: PolicyDecision | None,
    receipt: ActionReceipt | None,
    succeeded: bool,
    result: dict[str, Any] | None = None,
    error: str = "",
) -> None:
    """Complete the PEP lifecycle by confirming terminal state.

    Rule 5: if terminal write-back fails, raises PEPDenied(receipt_unconfirmed).
    No-op for read-only exemption (decision=None).
    """
    if decision is None or receipt is None:
        return  # read-only exemption

    provider = get_pep_provider()
    if provider is None:
        # Provider vanished mid-flight — can't confirm, can't succeed
        if succeeded:
            raise PEPDenied("pdp_unavailable", decision.decision_id)
        return

    status = "succeeded" if succeeded else "failed"
    reason: str | None = None
    if not succeeded:
        reason = "provider_failed" if error else "provider_failed"

    try:
        ok = provider.confirm_receipt(receipt, status, result, reason)
    except Exception as e:
        logger.warning("pep_confirm_receipt_exception", error=str(e))
        ok = False

    # Rule 5: terminal write-back failure blocks succeeded
    if not ok and succeeded:
        raise PEPDenied("receipt_unconfirmed", decision.decision_id)


def verify_permit(tool_name: str = "") -> None:
    """Verify permit at downstream adapter.

    Called by ProxyManager / MCP-stdio bridge. Raises PEPDenied if no
    permit is set and the tool is not server-registered read-only.

    The permit hash is propagated via ContextVar from the entry point.
    """
    permit = get_current_permit()
    if permit is not None:
        return  # valid permit from entry point

    # Read-only exemption
    if is_server_read_only(tool_name):
        return

    raise PEPDenied("no_permit_at_adapter")
