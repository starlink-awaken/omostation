"""DTO projections for Cockpit Workflow Mesh operations."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

try:
    from cockpit.web.auth import ApiAuthenticationError
except Exception:  # pragma: no cover - defensive fallback
    ApiAuthenticationError = ValueError  # type: ignore[assignment,misc]

try:
    from fastapi.responses import JSONResponse
except Exception:  # pragma: no cover - defensive fallback
    JSONResponse = None  # type: ignore[assignment,misc]

from .mesh_helpers import _projection_fields, _projection_value_is_private


def _episode_projection_http_dto(projection: Any) -> dict[str, Any]:
    """Build the public allowlisted DTO without mutating OMO's ledger view."""
    if not isinstance(projection, dict):
        return {}

    episodes: list[dict[str, Any]] = []
    for raw_episode in projection.get("episodes", []):
        episode = _projection_fields(
            raw_episode,
            (
                "episode_id",
                "schema_version",
                "opened_at",
                "closed_at",
                "status",
                "name",
                "event_count",
            ),
        )
        members: list[dict[str, Any]] = []
        if isinstance(raw_episode, dict):
            for raw_member in raw_episode.get("contains_event_refs", []):
                member = _projection_fields(
                    raw_member,
                    ("event_id", "schema_version", "emitted_at"),
                )
                raw_payload = raw_member.get("payload", {}) if isinstance(raw_member, dict) else {}
                member["payload"] = _projection_fields(
                    raw_payload,
                    (
                        "episode_id",
                        "request_id",
                        "summary",
                        "why_now",
                        "deadline",
                        "status",
                        "confidence",
                        "role_id",
                        "responsibility_id",
                        "action_id",
                        "output_origin",
                        "feedback_id",
                        "verdict",
                        "review_duration_seconds",
                        "estimated_time_saved_seconds",
                    ),
                )
                members.append(member)
        episode["contains_event_refs"] = members
        episodes.append(episode)

    raw_portfolio = projection.get("role_portfolio", {})
    role_portfolio = _projection_fields(raw_portfolio, ("principal_id",))
    assignments: list[dict[str, Any]] = []
    responsibilities: list[dict[str, Any]] = []
    if isinstance(raw_portfolio, dict):
        for raw_assignment in raw_portfolio.get("active_assignments", []):
            assignment = _projection_fields(
                raw_assignment,
                (
                    "assignment_id",
                    "principal_id",
                    "role_id",
                    "role_name",
                    "role_scope",
                    "version",
                    "status",
                ),
            )
            if isinstance(raw_assignment, dict):
                assignment["responsibilities"] = [
                    _projection_fields(item, ("resp_id", "responsibility_id", "name", "version"))
                    for item in raw_assignment.get("responsibilities", [])
                    if isinstance(item, dict)
                ]
            assignments.append(assignment)
        responsibilities = [
            _projection_fields(item, ("resp_id", "responsibility_id", "name", "version"))
            for item in raw_portfolio.get("responsibilities", [])
            if isinstance(item, dict)
        ]
        raw_counts = raw_portfolio.get("episode_counts", {})
        episode_counts = (
            {
                key: value
                for key, value in raw_counts.items()
                if isinstance(key, str)
                and not _projection_value_is_private(key)
                and isinstance(value, int)
                and not isinstance(value, bool)
            }
            if isinstance(raw_counts, dict)
            else {}
        )
    else:
        episode_counts = {}
    role_portfolio.update(
        {
            "active_assignments": assignments,
            "responsibilities": responsibilities,
            "episode_counts": episode_counts,
        }
    )

    inbox = [
        _projection_fields(
            item,
            (
                "card_type",
                "episode",
                "principal",
                "role",
                "responsibility",
                "request",
                "summary",
                "why_now",
                "risk",
                "authority",
                "deadline",
                "status",
                "confidence",
            ),
        )
        for item in projection.get("inbox", [])
        if isinstance(item, dict)
    ]
    blocked = [
        _projection_fields(item, ("event_id", "event_type", "sequence", "reason"))
        for item in projection.get("blocked", [])
        if isinstance(item, dict)
    ]
    raw_controls = projection.get("controls", {})
    controls = _projection_fields(
        raw_controls,
        (
            "events_read",
            "events_ignored",
            "events_blocked",
            "ledger_count_before",
            "ledger_count_after",
            "ledger_unchanged",
        ),
    )
    if isinstance(raw_controls, dict):
        controls["chain_before"] = _projection_fields(raw_controls.get("chain_before"), ("ok", "total"))
        controls["chain_after"] = _projection_fields(raw_controls.get("chain_after"), ("ok", "total"))

    dto = _projection_fields(projection, ("schema_version", "status", "principal_id"))
    dto.update(
        {
            "episodes": episodes,
            "role_portfolio": role_portfolio,
            "inbox": inbox,
            "blocked": blocked,
            "controls": controls,
        }
    )
    return dto


def _engineering_delivery_queue_http_dto(projection: Any) -> dict[str, Any]:
    """Allowlist the public engineering-delivery review projection."""
    if not isinstance(projection, dict):
        return {}
    result = _projection_fields(
        projection,
        ("schema", "status", "generated_at", "value_indicator_policy"),
    )
    result["summary"] = _projection_fields(
        projection.get("summary"),
        (
            "row_count",
            "pending_review_count",
            "reviewed_count",
            "adopted_count",
            "rejected_count",
        ),
    )
    rows: list[dict[str, Any]] = []
    for raw in projection.get("rows", []):
        row = _projection_fields(
            raw,
            (
                "delivery_id",
                "workflow_run_id",
                "workflow_state",
                "review_status",
                "decision",
                "latest_decision",
                "submitted_at",
                "reviewed_at",
                "delivery_duration_seconds",
                "evidence_count",
                "receipt_id",
                "outcome_id",
                "value_indicator_policy",
            ),
        )
        if isinstance(raw, dict):
            row["scene_binding"] = _projection_fields(
                raw.get("scene_binding"),
                ("scene_id", "journey_id", "outcome_metric"),
            )
        rows.append(row)
    result["rows"] = rows
    result["controls"] = {
        "read_only": True,
        "workflow_state_mutation": False,
        "provider_invocation": False,
        "automatic_promotion": False,
        "value_indicator_policy": False,
    }
    return result


def _workflow_mesh_operations_http_dto(projection: dict[str, Any]) -> dict[str, Any]:
    """Keep dedicated human-review scenes out of the generic feedback picker."""
    result = dict(projection)
    consumption = projection.get("consumption")
    if not isinstance(consumption, dict):
        return result
    eligible = consumption.get("eligible_outcomes")
    if not isinstance(eligible, list):
        return result
    result["consumption"] = {
        **consumption,
        "eligible_outcomes": [
            item
            for item in eligible
            if not (
                isinstance(item, dict)
                and isinstance(item.get("scene_binding"), dict)
                and item["scene_binding"].get("scene_id") == "engineering-delivery"
            )
        ],
        "dedicated_review_scenes": ["engineering-delivery"],
    }
    return result


def _engineering_delivery_review_http_dto(review: Any) -> dict[str, Any]:
    """Allowlist a persisted review acknowledgement without leaking internals."""
    if not isinstance(review, dict):
        return {}
    return _projection_fields(
        review,
        (
            "schema",
            "status",
            "delivery_id",
            "workflow_run_id",
            "decision",
            "reviewed_at",
            "outcome_id",
            "decision_outcome_id",
            "value_indicator_policy",
        ),
    )


def _engineering_delivery_auth_error(exc: Exception) -> Any:
    status_code = 401 if isinstance(exc, ApiAuthenticationError) else 403
    content = {
        "ok": False,
        "status": "unauthorized" if status_code == 401 else "forbidden",
        "error": (
            "engineering_delivery_auth_required" if status_code == 401 else "engineering_delivery_scope_required"
        ),
        "workflow_state_mutation": False,
        "provider_invocation": False,
        "automatic_promotion": False,
    }
    return JSONResponse(status_code=status_code, content=content) if JSONResponse is not None else content


def _personal_draft_dir() -> Path:
    """Resolve the server-owned local draft directory, never a caller path."""
    configured = os.environ.get("PERSONAL_DRAFT_DIR")
    if configured:
        return Path(configured).resolve()
    repo_root = Path(__file__).resolve().parents[5]
    return (repo_root / "runtime" / "omo" / "personal-drafts").resolve()


def _write_local_draft(
    context: Any,
    draft: dict[str, str],
    output_origin: str = "system",
) -> Path:
    """Atomically persist one server-named, never-send JSON artifact."""
    draft_dir = _personal_draft_dir()
    draft_dir.mkdir(parents=True, exist_ok=True)
    stable_name = hashlib.sha256(f"{context.episode_id}|{context.action_id}".encode()).hexdigest()[:24]
    target = draft_dir / f"personal-followup-{stable_name}.json"
    payload = {**draft, "never_send": True, "output_origin": output_origin}
    descriptor, temporary_name = tempfile.mkstemp(
        dir=draft_dir,
        prefix=f".{target.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=False)
            handle.write("\n")
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def _personal_draft_evidence_ref(artifact: Path) -> str:
    return f"file://{artifact}"


def _normalize_resp_input(
    responsibilities: list[str],
) -> tuple[list, set[str]]:
    """Normalize caller responsibility strings for OMO assign() and comparison.

    ``responsibility:xxx`` → mapping dict (exact resp_id, no re-slug);
    plain string → left as-is for OMO slug+prefix normalization.
    Returns ``(items_for_assign, expected_canonical_ids)``.
    """
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
    """Deterministically build a safe draft dict from a persisted Episode snapshot.

    Only uses fields already in the ledger event — summary, why_now,
    deadline.  Never touches raw signal body, filesystem paths, or URIs.
    """
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
