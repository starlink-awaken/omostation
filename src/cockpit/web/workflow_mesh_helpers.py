"""Pure helper functions for workflow mesh operations."""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any


def _unavailable_projection(error_type: str, next_action: str) -> dict[str, Any]:
    now_iso = datetime.datetime.now(datetime.UTC).isoformat()
    return {
        "schema_version": "workflow-mesh-operations/v1",
        "status": "unavailable",
        "source": {"kind": "omo_append_only_event_log"},
        "generated_at": now_iso,
        "error_type": error_type,
        "next_action": next_action,
    }


def _personal_error(reason: str, *, status_code: int = 409, json_response_cls: Any = None) -> Any:
    """Return a non-success response without leaking broker or PEP internals."""
    payload = {"ok": False, "status": "blocked", "error": reason}
    if json_response_cls is None:
        return payload
    return json_response_cls(status_code=status_code, content=payload)


def _required_text(body: dict[str, Any], field: str) -> str:
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid_request: {field} must be non-empty")
    return value.strip()


def _optional_burden(body: dict[str, Any], field: str) -> float | None:
    """Extract an optional non-negative finite numeric burden field."""
    if field not in body or body[field] is None:
        return None
    value = body[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"invalid_burden: {field} must be a number")
    v = float(value)
    if v < 0 or not math.isfinite(v):
        raise ValueError(f"invalid_burden: {field} must be non-negative and finite")
    return v


def _projection_value_is_private(value: Any) -> bool:
    """Reject path- and connector-shaped strings from the public projection."""
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    lowered = stripped.lower()
    return "file://" in lowered or "iris://" in lowered or stripped.startswith(("/", "~/")) or "/users/" in lowered


def _projection_fields(source: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """Copy explicitly public scalar fields from one projection mapping."""
    if not isinstance(source, dict):
        return {}
    result: dict[str, Any] = {}
    for field in fields:
        if field not in source:
            continue
        value = source.get(field)
        if value is None or isinstance(value, (str, int, float, bool)):
            if not _projection_value_is_private(value):
                result[field] = value
    return result


def _personal_draft_evidence_ref(artifact: Path) -> str:
    """Return a stable opaque reference without exposing the local artifact path."""
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    return f"evidence://personal-draft/sha256:{digest}"


def _normalize_resp_input(responsibilities: list[str]) -> tuple[list, set[str]]:
    """Normalize caller responsibility strings for OMO assign() and comparison."""
    import re

    def _slugify(name: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
        return slug or "item"

    items: list = []
    expected: set[str] = set()
    for r in responsibilities:
        r = r.strip()
        if r.startswith("responsibility:"):
            suffix = r.split(":", 1)[1]
            items.append({"resp_id": r, "name": suffix})
            expected.add(r)
        else:
            items.append(r)
            expected.add(f"responsibility:{_slugify(r)}")
    return items, expected


def _build_draft_from_snapshot(snapshot: Any) -> dict[str, str]:
    """Deterministically build a safe draft dict from a persisted Episode snapshot."""
    summary = str(getattr(snapshot, "summary", "") or "").strip()
    why_now = str(getattr(snapshot, "why_now", "") or "").strip()
    deadline = str(getattr(snapshot, "deadline", "") or "").strip()
    context_text = f"{summary}. {why_now}." if why_now else f"{summary}."
    return {
        "title": summary or "Personal follow-up draft",
        "context": context_text.strip(),
        "deadline": deadline,
        "next_action": "Review and edit the local draft.",
    }


__all__ = [
    "_unavailable_projection",
    "_personal_error",
    "_required_text",
    "_optional_burden",
    "_projection_value_is_private",
    "_projection_fields",
    "_personal_draft_evidence_ref",
    "_normalize_resp_input",
    "_build_draft_from_snapshot",
]
