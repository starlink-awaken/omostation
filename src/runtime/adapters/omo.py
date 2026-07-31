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


def _daemon_is_online(service: dict[str, Any]) -> bool:
    """G-CONV.2/3 de-false-positive online check (align compass_radar.collect_runtime_health).

    idle ≠ down (port listening / healthy empty load).
    healthy / healthy (probe) count online even when runtime status is degraded
    only if health_check still starts with healthy — degraded without healthy is offline.
    """
    if not isinstance(service, dict):
        return False
    runtime = service.get("runtime") or {}
    status = str(runtime.get("status") or "").lower()
    hc = str(service.get("health_check") or "").strip().lower()
    if status in {"running", "idle", "active"}:
        return True
    if hc.startswith("healthy") or hc in {"idle", "ok", "up"}:
        return True
    if service.get("port_listening") is True:
        return True
    return False


def summarize_system_health_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Summarize system health snapshot. Direct summary from snapshot data.

    ISC-3 / G-CONV.3 single-source: daemon-only ratio; idle and healthy(probe) count
    online — must match bin/compass_radar.collect_runtime_health so scheduler writes
    do not overwrite compass with a 0.75 phantom (ollama idle ≠ offline).
    """
    # Direct summary from snapshot data — omo.omo_state_schema was removed in
    # refactor; P82-S4 死 import 清理 (try/except 死块移除, 直接 summary, 非补实现).
    services = snapshot.get("services", {}) or {}
    daemons = {
        k: v
        for k, v in services.items()
        if isinstance(v, dict) and v.get("type") == "daemon"
    }
    total = len(daemons)
    if total <= 0:
        return {
            "online_services": 0,
            "total_services": 0,
            "ratio": None,
            "health_score": 0,
            "last_scan": str(snapshot.get("last_scan", "")),
            "service_count": len(services),
            "degraded": [],
            "source": "runtime_daemon_de_false_positive",
        }
    online = sum(1 for v in daemons.values() if _daemon_is_online(v))
    ratio = online / total
    return {
        "online_services": online,
        "total_services": total,
        "ratio": round(ratio, 4),
        "health_score": max(0, int(round(ratio * 100))),
        "last_scan": str(snapshot.get("last_scan", "")),
        "service_count": len(services),
        "degraded": [
            k
            for k, v in daemons.items()
            if str((v.get("runtime") or {}).get("status") or "").lower() == "degraded"
            and not _daemon_is_online(v)
        ],
        "source": "runtime_daemon_de_false_positive",
    }


__all__ = [
    "archive_resolved_debt_items",
    "summarize_system_health_snapshot",
]
