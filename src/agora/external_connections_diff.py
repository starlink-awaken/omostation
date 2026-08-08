"""External resource catalog diff — god-module split from external_connections.py.

catalog snapshot diff + change classification (admission-relevant vs health noise).
从 external_connections.py 抽离 (2026-08-06, god-module 拆解: 1663→<1500).
依赖: ExternalConnectionError (核心 error, 保留在 external_connections.py).
循环 import 安全: 本模块顶层 import ExternalConnectionError, external_connections
在 ExternalConnectionError 定义后 re-export diff_external_resource_catalog_snapshots.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from agora.external_connections_models import ExternalConnectionError

_CATALOG_DIFF_FIELDS = (
    "provider",
    "version",
    "capabilities",
    "mode",
    "lifecycle",
    "availability",
    "reason_codes",
    "health",
    "permission_ref",
    "expires_at",
    "review_at",
    "rollback_plan",
)

_REVIEW_REQUIRED_CHANGE_FIELDS = frozenset(
    {
        "provider",
        "protocol",
        "version",
        "capabilities",
        "mode",
        "lifecycle",
        "permission_ref",
        "expires_at",
        "review_at",
        "rollback_plan",
    }
)


def _classify_catalog_change(
    change: str, changed_fields: Iterable[str]
) -> dict[str, Any]:
    """Separate admission-relevant descriptor changes from health noise."""
    fields = frozenset(changed_fields)
    if change == "added":
        return {
            "review_required": True,
            "risk_class": "manual_review",
            "risk_codes": ["resource_added"],
        }
    if change == "removed":
        return {
            "review_required": True,
            "risk_class": "manual_review",
            "risk_codes": ["resource_removed"],
        }
    if fields & _REVIEW_REQUIRED_CHANGE_FIELDS:
        return {
            "review_required": True,
            "risk_class": "manual_review",
            "risk_codes": [
                f"descriptor_{field}_changed"
                for field in sorted(fields & _REVIEW_REQUIRED_CHANGE_FIELDS)
            ],
        }
    return {
        "review_required": False,
        "risk_class": "operational_observation",
        "risk_codes": [f"{field}_changed" for field in sorted(fields)],
    }


def _catalog_resource_view(resource: Mapping[str, Any]) -> dict[str, Any]:
    resource_id = str(resource.get("id") or "").strip()
    if not resource_id:
        raise ExternalConnectionError("catalog resource is missing id")
    return {key: resource.get(key) for key in _CATALOG_DIFF_FIELDS if key in resource}


def _catalog_resource_index(
    snapshot: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    resources = snapshot.get("resources", [])
    if not isinstance(resources, list):
        raise ExternalConnectionError("catalog resources must be a list")
    indexed: dict[str, Mapping[str, Any]] = {}
    for resource in resources:
        if not isinstance(resource, Mapping):
            raise ExternalConnectionError("catalog resource must be an object")
        resource_id = str(resource.get("id") or "").strip()
        if not resource_id:
            raise ExternalConnectionError("catalog resource is missing id")
        if resource_id in indexed:
            raise ExternalConnectionError(f"duplicate catalog resource: {resource_id}")
        indexed[resource_id] = resource
    return indexed


def _catalog_errors(snapshot: Mapping[str, Any]) -> set[tuple[str, str, str]]:
    errors = snapshot.get("errors", [])
    if not isinstance(errors, list):
        raise ExternalConnectionError("catalog errors must be a list")
    normalized: set[tuple[str, str, str]] = set()
    for error in errors:
        if not isinstance(error, Mapping):
            raise ExternalConnectionError("catalog error must be an object")
        normalized.add(
            (
                str(error.get("entry_point") or ""),
                str(error.get("status") or ""),
                str(error.get("error") or ""),
            )
        )
    return normalized


def diff_external_resource_catalog_snapshots(
    previous: Mapping[str, Any], current: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare two safe catalog projections without persisting either one."""
    for name, snapshot in (("previous", previous), ("current", current)):
        if (
            not isinstance(snapshot, Mapping)
            or snapshot.get("schema") != "external-resource-catalog/v1"
        ):
            raise ExternalConnectionError(f"{name} is not an external resource catalog")

    previous_index = _catalog_resource_index(previous)
    current_index = _catalog_resource_index(current)
    changes: list[dict[str, Any]] = []
    for resource_id in sorted(set(previous_index) | set(current_index)):
        old = previous_index.get(resource_id)
        new = current_index.get(resource_id)
        if old is None:
            item = {
                "id": resource_id,
                "change": "added",
                "changed_fields": list(_CATALOG_DIFF_FIELDS),
                "previous": None,
                "current": _catalog_resource_view(new),  # type: ignore[reportArgumentType]
            }
            item.update(_classify_catalog_change("added", item["changed_fields"]))
            changes.append(item)
            continue
        if new is None:
            item = {
                "id": resource_id,
                "change": "removed",
                "changed_fields": list(_CATALOG_DIFF_FIELDS),
                "previous": _catalog_resource_view(old),
                "current": None,
            }
            item.update(_classify_catalog_change("removed", item["changed_fields"]))
            changes.append(item)
            continue
        old_view = _catalog_resource_view(old)
        new_view = _catalog_resource_view(new)
        changed_fields = [
            field
            for field in _CATALOG_DIFF_FIELDS
            if old_view.get(field) != new_view.get(field)
        ]
        if changed_fields:
            item = {
                "id": resource_id,
                "change": "changed",
                "changed_fields": changed_fields,
                "previous": old_view,
                "current": new_view,
            }
            item.update(_classify_catalog_change("changed", changed_fields))
            changes.append(item)

    previous_errors = _catalog_errors(previous)
    current_errors = _catalog_errors(current)
    error_changes = [
        {
            "change": change,
            "entry_point": entry_point,
            "status": status,
            "error": error,
        }
        for change, error_set in (
            ("resolved", previous_errors - current_errors),
            ("added", current_errors - previous_errors),
        )
        for entry_point, status, error in sorted(error_set)
    ]
    return {
        "schema": "external-resource-catalog-diff/v1",
        "previous_observed_at": previous.get("observed_at"),
        "current_observed_at": current.get("observed_at"),
        "changes": changes,
        "error_changes": error_changes,
        "summary": {
            "change_count": len(changes),
            "added_count": sum(item["change"] == "added" for item in changes),
            "removed_count": sum(item["change"] == "removed" for item in changes),
            "changed_count": sum(item["change"] == "changed" for item in changes),
            "error_change_count": len(error_changes),
            "review_required": any(item["review_required"] for item in changes),
            "review_required_count": sum(item["review_required"] for item in changes),
            "operational_observation_count": sum(
                item["risk_class"] == "operational_observation" for item in changes
            ),
            "risk_codes": sorted(
                {code for item in changes for code in item["risk_codes"]}
            ),
        },
    }


__all__ = ["diff_external_resource_catalog_snapshots"]
