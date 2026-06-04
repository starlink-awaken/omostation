from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

try:
    from .omo_debt_metrics import collect_stale_evidence_item_ids
    from .omo_debt_registry import DebtItem
except ModuleNotFoundError:
    from .omo_debt_metrics import collect_stale_evidence_item_ids
    from .omo_debt_registry import DebtItem


REVIEW_WINDOW_DAYS = 7
ESCALATION_THRESHOLD_DAYS = 3
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
GATE_ORDER = {"gate": 0, "watchlist": 1, "none": 2}


def _parse_iso8601(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(value) from exc


def _normalize_owner(owner: str) -> str:
    return owner or "unowned"


def _priority_reason(item: DebtItem, stale_ids: set[str], overdue_by: int) -> str:
    if item.gate_level == "gate" and overdue_by > 0:
        return "gate_overdue"
    if item.id in stale_ids and overdue_by > 0:
        return "stale_and_overdue"
    if overdue_by >= ESCALATION_THRESHOLD_DAYS:
        return "overdue_threshold"
    if item.severity == "critical" and overdue_by > 0:
        return "critical_overdue"
    if overdue_by > 0:
        return "due_now"
    return "upcoming"


def _entry_payload(item: DebtItem, *, stale_ids: set[str], overdue_by: int) -> dict[str, object]:
    return {
        "id": item.id,
        "title": item.title,
        "owner": _normalize_owner(item.owner),
        "severity": item.severity,
        "dimension": item.dimension,
        "subdimension": item.subdimension,
        "lifecycle_state": item.lifecycle_state,
        "gate_level": item.gate_level,
        "next_review_at": item.next_review_at,
        "last_reviewed_at": item.last_reviewed_at,
        "stale_evidence": item.id in stale_ids,
        "overdue_by": overdue_by,
        "affected_roots": list(item.affected_roots),
        "priority_reason": _priority_reason(item, stale_ids, overdue_by),
    }


def build_review_queue(items: tuple[DebtItem, ...], now: str, repo_root: Path) -> dict[str, object]:
    current = _parse_iso8601(now)
    upcoming_cutoff = current + timedelta(days=REVIEW_WINDOW_DAYS)
    stale_ids = collect_stale_evidence_item_ids(items, repo_root=repo_root)
    due_now: list[dict[str, object]] = []
    upcoming: list[dict[str, object]] = []
    escalation_candidates: list[dict[str, object]] = []
    unscheduled: list[dict[str, object]] = []

    for item in items:
        if item.lifecycle_state == "closed":
            continue
        if not item.next_review_at:
            unscheduled.append(_entry_payload(item, stale_ids=stale_ids, overdue_by=0))
            continue

        due_at = _parse_iso8601(item.next_review_at)
        overdue_by = max((current - due_at).days, 0)
        entry = _entry_payload(item, stale_ids=stale_ids, overdue_by=overdue_by)

        if due_at <= current:
            due_now.append(entry)
        elif due_at <= upcoming_cutoff:
            upcoming.append(entry)

        if (
            (item.gate_level == "gate" and overdue_by > 0)
            or overdue_by >= ESCALATION_THRESHOLD_DAYS
            or (item.id in stale_ids and overdue_by > 0)
            or (item.severity == "critical" and overdue_by > 0)
        ):
            escalation_candidates.append({**entry, "escalation_reason": entry["priority_reason"]})

    def severity_rank(severity):
        return SEVERITY_ORDER.get(str(severity), 99)
    def gate_rank(gate):
        return GATE_ORDER.get(str(gate), 99)
    due_now.sort(key=lambda entry: (gate_rank(entry["gate_level"]), severity_rank(entry["severity"]), -int(entry["overdue_by"]), entry["id"]))
    escalation_candidates.sort(
        key=lambda entry: (gate_rank(entry["gate_level"]), severity_rank(entry["severity"]), -int(entry["overdue_by"]), entry["id"])
    )
    upcoming.sort(key=lambda entry: (entry["next_review_at"], severity_rank(entry["severity"]), entry["id"]))
    unscheduled.sort(key=lambda entry: (severity_rank(entry["severity"]), entry["id"]))

    open_items = [item for item in items if item.lifecycle_state != "closed"]
    return {
        "generated_at": now,
        "defaults": {
            "review_window_days": REVIEW_WINDOW_DAYS,
            "escalation_threshold_days": ESCALATION_THRESHOLD_DAYS,
        },
        "due_now": due_now,
        "upcoming": upcoming,
        "escalation_candidates": escalation_candidates,
        "unscheduled": unscheduled,
        "summary": {
            "due_now_count": len(due_now),
            "upcoming_count": len(upcoming),
            "escalation_candidate_count": len(escalation_candidates),
            "unscheduled_count": len(unscheduled),
            "by_severity": {
                severity: sum(1 for item in open_items if item.severity == severity)
                for severity in ("critical", "high", "medium", "low")
                if any(item.severity == severity for item in open_items)
            },
            "by_gate_level": {
                gate_level: sum(1 for item in open_items if item.gate_level == gate_level)
                for gate_level in ("gate", "watchlist", "none")
                if any(item.gate_level == gate_level for item in open_items)
            },
            "by_owner": {
                owner: sum(1 for item in open_items if _normalize_owner(item.owner) == owner)
                for owner in sorted({_normalize_owner(item.owner) for item in open_items})
            },
        },
    }
