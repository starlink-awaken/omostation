#!/usr/bin/env python3
"""Normalize a Scene Card into a safe, proposal-only intake projection.

The intake gate accepts a business-owned Scene Card, validates its contract and
reference boundaries, and returns the next governed step. It never reads raw
documents, persists the card, calls a provider, creates a WorkflowRun, or
activates a capability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, TextIO

SCHEMA = "scene-card-intake/v1"
SCENE_CARD_SCHEMA = "scene-card/v1"
OPAQUE_REF_PREFIXES = ("vault://", "evidence://", "ref://", "sample://")
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
REF_FIELDS = ("sample_refs", "demand_evidence_refs", "activation_evidence_refs")
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
SAFE_SCENE_FIELDS = REQUIRED_SCENE_FIELDS + (
    "schema",
    "lifecycle",
    "approval_state",
    "external_resource_policy",
    "opportunity_window",
    # Scene Card 2.0 optional fields (L4 specification layer)
    "scene_type",
    "admission_track",
    "approval",
    "activation_blockers",
    "blocker_resolution",
    "notes",
    "downstream_refs",
    "permission_scope",
    "input_schema",
    "output_schema",
    "reflection_contract",
    "checkpoints",
    "event_subscription",
)


class IntakeInputError(ValueError):
    """Raised when input cannot be safely normalized."""


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
        raise IntakeInputError(f"{field} must be a list")
    refs = sorted({str(item).strip() for item in value if str(item).strip()})
    if any(not ref.startswith(OPAQUE_REF_PREFIXES) for ref in refs):
        raise IntakeInputError(f"{field} must use opaque references")
    return refs


def _capabilities(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise IntakeInputError(f"{field} must be a list")
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _source_digest(scene_card: dict[str, Any]) -> str:
    canonical = json.dumps(scene_card, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _intake_id(scene_card: dict[str, Any], source_digest: str) -> str:
    scene_id = _text(scene_card.get("scene_id")) or "unidentified"
    digest = hashlib.sha256(f"{scene_id}:{source_digest}".encode()).hexdigest()[:16]
    return f"scene-intake:{scene_id}:{digest}"


def _safe_scene_snapshot(scene_card: dict[str, Any]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for field in SAFE_SCENE_FIELDS:
        value = scene_card.get(field)
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            if _text(value):
                snapshot[field] = value
        elif isinstance(value, (dict, list)):
            # Complex fields (2.0 schema: input_schema, checkpoints, etc.)
            # Raw content already checked by _find_raw_field recursion
            snapshot[field] = value
    for field in REF_FIELDS:
        snapshot[field] = _refs(scene_card.get(field, []), f"scene_card.{field}")
    required_capabilities = scene_card.get("required_capabilities")
    if required_capabilities is None:
        required_capabilities = scene_card.get("capability_refs", [])
    snapshot["required_capabilities"] = _capabilities(
        required_capabilities, "scene_card.required_capabilities"
    )
    return snapshot


def build_intake(scene_card: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic intake projection without side effects."""
    if not isinstance(scene_card, dict):
        raise IntakeInputError("scene card must be a JSON object")
    raw_field = _find_raw_field(scene_card)
    if raw_field:
        raise IntakeInputError(f"scene card contains forbidden field: {raw_field}")
    if scene_card.get("schema") != SCENE_CARD_SCHEMA:
        raise IntakeInputError(f"scene card must use {SCENE_CARD_SCHEMA}")

    source_digest = _source_digest(scene_card)
    safe_scene = _safe_scene_snapshot(scene_card)
    missing = [field for field in REQUIRED_SCENE_FIELDS if not _text(scene_card.get(field))]
    sample_refs = safe_scene["sample_refs"]
    demand_refs = safe_scene["demand_evidence_refs"]
    activation_refs = safe_scene["activation_evidence_refs"]
    required_capabilities = safe_scene["required_capabilities"]
    if not 3 <= len(sample_refs) <= 10:
        missing.append("sample_refs:3-10")
    if not demand_refs and not _text(scene_card.get("opportunity_window")):
        missing.append("demand_evidence_refs_or_opportunity_window")
    if not activation_refs:
        missing.append("activation_evidence_refs")
    if not required_capabilities:
        missing.append("required_capabilities")
    if scene_card.get("activation") not in {None, "forbidden"}:
        missing.append("activation_must_be_forbidden")
    if scene_card.get("lifecycle") not in {None, "proposal_only"}:
        missing.append("lifecycle_must_be_proposal_only")

    missing = sorted(set(missing))
    status = "blocked" if missing else "proposal_only"
    next_action = (
        "complete_scene_card_and_resubmit"
        if missing
        else "run_external_activation_preflight"
    )
    return {
        "schema": SCHEMA,
        "mode": "proposal_only_intake",
        "intake_id": _intake_id(scene_card, source_digest),
        "source_digest": source_digest,
        "status": status,
        "next_action": next_action,
        "activation": "forbidden",
        "missing_fields": missing,
        "scene_card": safe_scene,
        "side_effects": {
            "raw_content_read": False,
            "provider_called": False,
            "omo_written": False,
            "workflow_created": False,
            "activation_attempted": False,
        },
    }


def _load_json(stream: TextIO) -> dict[str, Any]:
    try:
        payload = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise IntakeInputError("input must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise IntakeInputError("input must be a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Scene Card JSON; stdin by default")
    args = parser.parse_args(argv)
    try:
        if args.input:
            with args.input.open(encoding="utf-8") as stream:
                scene_card = _load_json(stream)
        else:
            scene_card = _load_json(sys.stdin)
        result = build_intake(scene_card)
    except (OSError, IntakeInputError) as exc:
        print(f"scene-card-intake: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
