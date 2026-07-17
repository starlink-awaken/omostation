"""G-CONV.3: summarize_system_health_snapshot de-false-positive + single-source."""
from __future__ import annotations

from runtime.adapters.omo import _daemon_is_online, summarize_system_health_snapshot


def test_idle_daemon_counts_online():
    snap = {
        "last_scan": "t1",
        "services": {
            "agora-gateway": {
                "type": "daemon",
                "health_check": "healthy (probe)",
                "runtime": {"status": "running"},
            },
            "agora-sse": {
                "type": "daemon",
                "health_check": "healthy",
                "runtime": {"status": "running"},
            },
            "cron-service": {
                "type": "daemon",
                "health_check": "healthy",
                "runtime": {"status": "running"},
            },
            "ollama": {
                "type": "daemon",
                "health_check": "healthy",
                "runtime": {"status": "idle"},
            },
            "gbrain": {"type": "cli", "runtime": {"status": "unmanaged"}},
        },
    }
    summary = summarize_system_health_snapshot(snap)
    assert summary["total_services"] == 4
    assert summary["online_services"] == 4
    assert summary["ratio"] == 1.0
    assert summary["source"] == "runtime_daemon_de_false_positive"


def test_only_running_would_have_been_075():
    """Regression: old code used status=='running' only → idle ollama made 0.75."""
    assert _daemon_is_online({"runtime": {"status": "idle"}, "health_check": "healthy"})
    assert _daemon_is_online(
        {"runtime": {"status": "running"}, "health_check": "unhealthy (probe)"}
    )
    assert _daemon_is_online(
        {"runtime": {"status": "degraded"}, "health_check": "healthy (probe)"}
    )
    assert not _daemon_is_online(
        {"runtime": {"status": "dead"}, "health_check": "unhealthy"}
    )


def test_zero_daemons_ratio_none():
    summary = summarize_system_health_snapshot(
        {"services": {"x": {"type": "cli", "runtime": {"status": "running"}}}}
    )
    assert summary["total_services"] == 0
    assert summary["ratio"] is None
