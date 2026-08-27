"""Scenario-specific label contracts for KEMS human adjudication."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PRIVATE_SOURCE_REVIEW_SCENARIO = "private-source-review-v1"
PRIVATE_SOURCE_REVIEW_VERSION = "private-source-review-v1.0"
ENGINEERING_DELIVERY_REVIEW_SCENARIO = "engineering-delivery-review-v1"
ENGINEERING_DELIVERY_REVIEW_VERSION = "engineering-delivery-review-v1.0"

_ENUM_FIELDS = {
    "source_kind": {"oa", "email", "sms"},
    "document_type": {"task", "notice", "request", "alert", "transaction", "conversation", "other"},
    "actionability": {"actionable", "follow_up", "reference", "no_action"},
    "priority": {"urgent", "high", "normal", "low", "unknown"},
}
_BOOLEAN_FIELDS = {"has_deadline", "has_owner", "requires_omo_task"}
_REQUIRED_FIELDS = frozenset((*_ENUM_FIELDS, *_BOOLEAN_FIELDS))
_ENGINEERING_ENUM_FIELDS = {
    "delivery_quality": {"complete", "partial", "blocked", "unknown"},
    "evidence_sufficiency": {"sufficient", "insufficient", "unknown"},
    "workflow_alignment": {"aligned", "misaligned", "unknown"},
}
_ENGINEERING_BOOLEAN_FIELDS = {"requires_follow_up"}
_ENGINEERING_REQUIRED_FIELDS = frozenset((*_ENGINEERING_ENUM_FIELDS, *_ENGINEERING_BOOLEAN_FIELDS))


def annotation_schema(scenario_id: str) -> dict[str, Any]:
    """Return the versioned public label contract for a scenario."""
    if scenario_id != PRIVATE_SOURCE_REVIEW_SCENARIO:
        if scenario_id != ENGINEERING_DELIVERY_REVIEW_SCENARIO:
            return {"scenario_id": scenario_id, "schema_version": "generic-v1", "fields": []}
        fields = [
            {"name": field, "type": "enum", "values": sorted(values)}
            for field, values in _ENGINEERING_ENUM_FIELDS.items()
        ]
        fields.extend({"name": field, "type": "boolean"} for field in sorted(_ENGINEERING_BOOLEAN_FIELDS))
        return {
            "scenario_id": ENGINEERING_DELIVERY_REVIEW_SCENARIO,
            "schema_version": ENGINEERING_DELIVERY_REVIEW_VERSION,
            "fields": fields,
        }

    fields = [{"name": field, "type": "enum", "values": sorted(values)} for field, values in _ENUM_FIELDS.items()]
    fields.extend({"name": field, "type": "boolean"} for field in sorted(_BOOLEAN_FIELDS))
    return {
        "scenario_id": PRIVATE_SOURCE_REVIEW_SCENARIO,
        "schema_version": PRIVATE_SOURCE_REVIEW_VERSION,
        "fields": fields,
    }


def validate_annotation_labels(scenario_id: str, labels: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return labels without accepting free-form schema drift.

    Existing generic KEMS scenarios intentionally keep their historical label
    flexibility. The real private-source review scenario is stricter because
    its manifest is the production evaluation contract.
    """
    normalized = dict(labels)
    if scenario_id == ENGINEERING_DELIVERY_REVIEW_SCENARIO:
        normalized = dict(labels)
        missing = sorted(_ENGINEERING_REQUIRED_FIELDS - normalized.keys())
        extra = sorted(normalized.keys() - _ENGINEERING_REQUIRED_FIELDS)
        if missing or extra:
            details = []
            if missing:
                details.append(f"missing fields: {', '.join(missing)}")
            if extra:
                details.append(f"unsupported fields: {', '.join(extra)}")
            raise ValueError("engineering-delivery labels schema mismatch (" + "; ".join(details) + ")")
        for field, allowed in _ENGINEERING_ENUM_FIELDS.items():
            value = normalized[field]
            if not isinstance(value, str) or value not in allowed:
                options = ", ".join(sorted(allowed))
                raise ValueError(f"{field} must be one of: {options}")
        for field in _ENGINEERING_BOOLEAN_FIELDS:
            if type(normalized[field]) is not bool:
                raise ValueError(f"{field} must be a boolean")
        return normalized

    if scenario_id != PRIVATE_SOURCE_REVIEW_SCENARIO:
        return normalized

    missing = sorted(_REQUIRED_FIELDS - normalized.keys())
    extra = sorted(normalized.keys() - _REQUIRED_FIELDS)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if extra:
            details.append(f"unsupported fields: {', '.join(extra)}")
        raise ValueError("private-source-review labels schema mismatch (" + "; ".join(details) + ")")

    for field, allowed in _ENUM_FIELDS.items():
        value = normalized[field]
        if not isinstance(value, str) or value not in allowed:
            options = ", ".join(sorted(allowed))
            raise ValueError(f"{field} must be one of: {options}")
    for field in _BOOLEAN_FIELDS:
        if type(normalized[field]) is not bool:
            raise ValueError(f"{field} must be a boolean")
    return normalized
