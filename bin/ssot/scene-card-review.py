#!/usr/bin/env python3
"""Create a safe, proposal-only review receipt for a Scene Card candidate.

The reviewer consumes a candidate projection manually. The command never
activates a connection, creates a WorkflowRun, writes OMO state, or emits raw
review notes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, TextIO

SCHEMA = "scene-card-review/v1"
SOURCE_SCHEMA = "scene-card-candidate/v1"
DECISIONS = ("pending", "request_evidence", "reject", "approve")


class ReviewInputError(ValueError):
    """Raised when a candidate projection is not safe to review."""


def _text(value: Any, field: str, *, required: bool = True) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise ReviewInputError(f"missing required field: {field}")
    return result


def _list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ReviewInputError(f"{field} must be a list")
    return [str(item).strip() for item in value if str(item).strip()]


def _read_json(stream: TextIO) -> dict[str, Any]:
    try:
        payload = json.load(stream)
    except (json.JSONDecodeError, OSError) as exc:
        raise ReviewInputError("input must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ReviewInputError("input must be a JSON object")
    return payload


def _digest(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _review_id(candidate_id: str, decision: str, reviewer_ref: str, note: str) -> str:
    material = json.dumps(
        {
            "candidate_id": candidate_id,
            "decision": decision,
            "reviewer_ref": reviewer_ref,
            "note_digest": _digest(note) if note else "",
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"review:{candidate_id}:{hashlib.sha256(material.encode()).hexdigest()[:16]}"


def _candidate(payload: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    if payload.get("schema") != SOURCE_SCHEMA:
        raise ReviewInputError(f"unsupported candidate schema: {payload.get('schema')}")
    if payload.get("mode") != "candidate_only":
        raise ReviewInputError("candidate projection must be candidate_only")
    if payload.get("activation") != "forbidden":
        raise ReviewInputError("candidate projection must forbid activation")

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ReviewInputError("candidates must be a list")
    matches = [
        item
        for item in candidates
        if isinstance(item, dict) and item.get("candidate_id") == candidate_id
    ]
    if not matches:
        raise ReviewInputError(f"candidate not found: {candidate_id}")
    if len(matches) != 1:
        raise ReviewInputError(f"duplicate candidate: {candidate_id}")
    candidate = matches[0]
    for field in ("activation_evidence_refs", "sample_refs", "demand_evidence_refs"):
        if _list(candidate.get(field), f"candidate.{field}"):
            raise ReviewInputError(f"candidate.{field} must be empty")
    if _text(candidate.get("opportunity_window"), "candidate.opportunity_window", required=False):
        raise ReviewInputError("candidate.opportunity_window must be empty")
    _text(candidate.get("title"), "candidate.title")
    _list(candidate.get("discovery_refs"), "candidate.discovery_refs")
    _list(candidate.get("missing_activation_fields"), "candidate.missing_activation_fields")
    return candidate


def create_review_receipt(
    payload: dict[str, Any],
    *,
    candidate_id: str,
    decision: str = "pending",
    reviewer_ref: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Convert one candidate into a deterministic, non-activating review receipt."""
    if decision not in DECISIONS:
        raise ReviewInputError(f"unsupported decision: {decision}")
    reviewer_ref = reviewer_ref.strip()
    note = note.strip()
    if decision != "pending" and not reviewer_ref:
        raise ReviewInputError("reviewer_ref is required for a decision")
    if decision != "pending" and not note:
        raise ReviewInputError("note is required for a decision")

    candidate = _candidate(payload, candidate_id)
    missing_fields = _list(
        candidate.get("missing_activation_fields"),
        "candidate.missing_activation_fields",
    )
    if decision == "approve":
        status = "blocked"
        reason = (
            "scene_card_incomplete"
            if missing_fields
            else "activation_requires_omo_admission"
        )
        next_action = "complete_scene_card_and_submit_evidence"
    elif decision == "request_evidence":
        status = "needs_evidence"
        reason = "business_evidence_requested"
        next_action = "collect_redacted_samples_and_confirm_scene_card"
    elif decision == "reject":
        status = "rejected"
        reason = "reviewer_rejected_candidate"
        next_action = "keep_candidate_inactive"
    else:
        status = "pending"
        reason = "awaiting_business_review"
        next_action = "assign_business_reviewer"

    safe_snapshot = {
        "title": candidate["title"],
        "discovery_refs": _list(candidate["discovery_refs"], "candidate.discovery_refs"),
        "proposed_scene_id": _text(
            candidate.get("proposed_scene_id"), "candidate.proposed_scene_id", required=False
        ),
        "proposed_journey_id": _text(
            candidate.get("proposed_journey_id"), "candidate.proposed_journey_id", required=False
        ),
        "outcome_metric_hint": _text(
            candidate.get("outcome_metric_hint"), "candidate.outcome_metric_hint", required=False
        ),
        "capability_refs": _list(candidate.get("capability_refs"), "candidate.capability_refs"),
        "safe_observations": _list(
            candidate.get("safe_observations"), "candidate.safe_observations"
        ),
    }
    return {
        "schema": SCHEMA,
        "review_id": _review_id(candidate_id, decision, reviewer_ref, note),
        "candidate_id": candidate_id,
        "decision": decision,
        "status": status,
        "reason": reason,
        "next_action": next_action,
        "manual_consumption": "review_queue",
        "activation": "forbidden",
        "activation_attempted": False,
        "reviewer_ref": reviewer_ref,
        "note_digest": _digest(note) if note else "",
        "safe_candidate_snapshot": safe_snapshot,
        "missing_activation_fields": missing_fields,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=None, help="candidate JSON; stdin by default")
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--decision", choices=DECISIONS, default="pending")
    parser.add_argument("--reviewer-ref", default="")
    parser.add_argument("--note", default="")
    args = parser.parse_args(argv)
    try:
        if args.input:
            with args.input.open(encoding="utf-8") as stream:
                payload = _read_json(stream)
        else:
            payload = _read_json(sys.stdin)
        receipt = create_review_receipt(
            payload,
            candidate_id=args.candidate_id,
            decision=args.decision,
            reviewer_ref=args.reviewer_ref,
            note=args.note,
        )
    except (OSError, ReviewInputError) as exc:
        print(f"scene-card-review: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
