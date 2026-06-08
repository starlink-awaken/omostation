"""Runtime state schema helpers.

Keep this intentionally small: runtime only validates the shape it owns.
It should not import governance-layer contracts from projects/omo.
"""

from __future__ import annotations

from typing import Any


_GOVERNANCE_ONLY_KEYS = {
    "current_phase",
    "current_wave",
    "phase_status",
    "next_milestone",
    "health_score",
    "health_score_raw",
    "debt_weight",
    "debt_weight_items",
    "divergence_flags",
    "divergence_detail_refs",
    "promotion_blockers",
    "task_gate_summary",
    "next_active_tasks",
    "next_planned_tasks",
    "completed_tasks",
    "planned_tasks",
    "blocked_tasks",
    "total_tasks",
    "runtime_health_summary",
}


def validate_runtime_health_snapshot(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("runtime health snapshot must be a mapping")
    mixed = sorted(_GOVERNANCE_ONLY_KEYS.intersection(payload))
    if mixed:
        raise ValueError(
            "runtime health snapshot contains governance-only keys: "
            + ", ".join(mixed)
        )
    services = payload.get("services")
    if not isinstance(services, dict):
        raise ValueError("runtime health snapshot services must be a mapping")
    return payload
