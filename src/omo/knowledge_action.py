"""Durable knowledge-to-action receipts for the J2 journey.

The record is deliberately a reference plane: it proves that a knowledge
object was used to support an action without copying the source content into
OMO or turning search results into workflow state.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .omo_io import AppendOnlyLog, fcntl_lock

KNOWLEDGE_ACTION_SCHEMA = "knowledge-action/v1"
KNOWLEDGE_ACTION_LOG = Path("_knowledge/knowledge-mesh/actions.jsonl")
KNOWLEDGE_ACTION_KINDS = frozenset(
    {"retrieved", "cited", "task_created", "workflow_requested", "result_feedback_recorded"}
)
SCENE_BINDING_FIELDS = ("scene_id", "journey_id", "outcome_metric")
SCENE_REQUIRED_KINDS = frozenset(
    {"task_created", "workflow_requested", "result_feedback_recorded"}
)
KNOWLEDGE_REF_FIELDS = frozenset({"ref", "title", "source_type", "rank"})
FORBIDDEN_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "password",
        "private_key",
        "raw_content",
        "raw_input",
        "raw_output",
        "prompt",
        "model_output",
    }
)


class KnowledgeActionError(ValueError):
    """Raised when a knowledge action receipt is unsafe or inconsistent."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return f"sha256:{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()}"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _required_text(value: Any, field: str, *, max_length: int = 500) -> str:
    result = str(value or "").strip()
    if not result:
        raise KnowledgeActionError(f"missing required field: {field}")
    if len(result) > max_length:
        raise KnowledgeActionError(f"field is too long: {field}")
    return result


def _reject_forbidden(value: Any, path: str = "knowledge_action") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise KnowledgeActionError(f"forbidden raw or secret field: {path}.{key}")
            _reject_forbidden(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden(nested, f"{path}[{index}]")


def _observed_at(value: Any) -> str:
    result = _required_text(value or _utc_now(), "observed_at", max_length=64)
    try:
        datetime.fromisoformat(result.replace("Z", "+00:00"))
    except ValueError as exc:
        raise KnowledgeActionError("observed_at must be an ISO-8601 timestamp") from exc
    return result


def _scene_binding(value: Any, *, required: bool) -> dict[str, str] | None:
    if value is None and not required:
        return None
    if not isinstance(value, Mapping):
        raise KnowledgeActionError("scene_binding must be an object")
    missing = [field for field in SCENE_BINDING_FIELDS if not str(value.get(field) or "").strip()]
    if missing:
        raise KnowledgeActionError(f"scene_binding missing fields: {missing}")
    return {field: _required_text(value[field], f"scene_binding.{field}", max_length=160) for field in SCENE_BINDING_FIELDS}


def _knowledge_refs(value: Any, *, required: bool) -> list[dict[str, Any]]:
    if value is None:
        value = []
    if not isinstance(value, list):
        raise KnowledgeActionError("knowledge_refs must be a list")
    if required and not value:
        raise KnowledgeActionError("knowledge_refs must contain at least one reference")
    if len(value) > 20:
        raise KnowledgeActionError("knowledge_refs must contain at most 20 references")
    refs: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            item = {"ref": item}
        if not isinstance(item, Mapping):
            raise KnowledgeActionError(f"knowledge_refs[{index}] must be a string or object")
        unknown = sorted(set(item) - KNOWLEDGE_REF_FIELDS)
        if unknown:
            raise KnowledgeActionError(f"knowledge_refs[{index}] contains unsupported fields: {unknown}")
        ref = {"ref": _required_text(item.get("ref"), f"knowledge_refs[{index}].ref")}
        if item.get("title") is not None:
            ref["title"] = _required_text(item["title"], f"knowledge_refs[{index}].title", max_length=240)
        if item.get("source_type") is not None:
            ref["source_type"] = _required_text(item["source_type"], f"knowledge_refs[{index}].source_type", max_length=80)
        if item.get("rank") is not None:
            if not isinstance(item["rank"], int) or isinstance(item["rank"], bool) or item["rank"] < 1:
                raise KnowledgeActionError(f"knowledge_refs[{index}].rank must be a positive integer")
            ref["rank"] = item["rank"]
        refs.append(ref)
    return refs


def _normalise_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise KnowledgeActionError("knowledge action must be an object")
    _reject_forbidden(payload)
    if payload.get("schema") not in (None, KNOWLEDGE_ACTION_SCHEMA):
        raise KnowledgeActionError("unsupported knowledge action schema")
    action_kind = _required_text(payload.get("action_kind"), "action_kind", max_length=40)
    if action_kind not in KNOWLEDGE_ACTION_KINDS:
        raise KnowledgeActionError(f"unsupported action_kind: {action_kind}")
    query = str(payload.get("query") or "").strip()
    query_digest = str(payload.get("query_digest") or "").strip()
    if query:
        query_digest = _digest(query)
    if not query_digest.startswith("sha256:") or len(query_digest) != 71:
        raise KnowledgeActionError("query_digest must be a sha256 digest or query must be provided")
    refs = _knowledge_refs(payload.get("knowledge_refs"), required=action_kind in {"cited", *SCENE_REQUIRED_KINDS})
    scene_binding = _scene_binding(payload.get("scene_binding"), required=action_kind in SCENE_REQUIRED_KINDS)
    result = {
        "action_kind": action_kind,
        "query_digest": query_digest,
        "knowledge_refs": refs,
        "scene_binding": scene_binding,
        "task_ref": str(payload.get("task_ref") or "").strip(),
        "workflow_run_id": str(payload.get("workflow_run_id") or "").strip(),
        "outcome_id": str(payload.get("outcome_id") or "").strip(),
        "result_feedback_id": str(payload.get("result_feedback_id") or "").strip(),
        "observed_at": _observed_at(payload.get("observed_at")),
    }
    for field in ("task_ref", "workflow_run_id", "outcome_id", "result_feedback_id"):
        if len(result[field]) > 500:
            raise KnowledgeActionError(f"field is too long: {field}")
    if action_kind == "task_created" and not result["task_ref"]:
        raise KnowledgeActionError("task_ref is required for task_created")
    if action_kind == "workflow_requested" and not result["workflow_run_id"]:
        raise KnowledgeActionError("workflow_run_id is required for workflow_requested")
    if action_kind == "result_feedback_recorded" and not result["result_feedback_id"]:
        raise KnowledgeActionError("result_feedback_id is required for result_feedback_recorded")
    return result


def validate_knowledge_action(record: Mapping[str, Any]) -> dict[str, Any]:
    if record.get("schema") != KNOWLEDGE_ACTION_SCHEMA:
        raise KnowledgeActionError("invalid knowledge action schema")
    normalised = _normalise_payload(record)
    for field in ("action_id", "idempotency_key", "recorded_at", "actor"):
        _required_text(record.get(field), field)
    for field in normalised:
        if record.get(field) != normalised[field]:
            raise KnowledgeActionError(f"{field} mismatch")
    return dict(record)


def _log(omo_dir: Path) -> AppendOnlyLog:
    path = omo_dir / KNOWLEDGE_ACTION_LOG
    return AppendOnlyLog(path, lock=fcntl_lock(path.with_suffix(path.suffix + ".lock")))


def read_knowledge_actions(omo_dir: Path | str) -> list[dict[str, Any]]:
    return [validate_knowledge_action(record) for record in _log(Path(omo_dir)).read_all()]


def record_knowledge_action(
    omo_dir: Path | str,
    payload: Mapping[str, Any],
    *,
    actor: str = "cockpit",
) -> dict[str, Any]:
    normalised = _normalise_payload(payload)
    actor = _required_text(actor, "actor", max_length=240)
    identity = {key: normalised[key] for key in normalised if key != "observed_at"}
    action_id = f"knowledge-action:{_digest(identity)}"
    record = {
        "schema": KNOWLEDGE_ACTION_SCHEMA,
        "action_id": action_id,
        "idempotency_key": action_id,
        **normalised,
        "recorded_at": _utc_now(),
        "actor": actor,
    }
    validate_knowledge_action(record)
    log = _log(Path(omo_dir))
    for existing in log.read_all():
        if existing.get("idempotency_key") == action_id:
            return {"status": "deduplicated", "action": existing}
    log.append(record, sort_keys=True)
    return {"status": "recorded", "action": record}


def build_knowledge_action_snapshot(
    omo_dir: Path | str,
    *,
    scene_id: str | None = None,
) -> dict[str, Any]:
    records = read_knowledge_actions(omo_dir)
    if scene_id is not None:
        records = [record for record in records if (record.get("scene_binding") or {}).get("scene_id") == scene_id]
    by_kind = Counter(record["action_kind"] for record in records)
    source_counts: Counter[str] = Counter()
    for record in records:
        for ref in record["knowledge_refs"]:
            source_counts[str(ref["ref"])] += 1
    scene_rows: dict[str, dict[str, Any]] = {}
    for record in records:
        binding = record.get("scene_binding")
        key = str((binding or {}).get("scene_id") or "_unbound")
        row = scene_rows.setdefault(key, {"scene_binding": binding, "action_count": 0, "kinds": {}})
        row["action_count"] += 1
        kinds = row["kinds"]
        kinds[record["action_kind"]] = int(kinds.get(record["action_kind"], 0)) + 1
    task_refs = {record["task_ref"] for record in records if record.get("task_ref")}
    query_count = len({record["query_digest"] for record in records})
    return {
        "schema_version": "knowledge-action-operations/v1",
        "status": "live",
        "source": {"kind": "omo_append_only_knowledge_action_log", "path": str(KNOWLEDGE_ACTION_LOG), "projection": "log_derived"},
        "filter": {"scene_id": scene_id},
        "summary": {
            "action_count": len(records),
            "query_count": query_count,
            "task_count": len(task_refs),
            "by_kind": dict(sorted(by_kind.items())),
            "unique_source_count": len(source_counts),
        },
        "funnel": {
            "retrieved": by_kind.get("retrieved", 0),
            "cited": by_kind.get("cited", 0),
            "task_created": by_kind.get("task_created", 0),
            "workflow_requested": by_kind.get("workflow_requested", 0),
            "result_feedback_recorded": by_kind.get("result_feedback_recorded", 0),
        },
        "top_sources": [
            {"ref": ref, "use_count": count}
            for ref, count in source_counts.most_common(20)
        ],
        "by_scene": sorted(scene_rows.values(), key=lambda row: str((row.get("scene_binding") or {}).get("scene_id") or "_unbound")),
        "recent_actions": [
            {
                key: record[key]
                for key in ("action_id", "action_kind", "query_digest", "knowledge_refs", "scene_binding", "task_ref", "workflow_run_id", "result_feedback_id", "observed_at", "recorded_at")
            }
            for record in records[-20:]
        ],
        "next_action": (
            "record_result_feedback"
            if by_kind.get("workflow_requested")
            else "request_workflow_from_task"
            if by_kind.get("task_created")
            else "create_governed_task_from_citation"
            if by_kind.get("cited")
            else "cite_a_knowledge_result"
            if by_kind.get("retrieved")
            else "run_a_real_knowledge_search"
        ),
    }


__all__ = [
    "KNOWLEDGE_ACTION_KINDS",
    "KNOWLEDGE_ACTION_LOG",
    "KNOWLEDGE_ACTION_SCHEMA",
    "KnowledgeActionError",
    "build_knowledge_action_snapshot",
    "read_knowledge_actions",
    "record_knowledge_action",
    "validate_knowledge_action",
]
