"""Shared validation for Workspace-bound Documents owner jobs."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_MANIFEST_JOB_FIELDS = {
    "id",
    "domain_id",
    "owner",
    "action",
    "schedule",
    "timeout_seconds",
    "reads",
    "writes",
    "evidence_path",
    "fail_closed",
}
_FACTS_AUDIT_JOB_FIELDS = {
    "id",
    "domain_id",
    "owner",
    "action",
    "schedule",
    "timeout_seconds",
    "reads",
    "writes",
    "evidence_relative_path",
    "evidence_schema",
    "fail_closed",
}
_RUNTIME_STATE = {
    "owner": "runtime",
    "environment_override": "OMOSTATION_RUNTIME_STATE_ROOT",
    "default_home_relative": ".local/state/omostation/runtime",
}
_FACTS_AUDIT_READS = ["@工作文档/卫健委/_entities/facts"]
_FACTS_AUDIT_SCHEMA = "runtime.documents-facts-audit.evidence.v1"
_CONTROLLER_SHADOW_READS = [
    "@工作文档/卫健委/_control",
    "@工作文档/卫健委/_entities",
    "@工作文档/卫健委/_meta",
    "@工作文档/卫健委/_runtime",
    "@工作文档/卫健委/_storage",
    "@工作文档/卫健委/_knowledge",
]
_CONTROLLER_SHADOW_SCHEMA = "runtime.documents-controller-shadow.evidence.v2"
_CONTROLLER_SHADOW_EVIDENCE_PATH = (
    "control/evidence/documents-weijian-controller-shadow/"
    "documents-weijian-controller-shadow.json"
)


def _safe_relative_path(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not Path(value).is_absolute()
        and ".." not in Path(value).parts
        and Path(value) != Path(".")
    )


def _validate_common_job_fields(
    value: dict[str, object], index: int, known_domains: set[str], seen: set[str]
) -> tuple[str, list[str]]:
    """Validate the cross-contract fields and return a stable job label."""

    errors: list[str] = []
    job_id = value.get("id")
    label = job_id if isinstance(job_id, str) and job_id else f"runtime_jobs[{index}]"
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        errors.append(f"runtime_jobs[{index}].id must be a non-traversing identifier")
    elif job_id in seen:
        errors.append(f"runtime_jobs contains duplicate id: {job_id}")
    else:
        seen.add(job_id)

    domain_id = value.get("domain_id")
    if not isinstance(domain_id, str) or not domain_id:
        errors.append(f"runtime job {label} domain_id must be non-empty")
    elif domain_id not in known_domains:
        errors.append(f"runtime job {label} references unknown domain: {domain_id}")
    if value.get("schedule") != "manual":
        errors.append(f"runtime job {label} schedule must be manual")
    timeout = value.get("timeout_seconds")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout <= 0
    ):
        errors.append(f"runtime job {label} timeout_seconds must be positive")
    if value.get("writes") != []:
        errors.append(f"runtime job {label} must not declare Documents writes")
    if value.get("fail_closed") is not True:
        errors.append(f"runtime job {label} must be fail_closed")
    return label, errors


def _validate_manifest_job(value: dict[str, object], label: str) -> list[str]:
    errors: list[str] = []
    unknown_fields = sorted(set(value) - _MANIFEST_JOB_FIELDS)
    missing_fields = sorted(_MANIFEST_JOB_FIELDS - set(value))
    if unknown_fields:
        errors.append(
            f"runtime job {label} has unknown fields: {', '.join(unknown_fields)}"
        )
    if missing_fields:
        errors.append(
            f"runtime job {label} is missing fields: {', '.join(missing_fields)}"
        )
    if value.get("owner") != "l4-kernel":
        errors.append(f"runtime job {label} owner must be l4-kernel")
    if value.get("action") != "validate_manifest":
        errors.append(f"runtime job {label} action must be validate_manifest")
    if value.get("reads") != ["domain_registry", "registered_manifests"]:
        errors.append(
            f"runtime job {label} reads must be domain_registry and registered_manifests"
        )
    if not _safe_relative_path(value.get("evidence_path")):
        errors.append(
            f"runtime job {label} evidence_path must be relative and non-traversing"
        )
    return errors


def _validate_facts_audit_job(value: dict[str, object], label: str) -> list[str]:
    errors: list[str] = []
    unknown_fields = sorted(set(value) - _FACTS_AUDIT_JOB_FIELDS)
    missing_fields = sorted(_FACTS_AUDIT_JOB_FIELDS - set(value))
    if unknown_fields:
        errors.append(
            f"runtime facts job {label} has unknown fields: {', '.join(unknown_fields)}"
        )
    if missing_fields:
        errors.append(
            f"runtime facts job {label} is missing fields: {', '.join(missing_fields)}"
        )
    if value.get("owner") != "runtime-facts":
        errors.append(f"runtime facts job {label} owner must be runtime-facts")
    if value.get("action") != "audit_structured_facts":
        errors.append(
            f"runtime facts job {label} action must be audit_structured_facts"
        )
    if value.get("domain_id") != "work-weijian":
        errors.append(f"runtime facts job {label} domain_id must be work-weijian")
    if value.get("reads") != _FACTS_AUDIT_READS:
        errors.append(
            f"runtime facts job {label} reads must be @工作文档/卫健委/_entities/facts"
        )
    if not _safe_relative_path(value.get("evidence_relative_path")):
        errors.append(
            f"runtime facts job {label} evidence_relative_path must be relative and non-traversing"
        )
    if value.get("evidence_schema") != _FACTS_AUDIT_SCHEMA:
        errors.append(
            f"runtime facts job {label} evidence_schema must be {_FACTS_AUDIT_SCHEMA}"
        )
    return errors


def _validate_controller_shadow_job(value: dict[str, object], label: str) -> list[str]:
    errors: list[str] = []
    unknown_fields = sorted(set(value) - _FACTS_AUDIT_JOB_FIELDS)
    missing_fields = sorted(_FACTS_AUDIT_JOB_FIELDS - set(value))
    if unknown_fields:
        errors.append(
            f"runtime controller shadow job {label} has unknown fields: {', '.join(unknown_fields)}"
        )
    if missing_fields:
        errors.append(
            f"runtime controller shadow job {label} is missing fields: {', '.join(missing_fields)}"
        )
    if value.get("owner") != "runtime-control":
        errors.append(
            f"runtime controller shadow job {label} owner must be runtime-control"
        )
    if value.get("action") != "shadow_legacy_controller":
        errors.append(
            f"runtime controller shadow job {label} action must be shadow_legacy_controller"
        )
    if value.get("domain_id") != "work-weijian":
        errors.append(
            f"runtime controller shadow job {label} domain_id must be work-weijian"
        )
    if value.get("reads") != _CONTROLLER_SHADOW_READS:
        errors.append(
            f"runtime controller shadow job {label} reads must declare the six legacy controller planes"
        )
    if value.get("evidence_relative_path") != _CONTROLLER_SHADOW_EVIDENCE_PATH:
        errors.append(
            f"runtime controller shadow job {label} evidence_relative_path must be {_CONTROLLER_SHADOW_EVIDENCE_PATH}"
        )
    if value.get("evidence_schema") != _CONTROLLER_SHADOW_SCHEMA:
        errors.append(
            f"runtime controller shadow job {label} evidence_schema must be {_CONTROLLER_SHADOW_SCHEMA}"
        )
    return errors


def validate_runtime_state(raw: object) -> list[str]:
    """Require the one Runtime state binding that Cockpit can resolve."""

    if not isinstance(raw, dict):
        return ["runtime_state must be a mapping"]
    errors: list[str] = []
    unknown = sorted(set(raw) - set(_RUNTIME_STATE))
    missing = sorted(set(_RUNTIME_STATE) - set(raw))
    if unknown:
        errors.append(f"runtime_state has unknown fields: {', '.join(unknown)}")
    if missing:
        errors.append(f"runtime_state is missing fields: {', '.join(missing)}")
    for field, expected in _RUNTIME_STATE.items():
        if raw.get(field) != expected:
            errors.append(f"runtime_state.{field} must be {expected}")
    return errors


def validate_runtime_jobs(raw: object, domain_ids: Sequence[str]) -> list[str]:
    """Validate the permitted fail-closed Documents Runtime job contracts."""

    if not isinstance(raw, list) or not raw:
        return ["runtime_jobs must be a non-empty list"]

    errors: list[str] = []
    seen: set[str] = set()
    known_domains = set(domain_ids)
    for index, value in enumerate(raw):
        if not isinstance(value, dict):
            errors.append(f"runtime_jobs[{index}] must be a mapping")
            continue
        label, common_errors = _validate_common_job_fields(
            value, index, known_domains, seen
        )
        errors.extend(common_errors)
        if (
            value.get("owner") == "runtime-facts"
            or value.get("action") == "audit_structured_facts"
        ):
            errors.extend(_validate_facts_audit_job(value, label))
        elif (
            value.get("owner") == "runtime-control"
            or value.get("action") == "shadow_legacy_controller"
        ):
            errors.extend(_validate_controller_shadow_job(value, label))
        else:
            errors.extend(_validate_manifest_job(value, label))
    return errors


def get_runtime_job(
    raw: object, job_id: str, domain_ids: Sequence[str]
) -> Mapping[str, Any]:
    """Return one validated job from a validated binding registry."""

    errors = validate_runtime_jobs(raw, domain_ids)
    if errors:
        raise ValueError("; ".join(errors))
    assert isinstance(raw, list)
    matches = [value for value in raw if value.get("id") == job_id]
    if len(matches) != 1:
        raise ValueError(f"runtime job is not registered exactly once: {job_id}")
    return matches[0]


def get_manifest_validation_job(
    raw: object, job_id: str, domain_ids: Sequence[str]
) -> Mapping[str, Any]:
    """Return a L4 manifest-validation job for the legacy owner command only."""

    job = get_runtime_job(raw, job_id, domain_ids)
    if job["owner"] != "l4-kernel" or job["action"] != "validate_manifest":
        raise ValueError(f"runtime job is not a manifest validation job: {job_id}")
    return job
