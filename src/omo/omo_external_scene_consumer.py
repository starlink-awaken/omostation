"""Durable, proposal-only registration for an external scene consumer."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omo.omo_io import AppendOnlyLog, fcntl_lock

CONSUMER_SCHEMA = "external-scene-consumer/v1"
CONSUMER_LOG = Path("_knowledge/workflow-mesh/external-scene-consumers.jsonl")
_KINDS = frozenset({"human", "agent", "service", "workflow"})
_OPAQUE_PREFIXES = ("evidence://", "vault://redacted/", "ref://", "sample://")
_FORBIDDEN_KEYS = frozenset(
    {
        "access_token", "authorization", "content", "cookie", "document_body",
        "input_data", "output", "output_data", "password", "private_key",
        "raw_content", "raw_input", "raw_output", "refresh_token", "secret", "token",
    }
)


class ExternalSceneConsumerError(ValueError):
    """Raised when a consumer declaration is unsafe or incomplete."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()}"


def _text(value: Any, field: str, *, max_length: int = 500) -> str:
    text = str(value or "").strip()
    if not text:
        raise ExternalSceneConsumerError(f"missing required field: {field}")
    if len(text) > max_length:
        raise ExternalSceneConsumerError(f"field is too long: {field}")
    return text


def _opaque(value: Any, field: str) -> str:
    text = _text(value, field)
    if not text.startswith(_OPAQUE_PREFIXES):
        raise ExternalSceneConsumerError(f"{field} must be an opaque reference")
    return text


def _refs(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ExternalSceneConsumerError(f"{field} must be a list")
    refs = sorted({_opaque(item, f"{field}.item") for item in value})
    if not 1 <= len(refs) <= 20:
        raise ExternalSceneConsumerError(f"{field} must contain 1-20 references")
    return refs


def _binding(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ExternalSceneConsumerError("scene_binding must be an object")
    return {
        field: _text(value.get(field), f"scene_binding.{field}", max_length=240)
        for field in ("scene_id", "journey_id", "outcome_metric")
    }


def _reject_forbidden(value: Any, path: str = "consumer") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ExternalSceneConsumerError(f"forbidden raw or secret field: {path}.{key}")
            _reject_forbidden(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_forbidden(nested, f"{path}[{index}]")


def _normalise(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ExternalSceneConsumerError("consumer must be an object")
    _reject_forbidden(payload)
    allowed = {
        "schema", "consumer_id", "consumer_ref", "consumer_kind", "scene_binding", "owner_ref",
        "entrypoint_ref", "capability_ref", "permission_ref", "metric_ref", "rollback_ref",
        "evidence_refs", "status", "activation", "provider_invocation", "workflow_run_id",
        "actor", "source_ref", "observed_at",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise ExternalSceneConsumerError(f"consumer contains unsupported fields: {sorted(unknown)}")
    if payload.get("schema") != CONSUMER_SCHEMA:
        raise ExternalSceneConsumerError("unexpected consumer schema")
    if payload.get("status") != "declared":
        raise ExternalSceneConsumerError("consumer status must be declared")
    if payload.get("activation") != "forbidden":
        raise ExternalSceneConsumerError("consumer activation must be forbidden")
    if payload.get("provider_invocation") is not False:
        raise ExternalSceneConsumerError("consumer provider invocation must be false")
    if payload.get("workflow_run_id") not in (None, ""):
        raise ExternalSceneConsumerError("consumer cannot bind a WorkflowRun before promotion")
    kind = _text(payload.get("consumer_kind"), "consumer_kind", max_length=32)
    if kind not in _KINDS:
        raise ExternalSceneConsumerError(f"unsupported consumer kind: {kind}")
    observed_at = _text(payload.get("observed_at"), "observed_at", max_length=64)
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExternalSceneConsumerError("invalid timestamp: observed_at") from exc
    return {
        "schema": CONSUMER_SCHEMA,
        "consumer_id": _text(payload.get("consumer_id"), "consumer_id", max_length=240),
        "consumer_ref": _opaque(payload.get("consumer_ref"), "consumer_ref"),
        "consumer_kind": kind,
        "scene_binding": _binding(payload.get("scene_binding")),
        "owner_ref": _opaque(payload.get("owner_ref"), "owner_ref"),
        "entrypoint_ref": _opaque(payload.get("entrypoint_ref"), "entrypoint_ref"),
        "capability_ref": _opaque(payload.get("capability_ref"), "capability_ref"),
        "permission_ref": _opaque(payload.get("permission_ref"), "permission_ref"),
        "metric_ref": _opaque(payload.get("metric_ref"), "metric_ref"),
        "rollback_ref": _opaque(payload.get("rollback_ref"), "rollback_ref"),
        "evidence_refs": _refs(payload.get("evidence_refs"), "evidence_refs"),
        "status": "declared", "activation": "forbidden", "provider_invocation": False,
        "workflow_run_id": None,
        "actor": _text(payload.get("actor") or "scene-consumer", "actor", max_length=240),
        "source_ref": _text(payload.get("source_ref") or "omo:external-resources:scene-consumer", "source_ref"),
        "observed_at": observed_at,
    }


def _log(omo_dir: Path) -> AppendOnlyLog:
    path = omo_dir / CONSUMER_LOG
    return AppendOnlyLog(path, lock=fcntl_lock(path.with_suffix(path.suffix + ".lock")))


def _identity(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: nested for key, nested in value.items()
        if key not in {"actor", "source_ref", "observed_at", "recorded_at", "consumer_receipt_id", "consumer_digest"}
    }


def read_external_scene_consumers(omo_dir: Path | str) -> list[dict[str, Any]]:
    return [dict(record) for record in _log(Path(omo_dir)).read_all()]


def record_external_scene_consumer(omo_dir: Path | str, payload: Mapping[str, Any]) -> dict[str, Any]:
    normalised = _normalise(payload)
    digest = _digest(_identity(normalised))
    receipt_id = f"external-scene-consumer:{hashlib.sha256(normalised['consumer_id'].encode()).hexdigest()[:32]}"
    record = {
        **normalised,
        "consumer_receipt_id": receipt_id,
        "consumer_digest": digest,
        "recorded_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    log = _log(Path(omo_dir))
    for existing in log.read_all():
        if existing.get("consumer_receipt_id") != receipt_id:
            continue
        if existing.get("consumer_digest") != digest and _digest(_identity(existing)) != digest:
            raise ExternalSceneConsumerError("conflicting duplicate consumer_id")
        return {"status": "deduplicated", "receipt": existing}
    log.append(record, sort_keys=True)
    return {"status": "recorded", "receipt": record}


__all__ = [
    "CONSUMER_LOG", "CONSUMER_SCHEMA", "ExternalSceneConsumerError",
    "read_external_scene_consumers", "record_external_scene_consumer",
]
