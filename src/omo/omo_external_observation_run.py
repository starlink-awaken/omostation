"""Durable run-level receipts for a read-only external catalog observation.

This is an operational receipt for discovery and explicit health probes. It is
not a business result, a WorkflowRun transition, an admission decision, or a
provider invocation receipt.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omo.omo_io import AppendOnlyLog, fcntl_lock

RUN_SCHEMA = "external-resource-observation-run/v1"
RUN_LOG = Path("_knowledge/workflow-mesh/external-resource-observation-runs.jsonl")
_RESULT_STATES = frozenset({"succeeded", "degraded", "unavailable"})
_COST_STATES = frozenset({"unmetered", "estimated", "measured"})
_FORBIDDEN_KEYS = frozenset(
    {
        "access_token",
        "authorization",
        "content",
        "cookie",
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


class ExternalObservationRunError(ValueError):
    """Raised when a read-only observation run is malformed or unsafe."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()}"


def _required_text(value: Any, field: str, *, max_length: int = 500) -> str:
    text = str(value or "").strip()
    if not text:
        raise ExternalObservationRunError(f"missing required field: {field}")
    if len(text) > max_length:
        raise ExternalObservationRunError(f"field is too long: {field}")
    return text


def _timestamp(value: Any, field: str) -> str:
    text = _required_text(value, field, max_length=64)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExternalObservationRunError(f"invalid timestamp: {field}") from exc
    return text


def _number(value: Any, field: str, *, integer: bool = False) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ExternalObservationRunError(f"{field} must be a non-negative number")
    if integer and not isinstance(value, int):
        raise ExternalObservationRunError(f"{field} must be an integer")
    return value


def _reject_forbidden(value: Any, path: str = "observation_run") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                raise ExternalObservationRunError(f"forbidden raw or secret field: {path}.{key}")
            _reject_forbidden(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_forbidden(nested, f"{path}[{index}]")


def _summary(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ExternalObservationRunError("summary must be an object")
    allowed = {
        "resource_count",
        "healthy_count",
        "degraded_count",
        "unavailable_count",
        "error_count",
        "probe_count",
        "probe_failure_count",
    }
    unknown = set(value) - allowed
    if unknown:
        raise ExternalObservationRunError(f"summary contains unsupported fields: {sorted(unknown)}")
    return {
        key: int(_number(value.get(key, 0), f"summary.{key}", integer=True))
        for key in sorted(allowed)
    }


def _latency(value: Any) -> dict[str, int | float | None]:
    if not isinstance(value, Mapping):
        raise ExternalObservationRunError("latency must be an object")
    allowed = {"duration_ms", "probe_latency_ms_sum", "probe_latency_ms_max"}
    unknown = set(value) - allowed
    if unknown:
        raise ExternalObservationRunError(f"latency contains unsupported fields: {sorted(unknown)}")
    result: dict[str, int | float | None] = {}
    for key in sorted(allowed):
        nested = value.get(key)
        result[key] = None if nested is None else _number(nested, f"latency.{key}")
    if result["duration_ms"] is None:
        raise ExternalObservationRunError("latency.duration_ms is required")
    return result


def _cost(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ExternalObservationRunError("cost must be an object")
    allowed = {"state", "amount", "currency", "basis"}
    unknown = set(value) - allowed
    if unknown:
        raise ExternalObservationRunError(f"cost contains unsupported fields: {sorted(unknown)}")
    state = _required_text(value.get("state"), "cost.state", max_length=32).lower()
    if state not in _COST_STATES:
        raise ExternalObservationRunError(f"unsupported cost state: {state}")
    amount = value.get("amount")
    if state == "unmetered" and amount is not None:
        raise ExternalObservationRunError("unmetered cost must not claim an amount")
    if amount is not None:
        amount = _number(amount, "cost.amount")
    return {
        "state": state,
        "amount": amount,
        "currency": _required_text(value.get("currency"), "cost.currency", max_length=16),
        "basis": _required_text(value.get("basis"), "cost.basis", max_length=160),
    }


def _normalise(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ExternalObservationRunError("observation run must be an object")
    _reject_forbidden(payload)
    allowed = {
        "schema",
        "run_id",
        "trace_id",
        "activation",
        "provider_business_invocation",
        "health_probe_invocation",
        "started_at",
        "finished_at",
        "catalog_observation_id",
        "catalog_digest",
        "result_state",
        "summary",
        "latency",
        "cost",
        "actor",
        "source_ref",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise ExternalObservationRunError(f"observation run contains unsupported fields: {sorted(unknown)}")
    if payload.get("schema") != RUN_SCHEMA:
        raise ExternalObservationRunError("unexpected observation run schema")
    if payload.get("activation") != "forbidden":
        raise ExternalObservationRunError("observation run activation must be forbidden")
    if payload.get("provider_business_invocation") is not False:
        raise ExternalObservationRunError("provider business invocation must be false")
    result_state = _required_text(payload.get("result_state"), "result_state", max_length=32).lower()
    if result_state not in _RESULT_STATES:
        raise ExternalObservationRunError(f"unsupported result state: {result_state}")
    return {
        "schema": RUN_SCHEMA,
        "run_id": _required_text(payload.get("run_id"), "run_id", max_length=240),
        "trace_id": _required_text(payload.get("trace_id"), "trace_id", max_length=240),
        "activation": "forbidden",
        "provider_business_invocation": False,
        "health_probe_invocation": bool(payload.get("health_probe_invocation")),
        "started_at": _timestamp(payload.get("started_at"), "started_at"),
        "finished_at": _timestamp(payload.get("finished_at"), "finished_at"),
        "catalog_observation_id": _required_text(payload.get("catalog_observation_id"), "catalog_observation_id", max_length=240),
        "catalog_digest": _required_text(payload.get("catalog_digest"), "catalog_digest", max_length=160),
        "result_state": result_state,
        "summary": _summary(payload.get("summary")),
        "latency": _latency(payload.get("latency")),
        "cost": _cost(payload.get("cost")),
        "actor": _required_text(payload.get("actor") or "external-resource-observer", "actor", max_length=240),
        "source_ref": _required_text(payload.get("source_ref") or "omo:external-resources:observe", "source_ref"),
    }


def _log(omo_dir: Path) -> AppendOnlyLog:
    path = omo_dir / RUN_LOG
    return AppendOnlyLog(path, lock=fcntl_lock(path.with_suffix(path.suffix + ".lock")))


def read_external_observation_runs(omo_dir: Path | str) -> list[dict[str, Any]]:
    records = _log(Path(omo_dir)).read_all()
    return [dict(record) for record in records]


def record_external_observation_run(
    omo_dir: Path | str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    normalised = _normalise(payload)
    digest = _digest(normalised)
    receipt_id = f"external-observation-run:{hashlib.sha256(normalised['run_id'].encode()).hexdigest()[:32]}"
    record = {
        **normalised,
        "receipt_id": receipt_id,
        "run_digest": digest,
        "recorded_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    log = _log(Path(omo_dir))
    for existing in log.read_all():
        if existing.get("receipt_id") != receipt_id:
            continue
        if existing.get("run_digest") != digest:
            raise ExternalObservationRunError("conflicting duplicate observation run")
        return {"status": "deduplicated", "receipt": existing}
    log.append(record, sort_keys=True)
    return {"status": "recorded", "receipt": record}


__all__ = [
    "RUN_LOG",
    "RUN_SCHEMA",
    "ExternalObservationRunError",
    "read_external_observation_runs",
    "record_external_observation_run",
]
