"""Mesh health monitor - active probing and alerting for Workflow Mesh connectivity.

Complements the passive mesh_gate (Phase 3) with active health checks:
- Event flow rate: events per hour from the Mesh store
- Last event age: how long since the most recent event
- Store accessibility: can we read/write to the store
- Bridge coverage: which of the 4 bridge channels are emitting

Usage:
    from ecos.workflow.mesh_health import mesh_health_snapshot
    health = mesh_health_snapshot()
    # health["status"] == "healthy" | "degraded" | "unavailable"
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger("ecos.workflow.mesh_health")


def _parse_timestamp(ts: str) -> datetime | None:
    """Parse ISO timestamp, return None on failure."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def mesh_health_snapshot() -> dict[str, Any]:
    """Take a snapshot of Mesh health.

    Returns dict with:
    - status: "healthy" | "degraded" | "unavailable"
    - connected: bool
    - event_count: int
    - last_event_age_seconds: float | None
    - events_last_hour: int
    - bridges_active: list[str]  (producers seen in events)
    - reason: str
    """
    from ecos.workflow.default_mesh_sink import _get_workflow_mesh_store

    store = _get_workflow_mesh_store()
    if store is None:
        return {
            "status": "unavailable",
            "connected": False,
            "event_count": 0,
            "last_event_age_seconds": None,
            "events_last_hour": 0,
            "bridges_active": [],
            "reason": "Mesh store not found",
        }

    try:
        events = store.events()
    except Exception as exc:
        return {
            "status": "unavailable",
            "connected": False,
            "event_count": 0,
            "last_event_age_seconds": None,
            "events_last_hour": 0,
            "bridges_active": [],
            "reason": f"Store read error: {exc}",
        }

    if not events:
        return {
            "status": "degraded",
            "connected": True,
            "event_count": 0,
            "last_event_age_seconds": None,
            "events_last_hour": 0,
            "bridges_active": [],
            "reason": "Store connected but no events recorded",
        }

    now = datetime.now(UTC)
    one_hour_ago = now - timedelta(hours=1)

    last_event = events[-1]
    last_ts = _parse_timestamp(last_event.get("occurred_at", ""))
    last_age = (now - last_ts).total_seconds() if last_ts else None

    events_last_hour = 0
    producers: set[str] = set()
    for event in events:
        ts = _parse_timestamp(event.get("occurred_at", ""))
        if ts and ts > one_hour_ago:
            events_last_hour += 1
        producer = event.get("producer", "")
        if producer:
            producers.add(producer)

    known_bridges = {
        "agent-workflow",
        "omo.omo_worker_dispatch",
        "omo.workflow_dispatch",
        "ecos.workflow.executor",
    }
    bridges_active = sorted(known_bridges & producers)

    if last_age is not None and last_age > 3600:
        status = "degraded"
        reason = f"No events in {int(last_age / 3600)}h"
    elif events_last_hour == 0:
        status = "degraded"
        reason = "No events in the last hour"
    else:
        status = "healthy"
        reason = f"{events_last_hour} events in last hour, {len(bridges_active)} bridges active"

    return {
        "status": status,
        "connected": True,
        "event_count": len(events),
        "last_event_age_seconds": last_age,
        "events_last_hour": events_last_hour,
        "bridges_active": bridges_active,
        "reason": reason,
    }


def mesh_health_check() -> list[dict[str, Any]]:
    """Return violations list for governance gate integration.

    Empty list = healthy, non-empty = warnings/errors.
    """
    health = mesh_health_snapshot()

    if health["status"] == "unavailable":
        return [{
            "id": "MESH-HEALTH-01",
            "severity": "warning",
            "message": f"Mesh health: {health['reason']}",
        }]

    if health["status"] == "degraded":
        return [{
            "id": "MESH-HEALTH-02",
            "severity": "warning",
            "message": f"Mesh health degraded: {health['reason']}",
        }]

    return []
