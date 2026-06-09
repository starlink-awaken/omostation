"""KOS Health Monitor — detect index drift, no auto-reindex."""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

BASELINE = {
    "captured_at": "2026-05-30",
    "documents": 7327,
    "zones": {
        "workspace_root": 8,
        "omo": 179,
        "kairon": 1886,
        "agentmesh": 38,
        "gbrain": 506,
        "sharedbrain": 4710,
    },
    "known_doc_ids": [
        "kos/intro",
        "kos/setup",
        "kos/usage",
        "kos/api",
        "kos/deploy",
        "sharedbrain/intro",
        "sharedbrain/organs",
        "kairon/intro",
        "kairon/quickstart",
        "kairon/architecture",
    ],
}

THRESHOLDS = {
    "total_docs": {"warning": 5.0, "critical": 10.0},
    "per_zone": {"warning": 10.0, "critical": 20.0},
    "known_doc": {"warning": 8, "critical": 8},
}


def get_baseline():
    return dict(BASELINE)


def check_drift(current_count: int, current_zones: dict[str, int]) -> list[dict]:
    alerts = []
    if current_count is None:
        alerts.append(
            {"metric": "total_docs", "level": "critical", "message": "DB_UNAVAILABLE"}
        )
        return alerts
    drift_pct = (
        (current_count - BASELINE["documents"]) / max(BASELINE["documents"], 1) * 100
    )
    t = THRESHOLDS["total_docs"]
    if abs(drift_pct) >= t["critical"]:
        alerts.append(
            {
                "metric": "total_docs",
                "level": "critical",
                "drift_pct": round(drift_pct, 2),
                "action": "NO_AUTO_REINDEX",
            }
        )
    elif abs(drift_pct) >= t["warning"]:
        alerts.append(
            {
                "metric": "total_docs",
                "level": "warning",
                "drift_pct": round(drift_pct, 2),
                "action": "LOG_ONLY",
            }
        )
    if current_zones:
        for zone, baseline_count in BASELINE["zones"].items():
            curr = current_zones.get(zone, 0)
            if curr == 0:
                alerts.append(
                    {
                        "metric": f"zone_{zone}",
                        "level": "critical",
                        "message": "MISSING_ZONE",
                        "action": "HUMAN_INVESTIGATE",
                    }
                )
                continue
            z_drift = (curr - baseline_count) / max(baseline_count, 1) * 100
            zt = THRESHOLDS["per_zone"]
            if abs(z_drift) >= zt["critical"]:
                alerts.append(
                    {
                        "metric": f"zone_{zone}",
                        "level": "critical",
                        "drift_pct": round(z_drift, 2),
                        "action": "NO_AUTO_REINDEX",
                    }
                )
            elif abs(z_drift) >= zt["warning"]:
                alerts.append(
                    {
                        "metric": f"zone_{zone}",
                        "level": "warning",
                        "drift_pct": round(z_drift, 2),
                        "action": "LOG_ONLY",
                    }
                )
    return alerts


def check_known_docs(search_fn) -> dict:
    found = 0
    failed = []
    for doc_id in BASELINE["known_doc_ids"]:
        try:
            if search_fn(doc_id):
                found += 1
            else:
                failed.append(doc_id)
        except Exception:
            failed.append(doc_id)
    return {
        "found": found,
        "total": len(BASELINE["known_doc_ids"]),
        "failed_ids": failed,
        "level": "ok" if found >= 10 else "critical" if found < 8 else "warning",
    }


def generate_reindex_request(alerts: list, caller="kos-health-monitor") -> dict:
    return {
        "_confirmed": False,
        "type": "reindex_request",
        "caller": caller,
        "reason": f"{len([a for a in alerts if a['level'] == 'critical'])} critical alerts",
        "alerts": alerts,
        "baseline": BASELINE["documents"],
        "recommendation": "Manual investigation before any reindex",
        "requested_action": "kos run_indexer --zones all (L2 approval required)",
    }
