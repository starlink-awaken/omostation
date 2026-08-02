"""Executable boundary for the External Connection Fabric.

Agora owns discovery and capability routing. OMO remains the authority for
workflow admission and evidence persistence; this module only returns
deterministic decisions and credential-free receipts that callers can append
to the Workflow Mesh event stream.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import metadata
from typing import Any

RESOURCE_KINDS = frozenset(
    {
        "knowledge_source",
        "data_source",
        "resource_provider",
        "method_pack",
        "tool_capability",
        "channel",
        "model_provider",
    }
)
LIFECYCLE_STATES = frozenset(
    {
        "discovered",
        "sandbox",
        "admitted",
        "active",
        "degraded",
        "quarantined",
        "retired",
    }
)
LIFECYCLE_TRANSITIONS: dict[str, frozenset[str]] = {
    "discovered": frozenset({"sandbox", "retired"}),
    "sandbox": frozenset({"admitted", "discovered", "quarantined", "retired"}),
    "admitted": frozenset({"active", "sandbox", "quarantined", "retired"}),
    "active": frozenset({"degraded", "quarantined", "retired"}),
    "degraded": frozenset({"active", "quarantined", "retired"}),
    "quarantined": frozenset({"sandbox", "retired"}),
    "retired": frozenset(),
}
_SECRET_KEYS = frozenset(
    {"access_token", "refresh_token", "password", "private_key", "raw_private_content"}
)
_RAW_CONTENT_KEYS = frozenset(
    {
        "content",
        "raw_content",
        "raw_input",
        "raw_output",
        "sample_data",
        "input_data",
        "output_data",
    }
)
_OPAQUE_REF_PREFIXES = ("evidence://", "vault://redacted/")
_SCENE_CARD_MARKERS = frozenset(
    {"goal", "trigger", "input_contract", "result_contract", "sample_refs"}
)


class ExternalConnectionError(ValueError):
    """Raised when an external resource violates the fabric contract."""


def _reject_secrets(value: Any, path: str = "descriptor") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key).lower()
            if key_text in _SECRET_KEYS:
                raise ExternalConnectionError(
                    f"secret field is forbidden: {path}.{key}"
                )
            _reject_secrets(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_secrets(nested, f"{path}[{index}]")


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ExternalConnectionError(f"missing required field: {field_name}")
    return text


def _reject_raw_content(value: Any, path: str = "scene_card") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in _RAW_CONTENT_KEYS:
                raise ExternalConnectionError(
                    f"raw content field is forbidden: {path}.{key}"
                )
            _reject_raw_content(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_raw_content(nested, f"{path}[{index}]")


def _opaque_refs(
    value: Any, field_name: str, *, minimum: int, maximum: int | None = None
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        raise ExternalConnectionError(f"{field_name} must be a list of opaque refs")
    raw_refs = tuple(str(item).strip() for item in value if str(item).strip())
    invalid = [ref for ref in raw_refs if not ref.startswith(_OPAQUE_REF_PREFIXES)]
    if invalid:
        raise ExternalConnectionError(f"{field_name} contains a non-opaque ref")
    refs = tuple(sorted(set(raw_refs)))
    if len(refs) < minimum:
        raise ExternalConnectionError(
            f"{field_name} must contain at least {minimum} opaque refs"
        )
    if maximum is not None and len(refs) > maximum:
        raise ExternalConnectionError(f"{field_name} must contain at most {maximum} refs")
    return refs


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ExternalConnectionError(f"invalid timestamp: {value}") from exc


@dataclass(frozen=True)
class SceneBinding:
    """Business context required before a resource can become active."""

    scene_id: str
    journey_id: str
    outcome_metric: str
    data_scope: str
    operator: str
    permission_ref: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> SceneBinding:
        return cls(
            scene_id=_required_text(value.get("scene_id"), "scene_id"),
            journey_id=_required_text(value.get("journey_id"), "journey_id"),
            outcome_metric=_required_text(
                value.get("outcome_metric"), "outcome_metric"
            ),
            data_scope=_required_text(value.get("data_scope"), "data_scope"),
            operator=_required_text(value.get("operator"), "operator"),
            permission_ref=_required_text(
                value.get("permission_ref"), "permission_ref"
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "scene_id": self.scene_id,
            "journey_id": self.journey_id,
            "outcome_metric": self.outcome_metric,
            "data_scope": self.data_scope,
            "operator": self.operator,
            "permission_ref": self.permission_ref,
        }


@dataclass(frozen=True)
class SceneCard:
    """Business-owned activation contract for one product scene.

    A card contains descriptions and opaque references only.  It is the
    minimum evidence needed to activate an external capability; raw business
    samples and credentials remain outside Agora.
    """

    scene_id: str
    journey_id: str
    goal: str
    trigger: str
    input_contract: str
    result_contract: str
    outcome_metric: str
    consumer: str
    approver: str
    owner: str
    failure_cost: str
    data_classification: str
    data_scope: str
    operator: str
    permission_ref: str
    rollback_plan: str
    sample_refs: tuple[str, ...]
    demand_evidence_refs: tuple[str, ...] = ()
    opportunity_window: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> SceneCard:
        _reject_secrets(value)
        _reject_raw_content(value)
        return cls(
            scene_id=_required_text(value.get("scene_id"), "scene_id"),
            journey_id=_required_text(value.get("journey_id"), "journey_id"),
            goal=_required_text(value.get("goal"), "goal"),
            trigger=_required_text(value.get("trigger"), "trigger"),
            input_contract=_required_text(
                value.get("input_contract"), "input_contract"
            ),
            result_contract=_required_text(
                value.get("result_contract"), "result_contract"
            ),
            outcome_metric=_required_text(
                value.get("outcome_metric"), "outcome_metric"
            ),
            consumer=_required_text(value.get("consumer"), "consumer"),
            approver=_required_text(value.get("approver"), "approver"),
            owner=_required_text(value.get("owner"), "owner"),
            failure_cost=_required_text(
                value.get("failure_cost"), "failure_cost"
            ),
            data_classification=_required_text(
                value.get("data_classification"), "data_classification"
            ),
            data_scope=_required_text(value.get("data_scope"), "data_scope"),
            operator=_required_text(value.get("operator"), "operator"),
            permission_ref=_required_text(
                value.get("permission_ref"), "permission_ref"
            ),
            rollback_plan=_required_text(
                value.get("rollback_plan"), "rollback_plan"
            ),
            sample_refs=_opaque_refs(
                value.get("sample_refs"), "sample_refs", minimum=3, maximum=10
            ),
            demand_evidence_refs=_opaque_refs(
                value.get("demand_evidence_refs", ()),
                "demand_evidence_refs",
                minimum=0,
            ),
            opportunity_window=str(value.get("opportunity_window") or "").strip(),
        )

    def to_binding(self) -> SceneBinding:
        return SceneBinding(
            scene_id=self.scene_id,
            journey_id=self.journey_id,
            outcome_metric=self.outcome_metric,
            data_scope=self.data_scope,
            operator=self.operator,
            permission_ref=self.permission_ref,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "journey_id": self.journey_id,
            "goal": self.goal,
            "trigger": self.trigger,
            "input_contract": self.input_contract,
            "result_contract": self.result_contract,
            "outcome_metric": self.outcome_metric,
            "consumer": self.consumer,
            "approver": self.approver,
            "owner": self.owner,
            "failure_cost": self.failure_cost,
            "data_classification": self.data_classification,
            "data_scope": self.data_scope,
            "operator": self.operator,
            "permission_ref": self.permission_ref,
            "rollback_plan": self.rollback_plan,
            "sample_refs": list(self.sample_refs),
            "demand_evidence_refs": list(self.demand_evidence_refs),
            "opportunity_window": self.opportunity_window,
        }


@dataclass(frozen=True)
class SceneCardDecision:
    status: str
    scene_id: str
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "scene_id": self.scene_id,
            "reasons": list(self.reasons),
        }


def evaluate_scene_card(card: SceneCard) -> SceneCardDecision:
    """Apply the business activation gate without touching runtime state."""
    reasons: list[str] = []
    if not card.demand_evidence_refs and not card.opportunity_window:
        reasons.append("missing_demand_evidence_or_opportunity_window")
    return SceneCardDecision(
        status="eligible" if not reasons else "rejected",
        scene_id=card.scene_id,
        reasons=tuple(reasons),
    )


@dataclass(frozen=True)
class ExternalResourceDescriptor:
    """Credential-free description of one external capability."""

    id: str
    kind: str
    provider: str
    protocol: str
    capabilities: tuple[str, ...]
    data_classification: str
    provenance: Mapping[str, Any]
    lifecycle: str
    health: Mapping[str, Any]
    owner: str
    version: str
    permission_ref: str = ""
    mode: str = "live_query"
    expires_at: str | None = None
    review_at: str | None = None
    rollback_plan: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExternalResourceDescriptor:
        _reject_secrets(value)
        capabilities = value.get("capabilities")
        if not isinstance(capabilities, (list, tuple, set)) or not capabilities:
            raise ExternalConnectionError("capabilities must be a non-empty list")
        kind = _required_text(value.get("kind"), "kind")
        if kind not in RESOURCE_KINDS:
            raise ExternalConnectionError(f"unknown resource kind: {kind}")
        lifecycle = _required_text(value.get("lifecycle"), "lifecycle")
        if lifecycle not in LIFECYCLE_STATES:
            raise ExternalConnectionError(f"unknown lifecycle state: {lifecycle}")
        health = value.get("health")
        provenance = value.get("provenance")
        if not isinstance(health, Mapping):
            raise ExternalConnectionError("health must be an object")
        if not isinstance(provenance, Mapping) or not provenance:
            raise ExternalConnectionError("provenance must be a non-empty object")
        mode = str(value.get("mode") or "live_query").strip()
        if not mode:
            raise ExternalConnectionError("mode must not be empty")
        return cls(
            id=_required_text(value.get("id"), "id"),
            kind=kind,
            provider=_required_text(value.get("provider"), "provider"),
            protocol=_required_text(value.get("protocol"), "protocol"),
            capabilities=tuple(
                sorted(
                    {str(item).strip() for item in capabilities if str(item).strip()}
                )
            ),
            data_classification=_required_text(
                value.get("data_classification"), "data_classification"
            ),
            provenance=dict(provenance),
            lifecycle=lifecycle,
            health=dict(health),
            owner=_required_text(value.get("owner"), "owner"),
            version=_required_text(value.get("version"), "version"),
            permission_ref=str(value.get("permission_ref") or "").strip(),
            mode=mode,
            expires_at=str(value.get("expires_at") or "").strip() or None,
            review_at=str(value.get("review_at") or "").strip() or None,
            rollback_plan=str(value.get("rollback_plan") or "").strip(),
            metadata=dict(value.get("metadata") or {}),
        )

    def to_public_dict(self) -> dict[str, Any]:
        """Return a safe descriptor suitable for logs and UI projections."""
        return {
            "id": self.id,
            "kind": self.kind,
            "provider": self.provider,
            "protocol": self.protocol,
            "capabilities": list(self.capabilities),
            "data_classification": self.data_classification,
            "provenance": dict(self.provenance),
            "lifecycle": self.lifecycle,
            "health": dict(self.health),
            "owner": self.owner,
            "version": self.version,
            "permission_ref": self.permission_ref,
            "mode": self.mode,
            "expires_at": self.expires_at,
            "review_at": self.review_at,
            "rollback_plan": self.rollback_plan,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AdmissionDecision:
    status: str
    resource_id: str
    trace_id: str
    policy_digest: str
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "resource_id": self.resource_id,
            "trace_id": self.trace_id,
            "policy_digest": self.policy_digest,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class RouteDecision:
    status: str
    trace_id: str
    policy_digest: str
    selected_resource_id: str | None = None
    decision_factors: Mapping[str, Any] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "trace_id": self.trace_id,
            "policy_digest": self.policy_digest,
            "selected_resource_id": self.selected_resource_id,
            "decision_factors": dict(self.decision_factors),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ResourceCandidateDecision:
    """Explainable, credential-free decision for one catalog resource."""

    resource_id: str
    capability: str
    status: str
    reasons: tuple[str, ...] = ()
    decision_factors: Mapping[str, Any] = field(default_factory=dict)
    rank: tuple[Any, ...] = ()
    availability: str | None = None
    provenance_ref: str = "unavailable"

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "capability": self.capability,
            "status": self.status,
            "reasons": list(self.reasons),
            "decision_factors": dict(self.decision_factors),
            "rank": list(self.rank),
            "availability": self.availability,
            "provenance_ref": self.provenance_ref,
        }


@dataclass(frozen=True)
class ResourceEvaluation:
    """Read-only evaluation result shared by route and human observation surfaces."""

    capability: str
    trace_id: str
    policy_digest: str
    scene_binding: Mapping[str, str]
    status: str
    candidates: tuple[ResourceCandidateDecision, ...]
    selected_resource_id: str | None = None
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        eligible_count = sum(item.status == "eligible" for item in self.candidates)
        rejected_count = sum(item.status == "rejected" for item in self.candidates)
        not_applicable_count = sum(
            item.status == "not_applicable" for item in self.candidates
        )
        return {
            "schema": "external-resource-evaluation/v1",
            "mode": "read_only_evaluation",
            "activation": "forbidden",
            "raw_content_policy": "never_read_or_export",
            "capability": self.capability,
            "trace_id": self.trace_id,
            "policy_digest": self.policy_digest,
            "scene_binding": dict(self.scene_binding),
            "status": self.status,
            "selected_resource_id": self.selected_resource_id,
            "candidates": [item.to_dict() for item in self.candidates],
            "reasons": list(self.reasons),
            "summary": {
                "candidate_count": len(self.candidates),
                "eligible_count": eligible_count,
                "rejected_count": rejected_count,
                "not_applicable_count": not_applicable_count,
            },
        }


@dataclass(frozen=True)
class ConnectionReceipt:
    """Safe result of an external invocation; never carries raw output."""

    receipt_id: str
    trace_id: str
    resource_id: str
    operation: str
    result_state: str
    observed_at: str
    provenance_ref: str
    policy_digest: str
    decision_factors: Mapping[str, Any] = field(default_factory=dict)
    output_digest: str | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "trace_id": self.trace_id,
            "resource_id": self.resource_id,
            "operation": self.operation,
            "result_state": self.result_state,
            "observed_at": self.observed_at,
            "provenance_ref": self.provenance_ref,
            "policy_digest": self.policy_digest,
            "decision_factors": dict(self.decision_factors),
            "output_digest": self.output_digest,
            "error_code": self.error_code,
        }

    def evidence_payload(
        self, workflow_run_id: str, step_run_id: str | None = None
    ) -> dict[str, Any]:
        """Build a legacy-compatible payload for inspection.

        New writes must pass ``to_dict()`` through OMO's
        ``record_external_receipt`` broker; callers must not append this
        payload directly to the Workflow Mesh event log.
        """
        evidence_id = f"external:{self.resource_id}:{self.receipt_id}"
        payload = {
            "evidence_id": evidence_id,
            "evidence_schema": "external-connection-receipt/v1",
            "kind": "external_connection",
            "uri": f"external://{self.resource_id}/{self.operation}",
            "sha256": self.output_digest,
            "resource_id": self.resource_id,
            "trace_id": self.trace_id,
            "workflow_run_id": workflow_run_id,
            "result_state": self.result_state,
            "observed_at": self.observed_at,
            "provenance_ref": self.provenance_ref,
            "policy_digest": self.policy_digest,
            "receipt_id": self.receipt_id,
            "decision_factors": dict(self.decision_factors),
        }
        if step_run_id:
            payload["step_run_id"] = step_run_id
        return payload


@dataclass(frozen=True)
class DiscoveryRecord:
    descriptor: ExternalResourceDescriptor | None
    entry_point: str
    error: str | None = None
    health_override: Mapping[str, Any] | None = None


def _probe_health(provider: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Run only the provider's explicit, read-only health probe.

    Discovery must never infer health by calling an adapter's business API.
    A provider that cannot expose the probe contract is retained as an
    unavailable candidate so one bad adapter cannot hide the rest of the
    catalog.
    """
    probe = getattr(provider, "health_probe", None)
    if not callable(probe):
        return None, "missing_health_probe"
    try:
        result = probe()
        if not isinstance(result, Mapping):
            return None, "invalid_health_probe"
        _reject_secrets(result, "health_probe")
        required = ("observed_at", "status", "source")
        if any(not str(result.get(field) or "").strip() for field in required):
            return None, "invalid_health_probe"
        status = str(result["status"]).strip().lower()
        if status not in {"healthy", "degraded", "unhealthy"}:
            return None, "invalid_health_probe"
        try:
            datetime.fromisoformat(str(result["observed_at"]))
        except ValueError:
            return None, "invalid_health_probe"
        latency_ms = result["latency_ms"]
        if isinstance(latency_ms, bool) or not isinstance(
            latency_ms, (int, float)
        ) or latency_ms < 0:
            return None, "invalid_health_probe"
        return dict(result), None
    except Exception as exc:  # noqa: BLE001 - isolate one provider failure
        return None, type(exc).__name__


def _probe_failure_health() -> dict[str, Any]:
    """Force a failed probe to remain unavailable instead of reusing old health."""
    return {
        "status": "unhealthy",
        "observed_at": datetime.now(UTC).isoformat(),
        "latency_ms": None,
        "source": "agora.external_connections.health_probe",
    }


def _health_projection(
    health: Mapping[str, Any], *, now: datetime, ttl_seconds: int
) -> tuple[str, list[str], dict[str, Any]]:
    """Normalize provider health into a safe, explainable catalog state."""
    status = str(health.get("status") or "").strip().lower()
    observed_at = str(health.get("observed_at") or "").strip()
    source = str(health.get("source") or "").strip()
    latency_ms = health.get("latency_ms")
    reasons: list[str] = []

    if status not in {"healthy", "degraded", "unhealthy"}:
        reasons.append("missing_health_status")
    if not observed_at:
        reasons.append("missing_health_observed_at")
    if not source:
        reasons.append("missing_health_source")

    age_seconds: float | None = None
    if observed_at:
        try:
            age_seconds = max(0.0, (now - datetime.fromisoformat(observed_at)).total_seconds())
        except ValueError:
            reasons.append("invalid_health_observed_at")
    if age_seconds is not None and age_seconds > ttl_seconds:
        reasons.append("health_stale")

    if reasons:
        state = "stale" if "health_stale" in reasons else "unavailable"
    elif status == "healthy":
        state = "healthy"
    elif status == "degraded":
        state = "degraded"
    else:
        state = "unavailable"
        reasons.append("health_unhealthy")

    metrics = health.get("metrics")
    safe_metrics = {}
    if isinstance(metrics, Mapping):
        for key in ("trust", "freshness", "cost", "latency"):
            if key in metrics:
                safe_metrics[key] = metrics[key]
    return state, reasons, {
        "status": status or "unknown",
        "observed_at": observed_at or None,
        "source": source or None,
        "latency_ms": latency_ms,
        "age_seconds": age_seconds,
        "metrics": safe_metrics,
    }


def build_external_resource_catalog_snapshot(
    records: Iterable[DiscoveryRecord],
    *,
    observed_at: str | None = None,
    now: datetime | None = None,
    health_ttl_seconds: int = 900,
    catalog_ttl_seconds: int = 3600,
    policy_digest: str = "external-connection-fabric/v1",
) -> dict[str, Any]:
    """Build a read-only, credential-free projection for human consumers.

    The snapshot is deliberately not a runtime catalog. It exposes discovery
    facts and explicit failure reasons, while activation, invocation and OMO
    evidence remain owned by their existing boundaries.
    """
    if health_ttl_seconds <= 0:
        raise ExternalConnectionError("health_ttl_seconds must be positive")
    if catalog_ttl_seconds <= 0:
        raise ExternalConnectionError("catalog_ttl_seconds must be positive")
    current = now or datetime.now(UTC)
    resources: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    seen: dict[str, str] = {}

    for record in records:
        if record.error:
            errors.append(
                {
                    "entry_point": record.entry_point,
                    "status": "unavailable",
                    "error": record.error,
                }
            )
        descriptor = record.descriptor
        if descriptor is None:
            if not record.error:
                errors.append(
                    {
                        "entry_point": record.entry_point,
                        "status": "unavailable",
                        "error": "missing_descriptor",
                    }
                )
            continue
        previous_entry_point = seen.get(descriptor.id)
        if previous_entry_point is not None:
            errors.append(
                {
                    "entry_point": record.entry_point,
                    "status": "unavailable",
                    "error": f"duplicate_descriptor:{descriptor.id}:{previous_entry_point}",
                }
            )
            continue
        seen[descriptor.id] = record.entry_point

        health_state, health_reasons, health = _health_projection(
            record.health_override or descriptor.health,
            now=current,
            ttl_seconds=health_ttl_seconds,
        )
        reasons = list(health_reasons)
        if record.error:
            reasons.append("provider_probe_failed")
        lifecycle = descriptor.lifecycle
        if lifecycle not in {"active", "degraded"}:
            reasons.append(f"lifecycle_{lifecycle}")

        deadline = descriptor.expires_at or descriptor.review_at
        if deadline:
            try:
                if (_parse_time(deadline) or current) <= current:
                    reasons.append("descriptor_expired")
            except ExternalConnectionError:
                reasons.append("invalid_descriptor_deadline")
        else:
            reasons.append("missing_expiry_or_review")

        if descriptor.mode == "proposal_only":
            availability = "proposal_only"
        elif (
            lifecycle not in {"active", "degraded"}
            or health_state not in {"healthy", "degraded"}
            or any(
                reason in reasons
                for reason in ("descriptor_expired", "invalid_descriptor_deadline")
            )
        ):
            availability = "unavailable"
        else:
            availability = "available"

        provenance_ref = ExternalConnectionCatalog._provenance_ref(descriptor)
        resources.append(
            {
                "id": descriptor.id,
                "kind": descriptor.kind,
                "provider": descriptor.provider,
                "protocol": descriptor.protocol,
                "capabilities": list(descriptor.capabilities),
                "data_classification": descriptor.data_classification,
                "owner": descriptor.owner,
                "version": descriptor.version,
                "permission_ref": descriptor.permission_ref,
                "mode": descriptor.mode,
                "lifecycle": lifecycle,
                "availability": availability,
                "reason_codes": sorted(set(reasons)),
                "provenance_ref": provenance_ref,
                "entry_point": record.entry_point,
                "health": health,
                "rollback_plan": bool(descriptor.rollback_plan),
                "expires_at": descriptor.expires_at,
                "review_at": descriptor.review_at,
            }
        )

    resources.sort(key=lambda item: item["id"])
    by_kind: dict[str, int] = {}
    by_availability: dict[str, int] = {}
    for resource in resources:
        by_kind[resource["kind"]] = by_kind.get(resource["kind"], 0) + 1
        by_availability[resource["availability"]] = by_availability.get(resource["availability"], 0) + 1
    unavailable_count = by_availability.get("unavailable", 0) + len(errors)
    return {
        "schema": "external-resource-catalog/v1",
        "mode": "read_only_projection",
        "activation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "observed_at": observed_at or current.isoformat(),
        "health_ttl_seconds": health_ttl_seconds,
        "catalog_ttl_seconds": catalog_ttl_seconds,
        "policy_digest": policy_digest,
        "resources": resources,
        "errors": errors,
        "summary": {
            "resource_count": len(resources),
            "unavailable_count": unavailable_count,
            "error_count": len(errors),
            "by_kind": dict(sorted(by_kind.items())),
            "by_availability": dict(sorted(by_availability.items())),
        },
    }


_CATALOG_DIFF_FIELDS = (
    "provider",
    "version",
    "capabilities",
    "mode",
    "lifecycle",
    "availability",
    "reason_codes",
    "health",
    "permission_ref",
    "expires_at",
    "review_at",
    "rollback_plan",
)

_REVIEW_REQUIRED_CHANGE_FIELDS = frozenset(
    {
        "provider",
        "protocol",
        "version",
        "capabilities",
        "mode",
        "lifecycle",
        "permission_ref",
        "expires_at",
        "review_at",
        "rollback_plan",
    }
)


def _classify_catalog_change(
    change: str, changed_fields: Iterable[str]
) -> dict[str, Any]:
    """Separate admission-relevant descriptor changes from health noise."""
    fields = frozenset(changed_fields)
    if change == "added":
        return {
            "review_required": True,
            "risk_class": "manual_review",
            "risk_codes": ["resource_added"],
        }
    if change == "removed":
        return {
            "review_required": True,
            "risk_class": "manual_review",
            "risk_codes": ["resource_removed"],
        }
    if fields & _REVIEW_REQUIRED_CHANGE_FIELDS:
        return {
            "review_required": True,
            "risk_class": "manual_review",
            "risk_codes": [
                f"descriptor_{field}_changed"
                for field in sorted(fields & _REVIEW_REQUIRED_CHANGE_FIELDS)
            ],
        }
    return {
        "review_required": False,
        "risk_class": "operational_observation",
        "risk_codes": [
            f"{field}_changed" for field in sorted(fields)
        ],
    }


def _catalog_resource_view(resource: Mapping[str, Any]) -> dict[str, Any]:
    resource_id = str(resource.get("id") or "").strip()
    if not resource_id:
        raise ExternalConnectionError("catalog resource is missing id")
    return {
        key: resource.get(key)
        for key in _CATALOG_DIFF_FIELDS
        if key in resource
    }


def _catalog_resource_index(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    resources = snapshot.get("resources", [])
    if not isinstance(resources, list):
        raise ExternalConnectionError("catalog resources must be a list")
    indexed: dict[str, Mapping[str, Any]] = {}
    for resource in resources:
        if not isinstance(resource, Mapping):
            raise ExternalConnectionError("catalog resource must be an object")
        resource_id = str(resource.get("id") or "").strip()
        if not resource_id:
            raise ExternalConnectionError("catalog resource is missing id")
        if resource_id in indexed:
            raise ExternalConnectionError(f"duplicate catalog resource: {resource_id}")
        indexed[resource_id] = resource
    return indexed


def _catalog_errors(snapshot: Mapping[str, Any]) -> set[tuple[str, str, str]]:
    errors = snapshot.get("errors", [])
    if not isinstance(errors, list):
        raise ExternalConnectionError("catalog errors must be a list")
    normalized: set[tuple[str, str, str]] = set()
    for error in errors:
        if not isinstance(error, Mapping):
            raise ExternalConnectionError("catalog error must be an object")
        normalized.add(
            (
                str(error.get("entry_point") or ""),
                str(error.get("status") or ""),
                str(error.get("error") or ""),
            )
        )
    return normalized


def diff_external_resource_catalog_snapshots(
    previous: Mapping[str, Any], current: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare two safe catalog projections without persisting either one."""
    for name, snapshot in (("previous", previous), ("current", current)):
        if not isinstance(snapshot, Mapping) or snapshot.get("schema") != "external-resource-catalog/v1":
            raise ExternalConnectionError(f"{name} is not an external resource catalog")

    previous_index = _catalog_resource_index(previous)
    current_index = _catalog_resource_index(current)
    changes: list[dict[str, Any]] = []
    for resource_id in sorted(set(previous_index) | set(current_index)):
        old = previous_index.get(resource_id)
        new = current_index.get(resource_id)
        if old is None:
            item = {
                "id": resource_id,
                "change": "added",
                "changed_fields": list(_CATALOG_DIFF_FIELDS),
                "previous": None,
                "current": _catalog_resource_view(new),
            }
            item.update(_classify_catalog_change("added", item["changed_fields"]))
            changes.append(item)
            continue
        if new is None:
            item = {
                "id": resource_id,
                "change": "removed",
                "changed_fields": list(_CATALOG_DIFF_FIELDS),
                "previous": _catalog_resource_view(old),
                "current": None,
            }
            item.update(_classify_catalog_change("removed", item["changed_fields"]))
            changes.append(item)
            continue
        old_view = _catalog_resource_view(old)
        new_view = _catalog_resource_view(new)
        changed_fields = [
            field for field in _CATALOG_DIFF_FIELDS if old_view.get(field) != new_view.get(field)
        ]
        if changed_fields:
            item = {
                "id": resource_id,
                "change": "changed",
                "changed_fields": changed_fields,
                "previous": old_view,
                "current": new_view,
            }
            item.update(_classify_catalog_change("changed", changed_fields))
            changes.append(item)

    previous_errors = _catalog_errors(previous)
    current_errors = _catalog_errors(current)
    error_changes = [
        {
            "change": change,
            "entry_point": entry_point,
            "status": status,
            "error": error,
        }
        for change, error_set in (
            ("resolved", previous_errors - current_errors),
            ("added", current_errors - previous_errors),
        )
        for entry_point, status, error in sorted(error_set)
    ]
    return {
        "schema": "external-resource-catalog-diff/v1",
        "previous_observed_at": previous.get("observed_at"),
        "current_observed_at": current.get("observed_at"),
        "changes": changes,
        "error_changes": error_changes,
        "summary": {
            "change_count": len(changes),
            "added_count": sum(item["change"] == "added" for item in changes),
            "removed_count": sum(item["change"] == "removed" for item in changes),
            "changed_count": sum(item["change"] == "changed" for item in changes),
            "error_change_count": len(error_changes),
            "review_required": any(item["review_required"] for item in changes),
            "review_required_count": sum(
                item["review_required"] for item in changes
            ),
            "operational_observation_count": sum(
                item["risk_class"] == "operational_observation" for item in changes
            ),
            "risk_codes": sorted(
                {
                    code
                    for item in changes
                    for code in item["risk_codes"]
                }
            ),
        },
    }


def discover_entry_points(
    entry_points: Iterable[Any] | None = None,
    *,
    group: str = "external.resources",
    probe: bool = False,
    mark_unprobed: bool = False,
) -> list[DiscoveryRecord]:
    """Discover providers and optionally run only their explicit health probe.

    ``mark_unprobed`` is used by descriptor-only observers that need to make
    the absence of a fresh probe explicit in the catalog projection.
    """
    if entry_points is None:
        available = metadata.entry_points()
        entry_points = (
            available.select(group=group)
            if hasattr(available, "select")
            else available.get(group, [])
        )
    records: list[DiscoveryRecord] = []
    for entry_point in entry_points:
        label = f"{getattr(entry_point, 'group', group)}:{getattr(entry_point, 'name', 'unknown')}"
        try:
            loaded = entry_point.load()
            provider = loaded() if isinstance(loaded, type) else loaded
            descriptor = (
                provider.external_descriptor()
                if hasattr(provider, "external_descriptor")
                else provider
            )
            if not isinstance(descriptor, Mapping):
                raise ExternalConnectionError(
                    "provider returned a non-object descriptor"
                )
            parsed_descriptor = ExternalResourceDescriptor.from_mapping(descriptor)
            health_override = None
            probe_error = None
            if probe:
                health_override, probe_error = _probe_health(provider)
                if probe_error:
                    health_override = _probe_failure_health()
            elif mark_unprobed:
                probe_error = "health_probe_skipped"
                health_override = _probe_failure_health()
            records.append(
                DiscoveryRecord(
                    descriptor=parsed_descriptor,
                    entry_point=label,
                    error=probe_error,
                    health_override=health_override,
                )
            )
        except Exception as exc:  # noqa: BLE001 - one bad adapter must not stop discovery
            records.append(
                DiscoveryRecord(
                    descriptor=None, entry_point=label, error=type(exc).__name__
                )
            )
    return records


class ExternalConnectionCatalog:
    """In-memory catalog and deterministic router for one process boundary."""

    def __init__(self, *, policy_digest: str = "external-connection-fabric/v1") -> None:
        self.policy_digest = policy_digest
        self._resources: dict[str, ExternalResourceDescriptor] = {}

    def register(
        self, descriptor: ExternalResourceDescriptor | Mapping[str, Any]
    ) -> ExternalResourceDescriptor:
        parsed = (
            descriptor
            if isinstance(descriptor, ExternalResourceDescriptor)
            else ExternalResourceDescriptor.from_mapping(descriptor)
        )
        existing = self._resources.get(parsed.id)
        if existing and existing != parsed:
            raise ExternalConnectionError(f"conflicting descriptor: {parsed.id}")
        self._resources[parsed.id] = parsed
        return parsed

    def list(self) -> list[ExternalResourceDescriptor]:
        return [self._resources[key] for key in sorted(self._resources)]

    def get(self, resource_id: str) -> ExternalResourceDescriptor | None:
        return self._resources.get(resource_id)

    def transition(self, resource_id: str, target: str) -> ExternalResourceDescriptor:
        current = self._resources.get(resource_id)
        if current is None:
            raise ExternalConnectionError(f"unknown resource: {resource_id}")
        if target not in LIFECYCLE_STATES:
            raise ExternalConnectionError(f"unknown lifecycle state: {target}")
        if target not in LIFECYCLE_TRANSITIONS[current.lifecycle]:
            raise ExternalConnectionError(
                f"invalid lifecycle transition: {current.lifecycle} -> {target}"
            )
        updated = ExternalResourceDescriptor(
            **{**current.to_public_dict(), "lifecycle": target}
        )
        self._resources[resource_id] = updated
        return updated

    def admit(
        self,
        resource_id: str,
        scene: SceneBinding | Mapping[str, Any],
        *,
        trace_id: str,
        now: datetime | None = None,
    ) -> AdmissionDecision:
        binding = (
            scene
            if isinstance(scene, SceneBinding)
            else SceneBinding.from_mapping(scene)
        )
        resource = self._resources.get(resource_id)
        reasons: list[str] = []
        if resource is None:
            reasons.append("resource_not_found")
        else:
            if resource.lifecycle in {"retired", "quarantined", "discovered"}:
                reasons.append(f"lifecycle_{resource.lifecycle}")
            if (
                not resource.permission_ref
                or resource.permission_ref != binding.permission_ref
            ):
                reasons.append("missing_or_mismatched_permission")
            health_status = self._health_status(resource.health)
            if health_status not in {"healthy", "degraded"}:
                reasons.append("missing_or_unhealthy_health")
            if not resource.rollback_plan:
                reasons.append("missing_rollback_plan")
            if not resource.expires_at and not resource.review_at:
                reasons.append("missing_expiry_or_review")
            else:
                deadline = _parse_time(resource.expires_at or resource.review_at)
                current = now or datetime.now(UTC)
                if deadline is None or deadline <= current:
                    reasons.append("expired_descriptor")
            if not resource.provenance:
                reasons.append("missing_provenance")
        return AdmissionDecision(
            status="admitted" if not reasons else "rejected",
            resource_id=resource_id,
            trace_id=trace_id,
            policy_digest=self.policy_digest,
            reasons=tuple(reasons),
        )

    def activate(
        self,
        resource_id: str,
        scene: SceneCard | SceneBinding | Mapping[str, Any],
        *,
        trace_id: str,
        now: datetime | None = None,
    ) -> AdmissionDecision:
        if isinstance(scene, SceneCard) or (
            isinstance(scene, Mapping)
            and bool(_SCENE_CARD_MARKERS.intersection(scene))
        ):
            return self.activate_with_scene_card(
                resource_id, scene, trace_id=trace_id, now=now
            )
        decision = self.admit(resource_id, scene, trace_id=trace_id, now=now)
        if decision.status != "admitted":
            return decision
        resource = self._resources[resource_id]
        if resource.lifecycle == "sandbox":
            self.transition(resource_id, "admitted")
            self.transition(resource_id, "active")
        return decision

    def activate_with_scene_card(
        self,
        resource_id: str,
        scene: SceneCard | Mapping[str, Any],
        *,
        trace_id: str,
        now: datetime | None = None,
    ) -> AdmissionDecision:
        """Activate only after the full business Scene Card passes its gate."""
        try:
            card = scene if isinstance(scene, SceneCard) else SceneCard.from_mapping(scene)
        except ExternalConnectionError as exc:
            return AdmissionDecision(
                status="rejected",
                resource_id=resource_id,
                trace_id=trace_id,
                policy_digest=self.policy_digest,
                reasons=(f"invalid_scene_card:{exc}",),
            )
        card_decision = evaluate_scene_card(card)
        if card_decision.status != "eligible":
            return AdmissionDecision(
                status="rejected",
                resource_id=resource_id,
                trace_id=trace_id,
                policy_digest=self.policy_digest,
                reasons=tuple(
                    f"scene_card:{reason}" for reason in card_decision.reasons
                ),
            )
        decision = self.admit(
            resource_id, card.to_binding(), trace_id=trace_id, now=now
        )
        if decision.status != "admitted":
            return decision
        resource = self._resources[resource_id]
        if resource.lifecycle == "sandbox":
            self.transition(resource_id, "admitted")
            self.transition(resource_id, "active")
        return decision

    def evaluate_candidates(
        self,
        capability: str,
        scene: SceneBinding | Mapping[str, Any],
        *,
        trace_id: str,
        now: datetime | None = None,
        availability_by_resource: Mapping[str, str] | None = None,
    ) -> ResourceEvaluation:
        """Evaluate every resource without changing state or invoking providers."""
        binding = (
            scene
            if isinstance(scene, SceneBinding)
            else SceneBinding.from_mapping(scene)
        )
        requested_capability = _required_text(capability, "capability")
        availability = availability_by_resource or {}
        candidates: list[ResourceCandidateDecision] = []
        eligible: list[tuple[tuple[Any, ...], ExternalResourceDescriptor, dict[str, Any]]] = []
        rejected: list[str] = []

        for resource in self.list():
            resource_availability = availability.get(resource.id)
            provenance_ref = self._provenance_ref(resource)
            if requested_capability not in resource.capabilities:
                candidates.append(
                    ResourceCandidateDecision(
                        resource_id=resource.id,
                        capability=requested_capability,
                        status="not_applicable",
                        reasons=("capability_not_supported",),
                        availability=resource_availability,
                        provenance_ref=provenance_ref,
                    )
                )
                continue

            reasons: list[str] = []
            if resource_availability and resource_availability not in {"available", "degraded"}:
                reasons.append(f"catalog_{resource_availability}")
            if resource.lifecycle not in {"active", "degraded", "admitted"}:
                reasons.append(f"lifecycle_{resource.lifecycle}")
            if not reasons:
                admission = self.admit(
                    resource.id,
                    binding,
                    trace_id=trace_id,
                    now=now,
                )
                if admission.status != "admitted":
                    reasons.extend(admission.reasons)

            if reasons:
                rejected.extend(f"{resource.id}:{reason}" for reason in reasons)
                candidates.append(
                    ResourceCandidateDecision(
                        resource_id=resource.id,
                        capability=requested_capability,
                        status="rejected",
                        reasons=tuple(sorted(set(reasons))),
                        availability=resource_availability,
                        provenance_ref=provenance_ref,
                    )
                )
                continue

            factors = self._decision_factors(resource, binding)
            rank = (
                1 if factors["health"] == "healthy" else 0,
                factors["permission"],
                factors["trust"],
                factors["freshness"],
                -factors["cost"],
                -factors["latency"],
                resource.id,
            )
            eligible.append((rank, resource, factors))
            candidates.append(
                ResourceCandidateDecision(
                    resource_id=resource.id,
                    capability=requested_capability,
                    status="eligible",
                    decision_factors=factors,
                    rank=rank,
                    availability=resource_availability,
                    provenance_ref=provenance_ref,
                )
            )

        selected_resource_id = None
        if eligible:
            _, selected, _ = max(eligible, key=lambda item: item[0])
            selected_resource_id = selected.id
        evaluation_status = "selected" if selected_resource_id else "unavailable"
        reasons = () if selected_resource_id else ("no_eligible_candidate", *rejected)
        return ResourceEvaluation(
            capability=requested_capability,
            trace_id=trace_id,
            policy_digest=self.policy_digest,
            scene_binding=binding.to_dict(),
            status=evaluation_status,
            candidates=tuple(candidates),
            selected_resource_id=selected_resource_id,
            reasons=tuple(reasons),
        )

    def route(
        self,
        capability: str,
        scene: SceneBinding | Mapping[str, Any],
        *,
        trace_id: str,
        now: datetime | None = None,
    ) -> RouteDecision:
        evaluation = self.evaluate_candidates(
            capability,
            scene,
            trace_id=trace_id,
            now=now,
        )
        if evaluation.selected_resource_id is None:
            return RouteDecision(
                status="unavailable",
                trace_id=trace_id,
                policy_digest=self.policy_digest,
                reasons=("no_admitted_capability", *evaluation.reasons[1:]),
            )
        selected = self._resources[evaluation.selected_resource_id]
        factors = next(
            item.decision_factors
            for item in evaluation.candidates
            if item.resource_id == selected.id
        )
        return RouteDecision(
            status="selected",
            trace_id=trace_id,
            policy_digest=self.policy_digest,
            selected_resource_id=selected.id,
            decision_factors=factors,
        )

    def invoke(
        self,
        capability: str,
        scene: SceneBinding | Mapping[str, Any],
        *,
        trace_id: str,
        operation: str,
        handler: Callable[[ExternalResourceDescriptor], Any] | None = None,
        now: datetime | None = None,
    ) -> ConnectionReceipt:
        decision = self.route(capability, scene, trace_id=trace_id, now=now)
        observed_at = (now or datetime.now(UTC)).isoformat()
        resource_id = decision.selected_resource_id or "unavailable"
        descriptor = self._resources.get(resource_id)
        provenance_ref = self._provenance_ref(descriptor)
        receipt_id = self._receipt_id(trace_id, resource_id, operation)
        if decision.status != "selected" or descriptor is None:
            return ConnectionReceipt(
                receipt_id=receipt_id,
                trace_id=trace_id,
                resource_id=resource_id,
                operation=operation,
                result_state="unavailable",
                observed_at=observed_at,
                provenance_ref=provenance_ref,
                policy_digest=self.policy_digest,
                decision_factors=decision.to_dict(),
                error_code="no_route",
            )
        if descriptor.mode == "proposal_only":
            return ConnectionReceipt(
                receipt_id=receipt_id,
                trace_id=trace_id,
                resource_id=resource_id,
                operation=operation,
                result_state="proposed",
                observed_at=observed_at,
                provenance_ref=provenance_ref,
                policy_digest=self.policy_digest,
                decision_factors=decision.to_dict(),
            )
        if handler is None:
            state = (
                "degraded"
                if self._health_status(descriptor.health) == "degraded"
                else "unavailable"
            )
            return ConnectionReceipt(
                receipt_id=receipt_id,
                trace_id=trace_id,
                resource_id=resource_id,
                operation=operation,
                result_state=state,
                observed_at=observed_at,
                provenance_ref=provenance_ref,
                policy_digest=self.policy_digest,
                decision_factors=decision.to_dict(),
                error_code="invoker_unavailable",
            )
        try:
            output = handler(descriptor)
            output_digest = hashlib.sha256(
                json.dumps(
                    output, ensure_ascii=False, sort_keys=True, default=str
                ).encode()
            ).hexdigest()
            state = (
                "degraded"
                if self._health_status(descriptor.health) == "degraded"
                else "succeeded"
            )
            return ConnectionReceipt(
                receipt_id=receipt_id,
                trace_id=trace_id,
                resource_id=resource_id,
                operation=operation,
                result_state=state,
                observed_at=observed_at,
                provenance_ref=provenance_ref,
                policy_digest=self.policy_digest,
                decision_factors=decision.to_dict(),
                output_digest=output_digest,
            )
        except Exception as exc:  # noqa: BLE001 - adapter failure is an explicit receipt
            return ConnectionReceipt(
                receipt_id=receipt_id,
                trace_id=trace_id,
                resource_id=resource_id,
                operation=operation,
                result_state="failed",
                observed_at=observed_at,
                provenance_ref=provenance_ref,
                policy_digest=self.policy_digest,
                decision_factors=decision.to_dict(),
                error_code=type(exc).__name__,
            )

    @staticmethod
    def _health_status(health: Mapping[str, Any]) -> str:
        status = str(health.get("status") or "").lower()
        if status in {"healthy", "degraded", "unhealthy"}:
            return status
        if health.get("available") is True or health.get("healthy") is True:
            return "healthy"
        return "unhealthy"

    @staticmethod
    def _decision_factors(
        resource: ExternalResourceDescriptor, scene: SceneBinding
    ) -> dict[str, Any]:
        health = resource.health
        metrics = (
            health.get("metrics")
            if isinstance(health.get("metrics"), Mapping)
            else health
        )
        return {
            "health": ExternalConnectionCatalog._health_status(health),
            "permission": 1 if resource.permission_ref == scene.permission_ref else 0,
            "trust": float(metrics.get("trust", 0.0) or 0.0),
            "freshness": float(metrics.get("freshness", 0.0) or 0.0),
            "cost": float(metrics.get("cost", 0.0) or 0.0),
            "latency": float(metrics.get("latency", 0.0) or 0.0),
        }

    @staticmethod
    def _provenance_ref(resource: ExternalResourceDescriptor | None) -> str:
        if resource is None:
            return "unavailable"
        for key in ("source_ref", "uri", "adapter", "connector"):
            value = resource.provenance.get(key)
            if value:
                return str(value)
        return resource.id

    @staticmethod
    def _receipt_id(trace_id: str, resource_id: str, operation: str) -> str:
        raw = f"{trace_id}:{resource_id}:{operation}".encode()
        return f"receipt-{hashlib.sha256(raw).hexdigest()[:20]}"


def evaluate_external_resource_catalog_snapshot(
    snapshot: Mapping[str, Any],
    capability: str,
    scene: SceneBinding | Mapping[str, Any],
    *,
    trace_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate a safe catalog snapshot without activating or invoking resources."""
    _reject_secrets(snapshot, "catalog")
    _reject_raw_content(snapshot, "catalog")
    if snapshot.get("schema") != "external-resource-catalog/v1":
        raise ExternalConnectionError("catalog snapshot has an unexpected schema")
    if snapshot.get("mode") != "read_only_projection":
        raise ExternalConnectionError("catalog snapshot must be read_only_projection")
    if snapshot.get("activation") != "forbidden":
        raise ExternalConnectionError("catalog snapshot activation must be forbidden")
    resources = snapshot.get("resources")
    if not isinstance(resources, list):
        raise ExternalConnectionError("catalog resources must be a list")

    catalog = ExternalConnectionCatalog(
        policy_digest=str(snapshot.get("policy_digest") or "external-connection-fabric/v1")
    )
    availability: dict[str, str] = {}
    for resource in resources:
        if not isinstance(resource, Mapping):
            raise ExternalConnectionError("catalog resource must be an object")
        resource_id = _required_text(resource.get("id"), "resource.id")
        provenance_ref = _required_text(
            resource.get("provenance_ref"), "resource.provenance_ref"
        )
        descriptor = dict(resource)
        descriptor.pop("availability", None)
        descriptor.pop("reason_codes", None)
        descriptor.pop("entry_point", None)
        descriptor["provenance"] = {"source_ref": provenance_ref}
        descriptor["rollback_plan"] = (
            "declared" if bool(resource.get("rollback_plan")) else ""
        )
        descriptor["metadata"] = {}
        catalog.register(descriptor)
        availability[resource_id] = str(resource.get("availability") or "unavailable")

    return catalog.evaluate_candidates(
        capability,
        scene,
        trace_id=trace_id,
        now=now,
        availability_by_resource=availability,
    ).to_dict()


__all__ = [
    "LIFECYCLE_TRANSITIONS",
    "RESOURCE_KINDS",
    "AdmissionDecision",
    "ConnectionReceipt",
    "DiscoveryRecord",
    "ExternalConnectionCatalog",
    "ExternalConnectionError",
    "ExternalResourceDescriptor",
    "ResourceCandidateDecision",
    "ResourceEvaluation",
    "RouteDecision",
    "SceneBinding",
    "SceneCard",
    "SceneCardDecision",
    "build_external_resource_catalog_snapshot",
    "diff_external_resource_catalog_snapshots",
    "discover_entry_points",
    "evaluate_external_resource_catalog_snapshot",
    "evaluate_scene_card",
]
