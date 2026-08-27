from __future__ import annotations

import json
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

from cockpit.adapters.governance import _utils
from cockpit.adapters.governance_context import (
    _DOMAIN_BINDING_AUTHORITY,
    _DOMAIN_REGISTRY_AUTHORITY,
    _binding_context,
    _load_domains,
    resolve_workspace_root,
)

_FACTS_EVIDENCE_SCHEMA = "runtime.documents-facts-audit.evidence.v1"
_CONTROLLER_SHADOW_EVIDENCE_SCHEMA = "runtime.documents-controller-shadow.evidence.v2"
_MODEL_FRESHNESS_EVIDENCE_SCHEMA = "runtime.documents-model-freshness.evidence.v1"
_MODEL_FRESHNESS_EVIDENCE_AUTHORITY = "runtime-model-freshness-evidence"
_MODEL_FRESHNESS_EVIDENCE_PATH = (
    "control/evidence/documents-weijian-model-freshness/documents-weijian-model-freshness.json"
)
_SANYI_STATUS_EVIDENCE_SCHEMA = "runtime.documents-sanyi-status-consistency.evidence.v1"
_SANYI_STATUS_EVIDENCE_AUTHORITY = "runtime-sanyi-status-consistency-evidence"
_SANYI_STATUS_JOB_ID = "documents-weijian-sanyi-status-audit"
_SANYI_STATUS_EVIDENCE_PATH = (
    "control/evidence/documents-weijian-sanyi-status-audit/documents-weijian-sanyi-status-audit.json"
)
_SANYI_STATUS_ERRORS = frozenset(
    {
        "dashboard_invalid",
        "dashboard_unavailable",
        "facts_invalid",
        "facts_scope_empty",
        "facts_unavailable",
    }
)
_MODEL_FRESHNESS_ERRORS = frozenset(
    {
        "domain_root_missing",
        "domain_root_unreadable",
        "domain_root_not_direct",
        "domain_path_invalid",
        "entities_directory_missing",
        "entities_directory_unreadable",
        "entities_directory_not_direct",
        "facts_file_missing",
        "facts_file_not_regular",
        "facts_file_unreadable",
        "facts_last_reviewed_missing",
        "facts_last_reviewed_invalid",
        "models_directory_missing",
        "models_directory_unreadable",
        "models_directory_not_direct",
        "models_directory_empty",
        "model_file_not_regular",
        "model_file_unreadable",
        "model_last_reviewed_missing",
        "model_last_reviewed_invalid",
    }
)
_MODEL_FRESHNESS_PRE_FACTS_ERRORS = frozenset(
    {
        "domain_root_missing",
        "domain_root_unreadable",
        "domain_root_not_direct",
        "domain_path_invalid",
        "entities_directory_missing",
        "entities_directory_unreadable",
        "entities_directory_not_direct",
        "facts_file_missing",
        "facts_file_not_regular",
        "facts_file_unreadable",
        "facts_last_reviewed_missing",
        "facts_last_reviewed_invalid",
    }
)
_MODEL_FRESHNESS_DIRECTORY_ERRORS = frozenset(
    {
        "models_directory_missing",
        "models_directory_unreadable",
        "models_directory_not_direct",
        "models_directory_empty",
    }
)
_MODEL_FRESHNESS_REVIEWED_ERRORS = frozenset({"model_last_reviewed_missing", "model_last_reviewed_invalid"})
_CONTROLLER_SHADOW_LEGACY_RULE_IDS = (
    "CR01",
    "CR02",
    "CR03",
    "CR05",
    "CR08",
    "CR23",
    "CR24",
    "CR25",
    "CR26",
    "CR29",
    "CR30",
)
_CONTROLLER_SHADOW_OBSERVED_RULE_IDS = ("CR01", "CR02", "CR03", "CR05")
_CONTROLLER_SHADOW_UNOBSERVED_RULE_IDS = tuple(
    rule_id for rule_id in _CONTROLLER_SHADOW_LEGACY_RULE_IDS if rule_id not in _CONTROLLER_SHADOW_OBSERVED_RULE_IDS
)
_MAX_RUNTIME_RECEIPT_BYTES = 32 * 1024


def _runtime_facts_job(binding: dict[str, Any], domain_id: str) -> dict[str, str]:
    matches = [
        item
        for item in binding.get("runtime_jobs", [])
        if isinstance(item, dict)
        and item.get("domain_id") == domain_id
        and item.get("action") == "audit_structured_facts"
    ]
    if len(matches) != 1:
        raise ValueError(f"no unique runtime facts validation job configured for domain: {domain_id}")
    item = matches[0]
    job_id = item.get("id")
    owner = item.get("owner")
    evidence_schema = item.get("evidence_schema")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("runtime facts validation job id must be non-empty")
    if owner != "runtime-facts":
        raise ValueError("runtime facts validation job owner must be runtime-facts")
    if evidence_schema != _FACTS_EVIDENCE_SCHEMA:
        raise ValueError("runtime facts validation job has an unsupported evidence schema")
    evidence_path = _utils._relative_path(item.get("evidence_relative_path"), label="runtime evidence path")
    return {
        "id": job_id,
        "owner": owner,
        "action": "audit_structured_facts",
        "evidence_relative_path": str(evidence_path),
    }


def _runtime_controller_shadow_job(binding: dict[str, Any], domain_id: str) -> dict[str, str]:
    matches = [
        item
        for item in binding.get("runtime_jobs", [])
        if isinstance(item, dict)
        and item.get("domain_id") == domain_id
        and item.get("action") == "shadow_legacy_controller"
    ]
    if len(matches) != 1:
        raise ValueError(f"no unique Runtime controller shadow job configured for domain: {domain_id}")
    item = matches[0]
    job_id = item.get("id")
    owner = item.get("owner")
    evidence_schema = item.get("evidence_schema")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("Runtime controller shadow job id must be non-empty")
    if owner != "runtime-control":
        raise ValueError("Runtime controller shadow job owner must be runtime-control")
    if evidence_schema != _CONTROLLER_SHADOW_EVIDENCE_SCHEMA:
        raise ValueError("Runtime controller shadow job has an unsupported evidence schema")
    evidence_path = _utils._relative_path(item.get("evidence_relative_path"), label="Runtime evidence path")
    return {
        "id": job_id,
        "owner": owner,
        "action": "shadow_legacy_controller",
        "evidence_relative_path": str(evidence_path),
    }


def _runtime_model_freshness_job(binding: dict[str, Any], domain_id: str) -> dict[str, str]:
    matches = [
        item
        for item in binding.get("runtime_jobs", [])
        if isinstance(item, dict)
        and item.get("domain_id") == domain_id
        and item.get("action") == "audit_model_freshness"
    ]
    if len(matches) != 1:
        raise ValueError(f"no unique Runtime model freshness job configured for domain: {domain_id}")
    item = matches[0]
    job_id = item.get("id")
    owner = item.get("owner")
    evidence_schema = item.get("evidence_schema")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("Runtime model freshness job id must be non-empty")
    if owner != "runtime-control":
        raise ValueError("Runtime model freshness job owner must be runtime-control")
    if evidence_schema != _MODEL_FRESHNESS_EVIDENCE_SCHEMA:
        raise ValueError("Runtime model freshness job has an unsupported evidence schema")
    evidence_path = _utils._relative_path(item.get("evidence_relative_path"), label="Runtime evidence path")
    if str(evidence_path) != _MODEL_FRESHNESS_EVIDENCE_PATH:
        raise ValueError("Runtime model freshness job has an unsupported evidence path")
    return {
        "id": job_id,
        "owner": owner,
        "action": "audit_model_freshness",
        "evidence_relative_path": str(evidence_path),
    }


def _runtime_sanyi_status_job(binding: dict[str, Any], domain_id: str) -> dict[str, str]:
    matches = [
        item
        for item in binding.get("runtime_jobs", [])
        if isinstance(item, dict) and item.get("id") == _SANYI_STATUS_JOB_ID
    ]
    expected = {
        "id": _SANYI_STATUS_JOB_ID,
        "domain_id": domain_id,
        "owner": "runtime-control",
        "action": "audit_sanyi_status_consistency",
        "schedule": "manual",
        "timeout_seconds": 30,
        "reads": [
            "@工作文档/卫健委/_control/三医态势仪表盘.md",
            "@工作文档/卫健委/_entities/facts/01-progress.yaml",
        ],
        "scope_entity_ids": ["proj-syld", "proj-jingbao", "proj-emr-quality"],
        "writes": [],
        "evidence_relative_path": _SANYI_STATUS_EVIDENCE_PATH,
        "evidence_schema": _SANYI_STATUS_EVIDENCE_SCHEMA,
        "fail_closed": True,
    }
    if len(matches) != 1 or matches[0] != expected:
        raise ValueError("Runtime sanyi status job has an invalid contract")
    return {
        "id": _SANYI_STATUS_JOB_ID,
        "owner": "runtime-control",
        "action": "audit_sanyi_status_consistency",
        "evidence_relative_path": _SANYI_STATUS_EVIDENCE_PATH,
    }


def _path_identity_parts(path: Path) -> tuple[str, ...]:
    return tuple(part.casefold() for part in path.resolve(strict=False).parts)


def _paths_overlap(first: Path, second: Path) -> bool:
    first_parts = _path_identity_parts(first)
    second_parts = _path_identity_parts(second)
    return first_parts[: len(second_parts)] == second_parts or second_parts[: len(first_parts)] == first_parts


def _runtime_state_root(
    binding: dict[str, Any],
    *,
    runtime_state_root: str | Path | None,
    documents_root: str | Path | None,
) -> Path:
    state = binding.get("runtime_state")
    if not isinstance(state, dict) or state.get("owner") != "runtime":
        raise ValueError("runtime_state must be declared by runtime")
    if runtime_state_root is not None:
        candidate = Path(runtime_state_root).expanduser()
    else:
        environment_override = state.get("environment_override")
        default_home_relative = state.get("default_home_relative")
        if not isinstance(environment_override, str) or not environment_override:
            raise ValueError("runtime_state environment_override must be non-empty")
        default_relative = _utils._relative_path(default_home_relative, label="runtime_state default_home_relative")
        candidate = Path(os.environ.get(environment_override, str(Path.home() / default_relative))).expanduser()
    resolved = candidate.resolve(strict=False)
    if _paths_overlap(resolved, _utils._documents_root(documents_root)):
        raise ValueError("Runtime state root must not overlap Documents")
    return resolved


def _read_bounded_runtime_receipt(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    try:
        if not stat.S_ISDIR(os.lstat(root).st_mode):
            raise ValueError("runtime state root is not a directory")
        parent = root
        for part in relative.parts[:-1]:
            parent = parent / part
            if not stat.S_ISDIR(os.lstat(parent).st_mode):
                raise ValueError("runtime evidence parent is not a directory")
        before = os.lstat(path)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("runtime evidence is not a regular file")
        if before.st_size > _MAX_RUNTIME_RECEIPT_BYTES:
            raise ValueError("runtime evidence exceeds the bounded receipt size")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError as exc:
        raise ValueError("runtime evidence is unavailable") from exc
    except OSError as exc:
        raise ValueError("runtime evidence is unavailable") from exc

    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError("runtime evidence is not a regular file")
        encoded = os.read(descriptor, _MAX_RUNTIME_RECEIPT_BYTES + 1)
    except OSError as exc:
        raise ValueError("runtime evidence is unreadable") from exc
    finally:
        os.close(descriptor)
    if len(encoded) > _MAX_RUNTIME_RECEIPT_BYTES:
        raise ValueError("runtime evidence exceeds the bounded receipt size")
    try:
        raw = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("runtime evidence is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("runtime evidence must be a JSON object")
    return raw


def _non_negative_int(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"runtime evidence {label} must be a non-negative integer")
    return value


def _iso_date(value: object, *, label: str, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ValueError(f"runtime evidence {label} must be an ISO date")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"runtime evidence {label} must be an ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"runtime evidence {label} must be an ISO date")
    return value


def _unavailable_model_freshness_is_consistent(freshness: dict[str, Any]) -> bool:
    error = freshness["error"]
    facts_reviewed = freshness["facts_last_reviewed"]
    model_count = freshness["model_markdown_count"]
    fresh_count = freshness["fresh_model_count"]
    stale_count = freshness["stale_model_count"]
    invalid_count = freshness["invalid_reviewed_count"]
    unreadable_count = freshness["unreadable_regular_file_count"]
    no_model_observation = (
        model_count == 0 and fresh_count == 0 and stale_count == 0 and invalid_count == 0 and unreadable_count == 0
    )
    if error in _MODEL_FRESHNESS_PRE_FACTS_ERRORS:
        return facts_reviewed is None and no_model_observation
    if error in _MODEL_FRESHNESS_DIRECTORY_ERRORS:
        return facts_reviewed is not None and no_model_observation
    if error == "model_file_not_regular":
        return (
            facts_reviewed is not None
            and model_count > 0
            and fresh_count == 0
            and stale_count == 0
            and invalid_count == 0
            and unreadable_count == 0
        )
    if error == "model_file_unreadable":
        return (
            facts_reviewed is not None
            and model_count > 0
            and fresh_count == 0
            and stale_count == 0
            and invalid_count == 0
            and unreadable_count == 1
        )
    if error in _MODEL_FRESHNESS_REVIEWED_ERRORS:
        return (
            facts_reviewed is not None
            and model_count > 0
            and fresh_count == 0
            and stale_count == 0
            and invalid_count == 1
            and unreadable_count == 0
        )
    return False


def _validated_facts_receipt(receipt: dict[str, Any], job: dict[str, str]) -> tuple[str, dict[str, Any]]:
    if receipt.get("job_id") != job["id"] or receipt.get("owner") != job["owner"]:
        raise ValueError("runtime evidence does not match the configured job")
    if receipt.get("timed_out") is not False or receipt.get("evidence_error") is not None:
        raise ValueError("runtime evidence did not complete a valid audit")
    owner_evidence = receipt.get("owner_evidence")
    if not isinstance(owner_evidence, dict) or owner_evidence.get("schema") != _FACTS_EVIDENCE_SCHEMA:
        raise ValueError("runtime evidence has an invalid facts audit schema")
    owner_status = owner_evidence.get("status")
    if owner_status not in {"ok", "invalid"}:
        raise ValueError("runtime evidence has an invalid facts audit status")
    facts_total = _non_negative_int(owner_evidence.get("facts_total"), label="facts_total")
    by_type = owner_evidence.get("by_type")
    if not isinstance(by_type, dict) or any(
        not isinstance(name, str) or not name or isinstance(count, bool) or not isinstance(count, int) or count < 0
        for name, count in by_type.items()
    ):
        raise ValueError("runtime evidence has an invalid facts type summary")
    if sum(by_type.values()) != facts_total:
        raise ValueError("runtime evidence facts_total does not match by_type")
    validation = {
        "facts_total": facts_total,
        "by_type": dict(sorted(by_type.items())),
        "error_count": _non_negative_int(owner_evidence.get("error_count"), label="error_count"),
        "warning_count": _non_negative_int(owner_evidence.get("warning_count"), label="warning_count"),
    }
    receipt_status = receipt.get("status")
    exit_code = receipt.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise ValueError("runtime evidence exit_code must be an integer")
    if owner_status == "ok" and receipt_status == "succeeded" and exit_code == 0:
        return "ok", validation
    if owner_status == "invalid" and receipt_status == "failed" and exit_code != 0:
        return "violations", validation
    raise ValueError("runtime receipt and facts validation status disagree")


def _validated_model_freshness_receipt(receipt: dict[str, Any], job: dict[str, str]) -> tuple[str, dict[str, Any]]:
    if receipt.get("job_id") != job["id"] or receipt.get("owner") != job["owner"]:
        raise ValueError("Runtime evidence does not match the configured job")
    if receipt.get("timed_out") is not False or receipt.get("evidence_error") is not None:
        raise ValueError("Runtime evidence did not complete a valid model freshness audit")
    owner_evidence = receipt.get("owner_evidence")
    fields = {
        "schema",
        "status",
        "checked_on",
        "facts_last_reviewed",
        "model_markdown_count",
        "fresh_model_count",
        "stale_model_count",
        "invalid_reviewed_count",
        "unreadable_regular_file_count",
        "error",
    }
    if (
        not isinstance(owner_evidence, dict)
        or set(owner_evidence) != fields
        or owner_evidence.get("schema") != _MODEL_FRESHNESS_EVIDENCE_SCHEMA
    ):
        raise ValueError("Runtime evidence has an invalid model freshness schema")
    status = owner_evidence.get("status")
    if status not in {"ok", "attention", "unavailable"}:
        raise ValueError("Runtime evidence has an invalid model freshness status")
    freshness = {
        "checked_on": _iso_date(owner_evidence.get("checked_on"), label="checked_on"),
        "facts_last_reviewed": _iso_date(
            owner_evidence.get("facts_last_reviewed"),
            label="facts_last_reviewed",
            optional=True,
        ),
        "model_markdown_count": _non_negative_int(
            owner_evidence.get("model_markdown_count"), label="model_markdown_count"
        ),
        "fresh_model_count": _non_negative_int(owner_evidence.get("fresh_model_count"), label="fresh_model_count"),
        "stale_model_count": _non_negative_int(owner_evidence.get("stale_model_count"), label="stale_model_count"),
        "invalid_reviewed_count": _non_negative_int(
            owner_evidence.get("invalid_reviewed_count"), label="invalid_reviewed_count"
        ),
        "unreadable_regular_file_count": _non_negative_int(
            owner_evidence.get("unreadable_regular_file_count"),
            label="unreadable_regular_file_count",
        ),
        "error": owner_evidence.get("error"),
    }
    model_count = freshness["model_markdown_count"]
    fresh_count = freshness["fresh_model_count"]
    stale_count = freshness["stale_model_count"]
    invalid_count = freshness["invalid_reviewed_count"]
    unreadable_count = freshness["unreadable_regular_file_count"]
    error = freshness["error"]
    if (
        fresh_count + stale_count > model_count
        or (status == "unavailable") != (error in _MODEL_FRESHNESS_ERRORS)
        or (status != "unavailable" and error is not None)
        or (status == "unavailable" and not _unavailable_model_freshness_is_consistent(freshness))
        or (
            status == "ok"
            and (
                model_count == 0
                or fresh_count != model_count
                or stale_count != 0
                or invalid_count != 0
                or unreadable_count != 0
                or freshness["facts_last_reviewed"] is None
            )
        )
        or (
            status == "attention"
            and (
                model_count == 0
                or fresh_count + stale_count != model_count
                or stale_count == 0
                or invalid_count != 0
                or unreadable_count != 0
                or freshness["facts_last_reviewed"] is None
            )
        )
    ):
        raise ValueError("Runtime evidence has invalid model freshness aggregates")
    exit_code = receipt.get("exit_code")
    expected = {
        "ok": ("succeeded", 0),
        "attention": ("failed", 1),
        "unavailable": ("failed", 2),
    }[status]
    if isinstance(exit_code, bool) or (receipt.get("status"), exit_code) != expected:
        raise ValueError("Runtime receipt and model freshness status disagree")
    return status, freshness


def _validated_sanyi_status_receipt(receipt: dict[str, Any], job: dict[str, str]) -> tuple[str, dict[str, Any]]:
    if receipt.get("job_id") != job["id"] or receipt.get("owner") != job["owner"]:
        raise ValueError("Runtime evidence does not match the configured job")
    if receipt.get("timed_out") is not False or receipt.get("evidence_error") is not None:
        raise ValueError("Runtime evidence did not complete a valid sanyi status audit")
    owner_evidence = receipt.get("owner_evidence")
    fields = {
        "schema",
        "status",
        "checked_on",
        "dashboard_last_reviewed",
        "latest_verified_at",
        "relevant_fact_count",
        "error",
    }
    if (
        not isinstance(owner_evidence, dict)
        or set(owner_evidence) != fields
        or owner_evidence.get("schema") != _SANYI_STATUS_EVIDENCE_SCHEMA
    ):
        raise ValueError("Runtime evidence has an invalid sanyi status schema")
    status = owner_evidence.get("status")
    if status not in {"ok", "attention", "unavailable"}:
        raise ValueError("Runtime evidence has an invalid sanyi status")
    consistency = {
        "checked_on": _iso_date(owner_evidence.get("checked_on"), label="checked_on"),
        "dashboard_last_reviewed": _iso_date(
            owner_evidence.get("dashboard_last_reviewed"), label="dashboard_last_reviewed", optional=True
        ),
        "latest_verified_at": _iso_date(
            owner_evidence.get("latest_verified_at"), label="latest_verified_at", optional=True
        ),
        "relevant_fact_count": _non_negative_int(
            owner_evidence.get("relevant_fact_count"), label="relevant_fact_count"
        ),
        "error": owner_evidence.get("error"),
    }
    dashboard = consistency["dashboard_last_reviewed"]
    latest = consistency["latest_verified_at"]
    count = consistency["relevant_fact_count"]
    error = consistency["error"]
    if status == "unavailable":
        valid = dashboard is None and latest is None and count == 0 and error in _SANYI_STATUS_ERRORS
    else:
        valid = (
            dashboard is not None
            and latest is not None
            and count > 0
            and error is None
            and ((status == "ok" and latest <= dashboard) or (status == "attention" and latest > dashboard))
        )
    if not valid:
        raise ValueError("Runtime evidence has invalid sanyi status aggregates")
    expected = {
        "ok": ("succeeded", 0),
        "attention": ("failed", 1),
        "unavailable": ("failed", 2),
    }[status]
    exit_code = receipt.get("exit_code")
    if isinstance(exit_code, bool) or (receipt.get("status"), exit_code) != expected:
        raise ValueError("Runtime receipt and sanyi status disagree")
    return status, consistency


def _validated_controller_shadow_receipt(receipt: dict[str, Any], job: dict[str, str]) -> dict[str, Any]:
    if receipt.get("job_id") != job["id"] or receipt.get("owner") != job["owner"]:
        raise ValueError("Runtime evidence does not match the configured job")
    if receipt.get("timed_out") is not False or receipt.get("evidence_error") is not None:
        raise ValueError("Runtime evidence did not complete a valid controller shadow")
    exit_code = receipt.get("exit_code")
    if (
        receipt.get("status") != "failed"
        or isinstance(exit_code, bool)
        or not isinstance(exit_code, int)
        or exit_code == 0
    ):
        raise ValueError("Runtime receipt does not preserve the observed shadow status")
    owner_evidence = receipt.get("owner_evidence")
    if (
        not isinstance(owner_evidence, dict)
        or owner_evidence.get("schema") != _CONTROLLER_SHADOW_EVIDENCE_SCHEMA
        or owner_evidence.get("status") != "shadow_observed"
        or owner_evidence.get("legacy_controller_replaced") is not False
        or owner_evidence.get("cutover_ready") is not False
    ):
        raise ValueError("Runtime evidence has an invalid controller shadow schema")
    legacy_rule_ids = owner_evidence.get("legacy_rule_ids")
    if legacy_rule_ids != list(_CONTROLLER_SHADOW_LEGACY_RULE_IDS):
        raise ValueError("Runtime evidence has invalid controller shadow legacy rules")
    if owner_evidence.get("legacy_rule_count") != len(legacy_rule_ids):
        raise ValueError("Runtime evidence has an invalid controller shadow legacy rule count")
    observed_rule_ids = owner_evidence.get("observed_rule_ids")
    if observed_rule_ids != list(_CONTROLLER_SHADOW_OBSERVED_RULE_IDS):
        raise ValueError("Runtime evidence has invalid observed controller rules")
    if owner_evidence.get("observed_rule_count") != len(observed_rule_ids):
        raise ValueError("Runtime evidence has an invalid observed controller rule count")
    unobserved_rule_ids = owner_evidence.get("unobserved_rule_ids")
    if unobserved_rule_ids != list(_CONTROLLER_SHADOW_UNOBSERVED_RULE_IDS):
        raise ValueError("Runtime evidence has invalid unobserved controller rules")
    if owner_evidence.get("unobserved_rule_count") != len(unobserved_rule_ids):
        raise ValueError("Runtime evidence has an invalid unobserved controller rule count")
    return {
        "cutover_ready": False,
        "legacy_controller_replaced": False,
        "legacy_rule_ids": legacy_rule_ids,
        "observed_rule_ids": observed_rule_ids,
        "unobserved_rule_ids": unobserved_rule_ids,
    }


def _facts_validation_unavailable(
    requested: str,
    source: Path,
    binding_source: str,
    error: str,
    *,
    runtime_evidence: Path | None = None,
) -> dict[str, Any]:
    sources = {"domain_registry": str(source), "binding_registry": binding_source}
    if runtime_evidence is not None:
        sources["runtime_evidence"] = str(runtime_evidence)
    return {
        "schema": "cockpit.domain-facts-validation.v1",
        "status": "unavailable",
        "available": False,
        "domain_id": requested,
        "job": None,
        "validation": None,
        "sources": sources,
        "error": error,
    }


def _controller_shadow_unavailable(
    requested: str,
    source: Path,
    binding_source: str,
    error: str,
    *,
    runtime_evidence: Path | None = None,
) -> dict[str, Any]:
    sources = {"domain_registry": str(source), "binding_registry": binding_source}
    if runtime_evidence is not None:
        sources["runtime_evidence"] = str(runtime_evidence)
    return {
        "schema": "cockpit.domain-controller-shadow.v2",
        "status": "unavailable",
        "available": False,
        "domain_id": requested,
        "job": None,
        "shadow": None,
        "sources": sources,
        "error": error,
    }


def model_freshness_unavailable_envelope(
    domain_id: str,
    error_category: str,
    *,
    include_runtime_evidence: bool = False,
) -> dict[str, Any]:
    sources = {
        "domain_registry": _DOMAIN_REGISTRY_AUTHORITY,
        "binding_registry": _DOMAIN_BINDING_AUTHORITY,
    }
    if include_runtime_evidence:
        sources["runtime_evidence"] = _MODEL_FRESHNESS_EVIDENCE_AUTHORITY
    return {
        "schema": "cockpit.domain-model-freshness.v1",
        "status": "unavailable",
        "available": False,
        "domain_id": domain_id.strip(),
        "job": None,
        "freshness": None,
        "sources": sources,
        "error": error_category,
    }


def sanyi_status_consistency_unavailable_envelope(
    domain_id: str,
    error_category: str,
    *,
    include_runtime_evidence: bool = False,
) -> dict[str, Any]:
    sources = {
        "domain_registry": _DOMAIN_REGISTRY_AUTHORITY,
        "binding_registry": _DOMAIN_BINDING_AUTHORITY,
    }
    if include_runtime_evidence:
        sources["runtime_evidence"] = _SANYI_STATUS_EVIDENCE_AUTHORITY
    return {
        "schema": "cockpit.domain-sanyi-status-consistency.v1",
        "status": "unavailable",
        "available": False,
        "domain_id": domain_id.strip(),
        "job": None,
        "consistency": None,
        "sources": sources,
        "error": error_category,
    }


def domain_facts_validation_status(
    domain_id: str,
    *,
    workspace_root: str | Path | None = None,
    registry_path: str | Path | None = None,
    documents_root: str | Path | None = None,
    runtime_state_root: str | Path | None = None,
) -> dict[str, Any]:
    requested = domain_id.strip()
    source = _utils._registry_path(registry_path, documents_root=documents_root)
    workspace = resolve_workspace_root(workspace_root)
    binding = _binding_context(requested, workspace)
    binding_source = str(binding["source"])
    try:
        source, _registry, domains = _load_domains(registry_path, documents_root=documents_root)
        if not requested or not any(domain["id"] == requested for domain in domains):
            raise ValueError(f"unknown domain: {requested}")
        if binding["status"] != "ok":
            raise ValueError(binding.get("error", "domain binding is unavailable"))
        job = _runtime_facts_job(binding, requested)
        state_root = _runtime_state_root(
            binding,
            runtime_state_root=runtime_state_root,
            documents_root=documents_root,
        )
        evidence_path = state_root / job["evidence_relative_path"]
        receipt = _read_bounded_runtime_receipt(state_root, Path(job["evidence_relative_path"]))
        status, validation = _validated_facts_receipt(receipt, job)
    except (OSError, ValueError) as exc:
        evidence = locals().get("evidence_path")
        return _facts_validation_unavailable(
            requested,
            source,
            binding_source,
            str(exc),
            runtime_evidence=evidence if isinstance(evidence, Path) else None,
        )

    return {
        "schema": "cockpit.domain-facts-validation.v1",
        "status": status,
        "available": True,
        "domain_id": requested,
        "job": {key: job[key] for key in ("id", "owner", "action")},
        "validation": validation,
        "sources": {
            "domain_registry": str(source),
            "binding_registry": binding_source,
            "runtime_evidence": str(evidence_path),
        },
    }


def domain_model_freshness_status(
    domain_id: str,
    *,
    workspace_root: str | Path | None = None,
    registry_path: str | Path | None = None,
    documents_root: str | Path | None = None,
    runtime_state_root: str | Path | None = None,
) -> dict[str, Any]:
    requested = domain_id.strip()
    workspace = resolve_workspace_root(workspace_root)
    binding = _binding_context(requested, workspace)
    try:
        _source, _registry, domains = _load_domains(registry_path, documents_root=documents_root)
        registered = requested and any(domain["id"] == requested for domain in domains)
    except Exception:
        return model_freshness_unavailable_envelope(requested, "domain_registry_unavailable")
    if not registered:
        return model_freshness_unavailable_envelope(requested, "domain_not_registered")
    if binding["status"] != "ok":
        return model_freshness_unavailable_envelope(requested, "domain_binding_unavailable")
    try:
        job = _runtime_model_freshness_job(binding, requested)
    except (OSError, ValueError):
        return model_freshness_unavailable_envelope(requested, "runtime_job_unavailable")
    try:
        state_root = _runtime_state_root(
            binding,
            runtime_state_root=runtime_state_root,
            documents_root=documents_root,
        )
    except (OSError, ValueError):
        return model_freshness_unavailable_envelope(requested, "runtime_state_unavailable")
    try:
        receipt = _read_bounded_runtime_receipt(state_root, Path(job["evidence_relative_path"]))
        status, freshness = _validated_model_freshness_receipt(receipt, job)
    except (OSError, ValueError):
        return model_freshness_unavailable_envelope(
            requested,
            "runtime_receipt_unavailable",
            include_runtime_evidence=True,
        )

    return {
        "schema": "cockpit.domain-model-freshness.v1",
        "status": status,
        "available": status != "unavailable",
        "domain_id": requested,
        "job": {key: job[key] for key in ("id", "owner", "action")},
        "freshness": freshness,
        "sources": {
            "domain_registry": _DOMAIN_REGISTRY_AUTHORITY,
            "binding_registry": _DOMAIN_BINDING_AUTHORITY,
            "runtime_evidence": _MODEL_FRESHNESS_EVIDENCE_AUTHORITY,
        },
    }


def domain_sanyi_status_consistency_status(
    domain_id: str,
    *,
    workspace_root: str | Path | None = None,
    registry_path: str | Path | None = None,
    documents_root: str | Path | None = None,
    runtime_state_root: str | Path | None = None,
) -> dict[str, Any]:
    requested = domain_id.strip()
    workspace = resolve_workspace_root(workspace_root)
    binding = _binding_context(requested, workspace)
    try:
        _source, _registry, domains = _load_domains(registry_path, documents_root=documents_root)
        registered = requested and any(domain["id"] == requested for domain in domains)
    except Exception:
        return sanyi_status_consistency_unavailable_envelope(requested, "domain_registry_unavailable")
    if not registered:
        return sanyi_status_consistency_unavailable_envelope(requested, "domain_not_registered")
    if binding["status"] != "ok":
        return sanyi_status_consistency_unavailable_envelope(requested, "domain_binding_unavailable")
    try:
        job = _runtime_sanyi_status_job(binding, requested)
    except (OSError, ValueError):
        return sanyi_status_consistency_unavailable_envelope(requested, "runtime_job_unavailable")
    try:
        state_root = _runtime_state_root(
            binding,
            runtime_state_root=runtime_state_root,
            documents_root=documents_root,
        )
    except (OSError, ValueError):
        return sanyi_status_consistency_unavailable_envelope(requested, "runtime_state_unavailable")
    try:
        receipt = _read_bounded_runtime_receipt(state_root, Path(job["evidence_relative_path"]))
        status, consistency = _validated_sanyi_status_receipt(receipt, job)
    except (OSError, ValueError):
        return sanyi_status_consistency_unavailable_envelope(
            requested,
            "runtime_receipt_unavailable",
            include_runtime_evidence=True,
        )
    return {
        "schema": "cockpit.domain-sanyi-status-consistency.v1",
        "status": status,
        "available": status != "unavailable",
        "domain_id": requested,
        "job": {key: job[key] for key in ("id", "owner", "action")},
        "consistency": consistency,
        "sources": {
            "domain_registry": _DOMAIN_REGISTRY_AUTHORITY,
            "binding_registry": _DOMAIN_BINDING_AUTHORITY,
            "runtime_evidence": _SANYI_STATUS_EVIDENCE_AUTHORITY,
        },
    }


def domain_controller_shadow_status(
    domain_id: str,
    *,
    workspace_root: str | Path | None = None,
    registry_path: str | Path | None = None,
    documents_root: str | Path | None = None,
    runtime_state_root: str | Path | None = None,
) -> dict[str, Any]:
    requested = domain_id.strip()
    source = _utils._registry_path(registry_path, documents_root=documents_root)
    workspace = resolve_workspace_root(workspace_root)
    binding = _binding_context(requested, workspace)
    binding_source = str(binding["source"])
    try:
        source, _registry, domains = _load_domains(registry_path, documents_root=documents_root)
        if not requested or not any(domain["id"] == requested for domain in domains):
            raise ValueError(f"unknown domain: {requested}")
        if binding["status"] != "ok":
            raise ValueError(binding.get("error", "domain binding is unavailable"))
        job = _runtime_controller_shadow_job(binding, requested)
        state_root = _runtime_state_root(
            binding,
            runtime_state_root=runtime_state_root,
            documents_root=documents_root,
        )
        evidence_path = state_root / job["evidence_relative_path"]
        receipt = _read_bounded_runtime_receipt(state_root, Path(job["evidence_relative_path"]))
        shadow = _validated_controller_shadow_receipt(receipt, job)
    except (OSError, ValueError) as exc:
        evidence = locals().get("evidence_path")
        return _controller_shadow_unavailable(
            requested,
            source,
            binding_source,
            str(exc),
            runtime_evidence=evidence if isinstance(evidence, Path) else None,
        )

    return {
        "schema": "cockpit.domain-controller-shadow.v2",
        "status": "shadow_observed",
        "available": True,
        "domain_id": requested,
        "job": {key: job[key] for key in ("id", "owner", "action")},
        "shadow": shadow,
        "sources": {
            "domain_registry": str(source),
            "binding_registry": binding_source,
            "runtime_evidence": str(evidence_path),
        },
    }
