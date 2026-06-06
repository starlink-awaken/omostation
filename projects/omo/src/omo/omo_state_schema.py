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
}

_RUNTIME_ONLY_KEYS = {
    "last_scan",
    "services",
}


def _require_mapping(payload: Any, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a mapping")
    return payload


def validate_system_health_snapshot(payload: Any) -> dict[str, Any]:
    snapshot = _require_mapping(payload, "system_health snapshot")
    mixed = sorted(_GOVERNANCE_ONLY_KEYS.intersection(snapshot))
    if mixed:
        raise ValueError(
            "system_health snapshot contains governance-only keys: "
            + ", ".join(mixed)
        )
    services = snapshot.get("services")
    if services is not None and not isinstance(services, dict):
        raise ValueError("system_health snapshot services must be a mapping")
    return snapshot


def validate_system_state(payload: Any) -> dict[str, Any]:
    state = _require_mapping(payload, "system state")
    mixed = sorted(_RUNTIME_ONLY_KEYS.intersection(state))
    if mixed:
        raise ValueError(
            "system state contains runtime-snapshot keys: " + ", ".join(mixed)
        )
    return state


def summarize_system_health_snapshot(payload: Any) -> dict[str, Any]:
    snapshot = validate_system_health_snapshot(payload)
    services = snapshot.get("services") or {}
    total = len(services)
    online = 0
    healthy = 0
    unhealthy_services: list[str] = []
    stale_services: list[str] = []

    for name, service in services.items():
        if not isinstance(service, dict):
            continue
        if service.get("port_listening") is True:
            online += 1
        if service.get("health_check") == "healthy":
            healthy += 1
        elif service.get("health_check") not in (None, "unknown"):
            unhealthy_services.append(str(name))
        freshness_seconds = service.get("runtime", {}).get("freshness_seconds")
        if isinstance(freshness_seconds, int) and freshness_seconds > 86400:
            stale_services.append(str(name))

    return {
        "last_scan": snapshot.get("last_scan"),
        "total_services": total,
        "online_services": online,
        "healthy_services": healthy,
        "offline_services": max(total - online, 0),
        "unhealthy_services": sorted(unhealthy_services),
        "stale_services": sorted(stale_services),
    }
