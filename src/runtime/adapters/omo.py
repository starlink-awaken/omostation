"""Anti-corruption adapter for projects/omo (L2).

Re-exports the OMO governance symbols used by runtime scheduler.
Gracefully degrades if OMO modules are unavailable (ModuleNotFoundError).
"""

from __future__ import annotations

from typing import Any


def archive_resolved_debt_items(*args: Any, **kwargs: Any) -> Any:
    """Archive resolved debt items. Lazily imports from omo."""
    try:
        from omo.omo_gc import archive_resolved_debt_items as _fn

        return _fn(*args, **kwargs)
    except ModuleNotFoundError:
        pass
    return []


def summarize_system_health_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Summarize system health snapshot. Lazily imports from omo, falls back to direct summary."""
    try:
        from omo.omo_state_schema import summarize_system_health_snapshot as _fn

        return _fn(snapshot)
    except (ModuleNotFoundError, ImportError):
        pass
    # Direct summary from snapshot data — omo_state_schema was removed in refactor
    services = snapshot.get("services", {})
    daemons = {k: v for k, v in services.items() if v.get("type") == "daemon"}
    online = sum(
        1 for v in daemons.values() if v.get("runtime", {}).get("status") == "running"
    )
    total = len(daemons) or 1
    return {
        "online_services": online,
        "total_services": total,
        "ratio": round(online / total, 2),
        "health_score": max(0, int((online / total) * 100)),
        "last_scan": str(snapshot.get("last_scan", "")),
        "service_count": len(services),
        "degraded": [
            k
            for k, v in services.items()
            if v.get("runtime", {}).get("status") == "degraded"
        ],
    }


__all__ = [
    "archive_resolved_debt_items",
    "summarize_system_health_snapshot",
]
