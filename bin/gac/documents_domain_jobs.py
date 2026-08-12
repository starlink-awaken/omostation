"""Shared validation for Workspace-bound Documents owner jobs."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_JOB_FIELDS = {
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


def validate_runtime_jobs(raw: object, domain_ids: Sequence[str]) -> list[str]:
    """Validate the MVP owner-job binding and return deterministic errors."""

    if not isinstance(raw, list) or not raw:
        return ["runtime_jobs must be a non-empty list"]

    errors: list[str] = []
    seen: set[str] = set()
    known_domains = set(domain_ids)
    for index, value in enumerate(raw):
        if not isinstance(value, dict):
            errors.append(f"runtime_jobs[{index}] must be a mapping")
            continue
        job_id = value.get("id")
        label = (
            job_id if isinstance(job_id, str) and job_id else f"runtime_jobs[{index}]"
        )
        unknown_fields = sorted(set(value) - _JOB_FIELDS)
        missing_fields = sorted(_JOB_FIELDS - set(value))
        if unknown_fields:
            errors.append(
                f"runtime job {label} has unknown fields: {', '.join(unknown_fields)}"
            )
        if missing_fields:
            errors.append(
                f"runtime job {label} is missing fields: {', '.join(missing_fields)}"
            )
        if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
            errors.append(
                f"runtime_jobs[{index}].id must be a non-traversing identifier"
            )
        elif job_id in seen:
            errors.append(f"runtime_jobs contains duplicate id: {job_id}")
        else:
            seen.add(job_id)

        domain_id = value.get("domain_id")
        if not isinstance(domain_id, str) or not domain_id:
            errors.append(f"runtime job {label} domain_id must be non-empty")
        elif domain_id not in known_domains:
            errors.append(f"runtime job {label} references unknown domain: {domain_id}")
        if value.get("owner") != "l4-kernel":
            errors.append(f"runtime job {label} owner must be l4-kernel")
        if value.get("action") != "validate_manifest":
            errors.append(f"runtime job {label} action must be validate_manifest")
        if value.get("schedule") != "manual":
            errors.append(f"runtime job {label} schedule must be manual")
        timeout = value.get("timeout_seconds")
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
        ):
            errors.append(f"runtime job {label} timeout_seconds must be positive")
        if value.get("reads") != ["domain_registry", "registered_manifests"]:
            errors.append(
                f"runtime job {label} reads must be domain_registry and registered_manifests"
            )
        if value.get("writes") != []:
            errors.append(f"runtime job {label} must not declare Documents writes")
        evidence = value.get("evidence_path")
        if (
            not isinstance(evidence, str)
            or not evidence
            or Path(evidence).is_absolute()
            or ".." in Path(evidence).parts
            or Path(evidence) == Path(".")
        ):
            errors.append(
                f"runtime job {label} evidence_path must be relative and non-traversing"
            )
        if value.get("fail_closed") is not True:
            errors.append(f"runtime job {label} must be fail_closed")
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
