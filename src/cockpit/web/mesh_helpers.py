"""Shared helpers for Cockpit Workflow Mesh DTO projection."""

from __future__ import annotations

from typing import Any


def _projection_value_is_private(value: Any) -> bool:
    """Reject path- and connector-shaped strings from the public projection."""
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    lowered = stripped.lower()
    return (
        "file://" in lowered
        or "iris://" in lowered
        or stripped.startswith(("/", "~/"))
        or "/users/" in lowered
    )


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
