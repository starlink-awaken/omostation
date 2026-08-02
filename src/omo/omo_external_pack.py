"""Governed persistence for safe external-resource pack proposals.

This broker stores only the validated, credential-free projection produced by
the root pack checker. It never installs or imports a provider, runs a health
probe, writes Workflow Mesh state, or creates an admission.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omo.omo_io import AppendOnlyLog, fcntl_lock

PROPOSAL_CHECK_SCHEMA = "external-resource-pack-check/v1"
PROPOSAL_OBSERVATION_SCHEMA = "external-resource-pack-proposal-observation/v1"
PROPOSAL_PREVIEW_SCHEMA = "external-resource-pack-catalog-preview/v1"
PROPOSAL_LOG = Path("_knowledge/workflow-mesh/external-resource-pack-proposals.jsonl")
_REVIEW_ACTIONS = frozenset({"submit", "defer", "request_changes"})
_STATUS = frozenset({"proposal_only", "ready_for_catalog_preview"})
_FORBIDDEN_KEYS = frozenset(
    {
        "access_token",
        "authorization",
        "cookie",
        "content",
        "input_data",
        "output",
        "output_data",
        "password",
        "private_key",
        "raw_content",
        "raw_input",
        "raw_output",
        "refresh_token",
        "secret",
        "token",
    }
)


class ExternalResourcePackProposalError(ValueError):
    """Raised when a pack proposal cannot be safely persisted."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()}"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, field: str, *, max_length: int = 240) -> str:
    text = str(value or "").strip()
    if not text:
        raise ExternalResourcePackProposalError(f"missing required field: {field}")
    if len(text) > max_length:
        raise ExternalResourcePackProposalError(f"field is too long: {field}")
    return text


def _reject_forbidden(value: Any, path: str = "proposal") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ExternalResourcePackProposalError(
                    f"forbidden raw or secret field: {path}.{key}"
                )
            _reject_forbidden(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_forbidden(nested, f"{path}[{index}]")


def _pack_summary(value: Any) -> dict[str, str | None]:
    if not isinstance(value, Mapping):
        raise ExternalResourcePackProposalError("projection.pack must be an object")
    return {
        "pack_id": _text(value.get("pack_id"), "projection.pack.pack_id"),
        "pack_version": _text(value.get("pack_version"), "projection.pack.pack_version"),
        "provider": _text(value.get("provider"), "projection.pack.provider"),
    }


def _preview_summary(value: Any, status: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ExternalResourcePackProposalError("projection.catalog_preview must be an object")
    if value.get("schema") != PROPOSAL_PREVIEW_SCHEMA:
        raise ExternalResourcePackProposalError("catalog preview schema is invalid")
    if value.get("mode") != "read_only_pack_preview":
        raise ExternalResourcePackProposalError("catalog preview must be read_only_pack_preview")
    if value.get("activation") != "forbidden":
        raise ExternalResourcePackProposalError("catalog preview activation must be forbidden")
    if value.get("status") != status:
        raise ExternalResourcePackProposalError("catalog preview status does not match check")
    resource = value.get("resource")
    if not isinstance(resource, Mapping):
        raise ExternalResourcePackProposalError("catalog preview resource must be an object")
    health = resource.get("health")
    if resource.get("availability") != "unobserved":
        raise ExternalResourcePackProposalError("pack proposal availability must be unobserved")
    if not isinstance(health, Mapping) or health.get("status") != "unobserved":
        raise ExternalResourcePackProposalError("pack proposal health must be unobserved")
    capabilities = resource.get("capabilities", [])
    if not isinstance(capabilities, list) or len(capabilities) > 64:
        raise ExternalResourcePackProposalError(
            "catalog preview capabilities must be a bounded list"
        )
    return {
        "schema": PROPOSAL_PREVIEW_SCHEMA,
        "status": status,
        "resource": {
            "id": _text(resource.get("id"), "catalog_preview.resource.id"),
            "kind": _text(resource.get("kind"), "catalog_preview.resource.kind", max_length=80),
            "provider": _text(resource.get("provider"), "catalog_preview.resource.provider"),
            "version": _text(resource.get("version"), "catalog_preview.resource.version", max_length=80),
            "lifecycle": _text(resource.get("lifecycle"), "catalog_preview.resource.lifecycle", max_length=80),
            "mode": _text(resource.get("mode"), "catalog_preview.resource.mode", max_length=80),
            "capabilities": [
                _text(item, "catalog_preview.resource.capabilities.item", max_length=80)
                for item in capabilities
            ],
            "permission_ref": _text(
                resource.get("permission_ref"), "catalog_preview.resource.permission_ref"
            ),
            "availability": "unobserved",
            "health": {
                "status": "unobserved",
                "source": _text(
                    health.get("source"), "catalog_preview.resource.health.source", max_length=160
                ),
            },
        },
        "next_action": _text(value.get("next_action"), "catalog_preview.next_action", max_length=500),
    }


def _normalise_projection(projection: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(projection, Mapping):
        raise ExternalResourcePackProposalError("projection must be an object")
    _reject_forbidden(projection)
    if projection.get("schema") != PROPOSAL_CHECK_SCHEMA:
        raise ExternalResourcePackProposalError("unexpected pack check schema")
    if projection.get("mode") != "read_only_conformance":
        raise ExternalResourcePackProposalError("pack check must be read_only_conformance")
    if projection.get("activation") != "forbidden":
        raise ExternalResourcePackProposalError("pack check activation must be forbidden")
    status = _text(projection.get("status"), "projection.status", max_length=80)
    if status not in _STATUS:
        raise ExternalResourcePackProposalError(
            "only proposal_only or ready_for_catalog_preview can be persisted"
        )
    reason_codes = projection.get("reason_codes", [])
    if not isinstance(reason_codes, list) or len(reason_codes) > 64:
        raise ExternalResourcePackProposalError("projection.reason_codes must be a bounded list")
    return {
        "schema": PROPOSAL_CHECK_SCHEMA,
        "status": status,
        "reason_codes": [
            _text(item, "projection.reason_codes.item", max_length=160)
            for item in reason_codes
        ],
        "pack": _pack_summary(projection.get("pack")),
        "catalog_preview": _preview_summary(projection.get("catalog_preview"), status),
    }


def _log(omo_dir: Path) -> AppendOnlyLog:
    path = omo_dir / PROPOSAL_LOG
    return AppendOnlyLog(path, lock=fcntl_lock(path.with_suffix(path.suffix + ".lock")))


def read_external_resource_pack_proposals(omo_dir: Path | str) -> list[dict[str, Any]]:
    """Read proposal observations in append order."""
    records = _log(Path(omo_dir)).read_all()
    if not all(isinstance(record, Mapping) for record in records):
        raise ExternalResourcePackProposalError("proposal log contains a non-object")
    return [dict(record) for record in records]


def record_external_resource_pack_proposal(
    omo_dir: Path | str,
    projection: Mapping[str, Any],
    *,
    proposal_id: str,
    review_action: str = "submit",
    actor: str = "cockpit",
    source_ref: str = "omo:external-resources:pack-proposal",
    review_ref: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Persist a safe human review receipt without mutating runtime state."""
    normalised = _normalise_projection(projection)
    proposal_id = _text(proposal_id, "proposal_id")
    review_action = _text(review_action, "review_action", max_length=64)
    if review_action not in _REVIEW_ACTIONS:
        raise ExternalResourcePackProposalError("unsupported review_action")
    actor = _text(actor or "cockpit", "actor")
    source_ref = _text(source_ref or "omo:external-resources:pack-proposal", "source_ref", max_length=500)
    if review_ref is not None:
        review_ref = _text(review_ref, "review_ref", max_length=500)
        if not review_ref.startswith(("evidence://", "vault://redacted/")):
            raise ExternalResourcePackProposalError("review_ref must be an evidence or redacted vault reference")
    recorded = recorded_at or _utc_now()
    try:
        datetime.fromisoformat(recorded.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExternalResourcePackProposalError("invalid recorded_at") from exc

    material = {
        "proposal_id": proposal_id,
        "projection": normalised,
        "review_action": review_action,
        "review_ref": review_ref,
    }
    proposal_digest = _digest(material)
    record = {
        "schema": PROPOSAL_OBSERVATION_SCHEMA,
        "proposal_receipt_id": f"external-pack-proposal:{proposal_digest[7:31]}",
        "proposal_id": proposal_id,
        "proposal_digest": proposal_digest,
        "proposal_status": normalised["status"],
        "review_action": review_action,
        "review_ref": review_ref,
        "activation": "forbidden",
        "persistence": "omo_append_only",
        "provider_invocation": False,
        "external_side_effects": "disabled",
        "pack": normalised["pack"],
        "catalog_preview": normalised["catalog_preview"],
        "reason_codes": normalised["reason_codes"],
        "next_stage": (
            "catalog_discovery"
            if normalised["status"] == "ready_for_catalog_preview"
            else "proposal_evaluation"
        ),
        "recorded_at": recorded,
        "actor": actor,
        "source_ref": source_ref,
    }
    log = _log(Path(omo_dir))
    for existing in log.read_all():
        if existing.get("proposal_id") != proposal_id:
            continue
        if existing.get("proposal_digest") != proposal_digest:
            raise ExternalResourcePackProposalError("conflicting duplicate proposal_id")
        return {"status": "deduplicated", "proposal": existing}
    log.append(record, sort_keys=True)
    return {"status": "recorded", "proposal": record}


__all__ = [
    "PROPOSAL_LOG",
    "PROPOSAL_OBSERVATION_SCHEMA",
    "ExternalResourcePackProposalError",
    "read_external_resource_pack_proposals",
    "record_external_resource_pack_proposal",
]
