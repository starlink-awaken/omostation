#!/usr/bin/env python3
"""Build a read-only preflight for external connection activation.

The command joins a complete Scene Card with an observed external-resource
catalog. It never loads a provider, writes OMO state, creates a WorkflowRun,
or changes admission. The result is a safe checklist for the next human or
governed admission-preview step.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "external-activation-preflight/v1"
CATALOG_SCHEMA = "external-resource-catalog/v1"
DEFAULT_CATALOG_TTL_SECONDS = 3600
OPAQUE_REF_PREFIXES = ("vault://", "evidence://", "ref://", "sample://")
SCENE_CARD_SCHEMA = "scene-card/v1"
REQUIRED_SCENE_FIELDS = (
    "scene_id",
    "journey_id",
    "goal",
    "trigger",
    "input_contract",
    "result_contract",
    "outcome_metric",
    "consumer",
    "approver",
    "owner",
    "failure_cost",
    "data_classification",
    "data_scope",
    "operator",
    "permission_ref",
    "rollback_plan",
)
RAW_CONTENT_FIELDS = {
    "raw_content",
    "sample_data",
    "document_body",
    "content",
    "password",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
}


class PreflightInputError(ValueError):
    """Raised when a preflight input is unsafe or structurally invalid."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _find_raw_field(value: Any, path: str = "") -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).strip().lower()
            current = f"{path}.{key_text}" if path else key_text
            if key_text in RAW_CONTENT_FIELDS:
                return current
            found = _find_raw_field(nested, current)
            if found:
                return found
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found = _find_raw_field(nested, f"{path}[{index}]")
            if found:
                return found
    return None


def _refs(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise PreflightInputError(f"{field} must be a list")
    refs = sorted({str(item).strip() for item in value if str(item).strip()})
    return refs


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreflightInputError(f"cannot read JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise PreflightInputError(f"JSON must be an object: {path}")
    return payload


def _validate_catalog(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    if catalog.get("schema") != CATALOG_SCHEMA:
        raise PreflightInputError("catalog must be external-resource-catalog/v1")
    if catalog.get("mode") != "read_only_projection":
        raise PreflightInputError("catalog must be read_only_projection")
    if catalog.get("activation") != "forbidden":
        raise PreflightInputError("catalog activation must be forbidden")
    raw_field = _find_raw_field(catalog)
    if raw_field:
        raise PreflightInputError(f"catalog contains forbidden field: {raw_field}")
    resources = catalog.get("resources")
    if not isinstance(resources, list):
        raise PreflightInputError("catalog.resources must be a list")
    return [resource for resource in resources if isinstance(resource, dict)]


def _catalog_freshness(
    catalog: dict[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    """Classify the catalog snapshot itself, separately from provider health."""
    observed_at = _text(catalog.get("observed_at"))
    raw_ttl = catalog.get("catalog_ttl_seconds", DEFAULT_CATALOG_TTL_SECONDS)
    if isinstance(raw_ttl, bool) or not isinstance(raw_ttl, int) or raw_ttl <= 0:
        return {
            "status": "unknown",
            "observed_at": observed_at or None,
            "age_seconds": None,
            "ttl_seconds": None,
            "reason_codes": ["invalid_catalog_ttl"],
        }
    if not observed_at:
        return {
            "status": "unknown",
            "observed_at": None,
            "age_seconds": None,
            "ttl_seconds": raw_ttl,
            "reason_codes": ["missing_catalog_observed_at"],
        }
    try:
        parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("catalog observed_at must include timezone")
    except ValueError:
        return {
            "status": "unknown",
            "observed_at": observed_at,
            "age_seconds": None,
            "ttl_seconds": raw_ttl,
            "reason_codes": ["invalid_catalog_observed_at"],
        }
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    age_seconds = max(0.0, (current - parsed).total_seconds())
    stale = age_seconds > raw_ttl
    return {
        "status": "stale" if stale else "fresh",
        "observed_at": observed_at,
        "age_seconds": age_seconds,
        "ttl_seconds": raw_ttl,
        "reason_codes": ["catalog_stale"] if stale else [],
    }


def _scene_card_check(scene_card: dict[str, Any]) -> dict[str, Any]:
    raw_field = _find_raw_field(scene_card)
    if raw_field:
        raise PreflightInputError(f"scene card contains forbidden field: {raw_field}")

    schema = scene_card.get("schema")
    if schema is not None and schema != SCENE_CARD_SCHEMA:
        raise PreflightInputError(f"scene card must use {SCENE_CARD_SCHEMA}")

    missing = [field for field in REQUIRED_SCENE_FIELDS if not _text(scene_card.get(field))]
    sample_refs = _refs(scene_card.get("sample_refs", []), "scene_card.sample_refs")
    demand_refs = _refs(
        scene_card.get("demand_evidence_refs", []),
        "scene_card.demand_evidence_refs",
    )
    activation_refs = _refs(
        scene_card.get("activation_evidence_refs", []),
        "scene_card.activation_evidence_refs",
    )
    for field, refs in (
        ("sample_refs", sample_refs),
        ("demand_evidence_refs", demand_refs),
        ("activation_evidence_refs", activation_refs),
    ):
        if any(not ref.startswith(OPAQUE_REF_PREFIXES) for ref in refs):
            raise PreflightInputError(f"scene_card.{field} must use opaque references")
    if not 3 <= len(sample_refs) <= 10:
        missing.append("sample_refs:3-10")
    if not demand_refs and not _text(scene_card.get("opportunity_window")):
        missing.append("demand_evidence_refs_or_opportunity_window")
    if not activation_refs:
        missing.append("activation_evidence_refs")

    required_capabilities = scene_card.get("required_capabilities")
    if required_capabilities is None:
        required_capabilities = scene_card.get("capability_refs", [])
    required_capabilities = _refs(
        required_capabilities, "scene_card.required_capabilities"
    )
    if not required_capabilities:
        missing.append("required_capabilities")
    if scene_card.get("activation") not in {None, "forbidden"}:
        missing.append("activation_must_be_forbidden")
    if scene_card.get("lifecycle") not in {None, "proposal_only"}:
        missing.append("lifecycle_must_be_proposal_only")

    return {
        "missing_fields": sorted(set(missing)),
        "sample_ref_count": len(sample_refs),
        "demand_evidence_ref_count": len(demand_refs),
        "activation_evidence_ref_count": len(activation_refs),
        "required_capabilities": required_capabilities,
    }


def _capability_checks(
    required_capabilities: list[str], resources: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for capability in required_capabilities:
        matches = [
            resource
            for resource in resources
            if capability in resource.get("capabilities", [])
        ]
        safe_matches = [
            {
                "resource_id": str(resource.get("id", "")),
                "availability": str(resource.get("availability", "unavailable")),
                "lifecycle": str(resource.get("lifecycle", "unknown")),
                "reason_codes": sorted(
                    str(reason) for reason in resource.get("reason_codes", [])
                ),
            }
            for resource in matches
        ]
        executable = [
            item
            for item in safe_matches
            if item["availability"] in {"available", "degraded"}
        ]
        proposal = [
            item for item in safe_matches if item["availability"] == "proposal_only"
        ]
        checks.append(
            {
                "capability": capability,
                "status": (
                    "available"
                    if executable
                    else "proposal_only"
                    if proposal
                    else "unavailable"
                ),
                "candidates": safe_matches,
            }
        )
    return checks


def build_preflight(
    scene_card: dict[str, Any],
    catalog: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a deterministic, non-activating activation readiness projection."""
    resources = _validate_catalog(catalog)
    catalog_freshness = _catalog_freshness(catalog, now=now)
    scene_check = _scene_card_check(scene_card)
    capability_checks = _capability_checks(
        scene_check["required_capabilities"], resources
    )
    missing = list(scene_check["missing_fields"])
    if any(check["status"] == "unavailable" for check in capability_checks):
        missing.append("catalog_capability_availability")
    if catalog_freshness["status"] != "fresh":
        missing.append("catalog_freshness")
    proposal_only = any(
        check["status"] == "proposal_only" for check in capability_checks
    )
    if missing:
        status = "blocked"
        next_action = "complete_scene_card_and_refresh_catalog"
    elif proposal_only:
        status = "proposal_only"
        next_action = "replace_proposal_only_capabilities_before_admission"
    else:
        status = "ready_for_admission_preview"
        next_action = "submit_omo_admission_preview"
    return {
        "schema": SCHEMA,
        "mode": "read_only_preflight",
        "activation": "forbidden",
        "scene": {
            "scene_id": _text(scene_card.get("scene_id")),
            "journey_id": _text(scene_card.get("journey_id")),
            "outcome_metric": _text(scene_card.get("outcome_metric")),
        },
        "status": status,
        "next_action": next_action,
        "missing_fields": sorted(set(missing)),
        "scene_card": scene_check,
        "capability_checks": capability_checks,
        "catalog_freshness": catalog_freshness,
        "catalog_observed_at": catalog.get("observed_at"),
        "policy_digest": catalog.get("policy_digest"),
        "side_effects": {
            "provider_called": False,
            "omo_written": False,
            "workflow_created": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-card", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_preflight(_load_json(args.scene_card), _load_json(args.catalog))
    except (OSError, PreflightInputError) as exc:
        print(f"external-activation-preflight: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
