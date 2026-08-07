"""Shared data models for the External Connection Fabric.

Pure data/contract surface split out of ``agora.external_connections`` so the
executable boundary module stays under the god-module line limit.  This module
owns the constants, validation helpers and frozen dataclasses; it contains no
runtime state and no invocation logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
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
        raise ExternalConnectionError(
            f"{field_name} must contain at most {maximum} refs"
        )
    return refs


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
            failure_cost=_required_text(value.get("failure_cost"), "failure_cost"),
            data_classification=_required_text(
                value.get("data_classification"), "data_classification"
            ),
            data_scope=_required_text(value.get("data_scope"), "data_scope"),
            operator=_required_text(value.get("operator"), "operator"),
            permission_ref=_required_text(
                value.get("permission_ref"), "permission_ref"
            ),
            rollback_plan=_required_text(value.get("rollback_plan"), "rollback_plan"),
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


__all__ = [
    "LIFECYCLE_TRANSITIONS",
    "RESOURCE_KINDS",
    "AdmissionDecision",
    "ConnectionReceipt",
    "DiscoveryRecord",
    "ExternalConnectionError",
    "ExternalResourceDescriptor",
    "ResourceCandidateDecision",
    "ResourceEvaluation",
    "RouteDecision",
    "SceneBinding",
    "SceneCard",
    "SceneCardDecision",
]
